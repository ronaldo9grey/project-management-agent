#!/usr/bin/env python3
"""
步骤1：在应用服务器导出项目+任务数据

用法：
    python3 export_projects_data.py
"""

import json
import psycopg2
from datetime import date

# 数据库连接
conn = psycopg2.connect(
    host="localhost",
    database="project_cost_tracking",
    user="yjydb",
    password="qv52A03xcxAQCoDglUJelm4Sb"
)
cur = conn.cursor()

# 获取所有项目
cur.execute("""
    SELECT id, name, leader, status, progress
    FROM projects
    WHERE is_deleted = false
    ORDER BY id
""")
projects = cur.fetchall()

data = []

for proj in projects:
    pid, name, leader, status, progress = proj
    
    # 获取该项目的任务（最新版本）
    cur.execute("""
        SELECT task_id, task_name, task_level
        FROM project_tasks
        WHERE project_id::integer = %s
        AND is_deleted = false
        AND is_latest = true
        ORDER BY task_id
    """, (pid,))
    tasks = cur.fetchall()
    
    project_data = {
        "id": pid,
        "name": name,
        "leader": leader or "",
        "status": status or "",
        "progress": float(progress or 0),
        "tasks": [
            {
                "task_id": t[0],
                "task_name": t[1],
                "task_level": t[2]
            }
            for t in tasks
        ]
    }
    data.append(project_data)
    print(f"✓ 项目{pid}: {name} ({len(tasks)}个任务)")

cur.close()
conn.close()

# 保存到JSON文件
output_file = "projects_data.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✓ 导出完成: {output_file}")
print(f"  项目数: {len(data)}")
print(f"  总任务数: {sum(len(p['tasks']) for p in data)}")
