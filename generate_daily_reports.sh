#!/bin/bash

# 日报数据生成脚本
# 创建5个自由模式 + 5个关联模式日报

TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwMDAxIiwiZXhwIjoxNzc0NDMzMjIwfQ.xHSdfNyU6x-5t_WDhfBwkYPpMZVE9HXRFeVzEwDCuwU"
API_BASE="http://localhost:8000/api"

echo "开始生成日报数据..."

# ==================== 自由模式日报 (5个) ====================
echo ""
echo "【生成自由模式日报】"

# 自由模式日报1
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report": {
      "report_date": "2026-03-20",
      "employee_id": "0001",
      "employee_name": "admin",
      "work_target": "完成项目文档整理及代码审查",
      "key_work_tracking": "跟进600KA槽上部烟气治理项目进度",
      "tomorrow_plan": "继续进行设备采购招标文件准备",
      "planned_hours": 8.0
    },
    "work_items": [
      {
        "work_content": "整理项目技术文档，完善设计图纸说明",
        "hours_spent": 3.5,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "完成技术文档整理，共计25份文件"
      },
      {
        "work_content": "参与团队代码审查会议",
        "hours_spent": 2.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "发现3处潜在问题并提出改进建议"
      },
      {
        "work_content": "编写项目周报并提交",
        "hours_spent": 1.5,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "周报已提交至项目管理平台"
      }
    ]
  }' | grep -o '"id":[0-9]*' | head -1
echo "自由模式日报1 - 2026-03-20 已创建"

# 自由模式日报2
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report": {
      "report_date": "2026-03-21",
      "employee_id": "0001",
      "employee_name": "admin",
      "work_target": "完成招标需求文档编制",
      "key_work_tracking": "协调供应商技术交流",
      "tomorrow_plan": "组织内部技术评审会议",
      "planned_hours": 8.0
    },
    "work_items": [
      {
        "work_content": "编制设备采购招标需求文档",
        "hours_spent": 4.0,
        "progress_status": "进行中",
        "progress_percentage": 80,
        "result": "完成需求文档初稿，待内部审核"
      },
      {
        "work_content": "与3家潜在供应商进行技术交流",
        "hours_spent": 2.5,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "收集技术方案3份，已整理归档"
      },
      {
        "work_content": "更新项目进度跟踪表",
        "hours_spent": 1.0,
        "progress_status": "已完成",
        "progress_percentage": 100
      }
    ]
  }' > /dev/null
echo "自由模式日报2 - 2026-03-21 已创建"

# 自由模式日报3
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report": {
      "report_date": "2026-03-22",
      "employee_id": "0001",
      "employee_name": "admin",
      "work_target": "组织技术评审并完成会议纪要",
      "key_work_tracking": "评审图纸设计方案",
      "tomorrow_plan": "根据评审意见修改设计方案",
      "planned_hours": 8.0
    },
    "work_items": [
      {
        "work_content": "组织并主持技术评审会议",
        "hours_spent": 2.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "参会人员8人，评审通过主要设计方案"
      },
      {
        "work_content": "整理会议纪要并分发",
        "hours_spent": 1.5,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "纪要已发送给所有相关人员"
      },
      {
        "work_content": "审核电气系统设计图纸",
        "hours_spent": 3.0,
        "progress_status": "进行中",
        "progress_percentage": 60,
        "result": "发现2处标注问题需修正"
      },
      {
        "work_content": "回复项目相关邮件",
        "hours_spent": 1.0,
        "progress_status": "已完成",
        "progress_percentage": 100
      }
    ]
  }' > /dev/null
echo "自由模式日报3 - 2026-03-22 已创建"

# 自由模式日报4
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report": {
      "report_date": "2026-03-23",
      "employee_id": "0001",
      "employee_name": "admin",
      "work_target": "根据评审意见完善设计方案",
      "key_work_tracking": "修改电气系统图纸",
      "tomorrow_plan": "提交修改后的设计文档",
      "planned_hours": 8.0
    },
    "work_items": [
      {
        "work_content": "修改电气系统设计图纸",
        "hours_spent": 4.5,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "已完成所有标注问题的修正"
      },
      {
        "work_content": "更新控制系统接口文档",
        "hours_spent": 2.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "文档版本更新至V2.1"
      },
      {
        "work_content": "与自控团队确认接口细节",
        "hours_spent": 1.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "双方达成一致，无遗留问题"
      }
    ]
  }' > /dev/null
echo "自由模式日报4 - 2026-03-23 已创建"

# 自由模式日报5
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report": {
      "report_date": "2026-03-24",
      "employee_id": "0001",
      "employee_name": "admin",
      "work_target": "提交设计文档并准备招标启动",
      "key_work_tracking": "完善招标文件技术部分",
      "tomorrow_plan": "启动招标公告发布流程",
      "planned_hours": 8.0
    },
    "work_items": [
      {
        "work_content": "提交修改后的设计文档",
        "hours_spent": 1.5,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "文档已提交至文档管理系统"
      },
      {
        "work_content": "完善招标文件技术规范部分",
        "hours_spent": 4.0,
        "progress_status": "进行中",
        "progress_percentage": 75,
        "result": "技术规范书完成75%，预计明日完成"
      },
      {
        "work_content": "咨询法务部门合同条款",
        "hours_spent": 1.5,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "已获取合同模板及注意事项"
      },
      {
        "work_content": "准备招标公告发布材料",
        "hours_spent": 1.0,
        "progress_status": "进行中",
        "progress_percentage": 50
      }
    ]
  }' > /dev/null
echo "自由模式日报5 - 2026-03-24 已创建"

# ==================== 关联模式日报 (5个) ====================
echo ""
echo "【生成关联模式日报】"

# 关联模式日报1 - 关联项目12的任务
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report": {
      "report_date": "2026-03-20",
      "employee_id": "0001",
      "employee_name": "admin",
      "work_target": "完成图纸设计任务节点",
      "key_work_tracking": "推进600KA槽项目设计进度",
      "tomorrow_plan": "继续进行图纸审查",
      "planned_hours": 8.0
    },
    "work_items": [
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_1_图纸设计",
        "task_name": "2.1 图纸设计",
        "work_content": "完成烟气收集罩结构设计图纸",
        "hours_spent": 5.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "设计图纸已通过内部审核",
        "measures": "采用CAD三维建模确保精度"
      },
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_1_图纸设计",
        "task_name": "2.1 图纸设计",
        "work_content": "编制图纸设计说明文档",
        "hours_spent": 2.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "说明文档已完成"
      }
    ]
  }' > /dev/null
echo "关联模式日报1 - 2026-03-20 (任务:2.1图纸设计) 已创建"

# 关联模式日报2
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report": {
      "report_date": "2026-03-21",
      "employee_id": "0001",
      "employee_name": "admin",
      "work_target": "推进图纸审查流程",
      "key_work_tracking": "组织图纸审查会议",
      "tomorrow_plan": "根据审查意见修改图纸",
      "planned_hours": 8.0
    },
    "work_items": [
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_2_图纸/预算审查",
        "task_name": "2.2 图纸/预算审查",
        "work_content": "组织图纸/预算内部审查会议",
        "hours_spent": 3.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "审查会议顺利召开，共提出5条修改意见",
        "measures": "邀请设计、工艺、造价三方参与"
      },
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_2_图纸/预算审查",
        "task_name": "2.2 图纸/预算审查",
        "work_content": "整理审查意见并编制修改清单",
        "hours_spent": 3.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "修改清单已发送给设计团队"
      },
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_3_招标需求审批",
        "task_name": "2.3 招标需求审批",
        "work_content": "准备招标需求审批材料",
        "hours_spent": 2.0,
        "progress_status": "进行中",
        "progress_percentage": 60,
        "result": "已完成审批材料初稿"
      }
    ]
  }' > /dev/null
echo "关联模式日报2 - 2026-03-21 (任务:2.2图纸审查、2.3招标需求) 已创建"

# 关联模式日报3
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report": {
      "report_date": "2026-03-22",
      "employee_id": "0001",
      "employee_name": "admin",
      "work_target": "完成招标需求审批",
      "key_work_tracking": "推进招标流程",
      "tomorrow_plan": "启动招标程序",
      "planned_hours": 8.0
    },
    "work_items": [
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_3_招标需求审批",
        "task_name": "2.3 招标需求审批",
        "work_content": "提交招标需求至审批流程",
        "hours_spent": 2.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "已通过部门负责人审批",
        "measures": "提前沟通确保流程顺畅"
      },
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_4_招标启动",
        "task_name": "2.4 招标启动",
        "work_content": "准备招标启动会议材料",
        "hours_spent": 3.0,
        "progress_status": "进行中",
        "progress_percentage": 70,
        "result": "会议议程和PPT已完成"
      },
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_5_技术任务书审查",
        "task_name": "2.5 技术任务书审查",
        "work_content": "审查技术任务书内容",
        "hours_spent": 2.0,
        "progress_status": "进行中",
        "progress_percentage": 40,
        "result": "完成技术参数部分审查"
      }
    ]
  }' > /dev/null
echo "关联模式日报3 - 2026-03-22 (任务:2.3招标审批、2.4招标启动、2.5技术任务书) 已创建"

# 关联模式日报4
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report": {
      "report_date": "2026-03-23",
      "employee_id": "0001",
      "employee_name": "admin",
      "work_target": "完成招标启动并发布公告",
      "key_work_tracking": "启动公开招标程序",
      "tomorrow_plan": "跟进供应商报名情况",
      "planned_hours": 8.0
    },
    "work_items": [
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_4_招标启动",
        "task_name": "2.4 招标启动",
        "work_content": "召开招标启动会议",
        "hours_spent": 2.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "会议顺利完成，确定招标方案"
      },
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_6_招标公告",
        "task_name": "2.6 招标公告",
        "work_content": "编制并发布招标公告",
        "hours_spent": 3.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "公告已在指定平台发布",
        "measures": "同时在3个平台发布扩大影响"
      },
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_5_技术任务书审查",
        "task_name": "2.5 技术任务书审查",
        "work_content": "完成技术任务书审查",
        "hours_spent": 2.0,
        "progress_status": "已完成",
        "progress_percentage": 100,
        "result": "任务书已通过技术委员会审查"
      }
    ]
  }' > /dev/null
echo "关联模式日报4 - 2026-03-23 (任务:2.4招标启动、2.5技术任务书、2.6招标公告) 已创建"

# 关联模式日报5
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "report": {
      "report_date": "2026-03-24",
      "employee_id": "0001",
      "employee_name": "admin",
      "work_target": "跟进供应商报名并进行资格审查",
      "key_work_tracking": "收集供应商报名材料",
      "tomorrow_plan": "组织开标评标工作",
      "planned_hours": 8.0
    },
    "work_items": [
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_7_招标资格审查",
        "task_name": "2.7 招标资格审查",
        "work_content": "收集并审核供应商报名资料",
        "hours_spent": 4.0,
        "progress_status": "进行中",
        "progress_percentage": 80,
        "result": "已收到5家供应商报名，完成3家初审",
        "measures": "严格按照资质要求进行筛选"
      },
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_8_开标评标",
        "task_name": "2.8 开标评标",
        "work_content": "准备开标评标相关文件",
        "hours_spent": 2.5,
        "progress_status": "进行中",
        "progress_percentage": 50,
        "result": "评标办法和评分表已完成"
      },
      {
        "project_id": "12",
        "project_name": "600KA槽上部烟气治理的技术研究",
        "task_id": "12_2_2_7_招标资格审查",
        "task_name": "2.7 招标资格审查",
        "work_content": "编制资格审查报告",
        "hours_spent": 1.5,
        "progress_status": "进行中",
        "progress_percentage": 60,
        "result": "报告框架已完成，待补充审核结果"
      }
    ]
  }' > /dev/null
echo "关联模式日报5 - 2026-03-24 (任务:2.7资格审查、2.8开标评标) 已创建"

echo ""
echo "===================="
echo "日报数据生成完成！"
echo "自由模式日报：5个"
echo "关联模式日报：5个"
echo "===================="
