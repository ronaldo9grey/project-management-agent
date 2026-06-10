#!/usr/bin/env python3
"""
步骤2：在AI服务器导入数据到ChromaDB

用法：
    python3 import_to_chromadb.py
"""

import json
import chromadb
from chromadb.config import Settings
import httpx
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# 配置
CHROMADB_HOST = "127.0.0.1"
CHROMADB_PORT = 8000
COLLECTION_NAME = "projects"

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "bge-m3"


def get_embedding(text: str) -> list:
    """获取文本的embedding向量"""
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": OLLAMA_MODEL, "prompt": text}
            )
            if response.status_code == 200:
                return response.json().get("embedding", [])
    except Exception as e:
        logger.error(f"获取embedding失败: {e}")
    return []


def import_to_chromadb():
    """导入数据到ChromaDB"""
    
    # 读取数据文件
    with open("projects_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    logger.info(f"读取到 {len(data)} 个项目")
    
    # 连接ChromaDB
    client = chromadb.HttpClient(
        host=CHROMADB_HOST,
        port=CHROMADB_PORT,
        settings=Settings(anonymized_telemetry=False)
    )
    
    # 删除旧collection并重新创建（因为embedding维度变了）
    try:
        client.delete_collection(COLLECTION_NAME)
        logger.info("✓ 已删除旧collection")
    except:
        pass
    
    # 创建新collection（使用bge-m3的1024维）
    collection = client.create_collection(COLLECTION_NAME)
    logger.info("✓ 已创建新collection")
    
    # 清空旧数据（可选）
    # collection.delete(where={})
    
    for project in data:
        pid = project["id"]
        name = project["name"]
        leader = project.get("leader", "")
        tasks = project.get("tasks", [])
        
        logger.info(f"处理项目{pid}: {name} ({len(tasks)}个任务)")
        
        # 删除该项目的旧数据
        collection.delete(where={"project_id": str(pid)})
        
        # 添加项目信息
        proj_text = f"项目{pid}：{name}"
        if leader:
            proj_text += f"，负责人：{leader}"
        
        proj_embedding = get_embedding(proj_text)
        if proj_embedding:
            collection.add(
                ids=[f"proj_{pid}"],
                embeddings=[proj_embedding],
                documents=[proj_text],
                metadatas=[{
                    "type": "project",
                    "project_id": str(pid),
                    "project_name": name,
                    "leader": leader
                }]
            )
            logger.info(f"  ✓ 项目信息已添加")
        
        # 添加任务信息
        for task in tasks:
            task_id = task["task_id"]
            task_name = task["task_name"]
            task_level = task.get("task_level", 2)
            
            task_text = f"{name} - {task_name}"
            task_embedding = get_embedding(task_text)
            
            if task_embedding:
                collection.add(
                    ids=[f"task_{task_id}"],
                    embeddings=[task_embedding],
                    documents=[task_text],
                    metadatas=[{
                        "type": "task",
                        "project_id": str(pid),
                        "project_name": name,
                        "task_id": task_id,
                        "task_name": task_name,
                        "task_level": task_level
                    }]
                )
        
        logger.info(f"  ✓ 项目{pid}导入完成")
    
    # 统计结果
    final_count = collection.count()
    logger.info(f"\n✓ 导入完成，ChromaDB中共有 {final_count} 条记录")


if __name__ == "__main__":
    import_to_chromadb()
