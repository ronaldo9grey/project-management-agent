#!/usr/bin/env python3
"""
同步项目数据到远程ChromaDB向量库

功能：
1. 从PostgreSQL读取所有项目和任务
2. 生成项目描述文本
3. 写入远程ChromaDB（通过frpc穿透）
4. 支持增量更新

用法：
    python sync_projects_to_chroma.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
from datetime import datetime
from typing import List, Dict, Any
import chromadb
from sqlalchemy import text

# 导入数据库连接
from app.database import get_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# ChromaDB连接配置（通过frpc穿透）
CHROMADB_HOST = "127.0.0.1"
CHROMADB_PORT = 8002
COLLECTION_NAME = "projects"


def get_all_projects_with_tasks() -> List[Dict[str, Any]]:
    """从数据库获取所有项目和任务"""
    with get_connection() as conn:
        result = conn.execute(text("""
            SELECT 
                p.id,
                p.name,
                p.leader,
                p.status,
                p.start_date,
                p.end_date,
                p.progress,
                json_agg(
                    json_build_object(
                        'task_id', pt.task_id,
                        'task_name', pt.task_name,
                        'task_level', pt.task_level
                    )
                ) FILTER (WHERE pt.task_id IS NOT NULL) as tasks
            FROM projects p
            LEFT JOIN project_plan_versions ppv ON p.id = ppv.project_id
            LEFT JOIN project_tasks pt ON pt.plan_version_id = ppv.id 
                AND pt.is_deleted = false 
                AND pt.task_level = 1
            WHERE p.is_deleted = false
            GROUP BY p.id
            ORDER BY p.id
        """))
        
        projects = []
        for row in result:
            project = {
                "id": row[0],
                "name": row[1],
                "leader": row[2],
                "status": row[3],
                "start_date": str(row[4]) if row[4] else "",
                "end_date": str(row[5]) if row[5] else "",
                "progress": float(row[6] or 0),
                "tasks": row[7] or []
            }
            projects.append(project)
        
        return projects


def generate_project_text(project: Dict[str, Any]) -> str:
    """生成项目的文本描述（用于向量化）"""
    parts = [f"项目{project['id']}：{project['name']}"]
    
    if project['leader']:
        parts.append(f"负责人：{project['leader']}")
    
    if project['status']:
        parts.append(f"状态：{project['status']}")
    
    if project['tasks']:
        task_names = [t['task_name'] for t in project['tasks'][:10]]  # 最多10个任务
        parts.append(f"任务：{', '.join(task_names)}")
    
    return "\n".join(parts)


def sync_to_chroma(projects: List[Dict[str, Any]]):
    """同步项目数据到ChromaDB"""
    logger.info(f"连接ChromaDB: {CHROMADB_HOST}:{CHROMADB_PORT}")
    
    # 连接远程ChromaDB
    client = chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
    
    # 检查连接
    try:
        heartbeat = client.heartbeat()
        logger.info(f"ChromaDB心跳: {heartbeat}")
    except Exception as e:
        logger.error(f"无法连接ChromaDB: {e}")
        raise
    
    # 删除旧集合（如果存在）
    try:
        client.delete_collection(COLLECTION_NAME)
        logger.info(f"已删除旧集合: {COLLECTION_NAME}")
    except:
        pass
    
    # 创建新集合
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "项目知识库"}
    )
    logger.info(f"已创建集合: {COLLECTION_NAME}")
    
    # 批量写入项目数据
    ids = []
    documents = []
    metadatas = []
    
    for project in projects:
        project_id = f"project_{project['id']}"
        project_text = generate_project_text(project)
        
        ids.append(project_id)
        documents.append(project_text)
        metadatas.append({
            "project_id": project['id'],
            "project_name": project['name'],
            "leader": project['leader'] or "",
            "status": project['status'] or "",
            "task_count": len(project['tasks'] or [])
        })
    
    # 分批写入（每批100个）
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i+batch_size]
        batch_docs = documents[i:i+batch_size]
        batch_metas = metadatas[i:i+batch_size]
        
        collection.add(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_metas
        )
        logger.info(f"已写入 {min(i+batch_size, len(ids))}/{len(ids)} 个项目")
    
    logger.info(f"✅ 同步完成，共写入 {len(ids)} 个项目")
    
    # 验证
    count = collection.count()
    logger.info(f"集合中共有 {count} 条记录")


def test_search(query: str, top_k: int = 5):
    """测试向量检索"""
    logger.info(f"\n测试检索: '{query}'")
    
    client = chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
    collection = client.get_collection(COLLECTION_NAME)
    
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    
    logger.info(f"找到 {len(results['ids'][0])} 个相关项目:")
    for i, (doc, meta, dist) in enumerate(zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0]
    )):
        logger.info(f"\n{i+1}. [{meta['project_id']}] {meta['project_name']}")
        logger.info(f"   负责人: {meta['leader']}, 状态: {meta['status']}")
        logger.info(f"   相似度: {1-dist:.2f}")


def main():
    logger.info("=" * 60)
    logger.info("开始同步项目数据到ChromaDB")
    logger.info("=" * 60)
    
    # 1. 获取项目数据
    logger.info("\n步骤1: 从数据库读取项目数据...")
    projects = get_all_projects_with_tasks()
    logger.info(f"读取到 {len(projects)} 个项目")
    
    # 2. 同步到ChromaDB
    logger.info("\n步骤2: 写入ChromaDB...")
    sync_to_chroma(projects)
    
    # 3. 测试检索
    logger.info("\n步骤3: 测试向量检索...")
    test_search("隆林铝厂空压机")
    test_search("田阳阳极组装")
    test_search("Demo项目")
    
    logger.info("\n" + "=" * 60)
    logger.info("同步完成！")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
