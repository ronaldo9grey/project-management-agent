"""
远程AI服务器日报解析API
架构：
- 14B模型：完整语义解析
- 7B模型：快速提取 + 后端正则拆分
"""
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple, Dict, Any, Tuple
import chromadb
from chromadb.config import Settings
import json
import logging
import httpx
import asyncio
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Daily Parser API")

# Ollama API 地址
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

# 初始化ChromaDB
try:
    client = chromadb.HttpClient(host="127.0.0.1", port=8000, settings=Settings(anonymized_telemetry=False))
    collection = client.get_collection("projects")  # 不指定embedding_function
    
    # 加载所有项目
    all_projects = {}
    results = collection.get()
    
    if results and results['metadatas']:
        for meta in results['metadatas']:
            if meta.get('type') == 'project':
                pid = meta.get('project_id')
                if pid:
                    all_projects[pid] = {
                        "id": pid,
                        "name": meta.get('project_name', meta.get('name', '')),
                        "leader": meta.get('leader', '')
                    }
    
    logger.info(f"✓ 加载 {len(all_projects)} 个项目")
except Exception as e:
    logger.error(f"ChromaDB失败: {e}")
    collection = None
    all_projects = {}

# 手动生成embedding（用于query）
def get_embedding_for_query(text: str) -> list:
    """使用Ollama bge-m3生成embedding"""
    import httpx
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                "http://127.0.0.1:11434/api/embeddings",
                json={"model": "bge-m3", "prompt": text}
            )
            if response.status_code == 200:
                return response.json().get("embedding", [])
    except Exception as e:
        logger.error(f"生成embedding失败: {e}")
    return []

# 项目别名映射（逐步补充）
PROJECT_ALIAS_MAP = {
    # 无歧义别名
    "落地锰": "落地锰转化锰锭项目",
    "电解锰渣": "电解锰渣无害化处理项目",
    "锰转化": "落地锰转化锰锭项目",
    # 三厂部空压机项目（区分厂区）
    "德保铝厂空压机": "德保铝厂空压机集中控制项目研究",
    "德保铝厂空压站": "德保铝厂空压机集中控制项目研究",
    "隆林铝厂空压机": "隆林铝厂空压机集中控制项目研究",
    "田林铝厂空压机": "田林铝厂空压机集中控制项目研究",
    "田阳铝厂空压机": "田阳铝厂空压机集中控制项目研究",
    # 田林铝厂中频炉项目（项目38新名称）
    "田林铝厂阳极组装中频炉": "田林铝厂阳极组装中频炉三电四炉循环水监控系统",
    "田林铝厂中频炉": "田林铝厂阳极组装中频炉三电四炉循环水监控系统",
    "三电四炉": "田林铝厂阳极组装中频炉三电四炉循环水监控系统",
    # 其他项目别名
    "隆林铝厂净化系统": "隆林铝厂净化系统自动化控制项目",
    "净化系统自动化": "隆林铝厂净化系统自动化控制项目",
    # 田阳铝厂阳极组装项目（区分两个项目）
    "阳极组装提质": "田阳铝厂阳极组装提质增效项目的技术研究",
    "阳极组装提质增效": "田阳铝厂阳极组装提质增效项目的技术研究",
    "田阳铝厂阳极组装提质": "田阳铝厂阳极组装提质增效项目的技术研究",
    "提质增效反馈会议": "田阳铝厂阳极组装提质增效项目的技术研究",
    "阳极组装新增": "田阳铝厂阳极组装新增抓斗料破碎系统",
    "抓斗破碎": "田阳铝厂阳极组装新增抓斗料破碎系统",
}

class ParseRequest(BaseModel):
    text: str
    report_date: str
    employee_id: str = ""
    employee_name: str = ""
    model: str = "qwen2.5:14b"

class ParsedEntry(BaseModel):
    content: str
    matched_project_id: Optional[int] = None  # 允许为None（未匹配）
    matched_project_name: str = ""
    matched_task_id: str = ""
    matched_task_name: str = ""
    start_time: str = "08:15"
    end_time: str = "18:00"
    hours: float = 8.0
    confidence: float = 0.9

class ParseResponse(BaseModel):
    success: bool
    entries: List[ParsedEntry]
    matched_projects: List[Dict[str, Any]]
    duration_ms: int
    model_used: str
    match_method: str = "hybrid"

# ==================== 14B模型解析（保留原逻辑）====================

PARSE_PROMPT_14B = '''你是日报解析助手。请从日报文本中提取工作条目，输出JSON格式。

## 规则

### 时间段规则（重要）
- 上午：08:15-12:00（3.75小时）
- 下午：13:45-18:00（4.25小时）
- 晚上/加班：18:00之后，时长从文本提取
- 如果用户写"上午8:15-12:00"，使用该具体时间
- **默认规则**：如果用户没有指定时间段，默认为全天工作时间（08:15-18:00，8小时）
- 标准工时总和不超过8小时（上午+下午）
- **必须填写**：每个条目都必须有start_time、end_time和hours，不能为空或0

### 序号拆分规则
- 输入中的"1.xxx，2.xxx"需要拆成多个条目
- 每个序号对应一个独立工作条目
- 同时间段内多个项目共享时间段（第一个条目记录工时，其他设为0）

### 项目名提取规则
- 提取完整项目名（包含厂区名称）
- 例如："隆林铝厂空压机项目"，而不是"空压机"
- 如果无法确定完整名，提取关键词即可（后端会匹配）
- 必须从文本中提取，不要臆造项目名

### 加班条目规则
- 加班条目的project_hint使用上一个条目的项目名（延续同一项目）
- 加班条目的start_time必须是"18:00"
- 加班条目的end_time根据时长计算，如"18:00"到"20:00"是2小时

### 工作内容提取规则
- 提取具体工作内容（去掉序号、时间段等）
- 内容要完整、简洁

## 输出格式

```json
{
  "entries": [
    {
      "content": "协调完成合同线上审批",
      "project_hint": "隆林铝厂除尘器布袋脉冲精准控制研究项目",
      "start_time": "08:15",
      "end_time": "12:00",
      "hours": 3.75
    }
  ]
}
```

---

请解析以下日报文本，只输出JSON，不要其他内容：

'''


# ==================== 7B模型解析（新增快速版）====================

PARSE_PROMPT_7B = '''从日报文本中提取工作条目，输出JSON。

规则：
1. 每个条目提取：content（工作内容）、project_hint（项目名关键词）
2. 不要拆分序号（后端会处理）
3. 同一项目的多段描述合并为一个条目
4. 项目名尽量完整（包含厂区名称）

输出格式：
{"entries":[{"content":"工作内容","project_hint":"项目名关键词"}]}

文本：
'''


def match_project_and_task(project_hint: str, full_content: str = "", report_date: str = "") -> Dict:
    """
    匹配项目和任务
    返回: {
        "project_id": int,
        "project_name": str,
        "task_id": str,
        "task_name": str,
        "match_method": str,
        "confidence": float
    }
    
    参数:
    - project_hint: 7B模型提取的项目名关键词
    - full_content: 完整工作内容文本（用于任务匹配）
    """
    
    result = {
        "project_id": None,  # 改为None，表示未匹配
        "project_name": "",
        "task_id": "",
        "task_name": "",
        "match_method": "unmatched",
        "confidence": 0.0
    }
    
    if not project_hint or project_hint.strip() == "":
        logger.warning(f"[项目未匹配] project_hint为空")
        return result
    
    # 过滤无效关键词
    project_hint = project_hint.strip()
    invalid_hints = ["无", "其他", "未知", "不明确", "n/a", "na", "临时", "领导交办"]
    if project_hint.lower() in [h.lower() for h in invalid_hints]:
        logger.warning(f"[项目未匹配] 无效关键词: {project_hint}")
        return result
    
    # 精确匹配要求最小长度（避免单字匹配）
    MIN_HINT_LENGTH = 2
    
    # 0. 清理project_hint
    hint_clean = project_hint.replace("项目", "").replace("工程", "").replace("研究", "").strip()
    
    # 1. 别名映射（正向匹配：project_hint包含完整alias）
    for alias, full_name in PROJECT_ALIAS_MAP.items():
        if alias in project_hint or alias in hint_clean:
            for pid, p in all_projects.items():
                if p['name'] == full_name:
                    logger.info(f"[别名映射-正向] {alias} → {full_name} (ID: {pid})")
                    result["project_id"] = pid
                    result["project_name"] = full_name
                    result["match_method"] = "alias_map"
                    result["confidence"] = 1.0
                    # 不return，继续尝试任务匹配
                    break
        
        # 反向匹配：alias包含project_hint的核心词（如厂区名）
        # 用于project_hint不完整的情况
        # 提取alias中的厂区名（去掉项目类型词）
        alias_core = alias.replace("空压机", "").replace("空压站", "").replace("电机", "").replace("除尘器", "").strip()
        if len(alias_core) >= 2 and (alias_core in project_hint or project_hint in alias_core):
            # 找到了厂区匹配，但有多个候选项目，记录下来
            # 后续用RAG精确匹配
            logger.info(f"[别名候选] {project_hint} → 别名:{alias} (候选项目: {full_name})")
            # 不直接返回，等RAG精确匹配
    
    # 2. 精确匹配项目（要求最小长度，且只匹配一个项目）
    alias_candidates = []  # 别名候选项目列表
    exact_candidates = []  # 精确匹配项目列表
    
    if len(project_hint) >= MIN_HINT_LENGTH:
        # 收集精确匹配的项目
        for pid, p in all_projects.items():
            if project_hint in p['name'] or p['name'] in project_hint:
                exact_candidates.append((pid, p['name']))
        
        # 检查是否有别名候选在这些精确匹配中
        matched_by_alias = False  # 标志：是否已通过别名匹配
        for alias, full_name in PROJECT_ALIAS_MAP.items():
            alias_core = alias.replace("空压机", "").replace("空压站", "").replace("电机", "").replace("除尘器", "").strip()
            if len(alias_core) >= 2 and alias_core in project_hint:
                # 找到别名核心词匹配，检查项目名是否在精确匹配列表中
                for pid, pname in exact_candidates:
                    if pname == full_name:
                        logger.info(f"[别名候选优先] {project_hint} → {full_name} (ID: {pid})")
                        result["project_id"] = pid
                        result["project_name"] = full_name
                        result["match_method"] = "alias_priority"
                        result["confidence"] = 1.0
                        matched_by_alias = True
                        break
                if matched_by_alias:
                    break
        
        # 如果已通过别名匹配，跳过后续匹配
        if not matched_by_alias:
            # 只有唯一匹配时才设置结果（不return）
            if len(exact_candidates) == 1:
                pid, pname = exact_candidates[0]
                logger.info(f"[精确匹配] {project_hint} → {pname} (ID: {pid})")
                result["project_id"] = pid
                result["project_name"] = pname
                result["match_method"] = "exact"
                result["confidence"] = 0.95
                # 不return，继续尝试任务匹配
            elif len(exact_candidates) > 1:
                # 多个匹配，用RAG精确匹配
                logger.info(f"[精确匹配-多个候选] {project_hint} → {len(exact_candidates)} 个项目，交给RAG匹配")
    
    # RAG匹配（只有未通过别名匹配时才执行）
    if result["project_id"] is None and collection:
        try:
            query_emb = get_embedding_for_query(project_hint)
            if query_emb:
                results = collection.query(query_embeddings=[query_emb], n_results=5)
            if results and results['distances'] and results['distances'][0]:
                for i, distance in enumerate(results['distances'][0]):
                    similarity = 1 - distance
                    if similarity > 0.7:  # 降低阈值，增加匹配率
                        meta = results['metadatas'][0][i]
                        doc = results['documents'][0][i]
                        
                        # 确保是项目或任务类型
                        if meta.get('type') not in ['project', 'task']:
                            continue
                        
                        if meta['type'] == 'project':
                            # 匹配到项目
                            pid = int(meta['project_id'])
                            logger.info(f"[RAG项目匹配] {project_hint} → {doc} (ID: {pid}, 相似度: {similarity:.2f})")
                            result["project_id"] = pid
                            result["project_name"] = doc
                            result["match_method"] = "rag_project"
                            result["confidence"] = similarity
                            # 不return，继续尝试任务匹配
                            break
                        
                        elif meta['type'] == 'task':
                            # 匹配到任务，同时返回项目和任务信息
                            pid = int(meta['project_id'])
                            task_id = meta['task_id']
                            task_name = meta['task_name']
                            logger.info(f"[RAG任务匹配] {project_hint} → 任务:{task_name} (项目ID: {pid}, 相似度: {similarity:.2f})")
                            
                            # 获取项目名
                            project_name = all_projects.get(pid, {}).get('name', "")
                            
                            result["project_id"] = pid
                            result["project_name"] = project_name
                            result["task_id"] = task_id
                            result["task_name"] = task_name
                            result["match_method"] = "rag_task"
                            result["confidence"] = similarity
                            return result
        except Exception as e:
            logger.warning(f"[RAG匹配失败] {e}")
    
    # 如果项目匹配成功，尝试任务匹配
    if result["project_id"] is not None and full_content and collection:
        try:
            # 只在该项目的任务中搜索
            logger.info(f"[任务匹配开始] 在项目{result['project_id']}中搜索任务")
            query_emb = get_embedding_for_query(full_content)
            if query_emb:
                task_results = collection.query(
                    query_embeddings=[query_emb],
                where={"$and": [{"project_id": result["project_id"]}, {"type": "task"}]},
                n_results=15  # 增加候选数量，便于月份过滤
            )
            
            if task_results and task_results['distances'] and task_results['distances'][0]:
                logger.info(f"[任务匹配结果] 找到 {len(task_results['distances'][0])} 个候选")
                
                # ⚠️ 新增：月份过滤（对于按月份分组的项目）
                # 提取report_date的月份
                report_month = None
                if report_date:
                    try:
                        from datetime import datetime
                        report_month = datetime.strptime(report_date, "%Y-%m-%d").month
                        logger.info(f"[月份过滤] 日报月份: {report_month}月")
                    except:
                        pass
                
                # 收集所有候选任务（用于关键词匹配验证 + 月份过滤）
                candidates = []
                for i, distance in enumerate(task_results['distances'][0][:10]):
                    similarity = 1 - distance
                    meta = task_results['metadatas'][0][i]
                    doc = task_results['documents'][0][i]
                    logger.info(f"  候选{i+1}: {doc} (similarity={similarity:.2f})")
                    
                    if similarity > 0.55:
                        task_name = meta.get('task_name', doc)
                        
                        # ⚠️ 月份过滤：从task_name提取月份
                        if report_month:
                            # 提取任务名中的月份（如"3. 2026年6月技术服务"中的"6月"）
                            month_match = re.search(r'[\.．]\s*2026年(\d+)月|(\d+)月', task_name)
                            if month_match:
                                task_month = int(month_match.group(1) or month_match.group(2))
                                if task_month != report_month:
                                    logger.info(f"    [月份过滤] 排除: {task_name} (任务月份{task_month} ≠ 日报月份{report_month})")
                                    continue
                            else:
                                # 无月份信息的任务，检查task_id前缀（如"26_3_V2"中的"3"表示6月任务）
                                task_id_prefix = meta.get('task_id', '').split('_')[1] if '_' in meta.get('task_id', '') else None
                                if task_id_prefix:
                                    # 项目26的任务前缀映射：1=4月, 2=5月, 3=6月, ...
                                    # 前缀 = 月份 - 3
                                    if result["project_id"] == 26:  # 特殊处理项目26
                                        expected_prefix = str(report_month - 3)  # 如6月 → 前缀3
                                        if task_id_prefix != expected_prefix:
                                            logger.info(f"    [月份过滤-ID] 排除: {task_name} (前缀{task_id_prefix} ≠ 预期{expected_prefix})")
                                            continue
                        
                        candidates.append({
                            "task_id": meta.get('task_id', ''),
                            "task_name": task_name,
                            "similarity": similarity
                        })
                
                # ⚠️ 关键词匹配验证（解决向量稀释问题）
                if candidates:
                    best_vector_task = candidates[0]
                    keyword_task = verify_task_with_keywords(full_content, candidates)
                    
                    if keyword_task and keyword_task["task_id"] != best_vector_task["task_id"]:
                        # 关键词匹配结果更好，使用关键词匹配
                        logger.info(f"[任务匹配纠正] 向量:{best_vector_task['task_name']} → 关键词:{keyword_task['task_name']}")
                        result["task_id"] = keyword_task["task_id"]
                        result["task_name"] = keyword_task["task_name"]
                        result["match_method"] = result["match_method"] + "+task_keyword"
                    else:
                        # 使用向量检索结果
                        result["task_id"] = best_vector_task["task_id"]
                        result["task_name"] = best_vector_task["task_name"]
                        result["match_method"] = result["match_method"] + "+task"
                    
                    logger.info(f"[任务匹配成功] {full_content} → 任务:{result['task_name']}")
            else:
                logger.warning(f"[任务匹配] 项目{result['project_id']}下无任务数据")
        except Exception as e:
            logger.warning(f"[任务匹配失败] {e}")
    
    if result["project_id"] is None:
        logger.warning(f"[项目未匹配] {project_hint} → 空项目")
    
    return result


def split_by_numbered_items(text: str) -> List[str]:
    """按序号拆分内容"""
    items = re.split(r'\d\.', text)
    result = []
    for item in items[1:]:
        item = item.strip().rstrip('，。、')
        if item and len(item) > 2:
            result.append(item)
    return result


def parse_time_periods(text: str) -> List[Dict]:
    """解析时间段（支持分号分隔）"""
    periods = []
    
    # 先尝试按分号分隔
    if "；" in text or ";" in text:
        parts = re.split(r'[;；]', text)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # 对每个部分递归解析
            sub_periods = parse_time_periods(part)
            periods.extend(sub_periods)
        return periods
    
    # 查找时间段关键词（合并"晚上"和"加班"）
    period_keywords = []
    i = 0
    while i < len(text):
        if text[i:i+2] == "晚上" and i+2 < len(text) and text[i+2:i+4] == "加班":
            period_keywords.append((i, "晚上加班"))
            i += 4
        elif text[i:i+2] in ["上午", "下午", "晚上"]:
            period_keywords.append((i, text[i:i+2]))
            i += 2
        elif text[i:i+2] == "加班":
            period_keywords.append((i, "加班"))
            i += 2
        else:
            i += 1
    
    if not period_keywords:
        return [{"period": "全天", "start": "08:15", "end": "18:00", "hours": 8.0, "text": text}]
    
    # 按位置切分
    for i, (pos, keyword) in enumerate(period_keywords):
        next_pos = period_keywords[i+1][0] if i+1 < len(period_keywords) else len(text)
        period_text = text[pos:next_pos].strip()
        
        if keyword == "上午":
            periods.append({"period": "上午", "start": "08:15", "end": "12:00", "hours": 3.75, "text": period_text})
        elif keyword == "下午":
            periods.append({"period": "下午", "start": "13:45", "end": "18:00", "hours": 4.25, "text": period_text})
        elif keyword in ["晚上", "加班", "晚上加班"]:
            # 提取加班时长
            hours_match = re.search(r'(\d+)\s*小时', period_text)
            hours = float(hours_match.group(1)) if hours_match else 2.0
            periods.append({"period": "加班", "start": "18:00", "end": f"{18 + int(hours)}:00", "hours": hours, "text": period_text})
    
    return periods


async def call_ollama(prompt: str, model: str) -> str:
    """调用Ollama API"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                OLLAMA_URL,
                json={"model": model, "prompt": prompt, "stream": False, "format": "json"}
            )
            return response.json().get("response", "")
    except Exception as e:
        logger.error(f"Ollama调用失败: {e}")
        return ""


# ==================== 14B解析（保留）====================

@app.post("/api/parse_daily", response_model=ParseResponse)
async def parse_daily(request: ParseRequest):
    """14B模型完整解析"""
    start_time = asyncio.get_event_loop().time()
    
    prompt = PARSE_PROMPT_14B + request.text
    response = await call_ollama(prompt, "qwen2.5:14b")
    
    if not response:
        return ParseResponse(success=False, entries=[], matched_projects=[], duration_ms=0, model_used="qwen2.5:14b")
    
    try:
        result = json.loads(response)
        entries = result.get("entries", [])
        
        # 补充默认值
        for entry in entries:
            if not entry.get("start_time"):
                entry["start_time"] = "08:15"
            if not entry.get("end_time"):
                entry["end_time"] = "18:00"
            if not entry.get("hours"):
                entry["hours"] = 8.0
        
        # 项目匹配
        final_entries = []
        matched_projects = []
        seen_ids = set()
        
        for entry in entries:
            match_result = match_project_and_task(entry.get("project_hint", ""), entry.get("content", ""), request.report_date)
            final_entries.append({
                "content": entry.get("content", ""),
                "matched_project_id": match_result["project_id"],
                "matched_project_name": match_result["project_name"],
                "matched_task_id": match_result["task_id"],
                "matched_task_name": match_result["task_name"],
                "start_time": entry.get("start_time", "08:15"),
                "end_time": entry.get("end_time", "18:00"),
                "hours": entry.get("hours", 8.0),
                "confidence": match_result["confidence"]
            })
            if match_result["project_id"] not in seen_ids:
                matched_projects.append({
                    "id": match_result["project_id"], 
                    "name": match_result["project_name"], 
                    "leader": all_projects.get(match_result["project_id"], {}).get('leader', '')
                })
                seen_ids.add(match_result["project_id"])
        
        duration = int((asyncio.get_event_loop().time() - request_start_time) * 1000)
        return ParseResponse(success=True, entries=[ParsedEntry(**e) for e in final_entries], matched_projects=matched_projects, duration_ms=duration, model_used="qwen2.5:14b", match_method="llm_14b")
    
    except Exception as e:
        logger.error(f"解析失败: {e}")
        return ParseResponse(success=False, entries=[], matched_projects=[], duration_ms=0, model_used="qwen2.5:14b")


# ==================== 7B快速解析（新增）====================

@app.post("/api/parse_daily_fast", response_model=ParseResponse)
async def parse_daily_fast(request: ParseRequest):
    """7B模型快速解析 + 后端正则拆分（智能聚合）"""
    request_start_time = asyncio.get_event_loop().time()  # 改名避免冲突
    
    # ===== 新增：智能聚合检测 =====
    # 检查是否需要拆分（改进：避免误判描述性时间词）
    # 时间段分隔符模式：句首或标点后的"上午/下午/晚上/加班"
    time_period_pattern = r'(^|[，。；\n])(上午|下午|晚上|加班)[：:]\s*'
    has_time_periods = bool(re.search(time_period_pattern, request.text))
    
    has_numbered_items = bool(re.search(r'\d\.', request.text))
    has_multiple_projects = sum(1 for alias in PROJECT_ALIAS_MAP.keys() if alias in request.text) > 1
    
    # 如果没有时间段分隔符、序号、多项目，则不拆分，直接解析为一条
    if not has_time_periods and not has_numbered_items and not has_multiple_projects:
        logger.info(f"[智能聚合] 检测到单一工作内容，不拆分")
        
        # ⚠️ 新增：提取时间段（优先使用用户输入的时间）
        work_start_time = "08:15"
        work_end_time = "18:00"
        work_hours = 8.0
        
        # 从输入文本提取时间段
        time_match = re.search(r'(\d{1,2}:\d{2})\s*[—–\-至到]\s*(\d{1,2}:\d{2})', request.text)
        if time_match:
            work_start_time = time_match.group(1)
            work_end_time = time_match.group(2)
            # 计算工时（扣除午休）
            try:
                from datetime import datetime, timedelta
                start_dt = datetime.strptime(work_start_time, "%H:%M")
                end_dt = datetime.strptime(work_end_time, "%H:%M")
                duration_minutes = (end_dt - start_dt).total_seconds() / 60
                
                # 扣除午休（12:00-13:45，105分钟）
                if start_dt.hour < 12 and end_dt.hour > 13 or (end_dt.hour == 13 and end_dt.minute >= 45):
                    duration_minutes -= 105
                
                work_hours = round(duration_minutes / 60, 2)
                work_hours = max(0, min(work_hours, 8))  # 上限8小时，下限0
                logger.info(f"[时间段提取] {work_start_time}-{work_end_time}, 工时: {work_hours}小时")
            except Exception as e:
                logger.warning(f"[时间段计算失败] {e}")
        
        # 让AI提取项目关键词并润色内容
        prompt = f"""从以下工作描述中提取：
1. 项目名称关键词（如"田阳铝厂阳极组装"）
2. 核心工作内容摘要（简洁明了，不超过50字）

工作描述：{request.text}

返回JSON格式：
{{"project_hint": "项目关键词", "content_summary": "核心工作摘要"}}
"""
        response = await call_ollama(prompt, "qwen2.5:7b")
        
        try:
            result = json.loads(response)
            project_hint = result.get("project_hint", "")
            content_summary = result.get("content_summary", request.text)
        except:
            project_hint = request.text[:20]
            content_summary = request.text
        
        # 匹配项目和任务（传入report_date用于月份过滤）
        match_result = match_project_and_task(project_hint, content_summary, request.report_date)
        
        final_entries = [{
            "content": content_summary if len(content_summary) < len(request.text) else request.text,
            "matched_project_id": match_result["project_id"],
            "matched_project_name": match_result["project_name"],
            "matched_task_id": match_result["task_id"],
            "matched_task_name": match_result["task_name"],
            "start_time": work_start_time,
            "end_time": work_end_time,
            "hours": work_hours,
            "confidence": match_result["confidence"]
        }]
        
        matched_projects = []
        if match_result["project_id"]:
            matched_projects.append({
                "id": match_result["project_id"],
                "name": match_result["project_name"],
                "leader": all_projects.get(match_result["project_id"], {}).get('leader', '')
            })
        
        duration = int((asyncio.get_event_loop().time() - request_start_time) * 1000)
        return ParseResponse(
            success=True, 
            entries=[ParsedEntry(**e) for e in final_entries], 
            matched_projects=matched_projects, 
            duration_ms=duration, 
            model_used="qwen2.5:7b", 
            match_method="smart_aggregate"
        )
    
    # ===== 原有拆分逻辑（多时间段/多项目场景）=====
    # 1. 后端正则拆分时间段和序号
    periods = parse_time_periods(request.text)
    
    all_items = []
    for period in periods:
        # 提取时间段内的内容
        content_text = re.sub(r'^(上午|下午|晚上|加班)', '', period["text"])
        content_text = re.sub(r'\d{1,2}:\d{2}\s*[-至到]\s*\d{1,2}:\d{2}', '', content_text)
        content_text = re.sub(r'\d+\s*小时', '', content_text).strip()
        
        # 加班时间段特殊处理：即使内容为空，也要创建条目
        if period["period"] == "加班":
            if not content_text:
                content_text = "加班工作"
            all_items.append({"content": content_text, "period": period})
            continue
        
        # 按序号拆分
        items = split_by_numbered_items(content_text)
        if items:
            for item in items:
                all_items.append({"content": item, "period": period})
        else:
            # 无序号，尝试按逗号拆分（处理多项目合并描述）
            if '，' in content_text or '。' in content_text:
                # 按逗号或句号拆分
                sub_items = re.split(r'[，。]', content_text)
                for sub_item in sub_items:
                    sub_item = sub_item.strip()
                    if sub_item and len(sub_item) > 5:  # 过滤太短的内容
                        all_items.append({"content": sub_item, "period": period})
            elif content_text:
                all_items.append({"content": content_text, "period": period})
    
    if not all_items:
        all_items.append({"content": request.text, "period": {"start": "08:15", "end": "18:00", "hours": 8.0}})
    
    # 2. 7B提取项目名（批量）
    prompt = PARSE_PROMPT_7B + "\n".join([f"{i+1}. {item['content']}" for i, item in enumerate(all_items)])
    response = await call_ollama(prompt, "qwen2.5:7b")
    
    # 3. 解析结果（增强容错性）
    try:
        result = json.loads(response)
        llm_entries = result.get("entries", [])
    except json.JSONDecodeError:
        # JSON解析失败，使用后端兜底逻辑
        logger.warning(f"[JSON解析失败] 使用后端兜底逻辑")
        llm_entries = []
    
    # 确保条目数与all_items匹配
    while len(llm_entries) < len(all_items):
        llm_entries.append({"content": "", "project_hint": ""})
    
    for i in range(len(all_items)):
        if i < len(llm_entries):
            llm_entries[i]["content"] = all_items[i]["content"]
        else:
            llm_entries[i] = {"content": all_items[i]["content"], "project_hint": ""}
    
    # 4. 项目匹配 + 时间分配（同时间段内只有第一个条目记录工时）
    final_entries = []
    matched_projects = []
    seen_ids = set()
    seen_periods = {}  # 记录已处理的时间段
    last_project = None  # 记录上一个项目
    
    for i, entry in enumerate(llm_entries):
        item = all_items[i] if i < len(all_items) else {"period": {"start": "08:15", "end": "18:00", "hours": 8.0}}
        period = item["period"]
        period_key = f"{period['start']}-{period['end']}"
        
        # 加班条目：独立匹配，不盲目继承
        if period.get("period") == "加班":
            # 先尝试匹配加班内容中的项目
            overtime_content = entry.get("content", "")
            overtime_match = match_project_and_task(entry.get("project_hint", ""), overtime_content, request.report_date)
            
            # 检查加班内容是否属于"其他事项"
            other_keywords = ["临时", "领导交办", "其他", "杂事", "日常", "非项目"]
            is_other_task = any(kw in overtime_content for kw in other_keywords)
            
            # 检查加班内容是否暗示"延续上一个项目"
            continue_keywords = ["继续", "延续", "接着", "补充"]
            is_continue_task = any(kw in overtime_content for kw in continue_keywords)
            
            if overtime_match["project_id"] is not None and not is_other_task:
                # 加班内容匹配到项目
                pid = overtime_match["project_id"]
                pname = overtime_match["project_name"]
                task_id = overtime_match["task_id"]
                task_name = overtime_match["task_name"]
                method = overtime_match["match_method"] + "+overtime"
                conf = overtime_match["confidence"]
            elif is_continue_task and last_project:
                # 加班内容暗示延续上一个项目
                pid, pname, task_id, task_name = last_project
                # 尝试在该项目中匹配任务
                if collection:
                    try:
                        query_emb = get_embedding_for_query(overtime_content)
                        if query_emb:
                            task_results = collection.query(
                                query_embeddings=[query_emb],
                            where={"$and": [{"project_id": pid}, {"type": "task"}]},
                            n_results=5
                        )
                        if task_results and task_results['distances'] and task_results['distances'][0]:
                            for i, distance in enumerate(task_results['distances'][0]):
                                similarity = 1 - distance
                                if similarity > 0.55:
                                    meta = task_results['metadatas'][0][i]
                                    doc = task_results['documents'][0][i]
                                    task_id = meta.get('task_id', '')
                                    task_name = meta.get('task_name', doc)
                                    logger.info(f"[加班任务匹配] {overtime_content} → {task_name}")
                                    break
                    except Exception as e:
                        logger.warning(f"[加班任务匹配失败] {e}")
                method = "overtime_continue"
                conf = 0.9
            else:
                # 加班内容不属于任何项目
                pid = None
                pname = ""
                task_id = ""
                task_name = ""
                method = "overtime_unmatched"
                conf = 0.0
        else:
            match_result = match_project_and_task(entry.get("project_hint", ""), entry.get("content", ""), request.report_date)
            pid = match_result["project_id"]
            pname = match_result["project_name"]
            task_id = match_result["task_id"]
            task_name = match_result["task_name"]
            method = match_result["match_method"]
            conf = match_result["confidence"]
            
            # 只有匹配成功才更新last_project
            if pid is not None:
                last_project = (pid, pname, task_id, task_name)
        
        # 工时分配：同时间段内只有第一个条目记录工时
        if period_key in seen_periods:
            hours = 0.0  # 同时间段内后续条目工时为0
        else:
            hours = period["hours"]
            seen_periods[period_key] = True
        
        final_entries.append({
            "content": entry.get("content", item["content"]),
            "matched_project_id": pid,
            "matched_project_name": pname,
            "matched_task_id": task_id,
            "matched_task_name": task_name,
            "start_time": period["start"],
            "end_time": period["end"],
            "hours": hours,
            "confidence": conf
        })
        
        # 只有匹配成功的项目才加入matched_projects
        if pid is not None and pid not in seen_ids:
            matched_projects.append({
                "id": pid, 
                "name": pname, 
                "leader": all_projects.get(pid, {}).get('leader', '')
            })
            seen_ids.add(pid)
    
    duration = int((asyncio.get_event_loop().time() - request_start_time) * 1000)
    return ParseResponse(success=True, entries=[ParsedEntry(**e) for e in final_entries], matched_projects=matched_projects, duration_ms=duration, model_used="qwen2.5:7b", match_method="regex_7b")


@app.get("/health")
async def health():
    return {"status": "ok", "projects": len(all_projects), "models": ["qwen2.5:7b", "qwen2.5:14b"]}


# ==================== 关键词匹配函数（解决向量稀释问题）====================

def extract_task_keywords(text: str, top_k: int = 5) -> List[str]:
    """
    提取关键词（jieba分词 + 词性过滤）
    
    解决向量稀释问题：长查询中非核心词汇干扰核心词汇匹配
    """
    try:
        import jieba.posseg as pseg
    except ImportError:
        logger.warning("jieba 未安装，使用简单关键词提取")
        return [w for w in text if len(w) >= 2][:top_k]
    
    # 工程领域停用词
    stopwords = {
        "完成", "进行", "工作", "任务", "项目", "工程", "系统",
        "相关", "等", "及", "和", "的", "了", "在", "到", "对",
        "开展", "组织", "编写", "整理", "准备", "处理", "跟进",
        # 地名
        "德保", "田阳", "隆林", "百色", "南宁"
    }
    
    words = pseg.cut(text)
    keywords = [
        word for word, flag in words
        if (flag.startswith('n') or flag.startswith('v'))  # 名词/动词
        and len(word) >= 2
        and word not in stopwords
    ]
    
    return keywords[:top_k]


def calculate_task_match_score(keywords: List[str], task_name: str, original_content: str) -> float:
    """
    计算匹配分数（加权策略）
    
    权重设计：
    - 关键词命中：+0.5分/词
    - 关键词在边界（开头/结尾）：+0.3分额外
    - 原有关键词表匹配：+0.3分
    - 完全包含：+0.8分
    """
    score = 0
    task_name_lower = task_name.lower()
    content_lower = original_content.lower()
    
    # 权重1：关键词命中
    for kw in keywords:
        if kw in task_name_lower:
            score += 0.5
            if task_name_lower.startswith(kw) or task_name_lower.endswith(kw):
                score += 0.3
    
    # 权重2：原有关键词表匹配
    legacy_keywords = ["图纸", "审查", "设计", "招标", "采购", "施工", "勘察", "会议", "协调"]
    for kw in legacy_keywords:
        if kw in content_lower and kw in task_name_lower:
            score += 0.3
    
    # 权重3：完全包含
    if task_name_lower in content_lower:
        score += 0.8
    
    return min(score, 2.0)  # 上限2.0


def verify_task_with_keywords(content: str, candidates: List[Dict]) -> Optional[Dict]:
    """
    用关键词匹配验证向量检索结果是否最佳匹配
    
    返回：更匹配的任务（如果存在），否则返回None
    """
    if not candidates:
        return None
    
    # 提取关键词
    keywords = extract_task_keywords(content)
    
    # 计算每个候选任务的关键词匹配得分
    scored_candidates = []
    for candidate in candidates:
        task_name = candidate.get("task_name", "")
        score = calculate_task_match_score(keywords, task_name, content)
        scored_candidates.append({
            "task_id": candidate["task_id"],
            "task_name": task_name,
            "keyword_score": score,
            "vector_similarity": candidate.get("similarity", 0)
        })
    
    # 按关键词得分排序
    scored_candidates.sort(key=lambda x: x["keyword_score"], reverse=True)
    
    # 如果关键词得分最高的任务明显优于向量检索结果（得分差 > 0.5）
    if scored_candidates and scored_candidates[0]["keyword_score"] > 0.5:
        best_keyword_task = scored_candidates[0]
        # 比较关键词得分和向量相似度
        # 如果关键词得分 >= 1.0（强匹配），优先使用
        if best_keyword_task["keyword_score"] >= 1.0:
            return best_keyword_task
    
    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)# 修复版本: 2026-06-10 15:02 - 全部修复完成
