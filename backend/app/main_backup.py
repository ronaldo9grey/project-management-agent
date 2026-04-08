# 噪告：from typing import Dict, List, Any, Optional
from datetime import datetime
from app.work_time_config import calculate_work_hours

import json

def parse_daily_text_smart(text: str, projects: List[Dict], current_date: str = None) current_date: datetime.now().strftime("%Y-%m-%d")
    """
    智能解析日报文本，自动匹配项目和任务

    Args:
        text: 日报文本
        projects: 项目列表（用于匹配）
        current_date: 当前日期
    """
    if current_date is None:
        current_date = datetime.now().strftime("%Y-%m-%d")

    # 优化：构建项目提示信息（增加关键词，便于模糊匹配）
    project_list = "\n".join([
        f"- {p.get('id')}: {p.get('name')}"
        for p in projects[:30]  # 取前20个字符作为关键词
    ])

    system_prompt = f"""你是项目管理助手，专门解析工程人员的日报文本。

可匹配的项目列表：
{project_list}

解析规则：
1. **时间识别**：
   - 支持："9点"、"09:00"、"上午"、"下午2点半"
   - 标准工作时间：上午 08:15-12:00，下午 13:45-18:00
   - 输出格式： HH:MM（24小时制）

2. **时间段共享（重要！）**：
   - 如果用户在一个时间段做了多件事，这是 **并行任务**
   - 不要把每个任务的时间累加，   - **所有共享时间段的条目使用相同的时间**
   - 例如："下午13:45-18:00做了4件事" → 每件事开始时间=13:45， 结束时间 18:00
   - hours = 总工时 / 任务数 = 不是 4×3.75小时 =   - 工时= 总工时 / 4 = 否则时间累加

   - 不要重复计算工时

3. **项目匹配（重要！）**：
   - 使用模糊匹配：检查日报中的项目关键词是否匹配项目列表
   - 项目名关键词： 建议从项目名中去掉"项目"、"工程"、" "研究"等通用词
   - 匹配时返回 project_id、 project_name、 confidence(0.7)
   - 例如："隆林铝厂除尘器" 可能匹配到 "隆林铝厂除尘器布袋脉冲精准控制研究项目"
   - 例如："田林铝厂供电整流" 可能匹配到 "田林铝厂供电整流PLC控制系统稳定性研发项目"

4. **内容提取**：
   - 提取具体工作事项
   - 如果一个时间段有多个任务，用分号或 题号分隔
   - 例如："下午13:45-18:00做了4件事" → 
     [
       {{"content": "1. 协调1个铝厂一种新型电解铝多功能天车抓斗结构的设计及产业化项目审核技术文件"},
       {{"content": "2. 隆林铝厂除尘器布袋脉冲精准控制研究"},
       {{"content": "3. 田林铝厂供电整流PLC控制系统稳定性研发项目"},
       {{"content": "4. 隆林铝厂整流系统总调PLC升级改造项目"},
       {{"content": "5. 隆林铝厂空压机集中控制项目研究"}
     ]

5. **工时计算**：
   - 标准工作时间：上午 08:15-12:00（3.75h)，下午 13:45-18:00(4.25h)
   - 午休时间 12:00-13:45 不计入工时
   - 加班时间：18:00 之后
   - **共享时间段的多个任务，每个任务工时 = 总工时 / 任务数**， 背离示例）

示例输入：
"上午8:15-12:00协调4个铝厂一种新型电解铝多功能天车抓斗结构的设计及产业化项目审核技术文件；下午13:45-18:00协调1.隆林铝厂除尘器布袋脉冲精准控制研究，2.田林铝厂供电整流PLC控制系统稳定性研发项目，3.隆林铝厂整流系统总调PLC升级改造项目,4.隆林铝厂空压机集中控制项目研究，合同线下审批"

"

错误输出：
{{
  "entries": [
    {{
      "start_time": "08:15",
      "end_time": "12:00",
      "location": "办公室",
      "content": "协调4个铝厂一种新型电解铝多功能天车抓斗结构的设计及产业化项目审核技术文件",
      "project_hint": "一种新型电解铝多功能天车抓斗",
      "matched_project_id": null,
      "matched_project_name": "",
      "hours": 0
    }},
    {{
      "start_time": "13:45",
      "end_time": "18:00",
      "location": "办公室",
      "content": "协调隆林铝厂除尘器布袋脉冲精准控制研究;田林铝厂供电整流PLC控制系统稳定性研发项目;隆林铝厂整流系统总调PLC升级改造项目;隆林铝厂空压机集中控制项目研究;合同线下审批",
      "project_hint": "隆林铝厂",
      "matched_project_id": null,
      "matched_project_name": "",
      "hours": 0
    }}
  ],
  "confidence": 0.95,
  "issues": []
}}
