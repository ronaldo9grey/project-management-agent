"""
任务自动关联和状态管理模块
"""
import os
import json
import re
import asyncio
from datetime import date, datetime
from typing import Optional, Dict, List, Tuple, Any, Callable
from concurrent.futures import ThreadPoolExecutor

try:
    from .config import settings
except ImportError:
    # 当直接导入时使用绝对导入
    from config import settings

from functools import wraps

try:
    from .database import get_engine, text
    from .logger import ai_logger
    from .work_time_config import calculate_work_hours
except ImportError:
    # 当直接导入时使用绝对导入
    from database import get_engine, text
    from logger import ai_logger
    from work_time_config import calculate_work_hours

import httpx


def fix_json_string(json_str: str) -> str:
    """
    修复 AI 返回的 JSON 格式错误
    常见问题：缺少逗号分隔符、浮点数格式错误
    """
    import re
    
    # 尝试直接解析，如果成功则不需要修复
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass
    
    fixed = json_str
    
    # 修复策略：在换行后缺少逗号的情况
    # 模式：值后面换行，然后是下一个键，缺少逗号
    # 例如："content": "xxx"\n      "project" → "content": "xxx",\n      "project"
    
    # 1. 字符串值后缺少逗号："\n      " → ",\n      "
    fixed = re.sub(r'"\s*\n(\s*)"', r'",\n\1"', fixed)
    
    # 2. 数字值后缺少逗号（包括浮点数）：\d(.?\d*)\n      " → \d(.?\d*),\n      "
    fixed = re.sub(r'(\d(?:\.\d+)?)\s*\n(\s*)"', r'\1,\n\2"', fixed)
    
    # 3. 布尔值后缺少逗号：true/false\n → true/false,\n
    fixed = re.sub(r'(true|false|null)\s*\n(\s*)"', r'\1,\n\2"', fixed, flags=re.IGNORECASE)
    
    # 4. 对象结束符后缺少逗号：}\n      { → },\n      {
    fixed = re.sub(r'\}\s*\n(\s*)\{', r'},\n\1{', fixed)
    
    # 5. 对象结束符后缺少逗号（数组中）：}\n      { 或 }\n      "
    fixed = re.sub(r'\}\s*\n(\s*)("|\{)', r'},\n\1\2', fixed)
    
    # 6. 数组结束符后缺少逗号：]\n      { → ],\n      {
    fixed = re.sub(r'\]\s*\n(\s*)\{', r'],\n\1{', fixed)
    
    # 7. 数组结束符后缺少逗号：]\n      " → ],\n      "
    fixed = re.sub(r'\]\s*\n(\s*)"', r'],\n\1"', fixed)
    
    # 8. 尝试处理更复杂的换行情况（多行空格）
    fixed = re.sub(r'"\s+\n\s+"', r'",\n"', fixed)
    fixed = re.sub(r'(\d)\s+\n\s+"', r'\1,\n"', fixed)
    
    # 9. 处理数组中对象的逗号问题
    # },\n      { 可能被误写为 }\n      {
    # 已在规则4处理，但加强一下
    fixed = re.sub(r'\}\s*\n\s*\{', r'},\n{', fixed)
    
    return fixed


# AI 调用专用线程池（最多5个并发AI请求）
AI_EXECUTOR = ThreadPoolExecutor(max_workers=5, thread_name_prefix="ai_worker")



def run_sync_ai_in_thread(func: Callable) -> Callable:
    """
    装饰器：将同步AI调用函数包装为异步函数，在线程池中执行。
    
    用法：
        @run_sync_ai_in_thread
        def my_ai_call(text: str) -> Dict:
            # 同步AI调用
            return result
        
        # 调用时使用 await
        result = await my_ai_call(text)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(AI_EXECUTOR, func, *args, **kwargs)
    return wrapper


def run_in_thread(sync_func: Callable, *args, **kwargs) -> Any:
    """
    通用函数：在线程池中执行同步函数。
    
    用法：
        result = await run_in_thread(my_sync_ai_call, arg1, arg2, kwarg1=value)
    """
    loop = asyncio.get_event_loop()
    # 使用 lambda 传递 kwargs
    if kwargs:
        return loop.run_in_executor(AI_EXECUTOR, lambda: sync_func(*args, **kwargs))
    return loop.run_in_executor(AI_EXECUTOR, sync_func, *args)


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


def _match_task_by_content_ai_sync(work_content: str, project_id: int, project_name: str = None) -> Optional[Dict[str, str]]:
    """
    同步版：使用 AI 推理分析匹配任务（在线程池中执行）
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
        # 使用同步 httpx 客户端（线程安全）
        url = f"{settings.AI_BASE_URL}/chat/completions"
        ai_logger.debug(f"调用 DeepSeek API (线程池): {url}")
        
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.AI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.AI_MODEL,
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


async def match_task_by_content_ai(work_content: str, project_id: int, project_name: str = None) -> Optional[Dict[str, str]]:
    """异步接口：在线程池中执行AI任务匹配"""
    return await run_in_thread(_match_task_by_content_ai_sync, work_content, project_id, project_name)


def _batch_match_tasks_ai_sync(
    work_items: List[Dict[str, Any]],
    project_id: int,
    project_name: str = None
) -> Dict[int, Optional[Dict[str, str]]]:
    """
    同步版：批量匹配任务（在线程池中执行）
    """
    if not work_items:
        return {}
    
    tasks = get_latest_version_tasks(project_id)
    if not tasks:
        return {item["index"]: None for item in work_items}
    
    # 构建任务列表
    task_list = "\n".join([
        f"- {t['task_id']}: {t['task_name']} (状态: {t['status']}, 进度: {t['progress']}%)"
        for t in tasks
    ])
    
    # 构建工作事项列表
    work_list = "\n".join([
        f"[{item['index']}] {item['content']}"
        for item in work_items
    ])
    
    # 构建提示词
    prompt = f"""你是一个项目管理助手，需要批量匹配日报工作内容到项目任务。

项目：{project_name or f'项目{project_id}'}

项目任务列表：
{task_list}

日报工作事项：
{work_list}

请为每条工作事项匹配任务。要求：
1. 理解工作内容的语义，考虑任务上下文
2. 如果明显属于某个任务，返回任务ID和名称
3. 如果无法确定，返回 null

只返回 JSON 数组格式：
[
  {{"index": 0, "task_id": "P35V2T2", "task_name": "需求调研"}},
  {{"index": 1, "task_id": null}},
  {{"index": 2, "task_id": "P35V2T6", "task_name": "前端开发"}}
]

不要返回任何解释，只返回 JSON 数组。"""

    try:
        url = f"{settings.AI_BASE_URL}/chat/completions"
        ai_logger.debug(f"批量匹配调用 DeepSeek API (线程池): {len(work_items)} 条工作事项")
        
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.AI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是一个精确的任务匹配助手，只返回 JSON 数组格式结果。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # 解析 JSON 数组
                json_match = re.search(r'\[[\s\S]*\]', content)
                if json_match:
                    data_list = json.loads(json_match.group())
                    
                    # 验证并构建结果
                    task_dict = {t["task_id"]: t["task_name"] for t in tasks}
                    results = {}
                    
                    for item in data_list:
                        index = item.get("index")
                        task_id = item.get("task_id")
                        task_name = item.get("task_name")
                        
                        if task_id and task_id in task_dict:
                            if not task_name:
                                task_name = task_dict[task_id]
                            results[index] = {"task_id": task_id, "task_name": task_name}
                            ai_logger.info(f"批量匹配成功: [{index}] '{work_items[index]['content'][:30]}' -> {task_id}")
                        else:
                            results[index] = None
                    
                    # 补充缺失的索引
                    for item in work_items:
                        if item["index"] not in results:
                            results[item["index"]] = None
                    
                    return results
            
            ai_logger.error(f"批量匹配失败: {response.status_code}")
            return {item["index"]: None for item in work_items}
            
    except Exception as e:
        ai_logger.exception(f"批量任务匹配异常: {e}")
        return {item["index"]: None for item in work_items}


async def batch_match_tasks_ai(
    work_items: List[Dict[str, Any]],
    project_id: int,
    project_name: str = None
) -> Dict[int, Optional[Dict[str, str]]]:
    """异步接口：在线程池中执行批量AI任务匹配"""
    return await run_in_thread(_batch_match_tasks_ai_sync, work_items, project_id, project_name)


# 缓存：项目任务列表（5分钟过期）
_task_cache: Dict[int, Tuple[List[Dict], float]] = {}

def get_latest_version_tasks_cached(project_id: int, ttl_seconds: int = 300) -> List[Dict]:
    """
    获取项目任务列表（带缓存）
    
    默认缓存 5 分钟，减少数据库查询
    """
    import time
    current_time = time.time()
    
    if project_id in _task_cache:
        tasks, expire_time = _task_cache[project_id]
        if current_time < expire_time:
            return tasks
    
    # 缓存过期或不存在，重新获取
    tasks = get_latest_version_tasks(project_id)
    _task_cache[project_id] = (tasks, current_time + ttl_seconds)
    return tasks


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


# =====================================================================
# 一次 AI 调用完成日报解析（项目+任务+时间）
# =====================================================================

OTHER_WORK_PROJECT_ID = 36  # "其他工作"项目ID


def get_all_projects_with_tasks() -> List[Dict]:
    """
    获取所有项目及其最新版本任务列表
    
    返回：[{"id": 17, "name": "xxx", "tasks": [{"id": "xxx", "name": "xxx"}, ...]}, ...]
    """
    engine = get_db_engine()
    
    with engine.connect() as conn:
        # 获取所有未删除的项目
        projects_result = conn.execute(text("""
            SELECT id, name, leader
            FROM projects
            WHERE is_deleted = false
            ORDER BY id
        """))
        
        projects = []
        for row in projects_result:
            project_id = row[0]
            project_name = row[1]
            
            # 获取该项目最新版本的任务
            tasks = get_latest_version_tasks(project_id)
            
            projects.append({
                "id": project_id,
                "name": project_name,
                "tasks": tasks
            })
        
        return projects


async def search_projects_by_vector(user_input: str, all_projects: list, top_k: int = 10) -> list:
    """
    向量检索：本地嵌入计算 + 远程ChromaDB查询
    
    改进：
    - 嵌入计算：本地ONNX模型（毫秒级）
    - ChromaDB查询：远程frpc穿透（秒级）
    - 总耗时：约1秒（vs 之前36秒）
    """
    import os
    import numpy as np
    from transformers import AutoTokenizer
    import onnxruntime as ort
    import chromadb
    
    try:
        # 1. 本地嵌入计算（ONNX模型）
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        
        model_path = '/home/ubuntu/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx'
        
        ai_logger.info(f"[向量检索] 本地嵌入计算: {user_input[:30]}...")
        
        # 加载 tokenizer（首次加载会缓存）
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        
        # 加载 ONNX 模型（单例模式，避免重复加载）
        if not hasattr(search_projects_by_vector, '_onnx_session'):
            search_projects_by_vector._onnx_session = ort.InferenceSession(
                f"{model_path}/model.onnx"
            )
        session = search_projects_by_vector._onnx_session
        
        # Tokenize
        inputs = tokenizer(
            user_input,
            return_tensors='pt',
            padding=True,
            truncation=True,
            max_length=512
        )
        
        # ONNX 推理
        input_dict = {
            'input_ids': inputs['input_ids'].numpy(),
            'attention_mask': inputs['attention_mask'].numpy(),
            'token_type_ids': inputs.get('token_type_ids', inputs['input_ids'] * 0).numpy()
        }
        
        outputs = session.run(None, input_dict)
        embedding = outputs[0].mean(axis=1)[0].tolist()  # 平均池化
        
        ai_logger.info(f"[向量检索] 嵌入维度: {len(embedding)}")
        
        # 2. 查询远程ChromaDB（frpc穿透）
        chromadb_client = chromadb.HttpClient(host="127.0.0.1", port=8002)
        collection = chromadb_client.get_collection("projects")
        
        results = collection.query(
            query_embeddings=[embedding],
            n_results=top_k
        )
        
        # 3. 解析结果
        candidates = []
        for meta, dist in zip(
            results['metadatas'][0],
            results['distances'][0]
        ):
            # 从all_projects查找完整信息
            project_info = None
            for p in all_projects:
                if p['id'] == meta['project_id']:
                    project_info = p.copy()
                    project_info['similarity'] = max(0, 1 - dist)
                    break
            
            if project_info:
                candidates.append(project_info)
            else:
                # 如果找不到完整信息，构造一个基本结构
                candidates.append({
                    "id": meta['project_id'],
                    "name": meta['project_name'],
                    "tasks": []  # 必须有tasks字段
                })
        
        ai_logger.info(f"[向量检索] 找到 {len(candidates)} 个候选项目")
        
        return candidates
        
    except Exception as e:
        ai_logger.error(f"[向量检索] 异常: {e}")
        return []


def filter_projects_hybrid(user_input: str, projects: list, vector_candidates: list = None) -> list:
    """
    混合检索：向量检索 + 关键词过滤
    
    策略：
    1. 如果有向量候选，进行关键词精确过滤
    2. 如果无向量候选，回退到纯关键词匹配
    """
    # 提取地名关键词
    location_keywords = []
    locations = ["隆林", "田林", "田阳", "靖锰", "百矿", "德保", "平果", "华磊"]
    for loc in locations:
        if loc in user_input:
            location_keywords.append(loc)
    
    # 如果有向量候选，进行关键词过滤
    if vector_candidates:
        if location_keywords:
            # 地名精确过滤
            filtered = []
            for candidate in vector_candidates:
                name = candidate.get('name', '')
                for loc in location_keywords:
                    if loc in name:
                        filtered.append(candidate)
                        break
            
            if filtered:
                ai_logger.info(f"[混合检索] 地名过滤后: {len(filtered)} 个项目")
                return filtered[:12]
        
        # 无地名关键词，返回向量检索结果
        ai_logger.info(f"[混合检索] 使用向量检索结果: {len(vector_candidates)} 个项目")
        return vector_candidates[:12]
    
    # 向量检索失败，回退到关键词匹配
    ai_logger.info(f"[混合检索] 向量检索失败，回退关键词匹配")
    return filter_projects_by_keywords(user_input, projects)


def filter_projects_by_keywords(user_input: str, projects: list) -> list:
    """
    智能关键词匹配，筛选相关项目
    
    改进点：
    1. 动态提取项目名关键词（不依赖硬编码）
    2. 模糊匹配（支持简称）
    3. 语义相似度（简单的词频匹配）
    """
    import re
    
    # 1. 提取用户输入中的项目名关键词
    # 常见的项目名关键词模式
    user_keywords = set()
    
    # 从用户输入中提取可能的地点/项目名
    location_patterns = ["隆林", "田林", "田阳", "靖锰", "百矿", "德保", "平果", "华磊"]
    for loc in location_patterns:
        if loc in user_input:
            user_keywords.add(loc)
    
    # 从项目名中提取动态关键词（去掉常见词）
    project_keywords = set()
    common_words = {"项目", "工程", "系统", "改造", "建设", "安装", "调试", "改造项目", "建设工程"}
    
    for p in projects:
        name = p["name"]
        # 提取项目名中的关键词（去掉常见词）
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', name)  # 提取2字以上中文词
        for word in words:
            if word not in common_words and len(word) >= 2:
                project_keywords.add(word)
    
    # 2. 匹配逻辑
    matched = []
    
    # 先尝试精确匹配项目名
    for p in projects:
        name = p["name"]
        # 项目名中包含用户输入的关键词
        for kw in user_keywords:
            if kw in name:
                matched.append(p)
                break
    
    # 如果精确匹配结果太少，尝试模糊匹配
    if len(matched) < 3:
        # 提取用户输入中的所有可能的中文词组
        user_words = set(re.findall(r'[\u4e00-\u9fa5]{2,}', user_input))
        
        for p in projects:
            if p in matched:
                continue
            name = p["name"]
            # 项目名包含用户输入的任一词组
            for word in user_words:
                if word in name and len(word) >= 2:
                    matched.append(p)
                    break
    
    # 3. 如果仍然没有匹配，返回全部项目（不限制，保证识别度）
    if not matched:
        ai_logger.info(f"[预筛选] 未匹配关键词，返回全部项目")
        return projects  # 返回全部，由LLM处理
    
    ai_logger.info(f"[预筛选] {len(projects)}个项目 → 筛选出{len(matched)}个")
    return matched[:12]  # 匹配成功时限制12个


async def parse_daily_all_in_one(
    user_input: str,
    report_date: str = None
) -> Dict:
    """
    一次 AI 调用完成日报解析：项目匹配 + 任务匹配 + 时间计算
    
    参数：
    - user_input: 用户输入的日报文本
    - report_date: 日报日期（可选）
    
    返回：标准化的 JSON 结构
    """
    # 获取所有项目和任务
    all_projects = get_all_projects_with_tasks()
    
    # 预筛选可能匹配的项目，减少AI输入token
    projects = filter_projects_by_keywords(user_input, all_projects)
    
    # 构建项目任务列表文本
    project_list_text = []
    for p in projects:
        task_lines = []
        for t in p["tasks"]:
            task_lines.append(f"    - {t['task_id']}: {t['task_name']}")
        
        project_list_text.append(f"""【项目{p['id']}】{p['name']}
{chr(10).join(task_lines) if task_lines else '    (无任务)'}""")
    
    projects_context = "\n\n".join(project_list_text)
    
    # 构建系统提示词
    system_prompt = """你是一个日报解析助手，需要从用户输入中提取工作事项，并匹配项目、任务、计算工时。

## ⚠️ 核心规则：标准工作日 = 8小时
- 上午：08:15 - 12:00（3.75小时）
- 下午：13:45 - 18:00（4.25小时）
- 午休：12:00 - 13:45（不计入工时）
- **一天工作时间上限 = 8小时**
- 用户写 "8:15-18:30" 这种超出工作时间段的，按 8 小时计算
- 只有明确标注"加班"的才计算加班工时

## 时间计算规则
1. 跨午休时段，需扣除1.75小时（12:00-13:45）
2. 计算结果上限为 8 小时
3. 只有明确提到"额外X小时"、"加班X小时"、"晚上X小时"的，才计算加班
4. 只有"上午"或"下午"而无具体时间的，默认4小时
5. 无时间信息的，默认4小时

## ⚠️ 重要：同一时段多件事的处理方式
用户可能在同一时间段内完成多件事，常见格式：
- "8:15-18:30 1.xxx, 2.xxx, 3.xxx"
- "下午协调完成（1）xxx（2）xxx"

**处理规则**：
- **⚠️ 每个事项的 hours 必须设为 0！**
- 只需记录时间段（start/end）即可
- 用户的意思是："在这个时间段内完成了这些工作"
- 系统会自动计算总工时并合并展示
- 例：8:15-18:30干了7件事 → 每个事项 hours=0，时间 8:15-18:30

## 匹配规则
1. 根据工作内容语义匹配项目（理解上下文）
2. 在匹配的项目下匹配任务
3. 如果明确不属于任何项目，设置为 null（系统会归类为"其他工作"）
4. 如果属于某项目但无法匹配具体任务，task 设为 null
5. 根据时间表述计算工时

## 输出格式
严格返回 JSON，不要有任何额外文字"""

    # 构建用户提示词
    user_prompt = f"""## 项目任务列表

{projects_context}

## 用户日报内容

{user_input}

请解析并返回 JSON 格式：
{{
  "success": true,
  "entries": [
    {{
      "index": 0,
      "content": "工作内容描述",
      "project": {{"id": 17, "name": "项目名称"}} 或 null,
      "task": {{"id": "任务ID", "name": "任务名称"}} 或 null,
      "time": {{
        "start": "08:30",
        "end": "12:00",
        "hours": 3.5,
        "is_overtime": false
      }},
      "confidence": 0.95
    }}
  ],
  "warnings": []
}}

注意：
- 如果匹配不到项目，project 设为 null
- 如果匹配到项目但匹配不到任务，task 设为 null
- confidence 表示匹配置信度（0-1）"""

    try:
        url = f"{settings.AI_BASE_URL}/chat/completions"
        ai_logger.info(f"一次性解析日报，项目数: {len(projects)}, 输入长度: {len(user_input)}")
        
        # 最多重试2次
        max_retries = 2
        for retry in range(max_retries):
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {settings.AI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": settings.AI_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 2000,
                        # 关闭思考模式，避免 reasoning_content 干扰 JSON 输出
                        "thinking": {"type": "disabled"}
                    }
                )
            
            if response.status_code != 200:
                ai_logger.error(f"AI调用失败: {response.status_code} - {response.text[:200]}")
                if retry < max_retries - 1:
                    ai_logger.info(f"重试 {retry + 2}/{max_retries}")
                    continue
                return {
                    "success": False,
                    "entries": [],
                    "warnings": [f"AI解析失败: {response.status_code}"]
                }
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # 解析 JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if not json_match:
                ai_logger.error(f"AI返回格式错误: {content[:200]}")
                if retry < max_retries - 1:
                    ai_logger.info(f"重试 {retry + 2}/{max_retries}")
                    continue
                return {
                    "success": False,
                    "entries": [],
                    "warnings": ["AI返回格式错误"]
                }
            
            # 尝试解析，如果失败则尝试修复 JSON 格式
            raw_json = json_match.group()
            try:
                ai_result = json.loads(raw_json)
            except json.JSONDecodeError as e:
                ai_logger.warning(f"JSON解析失败，尝试修复: {e}")
                fixed_json = fix_json_string(raw_json)
                try:
                    ai_result = json.loads(fixed_json)
                    ai_logger.info("JSON修复成功")
                except json.JSONDecodeError as e2:
                    ai_logger.error(f"JSON修复后仍失败: {e2}")
                    ai_logger.error(f"原始JSON内容（前2000字符）: {raw_json[:2000]}")
                    if retry < max_retries - 1:
                        ai_logger.info(f"重试 {retry + 2}/{max_retries}")
                        continue
                    return {
                        "success": False,
                        "entries": [],
                        "warnings": [f"JSON格式错误，请重新输入或简化内容"]
                    }
            
            # 验证并修复结果
            validated_result = validate_ai_result(ai_result, all_projects)
            
            ai_logger.info(f"AI解析成功: {len(validated_result.get('entries', []))} 条工作事项")
            
            return validated_result
            
    except Exception as e:
        ai_logger.exception(f"日报解析异常: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "entries": [],
            "warnings": [f"解析异常: {str(e)}"]
        }


def parse_daily_all_in_one_sync(user_input: str, report_date: str = None) -> Dict:
    """
    parse_daily_all_in_one 的同步版本，运行在线程池中。
    每个线程创建独立的事件循环，避免与主事件循环冲突。
    """
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            parse_daily_all_in_one(user_input, report_date)
        )
        return result
    finally:
        loop.close()


async def parse_daily_all_in_one_threaded(user_input: str, report_date: str = None) -> Dict:
    """
    在线程池中执行 AI 解析，不阻塞主事件循环。
    
    关键改进：
    - AI 调用（6-30秒）在独立线程中执行
    - 主事件循环释放，可处理其他请求（登录、心跳等）
    - 最多5个并发 AI 请求
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        AI_EXECUTOR,
        parse_daily_all_in_one_sync,
        user_input,
        report_date
    )
    return result


def validate_ai_result(ai_result: Dict, projects: List[Dict]) -> Dict:
    """
    验证并修复 AI 返回结果
    """
    valid_project_ids = {p["id"] for p in projects}
    project_tasks = {p["id"]: {t["task_id"] for t in p["tasks"]} for p in projects}
    project_names = {p["id"]: p["name"] for p in projects}
    
    entries = ai_result.get("entries", [])
    warnings = ai_result.get("warnings", [])
    
    # ⚠️ 重要：先校正工时精度（处理同一时间段多件事的分摊问题）
    # 这样可以避免 AI 返回负工时时被单项校验覆盖
    entries = correct_hours_precision(entries)
    
    validated_entries = []
    
    for entry in entries:
        idx = entry.get("index", len(validated_entries))
        content = entry.get("content", "")
        project = entry.get("project")
        task = entry.get("task")
        time_info = entry.get("time")
        confidence = entry.get("confidence", 0.8)
        
        # 校验项目
        if project:
            pid = project.get("id")
            if pid not in valid_project_ids:
                warnings.append(f"第{idx+1}条: 项目ID {pid} 不存在")
                project = None
            else:
                # 修正项目名称
                project["name"] = project_names.get(pid, project.get("name"))
        
        # 校验任务
        if task and project:
            tid = task.get("id")
            pid = project.get("id")
            if tid not in project_tasks.get(pid, set()):
                warnings.append(f"第{idx+1}条: 任务 {tid} 不属于项目 {project.get('name')}")
                task = None
        
        # 校验工时（此时已校正过，只检查单项合理性）
        if time_info:
            hours = time_info.get("hours", 4.0)
            # ⚠️ 如果校正后仍有负值或超出范围，设为合理的均分值
            if hours < 0 or hours > 12:
                warnings.append(f"第{idx+1}条: 工时 {hours} 不合理，已设为默认值")
                # 使用默认均分值
                time_info["hours"] = round(8.0 / max(len(entries), 1), 2)
        else:
            # 默认时间
            time_info = {
                "start": None,
                "end": None,
                "hours": round(8.0 / max(len(entries), 1), 2),
                "is_overtime": False
            }
        
        # 低置信度提示
        if confidence < 0.6:
            warnings.append(f"第{idx+1}条: 匹配置信度较低 ({confidence:.0%})")
        
        validated_entries.append({
            "index": idx,
            "content": content,
            "project": project,
            "task": task,
            "time": time_info,
            "confidence": confidence
        })
    
    # 为未匹配项目的条目设置虚拟"其他工作"（project_id = null）
    for entry in validated_entries:
        if entry["project"] is None:
            entry["project"] = {"id": None, "name": "其他工作"}
    
    return {
        "success": ai_result.get("success", True),
        "entries": validated_entries,
        "warnings": warnings
    }


def correct_hours_precision(entries: List[Dict]) -> List[Dict]:
    """
    校正工时精度：同一时间段内的多项工作，确保工时总和正确
    
    例：上午8:15-12:00（3.75h）有2件事
    - AI返回每件1.87h，总和3.74h（误差0.01h）
    - 修正为1.87h + 1.88h = 3.75h
    """
    from collections import defaultdict
    import math
    
    # 按时间段分组
    time_groups = defaultdict(list)
    for entry in entries:
        time_info = entry.get("time", {})
        start = time_info.get("start")
        end = time_info.get("end")
        if start and end:
            key = (start, end)
            time_groups[key].append(entry)
    
    # 计算每个时间段的标准工时
    def calc_standard_hours(start: str, end: str) -> float:
        """
        计算时间段对应的标准工时
        
        规则：
        - 标准工作日：上午8:15-12:00（3.75h）+ 下午13:45-18:00（4.25h）= 8小时
        - 午休时间（12:00-13:45）不计入工时
        - **标准工时上限为 8 小时**，超出部分不计入（除非明确标记加班）
        - **⚠️ 默认开始时间：08:15**
          - 如果用户填写的开始时间早于08:15（如8:45写错成其他），默认从08:15开始
        """
        try:
            s_h, s_m = int(start[:2]), int(start[3:5])
            e_h, e_m = int(end[:2]), int(end[3:5])
            
            start_minutes = s_h * 60 + s_m
            end_minutes = e_h * 60 + e_m
            
            # ⚠️ 默认开始时间：08:15（495分钟）
            # 如果开始时间早于08:15，设为08:15
            standard_start = 8 * 60 + 15  # 495
            if start_minutes < standard_start:
                start_minutes = standard_start
            
            # 午休时间：12:00 - 13:45（105分钟）
            lunch_start = 12 * 60  # 720
            lunch_end = 13 * 60 + 45  # 825
            
            total_minutes = end_minutes - start_minutes
            
            # 如果跨越午休，扣除午休时间
            if start_minutes < lunch_start and end_minutes > lunch_end:
                total_minutes -= 105  # 扣除1小时45分
            elif start_minutes < lunch_start and end_minutes > lunch_start and end_minutes <= lunch_end:
                # 结束在午休期间
                total_minutes = lunch_start - start_minutes
            elif start_minutes >= lunch_start and start_minutes < lunch_end and end_minutes > lunch_end:
                # 开始于午休期间
                total_minutes = end_minutes - lunch_end
            
            hours = total_minutes / 60
            
            # ⚠️ 标准工作日上限为 8 小时
            # 超出部分不计入（除非明确标记为加班）
            hours = min(hours, 8.0)
            
            return round(hours, 2)
        except:
            return 4.0  # 默认
    
    # 处理同一时间段内的多件事
    for key, group in time_groups.items():
        if len(group) <= 1:
            continue
        
        start, end = key
        standard_hours = calc_standard_hours(start, end)
        
        # 检查是否有负值或零值
        has_negative = any(e["time"]["hours"] < 0 for e in group)
        has_zero = all(e["time"]["hours"] == 0 for e in group)
        
        if has_negative or has_zero:
            # 出现负值或全部为零时修正，均分为合理值
            if has_zero:
                ai_logger.info(f"工时修正: {start}-{end} 共{len(group)}项，hours=0，调整为均分 {standard_hours}h")
            else:
                ai_logger.warning(f"工时异常修正: {start}-{end} 共{len(group)}项，存在负值，调整为均分")
            
            # ⚠️ 精度修正：最后一条用减法，确保总和精确
            base_hours = standard_hours / len(group)
            allocated = 0.0
            for i, entry in enumerate(group):
                if i < len(group) - 1:
                    # 前面的条目用四舍五入
                    hours = round(base_hours, 2)
                    entry["time"]["hours"] = hours
                    allocated += hours
                else:
                    # 最后一条用减法，确保总和精确
                    entry["time"]["hours"] = round(standard_hours - allocated, 2)
        else:
            # 无负值且不全为零时，保留AI分配的工时，但设置一个标记
            # 让前端知道这些事项共享同一时间段
            for entry in group:
                if "time" not in entry:
                    entry["time"] = {}
                entry["time"]["shared_period"] = f"{start}-{end}"
                entry["time"]["period_total_hours"] = standard_hours
    
    return entries


# ========== 本地Ollama解析函数 ==========

async def parse_daily_all_in_one_local(
    user_input: str,
    report_date: str = None,
    employee_id: str = "",
    employee_name: str = ""
) -> Dict:
    """
    调用远程AI服务器完整API（一站式解析）- 使用35B模型
    
    改进：
    - 向量检索：远程本地计算（毫秒级）
    - LLM生成：远程本地计算（30-60秒）
    - 总耗时：约30-60秒（vs 之前超时）
    
    返回：
    - success: 是否成功
    - entries: 解析条目列表
    - matched_projects: 匹配的项目列表
    """
    import httpx
    
    try:
        # 调用远程完整API（35B模型）
        parser_url = "http://127.0.0.1:8003/api/parse_daily"
        
        ai_logger.info(f"[远程解析-35B] 调用远程API: {user_input[:30]}...")
        
        # 设置超时120秒（远程API包含LLM生成，可能需要更长时间）
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                parser_url,
                json={
                    "text": user_input,
                    "report_date": report_date,
                    "employee_id": employee_id,
                    "employee_name": employee_name
                }
            )
        
        if response.status_code != 200:
            ai_logger.error(f"[远程解析-35B] API调用失败: {response.status_code}")
            return {
                "success": False,
                "error": f"API调用失败: {response.status_code}",
                "entries": [],
                "matched_projects": []
            }
        
        result = response.json()
        
        ai_logger.info(f"[远程解析-35B] 成功，耗时: {result.get('duration_ms', 0)}ms，条目数: {len(result.get('entries', []))}")
        
        # 返回结果（转换为标准格式）
        return {
            "success": result.get("success", False),
            "entries": result.get("entries", []),
            "matched_projects": result.get("matched_projects", [])
        }
        
    except httpx.TimeoutException:
        ai_logger.error(f"[远程解析-35B] 超时")
        return {
            "success": False,
            "error": "远程解析超时",
            "entries": [],
            "matched_projects": []
        }
    except Exception as e:
        ai_logger.error(f"[远程解析-35B] 异常: {e}")
        return {
            "success": False,
            "error": str(e),
            "entries": [],
            "matched_projects": []
        }


# 项目别名映射表（用于项目匹配）
PROJECT_ALIAS_MAP = {
    "炭渣项目": 32,
    "炭渣试验": 32,
    "田阳铝厂电解质炭渣处理": 32,
    "锰渣无害化": 33,
    "锰渣专题": 33,
    "锰锭试制": 34,
    "锰锭": 34,
    "落地锰": 34,
    "落地锰转化锰锭": 34,
    "德保铝厂化锰筑炉": 34,
    "铁锭模": 34,
    "德保铝厂化锰铸锰锭": 34,
    "锰锭项目": 34,
    "田林铝厂供电整流": 19,
    "隆林铝厂除尘器": 18,
    "隆林铝厂空压机": 20,
    "田林铝厂空压机": 23,
    "德保铝厂空压机": 22,
    "田阳铝厂空压机": 21,
    "电解槽新烟管": 12,
    "新烟管": 12,
    "新烟管软连接": 12,
    "烟管软连接": 12,
    "600KA槽烟气": 12,
    "槽上部烟气": 12,
    "电解铝多功能天车抓斗": 14,
    "田林电解天车抓斗": 14,
    "天车抓斗改进": 14,
    "抓斗产业化": 14,
    "隆林铝厂整流系统": 24,
    "锰渣固化": 33,
}

# 任务关键词映射表（用于任务匹配）
TASK_KEYWORDS_MAP = {
    "图纸设计": ["设计", "CAD", "图纸", "绘图", "方案设计", "系统设计"],
    "图纸审查": ["审查", "审核", "图纸审查", "预算审查"],
    "招标": ["招标", "投标", "采购", "合同", "招标公告", "开标", "评标"],
    "技术任务书": ["技术任务书", "技术规格", "任务书"],
    "中标": ["中标", "中标通知"],
    "现场调试": ["调试", "现场", "安装调试", "联调"],
    "需求分析": ["需求", "调研", "需求分析", "需求调研"],
    "方案评审": ["评审", "方案评审", "评审会"],
    "技术交流": ["交流", "讨论", "会议", "技术交流"],
    "文档编制": ["文档", "编写", "编制", "说明书", "报告"],
}


async def parse_daily_with_7b(
    user_input: str,
    report_date: str = None,
    projects: List[Dict] = None
) -> Dict:
    """
    使用远程日报解析API（7B模型快速解析 + 后端正则拆分）
    
    特点：
    - 模型：qwen2.5:7b（端口8003）
    - 三级匹配：别名映射 → 精确匹配 → RAG匹配
    - 耗时：约1-4秒
    - 后端正则拆分序号、时间段识别
    
    返回：
    - success: 是否成功
    - entries: 解析条目列表
    - matched_projects: 匹配的项目列表
    """
    import httpx
    
    try:
        # 调用远程日报解析API（端口8003，7B快速解析）
        parser_url = "http://127.0.0.1:8003/api/parse_daily_fast"
        
        ai_logger.info(f"[7B快速解析] 开始解析: {user_input[:30]}...")
        
        # 设置超时30秒（7B模型推理较快）
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                parser_url,
                json={
                    "text": user_input,
                    "report_date": report_date,
                    "employee_id": "",
                    "employee_name": "",
                    "model": "qwen2.5:7b"
                }
            )
        
        if response.status_code != 200:
            ai_logger.error(f"[7B快速解析] API调用失败: {response.status_code}")
            return {
                "success": False,
                "error": f"Parser API失败: {response.status_code}",
                "entries": [],
                "matched_projects": []
            }
        
        result = response.json()
        
        # parser_api已经返回完整格式
        entries = result.get("entries", [])
        matched_projects = result.get("matched_projects", [])
        
        ai_logger.info(f"[7B快速解析] 成功，条目数: {len(entries)}，匹配项目: {len(matched_projects)}")
        
        return {
            "success": True,
            "entries": entries,
            "matched_projects": matched_projects
        }
        
    except httpx.TimeoutException:
        ai_logger.error(f"[7B快速解析] 超时")
        return {
            "success": False,
            "error": "14B模型解析超时",
            "entries": [],
            "matched_projects": []
        }
    except Exception as e:
        ai_logger.error(f"[7B快速解析] 异常: {e}")
        return {
            "success": False,
            "error": str(e),
            "entries": [],
            "matched_projects": []
        }


def parse_daily_all_in_one_local_sync(user_input: str, report_date: str = None) -> Dict:
    """同步版本（用于线程池）"""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(parse_daily_all_in_one_local(user_input, report_date))
        loop.close()
        return result
    except Exception as e:
        ai_logger.error(f"[本地解析-同步] 异常: {e}")
        return {
            "success": False,
            "entries": [],
            "warnings": [f"本地解析异常: {str(e)}"]
        }


async def parse_daily_all_in_one_local_threaded(user_input: str, report_date: str = None) -> Dict:
    """在线程池中执行本地解析"""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = await loop.run_in_executor(
            executor,
            parse_daily_all_in_one_local_sync,
            user_input,
            report_date
        )
    return result
