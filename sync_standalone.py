#!/usr/bin/env python3
"""
同步项目数据到ChromaDB向量库（AI服务器独立版）

用法：
    python3 sync_standalone.py [--project-id 38]
"""

import psycopg2
import chromadb
from chromadb.config import Settings
import httpx
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# 配置
DB_HOST = "127.0.0.1"  # 通过frpc穿透
DB_PORT = 5433
DB_NAME = "project_cost_tracking"
DB_USER = "yjydb"
DB_PASSWORD = "qv52A03xcxAQCoDglUJelm4Sb"

CHROMADB_HOST = "127.0.0.1"
CHROMADB_PORT = 8000
COLLECTION_NAME = "projects"

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "bge-m3"


def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


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


def sync_projects(project_id: int = None):
    """同步项目数据到ChromaDB"""
    
    # 连接数据库
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 连接ChromaDB
    client = chromadb.HttpClient(
        host=CHROMADB_HOST, 
        port=CHROMADB_PORT,
        settings=Settings(anonymized_telemetry=False)
    )
    
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except:
        collection = client.create_collection(COLLECTION_NAME)
    
    # 获取项目列表
    if project_id:
        cur.execute("""
            SELECT id, name, leader, status, progress
            FROM projects
            WHERE id = %s AND is_deleted = false
        """, (project_id,))
    else:
        cur.execute("""
            SELECT id, name, leader, status, progress
            FROM projects
            WHERE is_deleted = false
            ORDER BY id
        """)
    
    projects = cur.fetchall()
    logger.info(f"找到 {len(projects)} 个项目")
    
    for proj in projects:
        pid, name, leader, status, progress = proj
        logger.info(f"处理项目{pid}: {name}")
        
        # 删除旧数据
        collection.delete(where={"project_id": str(pid)})
        
        # 添加项目数据
        proj_text = f"项目{pid}：{name}"
        if leader:
            proj_text += f"，负责人：{leader}"
        if status:
            proj_text += f"，状态：{status}"
        
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
                    "leader": leader or ""
                }]
            )
            logger.info(f"  ✓ 项目信息已同步")
        
        # 获取任务的最新版本
        cur.execute("""
            SELECT pt.task_id, pt.task_name, pt.task_level
            FROM project_tasks pt
            JOIN project_plan_versions ppv ON pt.plan_version_id = ppv.id
            WHERE pt.project_id::integer = %s
            AND pt.is_deleted = false
            AND pt.is_latest = true
            ORDER BY pt.task_id
        """, (pid,))
        
        tasks = cur.fetchall()
        logger.info(f"  找到 {len(tasks)} 个任务")
        
        for task in tasks:
            task_id, task_name, task_level = task
            
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
        
        logger.info(f"  ✓ 项目{pid}同步完成（{len(tasks)}个任务）")
    
    cur.close()
    conn.close()
    
    # 统计结果
    final_count = collection.count()
    logger.info(f"✓ 同步完成，ChromaDB中共有 {final_count} 条记录")


if __name__ == "__main__":
    project_id = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.startswith("--project-id="):
            project_id = int(arg.split("=")[1])
        elif arg.isdigit():
            project_id = int(arg)
    
    if project_id:
        logger.info(f"只同步项目 {project_id}")
    else:
        logger.info("同步所有项目")
    
    sync_projects(project_id)
