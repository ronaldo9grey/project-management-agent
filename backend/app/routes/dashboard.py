"""
看板相关API路由
包括：今日聚焦、风险预警、项目看板等
"""
from fastapi import APIRouter, Depends
from typing import Dict, List
from datetime import datetime, timedelta

from ..database import get_connection, text
from ..auth import get_current_user
from ..logger import get_logger
from ..config import settings

logger = get_logger(__name__)

router = APIRouter(prefix="/api/agent/dashboard", tags=["看板"])


@router.get("/today-focus")
async def get_today_focus(current_user: Dict = Depends(get_current_user)):
    """获取今日聚焦任务"""
    username = current_user.get("username") or current_user.get("sub")
    employee_id = current_user.get("employee_id") or username
    
    today = datetime.now().date()
    
    with get_connection() as conn:
        # 查询用户负责的项目
        emp_result = conn.execute(text("""
            SELECT name FROM personnel WHERE employee_id = :emp_id
        """), {"emp_id": employee_id})
        emp_row = emp_result.fetchone()
        employee_name = emp_row[0] if emp_row else None
        
        if not employee_name:
            return {"tasks": [], "alerts": []}
        
        # 查询今日截止的任务
        tasks_result = conn.execute(text("""
            SELECT task_id, task_name, end_date, progress
            FROM project_tasks pt
            JOIN projects p ON CAST(p.id AS VARCHAR) = pt.project_id
            WHERE p.leader = :emp_name
              AND pt.end_date = :today
              AND pt.progress < 100
              AND pt.is_latest = true
              AND pt.is_deleted = false
            ORDER BY pt.end_date
        """), {"emp_name": employee_name, "today": today})
        
        tasks = []
        for row in tasks_result:
            tasks.append({
                "task_id": row[0],
                "task_name": row[1],
                "end_date": str(row[2]),
                "progress": float(row[3] or 0)
            })
        
        return {
            "tasks": tasks,
            "date": str(today),
            "employee": employee_name
        }


@router.get("/risk-alerts")
async def get_risk_alerts(current_user: Dict = Depends(get_current_user)):
    """获取风险预警"""
    username = current_user.get("username") or current_user.get("sub")
    employee_id = current_user.get("employee_id") or username
    
    today = datetime.now().date()
    
    with get_connection() as conn:
        emp_result = conn.execute(text("""
            SELECT name FROM personnel WHERE employee_id = :emp_id
        """), {"emp_id": employee_id})
        emp_row = emp_result.fetchone()
        employee_name = emp_row[0] if emp_row else None
        
        if not employee_name:
            return {"alerts": []}
        
        # 查询延期任务
        delayed_result = conn.execute(text("""
            SELECT p.name as project_name, pt.task_name, pt.end_date,
                   pt.progress, CURRENT_DATE - pt.end_date as delay_days
            FROM project_tasks pt
            JOIN projects p ON CAST(p.id AS VARCHAR) = pt.project_id
            WHERE p.leader = :emp_name
              AND pt.end_date < CURRENT_DATE
              AND pt.progress < 100
              AND pt.is_latest = true
              AND pt.is_deleted = false
            ORDER BY delay_days DESC
            LIMIT 10
        """), {"emp_name": employee_name})
        
        alerts = []
        for row in delayed_result:
            alerts.append({
                "type": "delayed",
                "severity": "high" if row[5] > 3 else "medium",
                "project_name": row[0],
                "task_name": row[1],
                "end_date": str(row[2]),
                "progress": float(row[3] or 0),
                "delay_days": int(row[4] or 0)
            })
        
        return {
            "alerts": alerts,
            "total": len(alerts),
            "employee": employee_name
        }


@router.get("/my-project-risks")
async def get_my_project_risks(current_user: Dict = Depends(get_current_user)):
    """获取我负责项目的风险"""
    username = current_user.get("username") or current_user.get("sub")
    employee_id = current_user.get("employee_id") or username
    
    with get_connection() as conn:
        emp_result = conn.execute(text("""
            SELECT name FROM personnel WHERE employee_id = :emp_id
        """), {"emp_id": employee_id})
        emp_row = emp_result.fetchone()
        employee_name = emp_row[0] if emp_row else None
        
        if not employee_name:
            return {"projects": []}
        
        # 查询用户负责的项目及其风险
        projects_result = conn.execute(text("""
            SELECT 
                p.id,
                p.name,
                p.progress,
                COUNT(pt.task_id) FILTER (WHERE pt.end_date < CURRENT_DATE AND pt.progress < 100) as delayed_tasks,
                COUNT(pt.task_id) FILTER (WHERE pt.end_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '3 days' AND pt.progress < 80) as soon_expire
            FROM projects p
            LEFT JOIN project_tasks pt ON CAST(p.id AS VARCHAR) = pt.project_id 
                AND pt.is_latest = true AND pt.is_deleted = false
            WHERE p.leader = :emp_name
              AND p.is_deleted = false
            GROUP BY p.id, p.name, p.progress
            ORDER BY delayed_tasks DESC, soon_expire DESC
        """), {"emp_name": employee_name})
        
        projects = []
        for row in projects_result:
            risk_score = int(row[3] or 0) * 15 + int(row[4] or 0) * 5
            projects.append({
                "id": row[0],
                "name": row[1],
                "progress": float(row[2] or 0),
                "delayed_tasks": int(row[3] or 0),
                "soon_expire": int(row[4] or 0),
                "risk_score": min(risk_score, 100)
            })
        
        return {
            "projects": projects,
            "employee": employee_name
        }


@router.get("/project-board")
async def get_project_board(current_user: Dict = Depends(get_current_user)):
    """获取项目看板"""
    with get_connection() as conn:
        result = conn.execute(text("""
            SELECT 
                p.id,
                p.name,
                p.leader,
                p.status,
                p.progress,
                p.start_date,
                p.end_date,
                COUNT(pt.task_id) as task_count
            FROM projects p
            LEFT JOIN project_tasks pt ON CAST(p.id AS VARCHAR) = pt.project_id 
                AND pt.is_latest = true AND pt.is_deleted = false
            WHERE p.is_deleted = false
            GROUP BY p.id, p.name, p.leader, p.status, p.progress, p.start_date, p.end_date
            ORDER BY p.progress DESC, p.end_date DESC
        """))
        
        projects = []
        for row in result:
            projects.append({
                "id": row[0],
                "name": row[1],
                "leader": row[2],
                "status": row[3],
                "progress": float(row[4] or 0),
                "start_date": str(row[5]) if row[5] else None,
                "end_date": str(row[6]) if row[6] else None,
                "task_count": int(row[7] or 0)
            })
        
        return {"projects": projects}


@router.get("/risk-matrix")
async def get_risk_matrix(current_user: Dict = Depends(get_current_user)):
    """获取风险矩阵"""
    today = datetime.now().date()
    
    with get_connection() as conn:
        # 按项目负责人统计风险
        result = conn.execute(text("""
            SELECT 
                p.leader,
                COUNT(DISTINCT p.id) as project_count,
                COUNT(pt.task_id) FILTER (WHERE pt.end_date < :today AND pt.progress < 100) as delayed_tasks,
                COUNT(pt.task_id) FILTER (WHERE pt.end_date BETWEEN :today AND :today + INTERVAL '3 days' AND pt.progress < 80) as soon_expire
            FROM projects p
            LEFT JOIN project_tasks pt ON CAST(p.id AS VARCHAR) = pt.project_id 
                AND pt.is_latest = true AND pt.is_deleted = false
            WHERE p.is_deleted = false
            GROUP BY p.leader
            ORDER BY delayed_tasks DESC
        """), {"today": today})
        
        matrix = []
        for row in result:
            matrix.append({
                "leader": row[0],
                "project_count": int(row[1] or 0),
                "delayed_tasks": int(row[2] or 0),
                "soon_expire": int(row[3] or 0),
                "risk_level": "high" if int(row[2] or 0) > 3 else ("medium" if int(row[2] or 0) > 0 else "low")
            })
        
        return {"matrix": matrix}


@router.get("/overview")
async def get_dashboard_overview(current_user: Dict = Depends(get_current_user)):
    """获取看板概览"""
    today = datetime.now().date()
    
    with get_connection() as conn:
        # 项目统计
        projects_result = conn.execute(text("""
            SELECT 
                COUNT(*) FILTER (WHERE status = '进行中') as ongoing,
                COUNT(*) FILTER (WHERE status = '已完成') as completed,
                COUNT(*) as total
            FROM projects
            WHERE is_deleted = false
        """))
        proj_row = projects_result.fetchone()
        
        # 成本统计
        cost_result = conn.execute(text("""
            SELECT 
                COALESCE(SUM(total_budget_cost), 0) as total_budget,
                COALESCE(SUM(total_actual_cost), 0) as total_actual
            FROM projects
            WHERE is_deleted = false
        """))
        cost_row = cost_result.fetchone()
        
        return {
            "stats": {
                "ongoing_projects": int(proj_row[0] or 0),
                "completed_projects": int(proj_row[1] or 0),
                "total_projects": int(proj_row[2] or 0),
                "total_budget": float(cost_row[0] or 0),
                "total_actual": float(cost_row[1] or 0)
            }
        }


@router.get("/projects")
async def get_dashboard_projects(current_user: Dict = Depends(get_current_user)):
    """获取看板项目列表"""
    username = current_user.get("username")
    role_id = current_user.get("role_id")
    
    with get_connection() as conn:
        if role_id == 11:  # 管理员
            result = conn.execute(text("""
                SELECT id, name, leader, status, progress, start_date, end_date
                FROM projects
                WHERE is_deleted = false
                ORDER BY progress DESC, end_date
            """))
        else:
            emp_result = conn.execute(text("""
                SELECT name FROM personnel WHERE employee_id = :emp_id
            """), {"emp_id": username})
            emp_row = emp_result.fetchone()
            employee_name = emp_row[0] if emp_row else username
            
            result = conn.execute(text("""
                SELECT id, name, leader, status, progress, start_date, end_date
                FROM projects
                WHERE leader = :emp_name AND is_deleted = false
                ORDER BY progress DESC, end_date
            """), {"emp_name": employee_name})
        
        projects = []
        for row in result:
            projects.append({
                "id": row[0],
                "name": row[1],
                "leader": row[2],
                "status": row[3],
                "progress": float(row[4] or 0),
                "start_date": str(row[5]) if row[5] else None,
                "end_date": str(row[6]) if row[6] else None
            })
        
        return projects


@router.get("/insight")
async def get_dashboard_insight(current_user: Dict = Depends(get_current_user)):
    """获取AI洞察"""
    # 简化版：返回基础信息
    today = datetime.now().date()
    
    with get_connection() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) FILTER (WHERE end_date < CURRENT_DATE AND progress < 100) as delayed_count
            FROM project_tasks
            WHERE is_latest = true AND is_deleted = false
        """))
        row = result.fetchone()
        delayed_count = int(row[0] or 0)
    
    insights = [f"今日日期: {today}"]
    if delayed_count > 0:
        insights.append(f"⚠️ 当前有 {delayed_count} 个任务延期")
    else:
        insights.append("✅ 暂无延期任务")
    
    return {"content": "\n".join(insights)}
