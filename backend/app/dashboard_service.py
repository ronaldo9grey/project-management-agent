"""
公共看板服务模块
独立功能，不影响其他模块
"""

from sqlalchemy import create_engine, text
from typing import List, Dict, Optional, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
import json
import os
from dotenv import load_dotenv

load_dotenv()

# 数据库连接
DB_URL = os.getenv("DATABASE_URL", "os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/project_cost_tracking")")
engine = create_engine(DB_URL)


# ==================== 健康度计算 ====================

def calc_health_score(project_id: int) -> Dict:
    """
    计算项目健康度
    
    返回：
    - health_score: 综合健康度
    - progress_score: 进度得分
    - cost_score: 成本得分
    - risk_score: 风险得分
    - details: 详细数据
    """
    with engine.connect() as conn:
        # 获取项目基础数据
        project = conn.execute(text("""
            SELECT id, name, progress, 
                   budget_total_cost, actual_total_cost,
                   material_budget, material_cost,
                   labor_budget, labor_cost,
                   outsourcing_budget, outsourcing_cost
            FROM projects WHERE id = :pid
        """), {"pid": project_id}).fetchone()
        
        if not project:
            return None
        
        # 获取任务数据（使用 is_latest 或版本号过滤）
        tasks = conn.execute(text("""
            WITH latest_version AS (
                SELECT MAX(CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER)) as max_ver
                FROM project_tasks
                WHERE project_id::integer = :pid AND is_deleted = false
            )
            SELECT task_id, status, progress, end_date, actual_end_date
            FROM project_tasks pt, latest_version lv
            WHERE pt.project_id::integer = :pid
              AND pt.is_deleted = false
              AND (
                  (lv.max_ver IS NULL OR lv.max_ver = 0 AND pt.is_latest = true)
                  OR CAST(SUBSTRING(pt.task_id FROM 'V([0-9]+)') AS INTEGER) = lv.max_ver
              )
        """), {"pid": project_id}).fetchall()
        
        # 计算进度得分
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t[1] == '已完成'])
        delayed_tasks = []
        today = date.today()
        
        for t in tasks:
            if t[1] != '已完成' and t[3]:  # 未完成且有截止日期
                if t[3] < today:  # 已过期
                    delayed_tasks.append(t)
        
        delay_days = 0
        if delayed_tasks:
            for t in delayed_tasks:
                delay_days = max(delay_days, (today - t[3]).days)
        
        # 进度得分 = 100 - 滞后天数×5 - 延期任务比例×20
        progress_score = 100 - max(0, delay_days * 5)
        if total_tasks > 0:
            progress_score -= (len(delayed_tasks) / total_tasks) * 20
        progress_score = max(0, min(100, progress_score))
        
        # 计算成本得分
        budget = float(project[3] or 0)  # budget_total_cost
        actual = float(project[4] or 0)  # actual_total_cost
        
        cost_overrun_pct = 0
        if budget > 0:
            cost_overrun_pct = max(0, (actual - budget) / budget)
        
        # 成本得分 = 100 - 超支比例×200
        cost_score = 100 - cost_overrun_pct * 200
        cost_score = max(0, min(100, cost_score))
        
        # 计算风险得分
        high_risk_count = len([t for t in tasks if t[1] == '延期'])
        medium_risk_count = len(delayed_tasks) - high_risk_count
        
        risk_score = 100 - high_risk_count * 10 - medium_risk_count * 5
        risk_score = max(0, min(100, risk_score))
        
        # 综合健康度
        health_score = progress_score * 0.4 + cost_score * 0.3 + risk_score * 0.3
        
        return {
            "health_score": round(health_score, 2),
            "progress_score": round(progress_score, 2),
            "cost_score": round(cost_score, 2),
            "risk_score": round(risk_score, 2),
            "details": {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "delayed_tasks": len(delayed_tasks),
                "delay_days": delay_days,
                "budget": budget,
                "actual": actual,
                "cost_overrun_pct": round(cost_overrun_pct * 100, 2)
            }
        }


def save_health_snapshot(project_id: int) -> bool:
    """保存项目健康度快照"""
    score_data = calc_health_score(project_id)
    if not score_data:
        return False
    
    with engine.connect() as conn:
        # 获取任务统计
        task_stats = conn.execute(text("""
            WITH latest_version AS (
                SELECT MAX(CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER)) as max_ver
                FROM project_tasks
                WHERE project_id::integer = :pid AND is_deleted = false
            )
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) as completed
            FROM project_tasks pt, latest_version lv
            WHERE pt.project_id::integer = :pid
              AND pt.is_deleted = false
              AND (
                  (lv.max_ver IS NULL OR lv.max_ver = 0 AND pt.is_latest = true)
                  OR CAST(SUBSTRING(pt.task_id FROM 'V([0-9]+)') AS INTEGER) = lv.max_ver
              )
        """), {"pid": project_id}).fetchone()
        
        # 获取成本数据
        cost_data = conn.execute(text("""
            SELECT budget_total_cost, actual_total_cost
            FROM projects WHERE id = :pid
        """), {"pid": project_id}).fetchone()
        
        # 插入或更新快照
        conn.execute(text("""
            INSERT INTO project_health_snapshots 
            (project_id, snapshot_date, health_score, progress_score, cost_score, risk_score,
             task_total, task_completed, task_delayed, cost_budget, cost_actual, cost_overrun_pct, details)
            VALUES 
            (:pid, :today, :health, :progress, :cost, :risk,
             :task_total, :task_completed, :task_delayed, :budget, :actual, :overrun, :details)
            ON CONFLICT (project_id, snapshot_date) 
            DO UPDATE SET
                health_score = EXCLUDED.health_score,
                progress_score = EXCLUDED.progress_score,
                cost_score = EXCLUDED.cost_score,
                risk_score = EXCLUDED.risk_score,
                task_total = EXCLUDED.task_total,
                task_completed = EXCLUDED.task_completed,
                task_delayed = EXCLUDED.task_delayed,
                cost_budget = EXCLUDED.cost_budget,
                cost_actual = EXCLUDED.cost_actual,
                cost_overrun_pct = EXCLUDED.cost_overrun_pct,
                details = EXCLUDED.details
        """), {
            "pid": project_id,
            "today": date.today(),
            "health": score_data["health_score"],
            "progress": score_data["progress_score"],
            "cost": score_data["cost_score"],
            "risk": score_data["risk_score"],
            "task_total": task_stats[0] or 0,
            "task_completed": task_stats[1] or 0,
            "task_delayed": score_data["details"]["delayed_tasks"],
            "budget": float(cost_data[0] or 0),
            "actual": float(cost_data[1] or 0),
            "overrun": score_data["details"]["cost_overrun_pct"],
            "details": json.dumps(score_data["details"])
        })
        conn.commit()
    
    return True


# ==================== 预警检测 ====================

def detect_alerts(project_id: int) -> List[Dict]:
    """
    检测项目预警
    返回预警列表
    """
    alerts = []
    
    with engine.connect() as conn:
        # 获取项目信息
        project = conn.execute(text("""
            SELECT id, name, leader_id, progress,
                   budget_total_cost, actual_total_cost
            FROM projects WHERE id = :pid AND is_deleted = false
        """), {"pid": project_id}).fetchone()
        
        if not project:
            return alerts
        
        today = date.today()
        
        # 1. 延期预警
        delayed_tasks = conn.execute(text("""
            WITH latest_version AS (
                SELECT MAX(CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER)) as max_ver
                FROM project_tasks
                WHERE project_id::integer = :pid AND is_deleted = false
            )
            SELECT task_id, task_name, end_date, status
            FROM project_tasks pt, latest_version lv
            WHERE pt.project_id::integer = :pid
              AND pt.is_deleted = false
              AND pt.status != '已完成'
              AND pt.end_date < :today
              AND (
                  (lv.max_ver IS NULL OR lv.max_ver = 0 AND pt.is_latest = true)
                  OR CAST(SUBSTRING(pt.task_id FROM 'V([0-9]+)') AS INTEGER) = lv.max_ver
              )
            ORDER BY pt.end_date
        """), {"pid": project_id, "today": today}).fetchall()
        
        if delayed_tasks:
            max_delay = max((today - t[2]).days for t in delayed_tasks)
            severity = "high" if max_delay >= 7 else ("medium" if max_delay >= 3 else "low")
            
            alerts.append({
                "project_id": project_id,
                "alert_type": "delay",
                "severity": severity,
                "title": f"任务延期预警",
                "content": f"项目有 {len(delayed_tasks)} 个任务已延期，最长延期 {max_delay} 天",
                "details": {
                    "delayed_count": len(delayed_tasks),
                    "max_delay_days": max_delay,
                    "tasks": [{"task_id": t[0], "task_name": t[1], "end_date": str(t[2])} for t in delayed_tasks[:5]]
                },
                "responsible_users": [project[2]] if project[2] else []
            })
        
        # 2. 沉默预警
        last_report = conn.execute(text("""
            SELECT MAX(dr.report_date) as last_date
            FROM daily_reports dr
            JOIN daily_work_items dwi ON dwi.report_id = dr.id
            JOIN project_tasks pt ON pt.task_id = dwi.task_id
            WHERE pt.project_id::integer = :pid
        """), {"pid": project_id}).fetchone()
        
        if last_report and last_report[0]:
            silent_days = (today - last_report[0]).days
        else:
            # 检查项目创建时间
            project_created = conn.execute(text("""
                SELECT created_at FROM projects WHERE id = :pid
            """), {"pid": project_id}).fetchone()
            if project_created and project_created[0]:
                silent_days = (today - project_created[0].date()).days
            else:
                silent_days = 30  # 默认认为沉默很久
        
        if silent_days >= 3:
            severity = "high" if silent_days >= 7 else ("medium" if silent_days >= 5 else "low")
            alerts.append({
                "project_id": project_id,
                "alert_type": "silence",
                "severity": severity,
                "title": "项目沉默预警",
                "content": f"项目已连续 {silent_days} 天无日报更新",
                "details": {"silent_days": silent_days},
                "responsible_users": [project[2]] if project[2] else []
            })
        
        # 3. 成本预警
        budget = float(project[4] or 0)
        actual = float(project[5] or 0)
        if budget > 0:
            overrun_pct = (actual - budget) / budget
            if overrun_pct > 0.1:
                severity = "high" if overrun_pct >= 0.5 else ("medium" if overrun_pct >= 0.2 else "low")
                alerts.append({
                    "project_id": project_id,
                    "alert_type": "cost",
                    "severity": severity,
                    "title": "成本超支预警",
                    "content": f"项目成本已超支 {round(overrun_pct * 100, 1)}%，预算 {budget:.0f}，实际 {actual:.0f}",
                    "details": {
                        "budget": budget,
                        "actual": actual,
                        "overrun_pct": round(overrun_pct * 100, 2)
                    },
                    "responsible_users": [project[2]] if project[2] else []
                })
        
        # 4. 进度预警（对比项目实际进度 vs 计划进度）
        # 获取项目的任务数据（含工期）
        tasks_info = conn.execute(text("""
            SELECT 
                pt.progress,
                pt.start_date,
                pt.end_date,
                pt.actual_end_date
            FROM project_tasks pt
            WHERE pt.project_id::integer = :pid
              AND pt.is_latest = true
              AND pt.is_deleted = false
        """), {"pid": project_id}).fetchall()
        
        if tasks_info and len(tasks_info) > 0:
            # 计算实际进度（按任务工期天数计算）
            from datetime import datetime
            today = datetime.now().date()
            total_work_days = 0
            completed_work_days = 0
            
            for t in tasks_info:
                task_progress = float(t[0] or 0) / 100
                task_start = t[1]
                task_end = t[2]
                task_actual_end = t[3]
                
                # 计算任务工期（天）
                if task_start and task_end:
                    start = task_start if isinstance(task_start, type(today)) else datetime.strptime(str(task_start), '%Y-%m-%d').date()
                    end = task_end if isinstance(task_end, type(today)) else datetime.strptime(str(task_end), '%Y-%m-%d').date()
                    work_days = max((end - start).days, 1)
                else:
                    work_days = 5  # 默认5天
                
                total_work_days += work_days
                
                if task_progress >= 1.0 or task_actual_end:
                    # 已完成：计入完整工期
                    completed_work_days += work_days
                elif task_end and task_end < today:
                    # 延期未完成：最高计50%
                    completed_work_days += work_days * min(task_progress, 0.5)
                else:
                    # 进行中：按进度计入
                    completed_work_days += work_days * task_progress
            
            actual_progress = round(completed_work_days / total_work_days * 100, 1) if total_work_days > 0 else 0
            
            # 获取项目时间范围计算计划进度
            project = conn.execute(text("""
                SELECT start_date, end_date FROM projects WHERE id = :pid
            """), {"pid": project_id}).fetchone()
            
            planned_progress = 0
            if project and project[0] and project[1]:
                start_date = project[0]
                end_date = project[1]
                today = datetime.now().date()
                start = datetime.strptime(str(start_date), '%Y-%m-%d').date() if isinstance(start_date, str) else start_date
                end = datetime.strptime(str(end_date), '%Y-%m-%d').date() if isinstance(end_date, str) else end_date
                
                if today <= start:
                    planned_progress = 0
                elif today >= end:
                    planned_progress = 100
                else:
                    total_days = (end - start).days
                    elapsed_days = (today - start).days
                    planned_progress = round(elapsed_days / total_days * 100, 1) if total_days > 0 else 0
            
            # 判断进度滞后：实际进度 < 计划进度 - 10%
            if actual_progress < planned_progress - 10:
                lag_amount = planned_progress - actual_progress
                severity = "high" if lag_amount >= 30 else ("medium" if lag_amount >= 20 else "low")
                alerts.append({
                    "project_id": project_id,
                    "alert_type": "progress",
                    "severity": severity,
                    "title": "进度滞后预警",
                    "content": f"实际进度 {actual_progress:.1f}% 低于计划进度 {planned_progress:.1f}%，滞后 {lag_amount:.1f} 个百分点",
                    "details": {
                        "planned_progress": planned_progress,
                        "actual_progress": actual_progress,
                        "total_tasks": len(tasks_info),
                        "lag_amount": round(lag_amount, 1)
                    },
                    "responsible_users": [project[2]] if project[2] else []
                })
    
    return alerts


def save_alerts(project_id: int, alerts: List[Dict]) -> bool:
    """保存预警记录（去重）"""
    if not alerts:
        return True
    
    with engine.connect() as conn:
        for alert in alerts:
            # 先删除同类型的未解决预警，再插入新的
            conn.execute(text("""
                DELETE FROM project_alerts 
                WHERE project_id = :pid 
                  AND alert_type = :type 
                  AND title = :title
                  AND NOT is_resolved
            """), {
                "pid": project_id,
                "type": alert["alert_type"],
                "title": alert["title"]
            })
            
            # 插入新预警
            conn.execute(text("""
                INSERT INTO project_alerts 
                (project_id, alert_type, severity, title, content, details, responsible_users, is_resolved)
                VALUES 
                (:pid, :type, :severity, :title, :content, :details, :users, false)
            """), {
                "pid": project_id,
                "type": alert["alert_type"],
                "severity": alert["severity"],
                "title": alert["title"],
                "content": alert["content"],
                "details": json.dumps(alert.get("details", {})),
                "users": alert.get("responsible_users", [])
            })
        conn.commit()
    
    return True


def run_daily_alert_detection():
    """每日预警检测任务（推送到微信群组）"""
    with engine.connect() as conn:
        # 获取所有进行中的项目
        projects = conn.execute(text("""
            SELECT id, name FROM projects 
            WHERE is_deleted = false AND status = '进行中'
        """)).fetchall()
        
        # 导入推送服务
        from .push_service import push_alert_to_wechat
        
        for p in projects:
            project_id = p[0]
            project_name = p[1]
            
            # 检测预警
            alerts = detect_alerts(project_id)
            
            # 保存预警
            if alerts:
                save_alerts(project_id, alerts)
                
                # 推送高风险预警到微信群组
                for alert in alerts:
                    if alert.get("severity") == "high":
                        push_alert_to_wechat(
                            alert=alert,
                            project_name=project_name
                        )
            
            # 保存健康度快照
            save_health_snapshot(project_id)
        
        return len(projects)


# ==================== 看板数据查询 ====================

def get_dashboard_overview(role: str = "admin", user_id: int = None) -> Dict:
    """
    获取看板概览数据
    
    role: admin/user/viewer
    user_id: 用户ID（用于个性化数据）
    """
    with engine.connect() as conn:
        # 基础统计
        stats = conn.execute(text("""
            SELECT 
                COUNT(*) FILTER (WHERE status = '进行中') as ongoing,
                COUNT(*) FILTER (WHERE status = '已完成') as completed,
                COUNT(*) as total
            FROM projects WHERE is_deleted = false
        """)).fetchone()
        
        # 预警统计
        alert_stats = conn.execute(text("""
            SELECT 
                COUNT(*) FILTER (WHERE severity = 'high' AND NOT is_resolved) as high,
                COUNT(*) FILTER (WHERE severity = 'medium' AND NOT is_resolved) as medium,
                COUNT(*) FILTER (WHERE severity = 'low' AND NOT is_resolved) as low,
                COUNT(*) FILTER (WHERE NOT is_resolved) as total
            FROM project_alerts
            WHERE created_at >= CURRENT_DATE
        """)).fetchone()
        
        # 项目健康度排名
        health_ranking = conn.execute(text("""
            SELECT 
                p.id, p.name, p.leader,
                COALESCE(hs.health_score, 50) as health_score,
                COALESCE(hs.progress_score, 50) as progress_score,
                COALESCE(hs.cost_score, 50) as cost_score,
                COALESCE(hs.risk_score, 50) as risk_score
            FROM projects p
            LEFT JOIN project_health_snapshots hs 
                ON hs.project_id = p.id AND hs.snapshot_date = CURRENT_DATE
            WHERE p.is_deleted = false AND p.status = '进行中'
            ORDER BY health_score DESC
            LIMIT 10
        """)).fetchall()
        
        # 最近预警
        recent_alerts = conn.execute(text("""
            SELECT 
                a.id, a.project_id, p.name as project_name,
                a.alert_type, a.severity, a.title, a.content,
                a.created_at, a.is_resolved
            FROM project_alerts a
            JOIN projects p ON p.id = a.project_id
            WHERE NOT a.is_resolved
            ORDER BY 
                CASE a.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                a.created_at DESC
            LIMIT 10
        """)).fetchall()
        
        return {
            "stats": {
                "ongoing_projects": stats[0] or 0,
                "completed_projects": stats[1] or 0,
                "total_projects": stats[2] or 0,
                "high_alerts": alert_stats[0] or 0,
                "medium_alerts": alert_stats[1] or 0,
                "low_alerts": alert_stats[2] or 0,
                "total_alerts": alert_stats[3] or 0
            },
            "health_ranking": [{
                "id": r[0],
                "name": r[1],
                "leader": r[2],
                "health_score": float(r[3] or 0),
                "progress_score": float(r[4] or 0),
                "cost_score": float(r[5] or 0),
                "risk_score": float(r[6] or 0)
            } for r in health_ranking],
            "recent_alerts": [{
                "id": r[0],
                "project_id": r[1],
                "project_name": r[2],
                "alert_type": r[3],
                "severity": r[4],
                "title": r[5],
                "content": r[6],
                "created_at": str(r[7]),
                "is_resolved": r[8]
            } for r in recent_alerts]
        }


def get_project_health_trend(project_id: int, days: int = 30) -> Dict:
    """获取项目健康度趋势"""
    with engine.connect() as conn:
        snapshots = conn.execute(text("""
            SELECT 
                snapshot_date, health_score, progress_score, cost_score, risk_score,
                task_total, task_completed, task_delayed, cost_overrun_pct
            FROM project_health_snapshots
            WHERE project_id = :pid
              AND snapshot_date >= :start_date
            ORDER BY snapshot_date
        """), {
            "pid": project_id,
            "start_date": date.today() - timedelta(days=days)
        }).fetchall()
        
        return {
            "project_id": project_id,
            "period_days": days,
            "trend": [{
                "date": str(s[0]),
                "health_score": float(s[1] or 0),
                "progress_score": float(s[2] or 0),
                "cost_score": float(s[3] or 0),
                "risk_score": float(s[4] or 0),
                "task_total": s[5] or 0,
                "task_completed": s[6] or 0,
                "task_delayed": s[7] or 0,
                "cost_overrun_pct": float(s[8] or 0)
            } for s in snapshots]
        }


def get_alert_rules() -> List[Dict]:
    """获取预警规则配置"""
    with engine.connect() as conn:
        rules = conn.execute(text("""
            SELECT id, alert_type, alert_name, enabled, thresholds, description
            FROM alert_rules
            ORDER BY id
        """)).fetchall()
        
        return [{
            "id": r[0],
            "alert_type": r[1],
            "alert_name": r[2],
            "enabled": r[3],
            "thresholds": r[4],
            "description": r[5]
        } for r in rules]


def update_alert_rule(rule_id: int, enabled: bool = None, thresholds: Dict = None) -> bool:
    """更新预警规则"""
    with engine.connect() as conn:
        if enabled is not None:
            conn.execute(text("""
                UPDATE alert_rules SET enabled = :enabled, updated_at = NOW()
                WHERE id = :id
            """), {"id": rule_id, "enabled": enabled})
        
        if thresholds:
            conn.execute(text("""
                UPDATE alert_rules SET thresholds = :thresholds, updated_at = NOW()
                WHERE id = :id
            """), {"id": rule_id, "thresholds": json.dumps(thresholds)})
        
        conn.commit()
    return True


def resolve_alert(alert_id: int, resolved_by: int) -> bool:
    """标记预警已处理"""
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE project_alerts 
            SET is_resolved = true, resolved_at = NOW(), resolved_by = :user_id
            WHERE id = :id
        """), {"id": alert_id, "user_id": resolved_by})
        conn.commit()
    return True
