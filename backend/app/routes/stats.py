"""
统计相关API路由
包括：团队工时、月度工时统计、项目维度工时、工时趋势等
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Optional
from datetime import datetime, timedelta
import io

# 使用相对导入
from ..database import get_connection, text
from ..auth import get_current_user
from ..logger import get_logger
from ..holidays import calculate_working_days  # 导入节假日计算

logger = get_logger(__name__)

router = APIRouter(prefix="/api/agent/stats", tags=["统计"])


def classify_other_work(work_content: str, project_name: str) -> str:
    """
    分类基础工作：项目类、行政类、会议类、日常类
    """
    content = (work_content or '') + ' ' + (project_name or '')
    
    # 项目类关键词（优先判断）
    project_keywords = ['项目', '方案编制', '方案设计', '技术方案', '可行性分析', 
                        '立项', '研发', '调研', '前期', '现场调研', '协调', 
                        '跟进', '推进', '落实', '编写', '编制', '修改', '完善',
                        '技术交流', '供应商交流', '设备选型']
    for kw in project_keywords:
        if kw in content:
            if '汇报' in content and '会' in content:
                continue
            return '项目类'
    
    # 行政类关键词
    admin_keywords = ['审批', '签字', '盖章', '报销', '发票', '合同', 
                      '采购', '财务', '付款', '资金计划', '招标', '订价',
                      '流程', '申请', '审核', '质保金', '开票']
    for kw in admin_keywords:
        if kw in content:
            return '行政类'
    
    # 会议类关键词
    meeting_keywords = ['会议', '早会', '晚会', '评审会', '分析会', '讨论会', 
                        '培训', '参加', '交流会', '立项评审']
    for kw in meeting_keywords:
        if kw in content:
            if '汇报' in content and '会' not in content:
                return '项目类'
            return '会议类'
    
    # 日常类关键词
    daily_keywords = ['检查', '整理', '任务清单', 'KPI', 
                      '绩效', '督办', '填写', '填报', '台账', '报表',
                      '录入', '数据', '资料', '电脑', '设备维护',
                      '安全检查', '隐患', '梳理', '汇总', '统计']
    for kw in daily_keywords:
        if kw in content:
            return '日常类'
    
    return '项目类'


@router.get("/team-work-hours")
async def get_team_work_hours(current_user: Dict = Depends(get_current_user)):
    """获取团队工时统计（项目负责人视角）"""
    username = current_user.get("username") or current_user.get("sub")
    employee_id = current_user.get("employee_id") or username

    if not employee_id:
        return []

    today = datetime.now().date()
    month_start = today.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    with get_connection() as conn:
        emp_result = conn.execute(text("""
            SELECT name FROM personnel 
            WHERE employee_id = :emp_id AND is_deleted = false
            LIMIT 1
        """), {"emp_id": employee_id})
        emp_row = emp_result.fetchone()
        employee_name = emp_row[0] if emp_row else None

        projects_result = conn.execute(text("""
            SELECT id, name FROM projects
            WHERE is_deleted = false AND leader = :emp_name
        """), {"emp_name": employee_name or ""})

        project_ids = [row[0] for row in projects_result]
        if not project_ids:
            return []

        result = conn.execute(text("""
            SELECT
                p.name as project_name,
                per.name as member_name,
                SUM(dwi.hours_spent) as total_hours
            FROM daily_work_items dwi
            JOIN daily_reports dr ON dr.id = dwi.report_id
            JOIN personnel per ON per.employee_id = dr.employee_id
            JOIN projects p ON dwi.project_name LIKE '%' || p.name || '%'
            WHERE p.id = ANY(:project_ids)
              AND dr.report_date >= :month_start
              AND dr.report_date <= :month_end
              AND dr.is_deleted = false
            GROUP BY p.name, per.name
            ORDER BY p.name, total_hours DESC
        """), {
            "project_ids": project_ids,
            "month_start": month_start,
            "month_end": month_end
        })

        project_hours = {}
        for row in result:
            project_name = row[0]
            member_name = row[1]
            hours = float(row[2] or 0)

            if project_name not in project_hours:
                project_hours[project_name] = {
                    "project_name": project_name,
                    "members": [],
                    "total_hours": 0
                }

            project_hours[project_name]["members"].append({
                "name": member_name,
                "hours": round(hours, 1),
                "percent": 0
            })
            project_hours[project_name]["total_hours"] += hours

        result_list = []
        for project_data in project_hours.values():
            total = project_data["total_hours"]
            for member in project_data["members"]:
                member["percent"] = round(100 * member["hours"] / total, 1) if total > 0 else 0
            project_data["total_hours"] = round(total, 1)
            result_list.append(project_data)

        return result_list


@router.get("/monthly-employee-hours")
async def get_monthly_employee_hours(
    year: int = None,
    month: int = None,
    current_user: Dict = Depends(get_current_user)
):
    """获取月度工时统计（人员维度）"""
    # 如果没有指定年月，使用当前月份
    if not year or not month:
        today = datetime.now()
        year = year or today.year
        month = month or today.month
    
    month_start = datetime(year, month, 1).date()
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # 动态计算工作日数（考虑节假日）
    working_days = calculate_working_days(year, month)
    
    with get_connection() as conn:
        # 查询所有员工的工时数据
        result = conn.execute(text("""
            SELECT 
                dr.employee_name,
                dwi.project_name,
                SUM(dwi.hours_spent) as total_hours,
                COUNT(DISTINCT dr.id) as report_count
            FROM daily_work_items dwi
            JOIN daily_reports dr ON dr.id = dwi.report_id
            WHERE dr.report_date >= :month_start
              AND dr.report_date <= :month_end
              AND dr.is_deleted = false
              AND LOWER(dr.employee_name) != 'admin'
            GROUP BY dr.employee_name, dwi.project_name
            ORDER BY dr.employee_name, total_hours DESC
        """), {"month_start": month_start, "month_end": month_end})
        
        # 按员工分组
        employees_data = {}
        total_hours_all = 0
        total_reports = 0
        
        for row in result:
            emp_name = row[0]
            project_name = row[1] or "其他工作"
            hours = float(row[2] or 0)
            count = int(row[3] or 0)
            
            if emp_name not in employees_data:
                employees_data[emp_name] = {
                    "employee_name": emp_name,
                    "projects": [],
                    "total_hours": 0,
                    "report_count": 0,
                    "required_days": working_days,
                    "filled_days": 0,
                    "missing_days": working_days
                }
            
            employees_data[emp_name]["projects"].append({
                "project_name": project_name,
                "hours": round(hours, 1),
                "percent": 0
            })
            employees_data[emp_name]["total_hours"] += hours
            employees_data[emp_name]["report_count"] += count
            total_hours_all += hours
            total_reports += count
        
        # 计算百分比和缺失天数
        employees_list = []
        for emp_data in employees_data.values():
            total = emp_data["total_hours"]
            for project in emp_data["projects"]:
                project["percent"] = round(100 * project["hours"] / total, 1) if total > 0 else 0
            
            emp_data["total_hours"] = round(total, 1)
            emp_data["filled_days"] = min(emp_data["report_count"], working_days)
            emp_data["missing_days"] = max(0, working_days - emp_data["filled_days"])
            employees_list.append(emp_data)
        
        return {
            "year": year,
            "month": month,
            "working_days": working_days,  # 月份总工作日
            "employee_count": len(employees_list),  # 参与人数
            "employees": employees_list,
            "total_hours": round(total_hours_all, 1),
            "total_reports": total_reports
        }


@router.get("/monthly-project-hours")
async def get_monthly_project_hours(
    year: int = None,
    month: int = None,
    current_user: Dict = Depends(get_current_user)
):
    """获取月度工时统计（项目维度）"""
    if not year or not month:
        today = datetime.now()
        year = year or today.year
        month = month or today.month
    
    month_start = datetime(year, month, 1).date()
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # 动态计算工作日数（考虑节假日）
    working_days = calculate_working_days(year, month)
    
    with get_connection() as conn:
        # 查询正式项目的工时数据
        official_result = conn.execute(text("""
            SELECT 
                p.id,
                p.name,
                dr.employee_name,
                SUM(dwi.hours_spent) as total_hours
            FROM daily_work_items dwi
            JOIN daily_reports dr ON dr.id = dwi.report_id
            JOIN projects p ON CAST(p.id AS VARCHAR) = dwi.project_id
            WHERE dr.report_date >= :month_start
              AND dr.report_date <= :month_end
              AND dr.is_deleted = false
              AND LOWER(dr.employee_name) != 'admin'
              AND dwi.project_id IS NOT NULL
              AND dwi.project_id != ''
            GROUP BY p.id, p.name, dr.employee_name
            ORDER BY p.name, total_hours DESC
        """), {"month_start": month_start, "month_end": month_end})
        
        # 按项目分组
        official_hours = {}
        all_employees = set()
        
        for row in official_result:
            project_id = row[0]
            project_name = row[1]
            emp_name = row[2]
            hours = float(row[3] or 0)
            
            all_employees.add(emp_name)
            
            if project_name not in official_hours:
                official_hours[project_name] = {
                    "project_name": project_name,
                    "members": {},
                    "total_hours": 0.0
                }
            
            # 统一精度：保留1位小数
            hours_rounded = round(hours, 1)
            official_hours[project_name]["members"][emp_name] = round(
                official_hours[project_name]["members"].get(emp_name, 0.0) + hours_rounded, 1
            )
            official_hours[project_name]["total_hours"] = round(official_hours[project_name]["total_hours"] + hours_rounded, 1)
        
        # 查询未匹配项目的工时数据
        other_result = conn.execute(text("""
            SELECT 
                dwi.project_name,
                dwi.work_content,
                dr.employee_name,
                SUM(dwi.hours_spent) as total_hours
            FROM daily_work_items dwi
            JOIN daily_reports dr ON dr.id = dwi.report_id
            WHERE dr.report_date >= :month_start
              AND dr.report_date <= :month_end
              AND dr.is_deleted = false
              AND LOWER(dr.employee_name) != 'admin'
              AND (dwi.project_id IS NULL OR dwi.project_id = '')
            GROUP BY dwi.project_name, dwi.work_content, dr.employee_name
            ORDER BY total_hours DESC
        """), {"month_start": month_start, "month_end": month_end})
        
        # 处理未匹配项目数据 - 按四类分类
        other_work_hours = {}
        for row in other_result:
            project_name_from_db = row[0] or ""
            work_content_from_db = row[1] or ""
            emp_name = row[2]
            hours = float(row[3] or 0)
            
            all_employees.add(emp_name)
            
            # 使用分类函数
            category_name = classify_other_work(work_content_from_db, project_name_from_db)
            
            if category_name not in other_work_hours:
                other_work_hours[category_name] = {
                    "project_name": category_name,
                    "members": {},
                    "total_hours": 0.0
                }
            
            # 统一精度：保留1位小数
            hours_rounded = round(hours, 1)
            other_work_hours[category_name]["members"][emp_name] = round(
                other_work_hours[category_name]["members"].get(emp_name, 0.0) + hours_rounded, 1
            )
            other_work_hours[category_name]["total_hours"] = round(other_work_hours[category_name]["total_hours"] + hours_rounded, 1)
        
        # 计算员工小计（统一精度）
        official_employee_totals_raw = {}
        for proj in official_hours.values():
            for emp, hours in proj["members"].items():
                official_employee_totals_raw[emp] = official_employee_totals_raw.get(emp, 0.0) + hours
        official_employee_totals = {k: round(v, 1) for k, v in official_employee_totals_raw.items()}
        official_grand_total = round(sum(official_employee_totals.values()), 1)
        
        other_employee_totals_raw = {}
        for proj in other_work_hours.values():
            for emp, hours in proj["members"].items():
                other_employee_totals_raw[emp] = other_employee_totals_raw.get(emp, 0.0) + hours
        other_employee_totals = {k: round(v, 1) for k, v in other_employee_totals_raw.items()}
        other_grand_total = round(sum(other_employee_totals.values()), 1)
        
        all_employee_totals_raw = {}
        for emp in all_employees:
            all_employee_totals_raw[emp] = official_employee_totals.get(emp, 0.0) + other_employee_totals.get(emp, 0.0)
        all_employee_totals = {k: round(v, 1) for k, v in all_employee_totals_raw.items()}
        
        grand_total = round(official_grand_total + other_grand_total, 1)
        
        # 转换为列表并排序
        official_list = list(official_hours.values())
        official_list.sort(key=lambda x: x["total_hours"], reverse=True)
        
        other_list = list(other_work_hours.values())
        other_list.sort(key=lambda x: {
            "项目类": 0,
            "行政类": 1,
            "会议类": 2,
            "日常类": 3
        }.get(x["project_name"], 4))
        
        return {
            "year": year,
            "month": month,
            "working_days": working_days,  # 月份总工作日
            "employee_count": len(all_employees),  # 参与人数
            "official_projects": official_list,
            "official_employee_totals": official_employee_totals,
            "official_grand_total": official_grand_total,
            "other_works": other_list,
            "other_employee_totals": other_employee_totals,
            "other_grand_total": other_grand_total,
            "all_employees": sorted(list(all_employees)),
            "all_employee_totals": all_employee_totals,
            "grand_total": grand_total,
            "official_project_count": len(official_list),
            "other_work_count": len(other_list)
        }


@router.get("/project-employee-details")
async def get_project_employee_details(
    project_name: str,
    employee_name: str,
    year: int,
    month: int,
    current_user: Dict = Depends(get_current_user)
):
    """获取指定项目、人员、月份的日报详情列表"""
    from urllib.parse import unquote
    
    project_name = unquote(project_name)
    employee_name = unquote(employee_name)
    
    month_start = datetime(year, month, 1).date()
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    with get_connection() as conn:
        basic_categories = ['会议类', '行政类', '日常类', '项目类']
        
        if project_name in basic_categories:
            result = conn.execute(text("""
                SELECT 
                    dr.report_date,
                    dwi.project_name,
                    dwi.work_content,
                    dwi.hours_spent,
                    dwi.start_time,
                    dwi.end_time
                FROM daily_work_items dwi
                JOIN daily_reports dr ON dr.id = dwi.report_id
                JOIN personnel p ON dr.employee_id = p.employee_id
                WHERE p.name = :emp_name
                  AND dr.report_date >= :month_start
                  AND dr.report_date <= :month_end
                  AND dr.is_deleted = false
                  AND dwi.is_deleted = false
                  AND (dwi.project_id IS NULL OR dwi.project_id = '')
                ORDER BY dr.report_date DESC
            """), {
                "emp_name": employee_name,
                "month_start": month_start,
                "month_end": month_end
            })
            
            details = []
            total_hours = 0
            for row in result:
                work_content = row[2] or ""
                proj_name = row[1] or ""
                if classify_other_work(work_content, proj_name) == project_name:
                    details.append({
                        "date": str(row[0]),
                        "project": row[1] or "基础工作",
                        "content": row[2],
                        "hours": float(row[3] or 0),
                        "time_range": f"{row[4] or ''}-{row[5] or ''}" if row[4] and row[5] else ""
                    })
                    total_hours += float(row[3] or 0)
        else:
            result = conn.execute(text("""
                SELECT 
                    dr.report_date,
                    dwi.project_name,
                    dwi.work_content,
                    dwi.hours_spent,
                    dwi.start_time,
                    dwi.end_time
                FROM daily_work_items dwi
                JOIN daily_reports dr ON dr.id = dwi.report_id
                JOIN personnel p ON dr.employee_id = p.employee_id
                WHERE p.name = :emp_name
                  AND dr.report_date >= :month_start
                  AND dr.report_date <= :month_end
                  AND dr.is_deleted = false
                  AND dwi.is_deleted = false
                  AND dwi.project_name = :project_name
                ORDER BY dr.report_date DESC
            """), {
                "emp_name": employee_name,
                "project_name": project_name,
                "month_start": month_start,
                "month_end": month_end
            })
            
            details = []
            total_hours = 0
            for row in result:
                details.append({
                    "date": str(row[0]),
                    "project": row[1],
                    "content": row[2],
                    "hours": float(row[3] or 0),
                    "time_range": f"{row[4] or ''}-{row[5] or ''}" if row[4] and row[5] else ""
                })
                total_hours += float(row[3] or 0)
        
        return {
            "project_name": project_name,
            "employee_name": employee_name,
            "year": year,
            "month": month,
            "details": details,
            "total_hours": round(total_hours, 2),
            "count": len(details)
        }


@router.get("/hours-trend")
async def get_hours_trend(
    months: int = 6,
    current_user: Dict = Depends(get_current_user)
):
    """获取工时趋势（最近N个月）"""
    today = datetime.now()
    
    with get_connection() as conn:
        result = conn.execute(text("""
            SELECT 
                TO_CHAR(dr.report_date, 'YYYY-MM') as month,
                SUM(dwi.hours_spent) as total_hours,
                COUNT(DISTINCT dr.employee_id) as employee_count
            FROM daily_work_items dwi
            JOIN daily_reports dr ON dr.id = dwi.report_id
            WHERE dr.report_date >= :start_date
              AND dr.is_deleted = false
            GROUP BY TO_CHAR(dr.report_date, 'YYYY-MM')
            ORDER BY month DESC
            LIMIT :months
        """), {
            "start_date": today - timedelta(days=months * 31),
            "months": months
        })
        
        trends = []
        for row in result:
            trends.append({
                "month": row[0],
                "hours": round(float(row[1] or 0), 1),
                "employees": int(row[2] or 0)
            })
        
        return {"trends": list(reversed(trends))}


@router.get("/project-distribution")
async def get_project_distribution(
    year: int = None,
    month: int = None,
    current_user: Dict = Depends(get_current_user)
):
    """获取项目工时分布"""
    if not year or not month:
        today = datetime.now()
        year = year or today.year
        month = month or today.month
    
    month_start = datetime(year, month, 1).date()
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    with get_connection() as conn:
        result = conn.execute(text("""
            SELECT 
                COALESCE(dwi.project_name, '其他工作') as project_name,
                SUM(dwi.hours_spent) as total_hours
            FROM daily_work_items dwi
            JOIN daily_reports dr ON dr.id = dwi.report_id
            WHERE dr.report_date >= :month_start
              AND dr.report_date <= :month_end
              AND dr.is_deleted = false
            GROUP BY COALESCE(dwi.project_name, '其他工作')
            ORDER BY total_hours DESC
            LIMIT 10
        """), {"month_start": month_start, "month_end": month_end})
        
        distribution = []
        total = 0
        for row in result:
            hours = float(row[1] or 0)
            total += hours
            distribution.append({
                "name": row[0],
                "hours": round(hours, 1)
            })
        
        for item in distribution:
            item["percent"] = round(100 * item["hours"] / total, 1) if total > 0 else 0
        
        return {
            "year": year,
            "month": month,
            "distribution": distribution,
            "total_hours": round(total, 1)
        }
