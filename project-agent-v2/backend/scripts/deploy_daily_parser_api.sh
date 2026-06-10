#!/bin/bash
# 远程AI服务器日报解析API部署脚本
# 包含：向量检索 + LLM生成

set -e

echo "=== 部署日报解析API（远程AI服务器） ==="

# 创建服务目录
mkdir -p ~/daily-parser-api
cd ~/daily-parser-api

# 创建虚拟环境
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ 虚拟环境已创建"
fi

source venv/bin/activate

# 安装依赖
pip install fastapi uvicorn ollama chromadb pydantic -q
echo "✅ 依赖已安装"

# 创建API服务代码
cat > parser_api.py << 'PYEOF'
"""
远程AI服务器日报解析API
功能：向量检索 + LLM生成（一站式）
"""
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import ollama
import chromadb
from chromadb.config import Settings
import json
import logging
import time
import re

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Daily Parser API")

# 初始化ChromaDB客户端
try:
    chromadb_client = chromadb.HttpClient(
        host="127.0.0.1", 
        port=8000,
        settings=Settings(anonymized_telemetry=False)
    )
    collection = chromadb_client.get_collection("projects")
    logger.info(f"✅ ChromaDB连接成功，项目数: {collection.count()}")
except Exception as e:
    logger.error(f"❌ ChromaDB连接失败: {e}")
    collection = None

class ParseRequest(BaseModel):
    text: str
    report_date: str
    employee_id: str = ""
    employee_name: str = ""

class ParsedEntry(BaseModel):
    content: str
    matched_project_id: int
    matched_project_name: str
    matched_task_id: str = ""
    matched_task_name: str = ""
    start_time: str = "09:00"
    end_time: str = "13:00"
    hours: float = 4.0
    confidence: float = 0.9

class ParseResponse(BaseModel):
    success: bool
    entries: List[ParsedEntry]
    matched_projects: List[Dict[str, Any]]
    duration_ms: int

@app.post("/api/parse_daily", response_model=ParseResponse)
async def parse_daily(request: ParseRequest):
    """
    一站式日报解析：
    1. 本地向量检索（nomic-embed-text，毫秒级）
    2. ChromaDB查询（毫秒级）
    3. 关键词过滤
    4. 本地LLM生成（qwen3.5:35B）
    """
    start_time = time.time()
    
    # 1. 向量检索
    logger.info(f"[向量检索] 输入: {request.text[:30]}...")
    
    if not collection:
        return ParseResponse(
            success=False,
            entries=[],
            matched_projects=[],
            duration_ms=int((time.time() - start_time) * 1000)
        )
    
    # 计算嵌入向量
    try:
        embedding = ollama.embeddings(
            model="nomic-embed-text",
            prompt=request.text
        )["embedding"]
    except Exception as e:
        logger.error(f"嵌入计算失败: {e}")
        return ParseResponse(
            success=False,
            entries=[],
            matched_projects=[],
            duration_ms=int((time.time() - start_time) * 1000)
        )
    
    # ChromaDB查询
    results = collection.query(
        query_embeddings=[embedding],
        n_results=10
    )
    
    # 解析候选项目
    candidates = []
    for meta, dist in zip(results['metadatas'][0], results['distances'][0]):
        candidates.append({
            "id": meta['project_id'],
            "name": meta['project_name'],
            "leader": meta.get('leader', ''),
            "similarity": max(0, 1 - dist)
        })
    
    logger.info(f"[向量检索] 找到 {len(candidates)} 个候选项目")
    
    # 2. 关键词过滤
    location_keywords = []
    locations = ["隆林", "田林", "田阳", "靖锰", "百矿", "德保", "平果", "华磊"]
    for loc in locations:
        if loc in request.text:
            location_keywords.append(loc)
    
    if location_keywords:
        filtered = []
        for c in candidates:
            for loc in location_keywords:
                if loc in c['name']:
                    filtered.append(c)
                    break
        candidates = filtered if filtered else candidates[:6]
    
    logger.info(f"[关键词过滤] 过滤后: {len(candidates)} 个项目")
    
    # 3. LLM生成
    # 获取候选项目的任务列表
    projects_with_tasks = []
    for c in candidates[:6]:  # 最多6个项目
        projects_with_tasks.append({
            "id": c['id'],
            "name": c['name'],
            "tasks": []  # 简化版，不包含任务
        })
    
    # 构建提示词
    system_prompt = """你是一个专业的日报解析助手。请将用户输入的工作内容解析为结构化的日报条目。

输出格式要求：
- 必须返回纯JSON数组，不要任何其他文字
- 每个条目包含：content, matched_project_id, matched_project_name, start_time, end_time, hours, confidence
- 时间格式：HH:MM（如 09:00）
- 工时为数字（如 4.0）
- confidence 范围 0.0-1.0

示例输出：
[{"content":"完成项目调试","matched_project_id":20,"matched_project_name":"隆林铝厂空压机集中控制项目","start_time":"09:00","end_time":"13:00","hours":4.0,"confidence":0.95}]"""

    projects_json = json.dumps(projects_with_tasks, ensure_ascii=False, indent=2)
    
    user_prompt = f"""请解析以下日报内容：
{request.text}

候选项目列表：
{projects_json}

要求：
1. 匹配最相关的项目
2. 合理分配时间（默认从09:00开始）
3. 返回纯JSON数组，不要任何其他文字"""

    logger.info(f"[LLM生成] 开始调用 qwen3.5:35B...")
    llm_start = time.time()
    
    try:
        # 调用Ollama（本地）
        response = ollama.generate(
            model="qwen3.5:35B",
            prompt=f"{system_prompt}\n\n{user_prompt}",
            stream=False
        )
        
        llm_duration = (time.time() - llm_start) * 1000
        logger.info(f"[LLM生成] 耗时: {llm_duration:.0f}ms")
        
        # 解析结果
        raw_text = response.get('response', '[]')
        
        # 提取JSON
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if json_match:
            entries_data = json.loads(json_match.group())
        else:
            entries_data = []
        
        # 构造返回结果
        entries = []
        for e in entries_data:
            entries.append(ParsedEntry(
                content=e.get('content', request.text),
                matched_project_id=e.get('matched_project_id', candidates[0]['id'] if candidates else 0),
                matched_project_name=e.get('matched_project_name', candidates[0]['name'] if candidates else ''),
                matched_task_id=e.get('matched_task_id', ''),
                matched_task_name=e.get('matched_task_name', ''),
                start_time=e.get('start_time', '09:00'),
                end_time=e.get('end_time', '13:00'),
                hours=float(e.get('hours', 4.0)),
                confidence=float(e.get('confidence', 0.9))
            ))
        
        total_duration = int((time.time() - start_time) * 1000)
        logger.info(f"[完成] 总耗时: {total_duration}ms, 解析条目: {len(entries)}")
        
        return ParseResponse(
            success=True,
            entries=entries,
            matched_projects=candidates[:6],
            duration_ms=total_duration
        )
        
    except Exception as e:
        logger.error(f"[LLM生成] 失败: {e}")
        return ParseResponse(
            success=False,
            entries=[],
            matched_projects=candidates[:6],
            duration_ms=int((time.time() - start_time) * 1000)
        )

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "chromadb": "connected" if collection else "disconnected",
        "model": "qwen3.5:35B + nomic-embed-text"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
PYEOF

echo "✅ API服务代码已创建"

# 创建systemd服务
sudo tee /etc/systemd/system/daily-parser.service > /dev/null << 'SERVICE'
[Unit]
Description=Daily Parser API (Remote AI Server)
After=network.target

[Service]
Type=simple
User=aiadmin
WorkingDirectory=/home/aiadmin/daily-parser-api
ExecStart=/home/aiadmin/daily-parser-api/venv/bin/python parser_api.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

echo "✅ systemd服务已创建"

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable daily-parser
sudo systemctl start daily-parser

echo ""
echo "=== 部署完成 ==="
echo "API地址: http://127.0.0.1:8003"
echo "健康检查: http://127.0.0.1:8003/health"
echo ""
echo "测试命令:"
echo "curl http://127.0.0.1:8003/health"
echo "curl -X POST http://127.0.0.1:8003/api/parse_daily -H 'Content-Type: application/json' -d '{\"text\":\"完成隆林铝厂空压机项目调试工作4小时\",\"report_date\":\"2026-06-08\"}'"
