"""
任务自动关联和状态管理模块
"""
import os
import json
import re
from datetime import date, datetime
from typing import Optional, Dict, List, Tuple
try:
    from .database import get_engine, text
    from .logger import ai_logger
except ImportError:
    # 当直接导入时使用绝对导入
    from database import get_engine, text
    from logger import ai_logger

import httpx

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


def get_db_engine():
    """获取数据库引擎（使用全局单例）"""
    return get_engine()


def extract_version(task_id: str) -> int:
    """
    从 task_id 提取版本号
    P35V2T3 -> 2
    """
    import re
    match = re.search(r'V(\d+)', task_id)
    return int(match.group(1)) if match else 0


def get_latest_version_tasks(project_id: int) -> List[Dict]:
    """
    获取项目最新版本的任务列表
    
    返回：只包含最新版本的任务
    """
    engine = get_db_engine()
    
    with engine.connect() as conn:
        # 获取最新版本号
        version_result = conn.execute(text("""
            SELECT MAX(CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER)) as max_version
            FROM project_tasks
            WHERE project_id::integer = :pid
              AND is_deleted = false
        """), {"pid": project_id})
        
        max_version_row = version_result.fetchone()
        max_version = max_version_row[0] if max_version_row and max_version_row[0] else 1
        
        # 只获取最新版本的任务
        result = conn.execute(text("""
            SELECT task_id, task_name, status, progress, 
                   start_date, end_date, actual_end_date,
                   assignee, planned_hours
            FROM project_tasks 
            WHERE project_id::integer = :pid
              AND is_deleted = false
              AND CAST(SUBSTRING(task_id FROM 'V([0-9]+)') AS INTEGER) = :max_version
            ORDER BY task_id
        """), {"pid": project_id, "max_version": max_version})
        
        tasks = []
        for row in result:
            tasks.append({
                "task_id": row[0],
                "task_name": row[1],
                "status": row[2],
                "progress": float(row[3] or 0),
                "start_date": row[4],
                "end_date": row[5],
                "actual_end_date": row[6],
                "assignee": row[7],
                "planned_hours": float(row[8] or 0),
                "version": max_version
            })
        
        return tasks


async def match_task_by_content_ai(work_content: str, project_id: int, project_name: str = None) -> Optional[Dict[str, str]]:
    """
    使用 AI 推理分析匹配任务
    
    参数：
    - work_content: 日报工作内容
    - project_id: 项目ID
    - project_name: 项目名称（用于上下文）
    
    返回：匹配的任务信息 {"task_id": "xxx", "task_name": "xxx"}，未匹配返回 None
    """
    tasks = get_latest_version_tasks(project_id)
    if not tasks:
        return None
    
    # 构建任务列表
    task_list = "\n".join([
        f"- {t['task_id']}: {t['task_name']} (状态: {t['status']}, 进度: {t['progress']}%)"
        for t in tasks
    ])
    
    # 构建提示词
    prompt = f"""你是一个项目管理助手，需要根据日报工作内容匹配项目任务。

项目：{project_name or f'项目{project_id}'}

项目任务列表：
{task_list}

日报工作内容：{work_content}

请分析工作内容，判断它属于哪个任务。要求：
1. 理解工作内容的语义，不要只看关键词
2. 考虑任务的上下文（需求分析可能属于"需求调研"任务）
3. 如果工作内容明显属于某个任务，返回任务ID和任务名称
4. 如果无法确定或不属于任何任务，返回 null

只返回 JSON 格式：
{{"matched_task_id": "P35V2T2", "matched_task_name": "需求调研"}} 或 {{"matched_task_id": null}}

不要返回任何解释，只返回 JSON。"""

    try:
        # 直接硬编码 URL，避免环境变量问题
        url = "https://api.deepseek.com/v1/chat/completions"
        ai_logger.debug(f"调用 DeepSeek API: {url}")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是一个精确的任务匹配助手，只返回 JSON 格式结果。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 100
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # 解析 JSON
                json_match = re.search(r'\{[^}]+\}', content)
                if json_match:
                    data = json.loads(json_match.group())
                    task_id = data.get("matched_task_id")
                    task_name = data.get("matched_task_name")
                    
                    # 验证 task_id 是否在任务列表中
                    task_dict = {t["task_id"]: t["task_name"] for t in tasks}
                    if task_id and task_id in task_dict:
                        # 如果API没有返回task_name，从本地任务列表获取
                        if not task_name:
                            task_name = task_dict[task_id]
                        
                        ai_logger.info(f"AI匹配成功: '{work_content}' -> {task_id} ({task_name})")
                        return {"task_id": task_id, "task_name": task_name}
                    
                ai_logger.debug(f"AI未匹配: '{work_content}'")
                return None
            else:
                ai_logger.error(f"AI调用失败: {response.status_code} - {response.text[:200]}")
                return None
            
    except Exception as e:
        ai_logger.exception(f"AI任务匹配异常: {e}")
        import traceback
        traceback.print_exc()
        return None


def match_task_by_content(work_content: str, project_id: int) -> Optional[str]:
    """
    根据 work_content 智能匹配任务（同步版本，使用简单匹配）
    
    注意：推荐使用 match_task_by_content_ai 进行 AI 推理匹配
    """
    tasks = get_latest_version_tasks(project_id)
    if not tasks:
        return None
    
    work_content_lower = work_content.lower().strip()
    
    # 简单匹配（备用）
    for task in tasks:
        if task["task_name"].lower() in work_content_lower:
            return task["task_id"]
    
    # 同义词匹配
    synonym_map = {
        "需求分析": ["需求调研", "需求讨论", "需求梳理"],
        "需求调研": ["需求分析", "需求讨论"],
        "系统设计": ["概要设计", "详细设计", "架构设计"],
        "数据库设计": ["db设计", "数据模型设计"],
        "后端开发": ["后端", "服务端开发", "api开发", "接口开发"],
        "前端开发": ["前端", "ui开发", "页面开发"],
        "测试": ["功能测试", "单元测试", "集成测试", "系统测试"],
        "部署": ["上线", "发布", "部署上线"],
        "接口联调": ["接口对接", "联调"],
    }
    
    for task in tasks:
        task_name = task["task_name"]
        synonyms = synonym_map.get(task_name, [])
        synonyms.append(task_name)
        
        for syn in synonyms:
            if syn in work_content_lower:
                return task["task_id"]
    
    return None


def calculate_task_status(task: Dict) -> Tuple[str, bool]:
    """
    根据进度和时间自动计算任务状态
    
    返回：(新状态, 是否有变化)
    """
    today = date.today()
    current_status = task["status"]
    progress = task["progress"]
    start_date = task["start_date"]
    end_date = task["end_date"]
    
    # 规则1：进度 >= 100% → 已完成
    if progress >= 100:
        return ("已完成", current_status != "已完成")
    
    # 规则2：计划结束时间已过，进度 < 100% → 延期
    if end_date and end_date < today and progress < 100:
        return ("延期", current_status != "延期")
    
    # 规则3：计划开始时间已过，且有进度 → 进行中
    if start_date and start_date <= today:
        if progress > 0:
            return ("进行中", current_status != "进行中")
        # 开始时间已过但无进度，仍然算进行中（可能刚开始）
        if end_date and end_date >= today:
            return ("进行中", current_status != "进行中")
    
    # 规则4：未到开始时间 → 未开始
    if start_date and start_date > today:
        return ("未开始", current_status != "未开始")
    
    # 默认保持原状态
    return (current_status, False)


def check_task_risks(project_id: int) -> List[Dict]:
    """
    检查项目任务风险
    
    返回：风险列表
    """
    tasks = get_latest_version_tasks(project_id)
    today = date.today()
    risks = []
    
    engine = get_db_engine()
    
    for task in tasks:
        task_name = task["task_name"]
        task_id = task["task_id"]
        start_date = task["start_date"]
        end_date = task["end_date"]
        progress = task["progress"]
        status = task["status"]
        
        # 检查是否有日报记录（用于多种风险判断）
        with engine.connect() as conn:
            # 获取所有关联日报
            report_result = conn.execute(text("""
                SELECT dwi.hours_spent, dwi.work_content, dr.report_date
                FROM daily_work_items dwi
                JOIN daily_reports dr ON dwi.report_id = dr.id
                WHERE dwi.task_id = :tid
                ORDER BY dr.report_date DESC
            """), {"tid": task_id})
            reports = report_result.fetchall()
        
        has_report = len(reports) > 0
        report_dates = [r[2] for r in reports] if reports else []
        last_report_date = max(report_dates) if report_dates else None
        last_report_hours = reports[0][0] if reports else 0
        total_report_hours = sum(r[0] for r in reports) if reports else 0
        
        # 计划时间段
        plan_period = f"{start_date} ~ {end_date}" if start_date and end_date else None
        
        # 1. 延期风险（已过结束时间，进度 < 100%）
        if end_date and end_date < today and progress < 100:
            delay_days = (today - end_date).days
            risks.append({
                "task_id": task_id,
                "task_name": task_name,
                "risk_type": "delayed",
                "risk_level": "high",
                "delay_days": delay_days,
                "progress": progress,
                "plan_start": str(start_date) if start_date else None,
                "plan_end": str(end_date),
                "plan_period": plan_period,
                "message": f"已延期 {delay_days} 天，当前进度 {progress}%，计划周期：{plan_period}"
            })
        
        # 2. 延期完成（日报记录晚于计划结束时间，但进度已100%或已有日报）
        elif end_date and has_report:
            last_report = max(report_dates)
            if last_report > end_date:
                delay_days = (last_report - end_date).days
                risks.append({
                    "task_id": task_id,
                    "task_name": task_name,
                    "risk_type": "delayed_completion",
                    "risk_level": "medium",
                    "delay_days": delay_days,
                    "last_report_date": str(last_report),
                    "plan_start": str(start_date) if start_date else None,
                    "plan_end": str(end_date),
                    "plan_period": plan_period,
                    "message": f"延期完成，计划 {end_date}，实际完成 {last_report}，延期 {delay_days} 天"
                })
        
        # 3. 即将到期风险（3天内到期，进度 < 80%）
        elif end_date and 0 < (end_date - today).days <= 3 and progress < 80 and not has_report:
            remaining_days = (end_date - today).days
            risks.append({
                "task_id": task_id,
                "task_name": task_name,
                "risk_type": "expiring_soon",
                "risk_level": "medium",
                "remaining_days": remaining_days,
                "progress": progress,
                "plan_start": str(start_date) if start_date else None,
                "plan_end": str(end_date),
                "plan_period": plan_period,
                "message": f"即将到期（剩余 {remaining_days} 天），进度仅 {progress}%，计划周期：{plan_period}"
            })
        
        # 4. 提前开始（计划日期未到，但已有日报，且日报日期早于计划开始）
        elif start_date and start_date > today and has_report:
            first_report = min(report_dates)
            if first_report < start_date:
                days_early = (start_date - first_report).days
                risks.append({
                    "task_id": task_id,
                    "task_name": task_name,
                    "risk_type": "started_early",
                    "risk_level": "low",
                    "days_early": days_early,
                    "first_report_date": str(first_report),
                    "last_report_date": str(last_report_date),
                    "plan_start": str(start_date),
                    "plan_end": str(end_date) if end_date else None,
                    "plan_period": plan_period,
                    "message": f"提前启动 {days_early} 天，首次日报：{first_report}，计划：{plan_period}"
                })
        
        # 5. 已启动未报告（开始时间已过，但无日报记录）
        elif start_date and start_date <= today and progress == 0 and not has_report:
            days_since_start = (today - start_date).days
            risks.append({
                "task_id": task_id,
                "task_name": task_name,
                "risk_type": "not_reported",
                "risk_level": "medium" if days_since_start <= 3 else "high",
                "days_since_start": days_since_start,
                "plan_start": str(start_date),
                "plan_end": str(end_date) if end_date else None,
                "plan_period": plan_period,
                "message": f"{'今日已启动' if days_since_start == 0 else f'已启动 {days_since_start} 天'}，但无进度报告，计划周期：{plan_period}"
            })
        
        # 6. 即将启动提醒（3天内开始）
        elif start_date and 0 < (start_date - today).days <= 3 and not has_report:
            days_to_start = (start_date - today).days
            risks.append({
                "task_id": task_id,
                "task_name": task_name,
                "risk_type": "starting_soon",
                "risk_level": "low",
                "days_to_start": days_to_start,
                "plan_start": str(start_date),
                "plan_end": str(end_date) if end_date else None,
                "plan_period": plan_period,
                "message": f"即将启动（{days_to_start} 天后），计划周期：{plan_period}"
            })
    
    return risks


def update_task_progress_from_daily(work_items: List[Dict]) -> List[str]:
    """
    根据日报工时更新任务进度
    
    参数：
    - work_items: 日报工作项列表，包含 task_id、hours_spent、work_content
    
    返回：已更新的 task_id 列表
    """
    engine = get_db_engine()
    updated_tasks = []
    
    for item in work_items:
        task_id = item.get("task_id")
        hours_spent = item.get("hours_spent", 0)
        work_content = item.get("work_content", "")
        
        if not task_id:
            continue
        
        try:
            with engine.connect() as conn:
                # 1. 获取任务信息
                task_result = conn.execute(text("""
                    SELECT task_name, planned_hours, progress, status, end_date
                    FROM project_tasks
                    WHERE task_id = :tid
                """), {"tid": task_id})
                
                task_row = task_result.fetchone()
                if not task_row:
                    continue
                
                task_name, planned_hours, current_progress, current_status, plan_end_date = task_row
                planned_hours = float(planned_hours or 0)
                current_progress = float(current_progress or 0)
                
                # 2. 检查工作内容是否包含"完成"关键词
                completion_keywords = ["完成", "已完成", "完毕", "结束", "完工"]
                is_completion_report = any(kw in work_content for kw in completion_keywords)
                
                # 3. 计算新进度
                if planned_hours > 0 and hours_spent > 0:
                    # 累计工时 = 当前进度% * 计划工时 + 本次工时
                    accumulated_hours = (current_progress / 100) * planned_hours + hours_spent
                    new_progress = min(100, (accumulated_hours / planned_hours) * 100)
                elif is_completion_report:
                    # 如果是完成报告，直接设为 100%
                    new_progress = 100
                else:
                    new_progress = current_progress
                
                # 如果工作内容明确说"已完成"，强制设为 100%
                if is_completion_report:
                    new_progress = 100
                
                # 4. 计算新状态和实际完成时间
                from datetime import date
                today = date.today()
                actual_end_date = None
                
                if new_progress >= 100:
                    new_status = "已完成"
                    # 设置实际完成时间为今天
                    actual_end_date = today
                elif plan_end_date and plan_end_date < today and new_progress < 100:
                    new_status = "延期"
                elif current_status == "未开始" and (hours_spent > 0 or new_progress > 0):
                    new_status = "进行中"
                else:
                    new_status = current_status
                
                # 5. 更新任务
                if actual_end_date:
                    conn.execute(text("""
                        UPDATE project_tasks
                        SET progress = :progress,
                            status = :status,
                            actual_end_date = :actual_end_date
                        WHERE task_id = :tid
                    """), {
                        "progress": new_progress,
                        "status": new_status,
                        "actual_end_date": actual_end_date,
                        "tid": task_id
                    })
                else:
                    conn.execute(text("""
                        UPDATE project_tasks
                        SET progress = :progress,
                            status = :status
                        WHERE task_id = :tid
                    """), {
                        "progress": new_progress,
                        "status": new_status,
                        "tid": task_id
                    })
                
                conn.commit()
                updated_tasks.append(task_id)
                ai_logger.info(f"进度更新: {task_id} ({task_name}): {current_progress:.1f}% -> {new_progress:.1f}%, 状态: {current_status} -> {new_status}" + 
                      (f", 实际完成: {actual_end_date}" if actual_end_date else ""))
                
        except Exception as e:
            ai_logger.error(f"更新任务 {task_id} 进度失败: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    return updated_tasks
