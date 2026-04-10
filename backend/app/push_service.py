"""
推送服务模块
支持飞书和微信推送
"""

import os
import requests
import json
from typing import Optional, List
from datetime import datetime


# PushPlus 配置
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "")
PUSHPLUS_API = "http://www.pushplus.plus/send"
PUSHPLUS_TOPIC = "projectalarm"  # 群组编码


def should_push() -> bool:
    """
    检查当前时间是否应该推送
    工作时间：08:00 - 22:00
    非工作时间不推送
    """
    hour = datetime.now().hour
    # 08:00 - 22:00 可以推送
    return 8 <= hour < 22


def push_to_wechat(
    title: str,
    content: str,
    token: str = None,
    template: str = "html",
    topic: str = None
) -> bool:
    """
    通过 PushPlus 推送到微信
    
    Args:
        title: 消息标题
        content: 消息内容（支持HTML）
        token: PushPlus token（默认使用全局token）
        template: 模板类型 html/txt/json
        topic: 群组编码（推送给群组所有成员）
    
    Returns:
        bool: 是否成功
    """
    # 使用传入的token，如果没有则使用全局token
    actual_token = token if token else PUSHPLUS_TOKEN
    actual_topic = topic if topic else PUSHPLUS_TOPIC
    
    try:
        data = {
            "token": actual_token,
            "title": title,
            "content": content,
            "template": template
        }
        
        # 如果有群组编码，添加到参数
        if actual_topic:
            data["topic"] = actual_topic
        
        print(f"[DEBUG] 推送参数: token={actual_token[:10]}..., topic={actual_topic}, title={title}")
        
        response = requests.post(PUSHPLUS_API, json=data, timeout=10)
        result = response.json()
        
        if result.get("code") == 200:
            target = f"群组[{actual_topic}]" if actual_topic else ("个人" if token else "全局")
            print(f"✅ 微信推送成功 -> {target}: {title}")
            return True
        else:
            print(f"❌ 微信推送失败: {result.get('msg', 'Unknown error')}")
            print(f"[DEBUG] 响应详情: {result}")
            return False
    
    except Exception as e:
        print(f"❌ 微信推送异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def push_alert_to_user(alert: dict, project_name: str, leader_name: str, leader_token: str = None):
    """
    推送预警给项目负责人
    
    Args:
        alert: 预警信息
        project_name: 项目名称
        leader_name: 负责人名称
        leader_token: 负责人的PushPlus token（如果没有则使用全局token）
    """
    # 如果有个人token则推送给个人，否则推送给群组
    token = leader_token if leader_token else PUSHPLUS_TOKEN
    topic = None if leader_token else PUSHPLUS_TOPIC  # 个人推送不用群组
    target = f"个人[{leader_name}]" if leader_token else f"群组[{PUSHPLUS_TOPIC}]"
    
    severity_emoji = {
        "high": "🔴",
        "medium": "🟠", 
        "low": "🟡"
    }
    
    severity_text = {
        "high": "高风险",
        "medium": "中风险",
        "low": "低风险"
    }
    
    severity_color = {
        "high": "#ef4444",
        "medium": "#f59e0b",
        "low": "#eab308"
    }
    
    emoji = severity_emoji.get(alert.get("severity", "low"), "⚪")
    level = severity_text.get(alert.get("severity", "low"), "未知")
    color = severity_color.get(alert.get("severity", "low"), "#666")
    
    title = f"{emoji} 项目预警：{project_name}"
    
    content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: {color}; border-bottom: 2px solid {color}; padding-bottom: 10px;">
            {alert.get('title', '预警通知')}
        </h2>
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
            <tr style="background: #f9fafb;">
                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold; width: 100px;">项目名称</td>
                <td style="padding: 10px; border: 1px solid #e5e7eb;">{project_name}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">项目负责人</td>
                <td style="padding: 10px; border: 1px solid #e5e7eb;">{leader_name}</td>
            </tr>
            <tr style="background: #f9fafb;">
                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">风险等级</td>
                <td style="padding: 10px; border: 1px solid #e5e7eb; color: {color}; font-weight: bold;">{level}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">预警类型</td>
                <td style="padding: 10px; border: 1px solid #e5e7eb;">{alert.get('alert_type', '-')}</td>
            </tr>
            <tr style="background: #f9fafb;">
                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">详细说明</td>
                <td style="padding: 10px; border: 1px solid #e5e7eb;">{alert.get('content', '-')}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">发生时间</td>
                <td style="padding: 10px; border: 1px solid #e5e7eb;">{datetime.now().strftime('%Y-%m-%d %H:%M')}</td>
            </tr>
        </table>
        <div style="margin-top: 20px; padding: 15px; background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;">
            <p style="margin: 0; color: #92400e; font-size: 14px;">
                <strong>⚠️ 提醒：</strong>请及时登录系统处理该预警，避免影响项目进度。
            </p>
        </div>
        <p style="color: #999; font-size: 12px; margin-top: 20px; text-align: center;">
            此消息由「项目智能体」自动推送 | <a href="https://yjypro.online/agent/" style="color: #3b82f6;">点击查看详情</a>
        </p>
    </div>
    """
    
    return push_to_wechat(title, content, token=token, topic=topic)


def push_alert_to_wechat(alert: dict, project_name: str):
    """推送预警到微信群组（使用群组topic）"""
    
    severity_emoji = {
        "high": "🔴",
        "medium": "🟠", 
        "low": "🟡"
    }
    
    severity_text = {
        "high": "高风险",
        "medium": "中风险",
        "low": "低风险"
    }
    
    severity_color = {
        "high": "#ef4444",
        "medium": "#f59e0b",
        "low": "#eab308"
    }
    
    emoji = severity_emoji.get(alert.get("severity", "low"), "⚪")
    level = severity_text.get(alert.get("severity", "low"), "未知")
    color = severity_color.get(alert.get("severity", "low"), "#666")
    
    title = f"{emoji} 项目预警：{project_name}"
    
    content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: {color}; border-bottom: 2px solid {color}; padding-bottom: 10px;">
            {alert.get('title', '预警通知')}
        </h2>
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
            <tr style="background: #f9fafb;">
                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold; width: 100px;">项目名称</td>
                <td style="padding: 10px; border: 1px solid #e5e7eb;">{project_name}</td>
            </tr>
            <tr style="background: #f9fafb;">
                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">风险等级</td>
                <td style="padding: 10px; border: 1px solid #e5e7eb; color: {color}; font-weight: bold;">{level}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">预警类型</td>
                <td style="padding: 10px; border: 1px solid #e5e7eb;">{alert.get('alert_type', '-')}</td>
            </tr>
            <tr style="background: #f9fafb;">
                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">详细说明</td>
                <td style="padding: 10px; border: 1px solid #e5e7eb;">{alert.get('content', '-')}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #e5e7eb; font-weight: bold;">发生时间</td>
                <td style="padding: 10px; border: 1px solid #e5e7eb;">{datetime.now().strftime('%Y-%m-%d %H:%M')}</td>
            </tr>
        </table>
        <div style="margin-top: 20px; padding: 15px; background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;">
            <p style="margin: 0; color: #92400e; font-size: 14px;">
                <strong>⚠️ 提醒：</strong>请及时登录系统处理该预警，避免影响项目进度。
            </p>
        </div>
        <p style="color: #999; font-size: 12px; margin-top: 20px; text-align: center;">
            此消息由「项目智能体」自动推送 | <a href="https://yjypro.online/agent/" style="color: #3b82f6;">点击查看详情</a>
        </p>
    </div>
    """
    
    # 使用群组topic推送
    return push_to_wechat(title, content, topic=PUSHPLUS_TOPIC)


def push_morning_alerts():
    """
    早上8:15推送：高风险预警汇总
    推送所有高风险项目到群组
    同一项目的多个预警合并显示
    """
    # 检查是否在推送时间
    if not should_push():
        print("非工作时间，跳过推送")
        return False
    
    from .database import get_engine, text
    import os
    
    from collections import defaultdict
    
    
    
    engine = get_engine()
    
    with engine.connect() as conn:
        # 获取所有高风险预警
        alerts = conn.execute(text("""
            SELECT 
                p.name as project_name,
                pa.alert_type,
                pa.title,
                pa.content
            FROM project_alerts pa
            JOIN projects p ON p.id = pa.project_id
            WHERE pa.severity = 'high' AND NOT pa.is_resolved
            ORDER BY p.name, pa.created_at DESC
        """)).fetchall()
    
    total_count = len(alerts)
    
    if not alerts:
        print("无高风险预警，跳过推送")
        return False
    
    # 按项目名称分组
    project_alerts = defaultdict(list)
    for a in alerts:
        project_name = a[0]
        project_alerts[project_name].append({
            "alert_type": a[1],
            "title": a[2],
            "content": a[3]
        })
    
    # 构建推送内容
    from datetime import datetime
    
    title = f"🚨 项目高风险预警（{len(project_alerts)}个项目，共{total_count}项）"
    
    # 预警类型映射
    alert_type_map = {
        "delay": "任务延期",
        "silence": "项目沉默",
        "cost": "成本超支",
        "progress": "进度滞后"
    }
    
    # 项目列表（合并显示）
    items_html = ""
    project_count = 0
    for project_name, alert_list in project_alerts.items():
        project_count += 1
        if project_count > 5:  # 最多显示5个项目
            break
        
        # 同一项目的多个预警合并
        if len(alert_list) == 1:
            # 单个预警：直接显示
            alert = alert_list[0]
            alert_type_text = alert_type_map.get(alert["alert_type"], "风险预警")
            items_html += f"""
    <div style="padding: 12px 15px; border-bottom: 1px solid #e5e7eb;">
      <div style="font-weight: 600; color: #111;">🔴 {project_name}</div>
      <div style="font-size: 13px; color: #ef4444; margin-top: 4px;">
        {alert_type_text} · {alert["content"]}
      </div>
    </div>
"""
        else:
            # 多个预警：合并显示
            alert_summary = []
            for alert in alert_list:
                alert_type_text = alert_type_map.get(alert["alert_type"], "风险预警")
                alert_summary.append(f"{alert_type_text}：{alert['content']}")
            
            items_html += f"""
    <div style="padding: 12px 15px; border-bottom: 1px solid #e5e7eb;">
      <div style="font-weight: 600; color: #111;">🔴 {project_name}（{len(alert_list)}项预警）</div>
      <div style="font-size: 13px; color: #ef4444; margin-top: 4px;">
        {'<br>        '.join(alert_summary)}
      </div>
    </div>
"""
    
    content = f"""
<div style="font-family: sans-serif; max-width: 600px;">
  <h2 style="color: #ef4444; margin: 0; padding: 15px; background: #fef2f2; border-radius: 8px 8px 0 0;">
    🚨 项目高风险预警（{project_count}个项目，共{total_count}项）
  </h2>
  <p style="color: #666; font-size: 12px; margin: 0; padding: 8px 15px; background: #f9fafb;">
    {datetime.now().strftime('%Y-%m-%d %H:%M')}
  </p>
  
  <div style="padding: 0;">
    {items_html}
  </div>
  
  <div style="padding: 15px; background: #fef3c7; border-radius: 0 0 8px 8px;">
    <div style="font-size: 13px; color: #92400e;">
      💡 请相关负责人及时处理
    </div>
    <a href="https://yjypro.online/agent/" style="display: inline-block; margin-top: 8px; padding: 6px 12px; background: #3b82f6; color: white; text-decoration: none; border-radius: 4px; font-size: 12px;">
      查看详情
    </a>
  </div>
</div>
"""
    
    return push_to_wechat(title, content, topic=PUSHPLUS_TOPIC)


def push_afternoon_reminder():
    """
    下午17:00推送：工作日报提醒
    包含日报提交情况和项目进度提醒
    同一项目的延期和即将到期信息合并显示
    """
    # 检查是否在推送时间
    if not should_push():
        print("非工作时间，跳过推送")
        return False
    
    from .database import get_engine, text
    import os
    
    from datetime import datetime, date
    from collections import defaultdict
    
    
    
    engine = get_engine()
    
    with engine.connect() as conn:
        # 今日日报提交情况
        today_reports = conn.execute(text("""
            SELECT COUNT(DISTINCT employee_name) as count
            FROM daily_reports
            WHERE report_date = CURRENT_DATE
        """)).fetchone()
        
        submitted_count = today_reports[0] if today_reports else 0
        
        # 获取延期风险项目（包含任务详细信息）
        delayed_projects = conn.execute(text("""
            SELECT 
                p.id,
                p.name,
                p.leader,
                pt.task_name,
                pt.progress as task_progress,
                pt.start_date,
                pt.end_date,
                CURRENT_DATE - pt.end_date as delay_days,
                (SELECT AVG(pt2.progress) FROM project_tasks pt2 
                 WHERE pt2.project_id = pt.project_id AND pt2.is_latest = true) as project_progress
            FROM projects p
            JOIN project_tasks pt ON pt.project_id = CAST(p.id AS VARCHAR) AND pt.is_latest = true
            WHERE p.status = '进行中' AND p.is_deleted = false
            AND pt.end_date < CURRENT_DATE AND pt.progress < 100
            ORDER BY delay_days DESC
            LIMIT 10
        """)).fetchall()
        
        # 获取即将到期项目（包含任务详细信息）
        upcoming_projects = conn.execute(text("""
            SELECT 
                p.id,
                p.name,
                p.leader,
                pt.task_name,
                pt.progress as task_progress,
                pt.start_date,
                pt.end_date,
                pt.end_date - CURRENT_DATE as remain_days,
                (SELECT AVG(pt2.progress) FROM project_tasks pt2 
                 WHERE pt2.project_id = pt.project_id AND pt2.is_latest = true) as project_progress
            FROM projects p
            JOIN project_tasks pt ON pt.project_id = CAST(p.id AS VARCHAR) AND pt.is_latest = true
            WHERE p.status = '进行中' AND p.is_deleted = false
            AND pt.end_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '3 days'
            AND pt.progress < 100
            ORDER BY pt.end_date
            LIMIT 10
        """)).fetchall()
    
    # 按项目分组统计
    delayed_project_names = set()
    upcoming_project_names = set()
    
    # 延期任务列表（按任务展示）
    delayed_html = ""
    if delayed_projects:
        current_project = None
        for p in delayed_projects[:6]:  # 最多6个任务
            project_name = p[1]
            leader = p[2] or "未指定"
            task_name = p[3][:20] + ("..." if len(p[3]) > 20 else "") if p[3] else ""
            task_progress = int(p[4]) if p[4] else 0
            start_date = str(p[5]) if p[5] else ""
            end_date = str(p[6]) if p[6] else ""
            delay_days = int(p[7]) if p[7] else 0
            project_progress = round(float(p[8]), 1) if p[8] else 0
            
            delayed_project_names.add(project_name)
            
            # 项目标题（首次出现时显示）
            if project_name != current_project:
                delayed_html += f"      <b>{project_name}</b>（负责人：{leader}，整体进度{project_progress}%）<br>\n"
                current_project = project_name
            
            # 任务详情
            delayed_html += f"        └ <b>{task_name}</b><br>\n"
            delayed_html += f"          计划：{start_date} ~ {end_date}，进度{task_progress}%，<span style='color:#ef4444'>已延期{delay_days}天</span><br>\n"
    
    # 即将到期任务列表（按任务展示）
    upcoming_html = ""
    if upcoming_projects:
        current_project = None
        for p in upcoming_projects[:6]:  # 最多6个任务
            project_name = p[1]
            leader = p[2] or "未指定"
            task_name = p[3][:20] + ("..." if len(p[3]) > 20 else "") if p[3] else ""
            task_progress = int(p[4]) if p[4] else 0
            start_date = str(p[5]) if p[5] else ""
            end_date = str(p[6]) if p[6] else ""
            remain_days = int(p[7]) if p[7] else 0
            project_progress = round(float(p[8]), 1) if p[8] else 0
            
            upcoming_project_names.add(project_name)
            
            # 项目标题（首次出现时显示）
            if project_name != current_project:
                upcoming_html += f"      <b>{project_name}</b>（负责人：{leader}，整体进度{project_progress}%）<br>\n"
                current_project = project_name
            
            # 任务详情
            if remain_days == 0:
                remain_text = "<span style='color:#ef4444'>今天到期</span>"
            elif remain_days == 1:
                remain_text = "<span style='color:#f59e0b'>明天到期</span>"
            else:
                remain_text = f"<span style='color:#f59e0b'>{remain_days}天后到期</span>"
            
            upcoming_html += f"        └ <b>{task_name}</b><br>\n"
            upcoming_html += f"          计划：{start_date} ~ {end_date}，进度{task_progress}%，{remain_text}<br>\n"
    
    # 如果没有延期和即将到期，显示空状态
    if not delayed_html:
        delayed_html = "      暂无延期任务<br>\n"
    if not upcoming_html:
        upcoming_html = "      暂无即将到期任务<br>\n"
    
    # 统计数量
    delayed_count = len(delayed_projects)
    upcoming_count = len(upcoming_projects)
    delayed_project_count = len(delayed_project_names)
    upcoming_project_count = len(upcoming_project_names)
    
    title = "📝 工作日报提醒"
    
    content = f"""
<div style="font-family: sans-serif; max-width: 600px;">
  <h2 style="color: #3b82f6; margin: 0; padding: 15px; background: #eff6ff; border-radius: 8px 8px 0 0;">
    📝 工作日报提醒
  </h2>
  <p style="color: #666; font-size: 12px; margin: 0; padding: 8px 15px; background: #f9fafb;">
    {datetime.now().strftime('%Y-%m-%d %H:%M')}
  </p>
  
  <!-- 日报提交情况 -->
  <div style="padding: 15px; border-bottom: 1px solid #e5e7eb;">
    <div style="font-weight: 600; margin-bottom: 10px;">📋 今日日报提交</div>
    <div style="font-size: 13px;">
      <span style="color: #22c55e;">✅ 已提交：{submitted_count}人</span>
    </div>
  </div>
  
  <!-- 项目进度提醒 -->
  <div style="padding: 15px; border-bottom: 1px solid #e5e7eb;">
    <div style="font-weight: 600; margin-bottom: 10px;">📊 项目进度提醒</div>
    
    <div style="margin-bottom: 10px;">
      <div style="font-size: 13px; color: #ef4444; font-weight: 600;">🔴 延期任务（{delayed_count}个任务，涉及{delayed_project_count}个项目）</div>
      <div style="font-size: 12px; color: #666; padding-left: 10px; margin-top: 4px;">
{delayed_html}      </div>
    </div>
    
    <div>
      <div style="font-size: 13px; color: #f59e0b; font-weight: 600;">🟡 即将到期（{upcoming_count}个任务，涉及{upcoming_project_count}个项目）</div>
      <div style="font-size: 12px; color: #666; padding-left: 10px; margin-top: 4px;">
{upcoming_html}      </div>
    </div>
  </div>
  
  <div style="padding: 15px; background: #ecfdf5; border-radius: 0 0 8px 8px;">
    <div style="font-size: 13px; color: #065f46;">
      💡 请大家按时完成日报和任务
    </div>
    <a href="https://yjypro.online/agent/" style="display: inline-block; margin-top: 8px; padding: 6px 12px; background: #3b82f6; color: white; text-decoration: none; border-radius: 4px; font-size: 12px;">
      去提交
    </a>
  </div>
</div>
"""
    
    return push_to_wechat(title, content, topic=PUSHPLUS_TOPIC)


def push_daily_summary_to_wechat(summary: dict):
    """推送每日摘要到微信"""
    
    title = f"📊 项目每日摘要 {datetime.now().strftime('%Y-%m-%d')}"
    
    # 计算健康度
    total = summary.get('total_projects', 0)
    ongoing = summary.get('ongoing_projects', 0)
    completed = summary.get('completed_projects', 0)
    high = summary.get('high_alerts', 0)
    medium = summary.get('medium_alerts', 0)
    low = summary.get('low_alerts', 0)
    
    content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #3b82f6; border-bottom: 2px solid #3b82f6; padding-bottom: 10px;">
            📊 项目运行概况
        </h2>
        <p style="color: #666; font-size: 14px; margin-bottom: 20px;">
            {datetime.now().strftime('%Y年%m月%d日')}
        </p>
        
        <!-- 项目统计 -->
        <div style="background: #f0f9ff; border-radius: 8px; padding: 15px; margin-bottom: 15px;">
            <h3 style="margin: 0 0 10px 0; color: #1e40af;">📈 项目统计</h3>
            <table style="width: 100%; text-align: center;">
                <tr>
                    <td style="padding: 10px;">
                        <div style="font-size: 24px; font-weight: bold; color: #3b82f6;">{ongoing}</div>
                        <div style="font-size: 12px; color: #666;">进行中</div>
                    </td>
                    <td style="padding: 10px;">
                        <div style="font-size: 24px; font-weight: bold; color: #22c55e;">{completed}</div>
                        <div style="font-size: 12px; color: #666;">已完成</div>
                    </td>
                    <td style="padding: 10px;">
                        <div style="font-size: 24px; font-weight: bold; color: #6b7280;">{total}</div>
                        <div style="font-size: 12px; color: #666;">总项目</div>
                    </td>
                </tr>
            </table>
        </div>
        
        <!-- 预警统计 -->
        <div style="background: #fef2f2; border-radius: 8px; padding: 15px; margin-bottom: 15px;">
            <h3 style="margin: 0 0 10px 0; color: #991b1b;">🚨 预警统计</h3>
            <table style="width: 100%; text-align: center;">
                <tr>
                    <td style="padding: 10px;">
                        <div style="font-size: 24px; font-weight: bold; color: #ef4444;">{high}</div>
                        <div style="font-size: 12px; color: #666;">🔴 高风险</div>
                    </td>
                    <td style="padding: 10px;">
                        <div style="font-size: 24px; font-weight: bold; color: #f59e0b;">{medium}</div>
                        <div style="font-size: 12px; color: #666;">🟠 中风险</div>
                    </td>
                    <td style="padding: 10px;">
                        <div style="font-size: 24px; font-weight: bold; color: #eab308;">{low}</div>
                        <div style="font-size: 12px; color: #666;">🟡 低风险</div>
                    </td>
                </tr>
            </table>
        </div>
        
        <!-- 提醒 -->
        <div style="margin-top: 20px; padding: 15px; background: #ecfdf5; border-left: 4px solid #22c55e; border-radius: 4px;">
            <p style="margin: 0; color: #065f46; font-size: 14px;">
                <strong>💡 温馨提示：</strong>请及时处理高风险预警，确保项目顺利推进。
            </p>
        </div>
        
        <p style="color: #999; font-size: 12px; margin-top: 20px; text-align: center;">
            此消息由「项目智能体」自动推送 | <a href="https://yjypro.online/agent/" style="color: #3b82f6;">点击查看详情</a>
        </p>
    </div>
    """
    
    return push_to_wechat(title, content)


# 飞书推送（已有飞书机器人配置）
async def push_to_feishu(
    webhook_url: str,
    title: str,
    content: str
) -> bool:
    """
    推送到飞书机器人
    
    Args:
        webhook_url: 飞书机器人 webhook
        title: 消息标题
        content: 消息内容
    
    Returns:
        bool: 是否成功
    """
    try:
        data = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "plain_text",
                            "content": content
                        }
                    }
                ]
            }
        }
        
        response = requests.post(webhook_url, json=data, timeout=10)
        result = response.json()
        
        if result.get("StatusCode") == 0:
            print(f"✅ 飞书推送成功: {title}")
            return True
        else:
            print(f"❌ 飞书推送失败: {result}")
            return False
    
    except Exception as e:
        print(f"❌ 飞书推送异常: {e}")
        return False


# 测试推送
if __name__ == "__main__":
    # 测试微信推送
    push_to_wechat(
        title="🔔 测试推送",
        content="<h3>推送测试</h3><p>这是一条测试消息</p>"
    )
