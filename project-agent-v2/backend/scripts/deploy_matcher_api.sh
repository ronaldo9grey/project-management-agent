#!/bin/bash
# 项目匹配API服务部署脚本
# 在远程AI服务器（aiserver）上执行

set -e

echo "=== 部署项目匹配API服务 ==="

# 创建服务目录
mkdir -p ~/project-matcher
cd ~/project-matcher

# 创建虚拟环境
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ 虚拟环境已创建"
fi

source venv/bin/activate

# 安装依赖
pip install fastapi uvicorn ollama chromadb -q
echo "✅ 依赖已安装"

# 创建API服务代码
cat > matcher_api.py << 'PYEOF'
"""
项目匹配API服务
功能：嵌入计算 + ChromaDB查询 + 关键词过滤（一站式）
"""
from fastapi import FastAPI
from pydantic import BaseModel
import ollama
import chromadb
from typing import List, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Project Matcher API")

# 初始化ChromaDB客户端
try:
    chromadb_client = chromadb.HttpClient(host="127.0.0.1", port=8000)
    collection = chromadb_client.get_collection("projects")
    logger.info(f"✅ ChromaDB连接成功，项目数: {collection.count()}")
except Exception as e:
    logger.error(f"❌ ChromaDB连接失败: {e}")
    collection = None

class SearchRequest(BaseModel):
    text: str
    top_k: int = 10
    location_keywords: Optional[List[str]] = None

class ProjectResult(BaseModel):
    id: int
    name: str
    similarity: float
    leader: str = ""
    status: str = ""

@app.post("/api/search_and_match", response_model=List[ProjectResult])
async def search_and_match(request: SearchRequest):
    """
    一站式项目检索：
    1. 本地嵌入计算（nomic-embed-text，毫秒级）
    2. ChromaDB向量查询（毫秒级）
    3. 关键词过滤（地名精确匹配）
    """
    import time
    start = time.time()
    
    # 1. 嵌入计算（本地，毫秒级）
    try:
        embedding = ollama.embeddings(
            model="nomic-embed-text",
            prompt=request.text
        )["embedding"]
        logger.info(f"嵌入计算耗时: {(time.time()-start)*1000:.0f}ms")
    except Exception as e:
        logger.error(f"嵌入计算失败: {e}")
        return []
    
    # 2. ChromaDB查询（本地，毫秒级）
    if not collection:
        logger.error("ChromaDB未连接")
        return []
    
    results = collection.query(
        query_embeddings=[embedding],
        n_results=request.top_k
    )
    
    # 3. 解析结果
    candidates = []
    for meta, dist in zip(results['metadatas'][0], results['distances'][0]):
        similarity = max(0, 1 - dist)
        candidates.append({
            "id": meta['project_id'],
            "name": meta['project_name'],
            "similarity": round(similarity, 4),
            "leader": meta.get('leader', ''),
            "status": meta.get('status', '')
        })
    
    logger.info(f"ChromaDB查询耗时: {(time.time()-start)*1000:.0f}ms")
    
    # 4. 关键词过滤（如果有）
    if request.location_keywords:
        filtered = []
        for candidate in candidates:
            for kw in request.location_keywords:
                if kw in candidate['name']:
                    filtered.append(candidate)
                    break
        result = filtered if filtered else candidates[:5]
    else:
        result = candidates
    
    logger.info(f"总耗时: {(time.time()-start)*1000:.0f}ms, 返回{len(result)}个项目")
    return result

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": "nomic-embed-text",
        "dimension": 768,
        "chromadb": "connected" if collection else "disconnected"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
PYEOF

echo "✅ API服务代码已创建"

# 创建systemd服务
sudo tee /etc/systemd/system/project-matcher.service > /dev/null << 'SERVICE'
[Unit]
Description=Project Matcher API Service
After=network.target

[Service]
Type=simple
User=aiadmin
WorkingDirectory=/home/aiadmin/project-matcher
ExecStart=/home/aiadmin/project-matcher/venv/bin/python matcher_api.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

echo "✅ systemd服务已创建"

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable project-matcher
sudo systemctl start project-matcher

echo ""
echo "=== 部署完成 ==="
echo "API地址: http://127.0.0.1:8003"
echo "健康检查: http://127.0.0.1:8003/health"
echo ""
echo "测试命令:"
echo "curl http://127.0.0.1:8003/health"
echo "curl -X POST http://127.0.0.1:8003/api/search_and_match -H 'Content-Type: application/json' -d '{\"text\":\"隆林铝厂空压机\",\"top_k\":5}'"
