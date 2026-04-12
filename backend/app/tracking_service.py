"""
项目追踪服务模块

三个视图：
1. 执行视图 - 任务驱动
2. 健康视图 - 风险雷达
3. 溯源视图 - 数据血缘

计算公式说明：
- 进度风险 = 过期任务数 / 总任务数 × 100
- 成本风险 = max(0, 超支率) 的加权平均
- 综合风险 = 进度风险 × 0.5 + 成本风险 × 0.5
- 项目风险分 = 延期天数×2 + 过期任务数×15 + 延期任务数×10
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
try:
    from .database import get_engine, text
    from .logger import get_logger
except ImportError:
    from database import get_engine, text
    from logger import get_logger

logger = get_logger(__name__)


def get_execution_view(user_id: str, user_name: str, role_id: int) -> Dict[str, Any]:
    """
    执行视图：任务驱动
    
    计算规则：
    - 今日截止：end_date == 今天
    - 本周截止：今天 < end_date <= 本周日
    - 本月截止：本周日 < end_date <= 本月末
    - 已过期：end_date < 今天（单独展示）
    
    返回：
    - 我的任务（今日/本周/本月/已过期）
    - 近期完成（最近7天）
    - 统计数据
    """
    engine = get_engine()
    today = date.today()
    week_end = today + timedelta(days=(6 - today.weekday()))  # 本周日
    month_end = date(today.year, today.month + 1, 1) - timedelta(days=1) if today.month < 12 else date(today.year + 1, 1, 1) - timedelta(days=1)
    
    with engine.connect() as conn:
        # 1. 查询任务（统一逻辑：进行中 + 延期）
        if role_id == 11:  # 管理员看所有
            my_tasks_query = """
                SELECT 
                    pt.task_id, pt.task_name, pt.progress, pt.status,
                    pt.start_date, pt.end_date, pt.assignee,
                    p.name as project_name, p.id as project_id
                FROM project_tasks pt
                JOIN projects p ON CAST(p.id AS VARCHAR) = pt.project_id
                WHERE pt.is_deleted = false 
                  AND pt.is_latest = true
                  AND pt.status IN ('进行中', '延期')
                  AND p.is_deleted = false
                ORDER BY pt.end_date NULLS LAST, pt.progress ASC
                LIMIT 50
            """
            my_tasks = conn.execute(text(my_tasks_query)).fetchall()
        else:
            my_tasks_query = """
                SELECT 
                    pt.task_id, pt.task_name, pt.progress, pt.status,
                    pt.start_date, pt.end_date, pt.assignee,
                    p.name as project_name, p.id as project_id
                FROM project_tasks pt
                JOIN projects p ON CAST(p.id AS VARCHAR) = pt.project_id
                WHERE pt.is_deleted = false 
                  AND pt.is_latest = true
                  AND pt.status IN ('进行中', '延期')
                  AND pt.assignee = :user_name
                  AND p.is_deleted = false
                ORDER BY pt.end_date NULLS LAST, pt.progress ASC
                LIMIT 50
            """
            my_tasks = conn.execute(text(my_tasks_query), {"user_name": user_name}).fetchall()
        
        # 分类任务
        today_tasks = []
        week_tasks = []
        month_tasks = []
        overdue_tasks = []
        
        for task in my_tasks:
            task_data = {
                "task_id": task[0],
                "task_name": task[1],
                "progress": float(task[2] or 0),
                "status": task[3],
                "start_date": str(task[4]) if task[4] else None,
                "end_date": str(task[5]) if task[5] else None,
                "assignee": task[6],
                "project_name": task[7],
                "project_id": task[8]
            }
            
            end_date = task[5]
            if end_date:
                if end_date < today:
                    # 已过期
                    task_data["delay_days"] = (today - end_date).days
                    overdue_tasks.append(task_data)
                elif end_date == today:
                    today_tasks.append(task_data)
                elif end_date <= week_end:
                    week_tasks.append(task_data)
                elif end_date <= month_end:
                    month_tasks.append(task_data)
        
        # 2. 近期完成（最近7天）
        completed_query = """
            SELECT 
                pt.task_id, pt.task_name, pt.actual_end_date,
                p.name as project_name
            FROM project_tasks pt
            JOIN projects p ON CAST(p.id AS VARCHAR) = pt.project_id
            WHERE pt.is_deleted = false
              AND pt.status = '已完成'
              AND pt.actual_end_date >= :week_ago
              AND p.is_deleted = false
            ORDER BY pt.actual_end_date DESC
            LIMIT 10
        """
        completed_tasks = conn.execute(text(completed_query), {
            "week_ago": today - timedelta(days=7)
        }).fetchall()
        
        completed = [{
            "task_id": t[0],
            "task_name": t[1],
            "completed_date": str(t[2]) if t[2] else None,
            "project_name": t[3]
        } for t in completed_tasks]
        
        # 3. 统计数据
        stats = {
            "today_count": len(today_tasks),
            "week_count": len(week_tasks),
            "month_count": len(month_tasks),
            "overdue_count": len(overdue_tasks),
            "completed_week": len(completed),
            "total_pending": len(today_tasks) + len(week_tasks) + len(month_tasks)
        }
        
        return {
            "today_tasks": today_tasks,
            "week_tasks": week_tasks,
            "month_tasks": month_tasks,
            "overdue_tasks": overdue_tasks,
            "completed": completed,
            "stats": stats,
            "formulas": {
                "today": "截止日期 = 今天",
                "week": "今天 < 截止日期 ≤ 本周日",
                "month": "本周日 < 截止日期 ≤ 本月末",
                "overdue": "截止日期 < 今天（已过期）"
            }
        }


def get_health_view(user_id: str, role_id: int) -> Dict[str, Any]:
    """
    健康视图：风险雷达
    
    计算公式：
    1. 进度风险 = 过期任务数 / 总任务数 × 100
       - 过期定义：end_date < 今天 且 progress < 100
       
    2. 成本风险 = max(0, 超支率)
       - 材料风险 = max(0, (材料实际 - 材料预算) / 材料预算 × 100)
       - 人工风险、外包风险、间接风险 同理
       - 只统计有实际成本的科目
       
    3. 综合风险 = 进度风险 × 0.5 + 成本风险 × 0.5
       - 成本风险 = 四项成本风险的加权平均（只算有数据的）
       
    4. 项目风险分 = 延期天数×2 + 过期任务数×15 + 延期任务数×10
       - 最高100分
    """
    engine = get_engine()
    today = date.today()
    
    with engine.connect() as conn:
        # ===== 1. 进度风险计算 =====
        # 过期任务 = end_date < 今天 且 progress < 100
        progress_result = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN end_date < :today AND progress < 100 THEN 1 END) as overdue,
                COUNT(CASE WHEN status = '延期' THEN 1 END) as delayed
            FROM project_tasks
            WHERE is_deleted = false AND is_latest = true
        """), {"today": today}).fetchone()
        
        total_tasks = progress_result[0] or 1
        overdue_tasks = progress_result[1] or 0
        delayed_tasks = progress_result[2] or 0
        
        # 进度风险 = 过期任务占比
        progress_risk = round(overdue_tasks * 100.0 / total_tasks, 1)
        
        # ===== 2. 成本风险计算 =====
        # 获取各科目超支情况
        cost_result = conn.execute(text("""
            SELECT 
                COUNT(CASE WHEN material_cost > 0 AND material_budget > 0 THEN 1 END) as material_count,
                AVG(CASE WHEN material_cost > 0 AND material_budget > 0 
                    THEN GREATEST(0, (material_cost - material_budget) * 100.0 / material_budget)
                    ELSE NULL END) as material_risk,
                COUNT(CASE WHEN labor_cost > 0 AND labor_budget > 0 THEN 1 END) as labor_count,
                AVG(CASE WHEN labor_cost > 0 AND labor_budget > 0 
                    THEN GREATEST(0, (labor_cost - labor_budget) * 100.0 / labor_budget)
                    ELSE NULL END) as labor_risk,
                COUNT(CASE WHEN outsourcing_cost > 0 AND outsourcing_budget > 0 THEN 1 END) as outsource_count,
                AVG(CASE WHEN outsourcing_cost > 0 AND outsourcing_budget > 0 
                    THEN GREATEST(0, (outsourcing_cost - outsourcing_budget) * 100.0 / outsourcing_budget)
                    ELSE NULL END) as outsource_risk,
                COUNT(CASE WHEN indirect_cost > 0 AND indirect_budget > 0 THEN 1 END) as indirect_count,
                AVG(CASE WHEN indirect_cost > 0 AND indirect_budget > 0 
                    THEN GREATEST(0, (indirect_cost - indirect_budget) * 100.0 / indirect_budget)
                    ELSE NULL END) as indirect_risk
            FROM projects
            WHERE is_deleted = false AND status = '进行中'
        """)).fetchone()
        
        # 计算各项成本风险（只算有数据的）
        material_risk = float(cost_result[1] or 0) if cost_result[0] else 0
        labor_risk = float(cost_result[3] or 0) if cost_result[2] else 0
        outsource_risk = float(cost_result[5] or 0) if cost_result[4] else 0
        indirect_risk = float(cost_result[7] or 0) if cost_result[6] else 0
        
        # 成本风险平均（只算有数据的项）
        cost_risks = [r for r in [material_risk, labor_risk, outsource_risk, indirect_risk] if r > 0]
        cost_risk_avg = round(sum(cost_risks) / len(cost_risks), 1) if cost_risks else 0
        
        # ===== 3. 综合风险 =====
        # 综合风险 = 进度风险 × 0.5 + 成本风险 × 0.5
        overall_risk = round(progress_risk * 0.5 + cost_risk_avg * 0.5, 1)
        
        radar_data = {
            "progress": progress_risk,
            "material": round(material_risk, 1),
            "labor": round(labor_risk, 1),
            "outsource": round(outsource_risk, 1),
            "indirect": round(indirect_risk, 1),
            "overall": min(100, overall_risk)
        }
        
        # ===== 4. 高风险项目 TOP5 =====
        # 项目风险分 = 延期天数×2 + 过期任务数×15 + 延期任务数×10
        risk_projects_query = """
            SELECT 
                p.id, p.name, p.leader, p.progress,
                COUNT(CASE WHEN pt.status = '延期' THEN 1 END) as delayed_tasks,
                COUNT(CASE WHEN pt.end_date < :today AND pt.progress < 100 THEN 1 END) as overdue_tasks,
                COALESCE(SUM(CASE 
                    WHEN pt.end_date < :today AND pt.progress < 100 
                    THEN :today - pt.end_date 
                    ELSE 0 
                END), 0) as total_delay_days
            FROM projects p
            LEFT JOIN project_tasks pt ON CAST(p.id AS VARCHAR) = pt.project_id 
                AND pt.is_deleted = false AND pt.is_latest = true
            WHERE p.is_deleted = false AND p.status = '进行中'
            GROUP BY p.id, p.name, p.leader, p.progress
            HAVING COUNT(CASE WHEN pt.status = '延期' THEN 1 END) > 0
               OR COUNT(CASE WHEN pt.end_date < :today AND pt.progress < 100 THEN 1 END) > 0
            ORDER BY 
                (COALESCE(SUM(CASE WHEN pt.end_date < :today AND pt.progress < 100 THEN :today - pt.end_date ELSE 0 END), 0) * 2 +
                 COUNT(CASE WHEN pt.end_date < :today AND pt.progress < 100 THEN 1 END) * 15 +
                 COUNT(CASE WHEN pt.status = '延期' THEN 1 END) * 10) DESC
            LIMIT 5
        """
        risk_projects = conn.execute(text(risk_projects_query), {"today": today}).fetchall()
        
        top_risks = []
        for p in risk_projects:
            delay_days = int(p[6] or 0)
            overdue = p[5] or 0
            delayed = p[4] or 0
            risk_score = min(100, delay_days * 2 + overdue * 15 + delayed * 10)
            
            top_risks.append({
                "project_id": p[0],
                "project_name": p[1],
                "leader": p[2],
                "progress": float(p[3] or 0),
                "delayed_tasks": delayed,
                "overdue_tasks": overdue,
                "total_delay_days": delay_days,
                "risk_score": risk_score
            })
        
        # ===== 5. 趋势预警 =====
        # 本周新增过期任务
        new_overdue = conn.execute(text("""
            SELECT COUNT(*) FROM project_tasks
            WHERE is_deleted = false 
              AND is_latest = true
              AND end_date < :today
              AND progress < 100
              AND end_date >= :week_ago
        """), {"today": today, "week_ago": today - timedelta(days=7)}).fetchone()[0]
        
        # 连续沉默项目（7天无日报）
        silent_projects = conn.execute(text("""
            SELECT COUNT(DISTINCT p.id)
            FROM projects p
            WHERE p.is_deleted = false
              AND p.status = '进行中'
              AND NOT EXISTS (
                  SELECT 1 FROM daily_work_items dwi
                  JOIN daily_reports dr ON dwi.report_id = dr.id
                  WHERE dwi.project_name = p.name
                    AND dr.report_date >= :week_ago
              )
        """), {"week_ago": today - timedelta(days=7)}).fetchone()[0]
        
        trends = {
            "new_overdue_week": new_overdue,
            "silent_projects": silent_projects,
            "total_overdue": overdue_tasks,
            "total_delayed": delayed_tasks
        }
        
        return {
            "radar": radar_data,
            "top_risks": top_risks,
            "trends": trends,
            "formulas": {
                "progress_risk": "过期任务数 ÷ 总任务数 × 100\n过期：截止日期<今天 且 进度<100%",
                "cost_risk": "max(0, (实际-预算)÷预算×100)\n只统计有实际成本的科目",
                "overall_risk": "进度风险 × 0.5 + 成本风险 × 0.5",
                "project_score": "延期天数×2 + 过期任务数×15 + 延期任务数×10\n最高100分"
            }
        }


def get_trace_view(user_id: str, role_id: int) -> Dict[str, Any]:
    """
    溯源视图：数据血缘
    
    计算公式：
    1. 关联率 = 已关联工作项数 / 总工作项数 × 100
       - 已关联：task_id 不为空且不为空字符串
       - 统计范围：近30天的日报
    
    2. 项目关联率 = 该项目已关联工作项 / 该项目总工作项 × 100
    
    3. 不可追溯项目：关联率 < 50% 且 有日报记录
    
    4. 进度无支撑：项目进度 > 0 但近30天无日报
    
    目标关联率分阶段：
    - 初级：50%
    - 中级：70%
    - 高级：80%
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        # ===== 1. 关联率统计 =====
        link_stats = conn.execute(text("""
            SELECT 
                COUNT(*) as total_items,
                COUNT(CASE WHEN task_id IS NOT NULL AND task_id != '' THEN 1 END) as linked_items
            FROM daily_work_items dwi
            JOIN daily_reports dr ON dwi.report_id = dr.id
            WHERE dr.report_date >= CURRENT_DATE - INTERVAL '30 days'
        """)).fetchone()
        
        total = link_stats[0] or 1
        linked = link_stats[1] or 0
        link_rate = round(linked * 100.0 / total, 1)
        
        # 目标分阶段
        if link_rate < 50:
            target = 50
            stage = "初级"
        elif link_rate < 70:
            target = 70
            stage = "中级"
        else:
            target = 80
            stage = "高级"
        
        # ===== 2. 项目关联率排行 =====
        project_link_query = """
            SELECT 
                p.id, p.name, p.progress,
                COUNT(DISTINCT dwi.id) as total_reports,
                COUNT(DISTINCT CASE WHEN dwi.task_id IS NOT NULL AND dwi.task_id != '' THEN dwi.id END) as linked_reports
            FROM projects p
            LEFT JOIN daily_work_items dwi ON dwi.project_name = p.name
            LEFT JOIN daily_reports dr ON dwi.report_id = dr.id
                AND dr.report_date >= CURRENT_DATE - INTERVAL '30 days'
            WHERE p.is_deleted = false AND p.status = '进行中'
            GROUP BY p.id, p.name, p.progress
            ORDER BY 
                CASE WHEN COUNT(DISTINCT dwi.id) > 0 
                    THEN COUNT(CASE WHEN dwi.task_id IS NOT NULL AND dwi.task_id != '' THEN 1 END) * 100.0 / COUNT(DISTINCT dwi.id)
                    ELSE 0 
                END ASC
            LIMIT 10
        """
        project_links = conn.execute(text(project_link_query)).fetchall()
        
        projects_trace = []
        untraceable_projects = []
        
        for p in project_links:
            total_r = p[3] or 0
            linked_r = p[4] or 0
            
            if total_r > 0:
                rate = round(linked_r * 100.0 / total_r, 1)
            else:
                rate = 0
            
            project_data = {
                "project_id": p[0],
                "project_name": p[1],
                "progress": float(p[2] or 0),
                "total_reports": total_r,
                "linked_reports": linked_r,
                "link_rate": rate
            }
            
            projects_trace.append(project_data)
            
            # 不可追溯标记（关联率低于50%且有日报）
            if rate < 50 and total_r > 0:
                untraceable_projects.append(project_data)
        
        # ===== 3. 进度无支撑项目 =====
        no_support_query = """
            SELECT p.id, p.name, p.progress, p.leader
            FROM projects p
            WHERE p.is_deleted = false
              AND p.status = '进行中'
              AND p.progress > 0
              AND NOT EXISTS (
                  SELECT 1 FROM daily_work_items dwi
                  JOIN daily_reports dr ON dwi.report_id = dr.id
                  WHERE dwi.project_name = p.name
                    AND dr.report_date >= CURRENT_DATE - INTERVAL '30 days'
              )
        """
        no_support = conn.execute(text(no_support_query)).fetchall()
        
        unsupported = [{
            "project_id": p[0],
            "project_name": p[1],
            "progress": float(p[2] or 0),
            "leader": p[3]
        } for p in no_support]
        
        return {
            "link_rate": link_rate,
            "linked_count": linked,
            "total_count": total,
            "target_link_rate": target,
            "current_stage": stage,
            "projects_trace": projects_trace,
            "untraceable_projects": untraceable_projects,
            "unsupported_progress": unsupported,
            "formulas": {
                "link_rate": "已关联工作项 ÷ 总工作项 × 100\n统计范围：近30天日报",
                "untraceable": "关联率 < 50% 且有日报记录",
                "unsupported": "项目进度 > 0 但近30天无日报",
                "target_stages": "初级50% → 中级70% → 高级80%"
            }
        }
