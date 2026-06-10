#!/usr/bin/env python3
"""
ChromaDB初始化脚本：从JSON文件加载项目和任务数据
执行方式：python3 init_chromadb.py chromadb_data.json
"""

import chromadb
from chromadb.config import Settings
import json
import sys

def init_chromadb(json_file):
    """初始化ChromaDB"""
    print("=" * 60)
    print("ChromaDB初始化脚本")
    print("=" * 60)
    
    # 读取数据
    print(f"\n正在读取 {json_file}...")
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    projects = data["projects"]
    tasks = data["tasks"]
    
    print(f"✓ 读取 {len(projects)} 个项目")
    print(f"✓ 读取 {len(tasks)} 个任务")
    
    # 连接ChromaDB
    client = chromadb.HttpClient(
        host="127.0.0.1",
        port=8000,
        settings=Settings(anonymized_telemetry=False)
    )
    
    # 删除旧collection
    try:
        client.delete_collection("projects")
        print("\n✓ 已删除旧collection")
    except Exception as e:
        print(f"\n删除失败（可能不存在）: {e}")
    
    # 创建新collection
    collection = client.create_collection(name="projects")
    print("✓ 创建新collection成功")
    
    # 准备数据
    ids = []
    documents = []
    metadatas = []
    
    # 添加项目
    for p in projects:
        ids.append(f"project_{p['id']}")
        documents.append(p["name"])
        metadatas.append({
            "type": "project",
            "project_id": p["id"],
            "project_name": p["name"],
            "leader": p["leader"]
        })
    
    # 添加任务
    for t in tasks:
        ids.append(f"task_{t['task_id']}")
        documents.append(t["task_name"])
        metadatas.append({
            "type": "task",
            "task_id": t["task_id"],
            "task_name": t["task_name"],
            "project_id": t["project_id"]
        })
    
    # 批量添加到ChromaDB
    print(f"\n正在添加 {len(ids)} 条记录到ChromaDB...")
    
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
        print(f"  添加 {i+1}-{min(i+batch_size, len(ids))} / {len(ids)}")
    
    print(f"\n✓ 成功加载 {len(projects)} 个项目 + {len(tasks)} 个任务")
    
    # 测试查询
    print("\n" + "=" * 60)
    print("测试查询")
    print("=" * 60)
    
    # 测试1：项目查询
    results = collection.query(query_texts=["空压机"], n_results=5)
    print("\n查询'空压机' (前5个结果):")
    for i, (doc, meta) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
        print(f"  {i+1}. [{meta['type']}] {doc}")
    
    # 测试2：任务查询
    results = collection.query(query_texts=["调试"], n_results=5)
    print("\n查询'调试' (前5个结果):")
    for i, (doc, meta) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
        project_id = meta.get('project_id', 'N/A')
        print(f"  {i+1}. [{meta['type']}] {doc} (项目ID: {project_id})")
    
    print("\n" + "=" * 60)
    print("✓ ChromaDB初始化完成！")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 init_chromadb.py chromadb_data.json")
        sys.exit(1)
    
    init_chromadb(sys.argv[1])
