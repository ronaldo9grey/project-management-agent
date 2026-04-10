"""
将数据库中的项目、任务信息同步到RAG知识库

定时任务：每天凌晨2点同步一次
"""

import os
import asyncio
from datetime import datetime
from .database import get_engine, text

import httpx




DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")


def get_db_engine():
    """获取数据库引擎（使用全局单例）"""
    return get_engine()


async def generate_embedding(text: str) -> list:
    """生成文本向量（暂时返回None，后续可接入向量模型）"""
    return None


def sync_projects_to_knowledge_base():
    """
    将所有项目信息同步到知识库
    
    生成内容：
    1. 项目基本信息（名称、负责人、状态、进度）
    2. 项目任务列表
    3. 项目风险情况
    """
    engine = get_db_engine()
    
    print(f"[同步开始] {datetime.now()}")
    
    with engine.connect() as conn:
        # 1. 获取所有项目
        projects_result = conn.execute(text("""
            SELECT id, name, leader, status, progress, 
                   start_date, end_date,
                   describe
            FROM projects 
            WHERE is_deleted = false
            ORDER BY id
        """))
        
        projects = []
        for row in projects_result:
            projects.append({
                "id": row[0],
                "name": row[1],
                "leader": row[2],
                "status": row[3],
                "progress": row[4],
                "planned_start_date": str(row[5]) if row[5] else None,
                "planned_end_date": str(row[6]) if row[6] else None,
                "description": row[7]
            })
        
        print(f"找到 {len(projects)} 个项目")
        
        # 2. 为每个项目生成知识库文档
        for project in projects:
            project_id = project["id"]
            
            # 获取项目的任务
            tasks_result = conn.execute(text("""
                SELECT task_id, task_name, assignee, status, progress,
                       start_date, end_date, actual_end_date
                FROM project_tasks
                WHERE CAST(project_id AS INTEGER) = :pid
                  AND is_deleted = false
                ORDER BY task_id
            """), {"pid": project_id})
            
            tasks = []
            for row in tasks_result:
                tasks.append({
                    "task_id": row[0],
                    "task_name": row[1],
                    "assignee": row[2],
                    "status": row[3],
                    "progress": row[4],
                    "start_date": str(row[5]) if row[5] else None,
                    "end_date": str(row[6]) if row[6] else None,
                    "actual_end_date": str(row[7]) if row[7] else None
                })
            
            # 生成markdown内容
            md_content = generate_project_markdown(project, tasks)
            
            # 删除旧的项目知识库文档
            conn.execute(text("""
                DELETE FROM project_knowledge_base
                WHERE project_id = :pid AND doc_name = '项目概况'
            """), {"pid": project_id})
            
            # 插入新的知识库文档
            conn.execute(text("""
                INSERT INTO project_knowledge_base 
                (project_id, project_name, doc_name, doc_type, content, summary, upload_time)
                VALUES (:pid, :pname, '项目概况', '项目概况', :content, :summary, NOW())
            """), {
                "pid": project_id,
                "pname": project["name"],
                "content": md_content,
                "summary": f"项目【{project['name']}】负责人：{project['leader']}，状态：{project['status']}，进度：{project['progress']}%，任务数：{len(tasks)}"
            })
        
        conn.commit()
    
    print(f"[同步完成] {datetime.now()}")
    return len(projects)


def generate_project_markdown(project: dict, tasks: list) -> str:
    """生成项目知识库markdown文档"""
    
    # 统计任务状态
    completed_tasks = [t for t in tasks if t["status"] == "已完成"]
    ongoing_tasks = [t for t in tasks if t["status"] == "进行中"]
    delayed_tasks = [t for t in tasks if t["status"] == "延期"]
    
    md = f"""# 项目概况：{project['name']}

## 基本信息

| 属性 | 值 |
|------|-----|
| 项目ID | {project['id']} |
| 项目名称 | {project['name']} |
| 负责人 | **{project['leader']}** |
| 状态 | {project['status']} |
| 进度 | {project['progress']}% |
| 开始日期 | {project['planned_start_date'] or '未设置'} |
| 结束日期 | {project['planned_end_date'] or '未设置'} |

## 任务统计

- 总任务数：{len(tasks)}
- 已完成：{len(completed_tasks)}
- 进行中：{len(ongoing_tasks)}
- 延期：{len(delayed_tasks)}

## 任务列表

"""
    
    if tasks:
        md += "| 任务ID | 任务名称 | 负责人 | 状态 | 进度 | 截止日期 |\n"
        md += "|--------|----------|--------|------|------|----------|\n"
        
        for task in tasks:
            md += f"| {task['task_id']} | {task['task_name']} | {task['assignee'] or '未分配'} | {task['status']} | {task['progress']}% | {task['end_date'] or '未设置'} |\n"
    
    # 添加延期任务详情
    if delayed_tasks:
        md += "\n## 延期任务详情\n\n"
        for task in delayed_tasks:
            md += f"- **{task['task_name']}**：负责人 {task['assignee']}，截止日期 {task['end_date']}，当前进度 {task['progress']}%\n"
    
    return md


if __name__ == "__main__":
    # 手动执行同步
    count = sync_projects_to_knowledge_base()
    print(f"已同步 {count} 个项目到知识库")
