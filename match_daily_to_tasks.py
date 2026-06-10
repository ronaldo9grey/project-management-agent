#!/usr/bin/env python3
"""
根据历史日报匹配田阳铝厂项目V2任务进度
"""

import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/project-agent-v2/backend')

import psycopg2
from datetime import datetime
import json

DB_URL = "postgresql://yjydb:qv52A03xcxAQCoDglUJelm4Sb@localhost:5432/project_cost_tracking"
PROJECT_ID = 26

# 任务匹配规则（关键词 → 任务序号）
TASK_KEYWORDS = {
    # 月度反馈会
    "反馈会": ("反馈会", "1"),
    "反馈会议": ("反馈会", "1"),
    
    # 会议纪要
    "会议纪要": ("会议纪要", "2"),
    "编写报告": ("会议纪要", "2"),
    "整理": ("会议纪要", "2"),
    
    # 组装效率达标
    "效率": ("组装效率", "3"),
    "组装": ("组装效率", "3"),
    "浇铸": ("组装效率", "3"),
    "诊断": ("组装效率", "3"),
    "现场": ("组装效率", "3"),
    "技术服务": ("组装效率", "3"),
    
    # 第二阶段验收
    "第二阶段": ("第二阶段验收", "4"),
    "第二阶段验收": ("第二阶段验收", "4"),
    
    # 第三阶段验收
    "第三阶段": ("第三阶段验收", "4"),
    "第三阶段验收": ("第三阶段验收", "4"),
}

def get_task_seq_from_date(date):
    """根据日期确定任务序号（月份 - 3）"""
    if date.month >= 4 and date.month <= 12:
        return date.month - 3  # 4月→1, 5月→2, ..., 12月→9
    return None

def match_task(work_content, report_date):
    """
    根据工作内容匹配任务
    返回: (task_name_keyword, process_idx)
    """
    content_lower = work_content.lower() if work_content else ""
    month = report_date.month
    
    # 优先匹配反馈会
    if "反馈会" in content_lower or "反馈会议" in content_lower:
        return ("反馈会", "1")
    
    # 匹配会议纪要
    if "会议纪要" in content_lower:
        return ("会议纪要", "2")
    
    # 匹配第二阶段验收（只在9月有效）
    if "第二阶段验收" in content_lower and month == 9:
        return ("第二阶段验收", "4")
    
    # 匹配第三阶段验收（只在12月有效）
    if "第三阶段验收" in content_lower and month == 12:
        return ("第三阶段验收", "4")
    
    # 默认匹配组装效率（大部分技术服务工作）
    if "诊断" in content_lower or "现场" in content_lower or "效率" in content_lower or "浇铸" in content_lower or "组装" in content_lower or "技术服务" in content_lower:
        return ("组装效率", "3")
    
    # 如果没有明确匹配，默认归入组装效率
    return ("组装效率", "3")

def get_task_id(task_seq, process_idx):
    """生成任务ID"""
    return f"{PROJECT_ID}_{task_seq}_{process_idx}_V2"

def match_and_update():
    """匹配日报并更新任务进度"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    try:
        # 获取项目26的所有日报工作项
        cur.execute("""
            SELECT 
                dwi.id,
                dwi.report_id,
                dr.report_date,
                dwi.work_content,
                dwi.hours_spent,
                dwi.progress_percentage
            FROM daily_work_items dwi
            JOIN daily_reports dr ON dwi.report_id = dr.id
            WHERE dwi.project_id = '26'
            ORDER BY dr.report_date
        """)
        
        work_items = cur.fetchall()
        print(f"共找到 {len(work_items)} 个工作项")
        
        # 按月份和任务类型统计工时
        task_hours = {}  # {task_id: total_hours}
        task_reports = {}  # {task_id: [report_ids]}
        
        for item in work_items:
            item_id, report_id, report_date, work_content, hours, progress = item
            
            # 获取任务序号（月份-3）
            task_seq = get_task_seq_from_date(report_date)
            if not task_seq:
                print(f"跳过日期 {report_date}（不在4-12月范围）")
                continue
            
            # 匹配任务
            task_keyword, process_idx = match_task(work_content, report_date)
            task_id = get_task_id(task_seq, process_idx)
            
            # 统计工时
            if task_id not in task_hours:
                task_hours[task_id] = 0
                task_reports[task_id] = []
            
            task_hours[task_id] += float(hours or 0)
            task_reports[task_id].append(report_id)
            
            print(f"  {report_date} | {work_content[:30] if work_content else ''}... → {task_id}")
        
        print("\n" + "=" * 80)
        print("任务工时统计:")
        print("-" * 80)
        
        # 计算进度并更新任务
        for task_id, total_hours in task_hours.items():
            report_count = len(set(task_reports[task_id]))
            
            # 获取任务信息
            cur.execute("""
                SELECT task_name, task_level, parent_task_id, start_date, end_date
                FROM project_tasks
                WHERE task_id = %s
            """, (task_id,))
            task_info = cur.fetchone()
            
            if not task_info:
                print(f"任务 {task_id} 不存在，跳过")
                continue
            
            task_name, task_level, parent_id, start_date, end_date = task_info
            
            # 计算进度（基于工时和报告数）
            # 简单规则：有报告就算有进度，报告越多进度越高
            # 对于反馈会任务：有报告 = 100%
            # 对于组装效率任务：根据工时和报告数估算
            
            if "反馈会" in task_name or "会议纪要" in task_name:
                # 反馈会和会议纪要：有报告即完成
                progress = 100.0 if report_count > 0 else 0.0
            elif "验收" in task_name:
                # 验收任务：需要明确提及才算完成
                progress = 100.0 if "验收" in task_name and report_count > 0 else 0.0
            else:
                # 组装效率任务：根据报告数估算
                # 假设每天一份报告，有报告就代表有进展
                # 计算该月应该有多少天数的工作
                days_in_month = (end_date - start_date).days + 1
                expected_reports = days_in_month * 0.5  # 假设50%的天数有报告
                
                if expected_reports > 0:
                    progress = min(100.0, (report_count / expected_reports) * 100)
                else:
                    progress = 0.0
            
            print(f"{task_id:20} | {task_name:30} | 工时:{total_hours:6.1f}h | 报告:{report_count}次 | 进度:{progress:.1f}%")
            
            # 更新任务进度
            cur.execute("""
                UPDATE project_tasks
                SET progress = %s
                WHERE task_id = %s
            """, (progress, task_id))
            
            # 更新日报工作项的task_id关联
            for report_id in set(task_reports[task_id]):
                cur.execute("""
                    UPDATE daily_work_items
                    SET task_id = %s
                    WHERE report_id = %s AND project_id = '26'
                """, (task_id, report_id))
        
        # 更新父任务进度（Level 1）
        print("\n更新父任务进度:")
        print("-" * 80)
        
        for task_seq in range(1, 10):  # 1-9对应4-12月
            parent_id = f"{PROJECT_ID}_{task_seq}_V2"
            
            # 获取所有子任务进度
            cur.execute("""
                SELECT progress FROM project_tasks
                WHERE parent_task_id = %s AND is_latest = true
            """, (parent_id,))
            child_progresses = [float(row[0] or 0) for row in cur.fetchall()]
            
            if child_progresses:
                avg_progress = sum(child_progresses) / len(child_progresses)
                cur.execute("""
                    UPDATE project_tasks SET progress = %s WHERE task_id = %s
                """, (round(avg_progress, 1), parent_id))
                print(f"{parent_id:15} | 平均进度: {avg_progress:.1f}%")
        
        conn.commit()
        print("\n✅ 进度更新完成！")
        
        # 显示最终结果
        print("\n最终任务进度:")
        print("-" * 80)
        cur.execute("""
            SELECT task_id, task_name, progress
            FROM project_tasks
            WHERE project_id = '26' AND is_latest = true
            ORDER BY task_id
        """)
        for row in cur.fetchall():
            print(f"{row[0]:20} | {row[1]:35} | {row[2]:.1f}%")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("开始匹配历史日报到V2任务...")
    print("=" * 80)
    match_and_update()