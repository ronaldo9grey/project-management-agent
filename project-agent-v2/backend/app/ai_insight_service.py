# AI洞察服务 - 规则生成 + 本地模型润色

import httpx
import json
import re
from datetime import date, datetime
from typing import Optional, Dict, Any
from .database import get_connection
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


async def polish_insight_with_local_model(raw_insight: str, period: str = "morning") -> str:
    """
    使用本地模型润色洞察内容
    
    参数：
    - raw_insight: 规则生成的原始洞察
    - period: "morning" 或 "noon"，用于调整语气
    
    返回：润色后的洞察内容
    """
    # 根据时段调整提示词
    time_context = "早安" if period == "morning" else "午安"
    time_style = "精力充沛、积极向上" if period == "morning" else "稳重、务实"
    
    system_prompt = f"""你是一个资深项目管理专家，擅长从数据中发现问题、预判风险、提出行动建议。

当前任务：对项目洞察数据进行**深度分析**，而非简单润色。

分析要求：
1. ⚠️ 必须保留"分析范围"部分，说明本次只分析已上传计划的项目
2. **深度解读**：
   - 从数据中发现潜在问题（如：进度与成本的关系、延期风险传导）
   - 预判下一步可能出现的风险
   - 提出具体可执行的行动建议
3. **数据缺失提醒**：如果发现数据异常（如成本为0、进度异常），明确提醒用户更新
4. 保持数据准确，不修改数字
5. 语言简洁专业，用emoji增强可读性
6. 开头用"{time_context}！"问候（不超过10个字），⚠️ 只输出一次问候
7. 风格：{time_style}
8. 总长度控制在400字以内
9. ⚠️ 不要重复输出内容，每个部分只输出一次

输出格式：直接输出分析后的内容，不要有任何解释或标记。

示例（供参考深度分析方向）：
原始："进度36.8%，无延期"
分析："进度平稳但需关注：1) 若持续低速推进可能导致后期赶工；2) 建议本周检查关键路径任务资源是否充足"
"""

    user_prompt = f"请润色以下项目洞察：\n\n{raw_insight}"
    
    try:
        # 调用本地Ollama（增加超时到180秒，因为frpc穿透慢）
        url = "http://127.0.0.1:8001/api/generate"
        
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        logger.info(f"[AI洞察润色] 调用本地模型，时段: {period}")
        
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                url,
                json={
                    "model": "qwen3.5:35B",
                    "prompt": full_prompt,
                    "stream": False
                }
            )
        
        if response.status_code != 200:
            logger.error(f"[AI洞察润色] 本地模型调用失败: {response.status_code}")
            return raw_insight  # 失败时返回原始内容
        
        result = response.json()
        polished = result.get("response", "").strip()
        
        if not polished:
            logger.warning("[AI洞察润色] 返回内容为空")
            return raw_insight
        
        # 去重处理：检测并去除重复内容
        lines = polished.split('\n')
        unique_lines = []
        seen_content = set()
        
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and line_stripped not in seen_content:
                unique_lines.append(line)
                seen_content.add(line_stripped)
        
        polished = '\n'.join(unique_lines)
        
        # 添加生成时间标记
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M")
        polished_with_time = f"🕐 生成时间：{time_str}\n\n{polished}"
        
        logger.info(f"[AI洞察润色] 成功，原始长度: {len(raw_insight)}, 润色后长度: {len(polished)}")
        return polished_with_time
        
    except httpx.ConnectError:
        logger.error("[AI洞察润色] 本地模型服务不可用")
        # 返回原始内容时也添加时间标记
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M")
        return f"🕐 生成时间：{time_str}\n\n{raw_insight}"
    except httpx.ReadTimeout:
        logger.error("[AI洞察润色] 本地模型超时")
        # 返回原始内容时也添加时间标记
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M")
        return f"🕐 生成时间：{time_str}\n\n{raw_insight}"
    except Exception as e:
        logger.error(f"[AI洞察润色] 异常: {e}")
        # 返回原始内容时也添加时间标记
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M")
        return f"🕐 生成时间：{time_str}\n\n{raw_insight}"


def generate_raw_insight() -> str:
    """
    生成原始洞察（规则模板）
    
    ⚠️ 只分析已上传计划的项目（有 project_plan_versions 记录）
    其他项目采用标准化模板管理，不在分析范围
    
    返回：规则生成的洞察内容
    """
    logger.info("[AI洞察] 开始规则生成")
    
    with get_connection() as conn:
        # ========== 分析范围说明 ==========
        # 只统计有实际任务数据的项目（上传了计划且有任务）
        tracked_projects = conn.execute(text("""
            SELECT p.id, p.name, p.status, p.progress, COUNT(pt.task_id) as task_count
            FROM projects p
            JOIN project_plan_versions ppv ON p.id = ppv.project_id
            JOIN project_tasks pt ON pt.plan_version_id = ppv.id AND pt.is_deleted = false
            WHERE p.is_deleted = false
            GROUP BY p.id, p.name, p.status, p.progress
            HAVING COUNT(pt.task_id) > 0
            ORDER BY task_count DESC
        """)).fetchall()
        
        tracked_count = len(tracked_projects)
        tracked_ids = [p[0] for p in tracked_projects]
        
        # 其他项目数（无任务数据或采用标准化模板）
        other_count = conn.execute(text("""
            SELECT COUNT(*) FROM projects 
            WHERE is_deleted = false 
            AND id NOT IN (
                SELECT DISTINCT p.id
                FROM projects p
                JOIN project_plan_versions ppv ON p.id = ppv.project_id
                JOIN project_tasks pt ON pt.plan_version_id = ppv.id AND pt.is_deleted = false
                WHERE p.is_deleted = false
            )
        """)).fetchone()[0]
        
        # ========== 获取已更新计划项目进度统计 ==========
        if tracked_count > 0:
            # 动态计算每个项目的进度（只计算一级任务task_level=1）
            project_progress = conn.execute(text("""
                SELECT 
                    p.id,
                    p.name,
                    p.status,
                    AVG(pt.progress) as avg_task_progress
                FROM projects p
                JOIN project_plan_versions ppv ON p.id = ppv.project_id
                JOIN project_tasks pt ON pt.plan_version_id = ppv.id 
                    AND pt.is_deleted = false 
                    AND pt.task_level = 1
                WHERE p.is_deleted = false
                AND p.id = ANY(:ids)
                GROUP BY p.id, p.name, p.status
            """), {"ids": tracked_ids}).fetchall()
            
            # 计算统计值
            total = len(project_progress)
            ongoing = sum(1 for p in project_progress if p[2] == '进行中')
            completed = sum(1 for p in project_progress if p[2] == '已完成')
            # 只统计进行中项目的平均进度
            ongoing_projects = [p for p in project_progress if p[2] == '进行中']
            avg_progress = sum(float(p[3] or 0) for p in ongoing_projects) / len(ongoing_projects) if ongoing_projects else 0
            
            progress_stats = [total, ongoing, completed, avg_progress, 0]  # low_progress暂时设为0，后面用延期和滞后代替
        
        else:
            # 如果没有更新过计划的项目
            progress_stats = [0, 0, 0, 0, 0]
            ongoing_projects = []
        
        # 获取风险统计（只统计已更新计划的项目）
        if tracked_count > 0:
            risk_stats = conn.execute(text("""
                SELECT 
                    COUNT(*) FILTER (WHERE pa.severity = 'high' AND NOT pa.is_resolved) as high,
                    COUNT(*) FILTER (WHERE pa.severity = 'medium' AND NOT pa.is_resolved) as medium,
                    COUNT(*) FILTER (WHERE pa.severity = 'low' AND NOT pa.is_resolved) as low
                FROM project_alerts pa
                WHERE pa.project_id = ANY(:ids)
                AND pa.created_at >= CURRENT_DATE - INTERVAL '7 days'
            """), {"ids": tracked_ids}).fetchone()
        
        else:
            risk_stats = [0, 0, 0]
        
        # 获取成本统计（只统计已更新计划的项目）
        if tracked_count > 0:
            cost_stats = conn.execute(text("""
                SELECT 
                    SUM(budget_total_cost) as total_budget,
                    SUM(actual_total_cost) as total_actual,
                    COUNT(*) FILTER (WHERE actual_total_cost > budget_total_cost * 1.1) as overspent
                FROM projects 
                WHERE is_deleted = false 
                AND id = ANY(:ids)
            """), {"ids": tracked_ids}).fetchone()
        
        else:
            cost_stats = [0, 0, 0]
        
        # ========== 延期和滞后判断（基于里程碑视角）==========
        delayed_projects = []  # 延期项目（有任务已过截止日期未完成）
        today = date.today()
        
        if tracked_count > 0:
            # 获取任务数据（兼容平铺和层级结构）
            tasks_data = conn.execute(text("""
                SELECT 
                    p.id as project_id,
                    p.name as project_name,
                    pt.task_id,
                    pt.task_name,
                    pt.task_level,
                    pt.parent_task_id,
                    pt.status,
                    pt.progress,
                    pt.end_date
                FROM projects p
                JOIN project_plan_versions ppv ON p.id = ppv.project_id
                JOIN project_tasks pt ON pt.plan_version_id = ppv.id 
                    AND pt.is_deleted = false
                WHERE p.is_deleted = false 
                AND p.status = '进行中'
                AND p.id = ANY(:ids)
                ORDER BY p.id, pt.end_date
            """), {"ids": tracked_ids}).fetchall()
            
            # 按项目分组
            project_map = {}
            for row in tasks_data:
                proj_id = row[0]
                if proj_id not in project_map:
                    project_map[proj_id] = {
                        "name": row[1],
                        "tasks": [],
                        "delayed_tasks": []
                    }
                
                task_data = {
                    "task_id": row[2],
                    "task_name": row[3],
                    "task_level": row[4],
                    "parent_task_id": row[5],
                    "status": row[6],
                    "progress": float(row[7] or 0),
                    "end_date": row[8]
                }
                project_map[proj_id]["tasks"].append(task_data)
                
                # 检查任务是否延期（已过截止时间且未完成）
                if task_data["end_date"] and task_data["end_date"] < today:
                    if task_data["progress"] < 100:
                        project_map[proj_id]["delayed_tasks"].append(task_data)
            
            # 整理延期项目列表
            for proj_id, proj_data in project_map.items():
                if proj_data["delayed_tasks"]:
                    delayed_projects.append({
                        "name": proj_data["name"],
                        "delayed_tasks": proj_data["delayed_tasks"]
                    })
            
            # 获取高成本超支项目
            overspent_projects = conn.execute(text("""
                SELECT name, 
                       (actual_total_cost - budget_total_cost) as overspent,
                       (actual_total_cost / NULLIF(budget_total_cost, 0) * 100) as overspent_pct
                FROM projects 
                WHERE is_deleted = false 
                AND actual_total_cost > budget_total_cost * 1.1
                AND id = ANY(:ids)
                ORDER BY overspent_pct DESC
                LIMIT 3
            """), {"ids": tracked_ids}).fetchall()
            
            # 获取已开始的进行中项目数
            started_projects_count = conn.execute(text("""
                SELECT COUNT(*) FROM projects 
                WHERE is_deleted = false 
                AND status = '进行中' 
                AND start_date <= CURRENT_DATE
                AND id = ANY(:ids)
            """), {"ids": tracked_ids}).fetchone()
        
        else:
            delayed_projects = []
            lagging_projects = []
            overspent_projects = []
            started_projects_count = [0]
    
    # 构建分析结果
    total = progress_stats[0] or 0
    ongoing = progress_stats[1] or 0
    completed = progress_stats[2] or 0
    avg_progress = float(progress_stats[3] or 0)
    
    high_risk = risk_stats[0] or 0
    medium_risk = risk_stats[1] or 0
    
    total_budget = float(cost_stats[0] or 0)
    total_actual = float(cost_stats[1] or 0)
    overspent = cost_stats[2] or 0
    started_count = started_projects_count[0] if started_projects_count else 0
    
    # 生成洞察内容
    lines = []
    
    # ========== 分析范围说明 ==========
    if tracked_count > 0:
        lines.append(f"📋 【分析范围】本次分析 {tracked_count} 个已上传详细计划的项目（有任务数据）")
        lines.append(f"   📌 其他 {other_count} 个项目采用标准化模板或暂无计划数据，不在分析范围")
    else:
        lines.append("📋 【分析范围】暂无项目上传详细计划")
        lines.append("   📌 请上传计划文件以启用智能追踪分析")
    lines.append("")
    
    # 项目进度分析（改进表达）
    if completed > 0:
        lines.append(f"📊 【项目进度】进行中 {ongoing} 个，已完成 {completed} 个，平均进度 {avg_progress:.1f}%")
    else:
        lines.append(f"📊 【项目进度】进行中 {ongoing} 个，暂无已完成项目，平均进度 {avg_progress:.1f}%")
    
    # 延期项目分析（任务已过截止日期未完成）
    if delayed_projects:
        lines.append(f"   🚨 延期任务 {sum(len(p['delayed_tasks']) for p in delayed_projects)} 个，涉及 {len(delayed_projects)} 个项目：")
        for p in delayed_projects[:3]:  # 只显示前3个项目
            for task in p["delayed_tasks"][:2]:  # 每个项目只显示前2个任务
                days_delayed = (today - task["end_date"]).days if task["end_date"] else 0
                lines.append(f"      • {p['name']}: {task['task_name']}（延期{days_delayed}天，进度{task['progress']:.0f}%）")
    else:
        lines.append("   ✅ 所有任务均未过期（里程碑正常）")
    
    lines.append("")
    
    # 风险预警分析
    lines.append(f"🚨 【风险预警】高风险 {high_risk} 个，中风险 {medium_risk} 个")
    if high_risk > 0:
        lines.append("   ⚠️ 存在高风险预警，建议立即处理")
    else:
        lines.append("   ✅ 暂无高风险预警")
    
    lines.append("")
    
    # 成本支出分析（增加数据缺失提醒）
    if total_budget > 0:
        cost_rate = (total_actual / total_budget * 100)
        lines.append(f"💰 【成本支出】预算 ¥{total_budget/10000:.1f}万，实际支出 ¥{total_actual/10000:.1f}万（{cost_rate:.1f}%）")
        
        if total_actual == 0:
            if started_count > 0:
                lines.append("   ⚠️ 有进行中项目但无成本记录，请及时更新成本数据")
            else:
                lines.append("   📊 暂无成本支出，项目可能处于筹备阶段")
        elif overspent > 0:
            lines.append(f"   ⚠️ {overspent} 个项目超支10%以上")
            if overspent_projects:
                lines.append(f"   📌 超支项目：{', '.join([f'{p[0]}(+{(p[2] or 0)-100:.0f}%)' for p in overspent_projects])}")
        elif cost_rate < 50:
            lines.append("   ✅ 成本支出低于预算50%")
        else:
            lines.append("   ✅ 成本控制良好")
    else:
        if started_count > 0:
            lines.append(f"💰 【成本支出】暂无预算数据")
            lines.append("   ⚠️ 有进行中项目但无成本记录，请及时更新成本数据")
        else:
            lines.append(f"💰 【成本支出】总支出 ¥{total_actual/10000:.1f}万")
    
    lines.append("")
    
    # 总结建议
    lines.append("💡 【建议】")
    if delayed_projects or high_risk > 0:
        if delayed_projects:
            lines.append("   🚨 优先处理延期任务，协调资源加快推进")
        if high_risk > 0:
            lines.append("   📌 及时处理高风险预警，降低项目风险")
    else:
        lines.append("   各项目关键里程碑正常，继续保持")
    
    if overspent > 0:
        lines.append("   加强成本管控，防止进一步超支")
    
    return "\n".join(lines)


async def generate_ai_insight_with_polish(period: str = "morning") -> Dict[str, Any]:
    """
    生成洞察并润色
    
    参数：
    - period: "morning" 或 "noon"
    
    返回：{
        "raw": "原始洞察",
        "polished": "润色后洞察",
        "period": "morning/noon",
        "generated_at": "生成时间"
    }
    """
    logger.info(f"[AI洞察] 开始生成，时段: {period}")
    
    # 1. 规则生成原始洞察
    raw_insight = generate_raw_insight()
    logger.info(f"[AI洞察] 规则生成完成，长度: {len(raw_insight)}")
    
    # 2. 本地模型润色
    polished_insight = await polish_insight_with_local_model(raw_insight, period)
    
    return {
        "raw": raw_insight,
        "polished": polished_insight,
        "period": period,
        "generated_at": datetime.now().isoformat()
    }


def save_insight_to_db(insight_data: Dict[str, Any]) -> int:
    """
    保存洞察到数据库
    
    返回：插入的记录ID
    """
    with get_connection() as conn:
        result = conn.execute(text("""
            INSERT INTO ai_insights (insight_date, period, content, raw_content, created_at)
            VALUES (:date, :period, :content, :raw_content, NOW())
            RETURNING id
        """), {
            "date": date.today(),
            "period": insight_data["period"],
            "content": insight_data["polished"],
            "raw_content": insight_data["raw"]
        })
        conn.commit()
        return result.fetchone()[0]


def get_latest_insight_from_db(period: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    从数据库获取最新洞察
    
    参数：
    - period: 可选，指定时段 "morning" 或 "noon"
    
    返回：洞察数据或None
    """
    with get_connection() as conn:
        if period:
            result = conn.execute(text("""
                SELECT id, insight_date, period, content, raw_content, created_at
                FROM ai_insights
                WHERE insight_date = :today AND period = :period
                ORDER BY created_at DESC
                LIMIT 1
            """), {"today": date.today(), "period": period}).fetchone()
        else:
            # 获取今天最新的洞察
            result = conn.execute(text("""
                SELECT id, insight_date, period, content, raw_content, created_at
                FROM ai_insights
                WHERE insight_date = :today
                ORDER BY created_at DESC
                LIMIT 1
            """), {"today": date.today()}).fetchone()
        
        if result:
            return {
                "id": result[0],
                "date": result[1],
                "period": result[2],
                "content": result[3],
                "raw_content": result[4],
                "created_at": result[5]
            }
        return None