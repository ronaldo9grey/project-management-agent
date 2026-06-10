#!/usr/bin/env python3
"""
导出项目和任务数据到ChromaDB格式
确保project_id为INTEGER类型
"""

import psycopg2
import json

# 数据库连接
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="project_cost_tracking",
    user="yjydb",
    password="qv52A03xcxAQCoDglUJelm4Sb"
)
cursor = conn.cursor()

# 获取项目
cursor.execute("""
    SELECT id, name, COALESCE(leader, '') as leader
    FROM projects
    WHERE status IN ('进行中', '已立项') OR status IS NULL
    ORDER BY id
""")
projects = [{"id": int(row[0]), "name": row[1], "leader": row[2]} for row in cursor.fetchall()]

# 获取任务（project_id转为INTEGER）
cursor.execute("""
    SELECT task_id, task_name, CAST(project_id AS INTEGER) as project_id
    FROM project_tasks
    WHERE is_latest = true AND is_deleted = false
    ORDER BY project_id, task_id
""")
tasks = [{"task_id": row[0], "task_name": row[1], "project_id": int(row[2])} for row in cursor.fetchall()]

cursor.close()
conn.close()

# 保存为JSON
data = {"projects": projects, "tasks": tasks}
with open("chromadb_data_v2.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✓ 导出 {len(projects)} 个项目")
print(f"✓ 导出 {len(tasks)} 个任务")

# 验证项目22的任务
tasks_22 = [t for t in tasks if t["project_id"] == 22]
print(f"\n项目22的任务数: {len(tasks_22)}")
for t in tasks_22[:5]:
    print(f"  - {t['task_name']}")