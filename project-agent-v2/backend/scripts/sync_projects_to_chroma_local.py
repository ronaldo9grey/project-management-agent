#!/usr/bin/env python3
"""
项目数据同步到 ChromaDB（使用本地 ONNX 模型）

改进：
- 使用本地 all-MiniLM-L6-v2 模型（ONNX格式）
- 无需网络下载，无需远程API
- 嵌入计算毫秒级完成
"""

import os
import sys
import json
import time
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 设置离线模式
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

import numpy as np
from transformers import AutoTokenizer
import onnxruntime as ort

# 添加后端路径
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/project-agent-v2/backend')
from app.database import get_engine
from sqlalchemy import text

# ========== ONNX 嵌入模型封装 ==========

class LocalEmbeddingModel:
    """本地 ONNX 嵌入模型"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.session = ort.InferenceSession(f"{model_path}/model.onnx")
        logger.info(f"✅ ONNX模型加载成功: {model_path}")
        
    def encode(self, texts: list) -> np.ndarray:
        """计算嵌入向量"""
        # Tokenize
        inputs = self.tokenizer(
            texts, 
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
        
        outputs = self.session.run(None, input_dict)
        
        # 平均池化
        embeddings = outputs[0].mean(axis=1)
        
        return embeddings

# ========== 主流程 ==========

def main():
    logger.info("=" * 60)
    logger.info("项目数据同步到 ChromaDB（本地模型）")
    logger.info("=" * 60)
    
    # 1. 初始化本地嵌入模型
    model_path = '/home/ubuntu/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx'
    embed_model = LocalEmbeddingModel(model_path)
    
    # 2. 连接数据库
    engine = get_engine()
    logger.info("✅ 数据库连接成功")
    
    # 3. 获取所有项目
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, name, leader, status
            FROM projects
            WHERE is_deleted = false
            ORDER BY id
        """))
        
        projects = []
        for row in result:
            projects.append({
                'id': row[0],
                'name': row[1],
                'leader': row[2] or '',
                'status': row[3] or ''
            })
    
    logger.info(f"📊 找到 {len(projects)} 个项目")
    
    # 4. 连接 ChromaDB
    import chromadb
    from chromadb.config import Settings
    
    client = chromadb.HttpClient(
        host="127.0.0.1",
        port=8002,
        settings=Settings(anonymized_telemetry=False)
    )
    
    # 删除旧集合
    try:
        client.delete_collection("projects")
        logger.info("🗑️  已删除旧集合")
    except:
        pass
    
    # 创建新集合（使用余弦距离）
    collection = client.create_collection(
        name="projects",
        metadata={"hnsw:space": "cosine"}
    )
    logger.info("✅ 创建新集合（余弦距离）")
    
    # 5. 批量处理项目
    batch_size = 10
    for i in range(0, len(projects), batch_size):
        batch = projects[i:i+batch_size]
        
        # 准备数据
        ids = [f"proj_{p['id']}" for p in batch]
        metadatas = [{
            'project_id': p['id'],
            'project_name': p['name'],
            'leader': p['leader'],
            'status': p['status']
        } for p in batch]
        documents = [p['name'] for p in batch]
        
        # 计算嵌入
        start = time.time()
        embeddings = embed_model.encode(documents)
        duration = (time.time() - start) * 1000
        
        logger.info(f"嵌入计算耗时: {duration:.0f}ms ({len(batch)}个项目)")
        
        # 写入 ChromaDB
        collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            documents=documents
        )
        
        logger.info(f"✅ 已写入 {i+len(batch)}/{len(projects)} 个项目")
    
    # 6. 验证数据
    count = collection.count()
    logger.info(f"✅ ChromaDB 项目数: {count}")
    
    # 7. 测试检索
    logger.info("\n" + "=" * 60)
    logger.info("测试向量检索")
    logger.info("=" * 60)
    
    test_queries = [
        "隆林铝厂空压机",
        "田阳阳极组装",
        "Demo项目",
        "科研课题"
    ]
    
    for query in test_queries:
        start = time.time()
        embedding = embed_model.encode([query])[0]
        
        results = collection.query(
            query_embeddings=[embedding.tolist()],
            n_results=3
        )
        
        duration = (time.time() - start) * 1000
        logger.info(f"\n查询: '{query}' ({duration:.0f}ms)")
        
        for meta, dist in zip(results['metadatas'][0], results['distances'][0]):
            similarity = max(0, 1 - dist)
            logger.info(f"  [{meta['project_id']}] {meta['project_name'][:25]}... (相似度: {similarity:.2%})")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ 同步完成")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
