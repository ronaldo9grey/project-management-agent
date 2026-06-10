#!/bin/bash

# 创建当月月度目标及关联日报

TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwMDAxIiwiZXhwIjoxNzc0NDMzMjIwfQ.xHSdfNyU6x-5t_WDhfBwkYPpMZVE9HXRFeVzEwDCuwU"
API_BASE="http://localhost:8000/api"

echo "开始创建当月计划及关联日报..."

# ==================== 1. 创建月度目标 ====================
echo ""
echo "【创建月度目标】"

MONTHLY_GOAL=$(curl -s -X POST "${API_BASE}/v1/monthly-goals" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "month": "2026-03",
    "title": "完成600KA槽烟气治理项目设计阶段工作",
    "description": "3月份主要目标是完成项目设计阶段的全部工作，包括图纸设计、审查、招标启动等关键节点，确保项目按计划推进至采购阶段。",
    "status": "published"
  }')

MONTHLY_GOAL_ID=$(echo $MONTHLY_GOAL | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
echo "月度目标创建成功，ID: $MONTHLY_GOAL_ID"

# ==================== 2. 创建周目标 ====================
echo ""
echo "【创建周目标】"

# 第3周目标 (3月16-22日)
WEEK3_GOAL=$(curl -s -X POST "${API_BASE}/v1/monthly-goals/${MONTHLY_GOAL_ID}/weekly-goals" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "week_number": 3,
    "title": "完成图纸/预算审查及招标需求准备",
    "description": "本周完成图纸设计和预算的内部审查工作，准备并提交招标需求审批。",
    "progress_rate": 60
  }')
WEEK3_ID=$(echo $WEEK3_GOAL | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
echo "第3周目标创建成功，ID: $WEEK3_ID"

# 第4周目标 (3月23-29日)
WEEK4_GOAL=$(curl -s -X POST "${API_BASE}/v1/monthly-goals/${MONTHLY_GOAL_ID}/weekly-goals" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "week_number": 4,
    "title": "完成招标启动及公告发布",
    "description": "本周完成招标启动会议，发布招标公告，开展供应商资格审查。",
    "progress_rate": 30
  }')
WEEK4_ID=$(echo $WEEK4_GOAL | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
echo "第4周目标创建成功，ID: $WEEK4_ID"

# ==================== 3. 创建关联模式日报 ====================
echo ""
echo "【创建关联模式日报】"

# 关联第3周目标的日报1
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"report\": {
      \"report_date\": \"2026-03-18\",
      \"employee_id\": \"0001\",
      \"employee_name\": \"admin\",
      \"work_target\": \"完成图纸审查并整理修改意见\",
      \"key_work_tracking\": \"推进月度目标：完成设计阶段工作\",
      \"tomorrow_plan\": \"准备招标需求审批材料\",
      \"planned_hours\": 8.0
    },
    \"work_items\": [
      {
        \"project_id\": \"12\",
        \"project_name\": \"600KA槽上部烟气治理的技术研究\",
        \"task_id\": \"12_2_2_2_图纸/预算审查\",
        \"task_name\": \"2.2 图纸/预算审查\",
        \"work_content\": \"组织图纸/预算内部审查会议\",
        \"hours_spent\": 3.0,
        \"progress_status\": \"已完成\",
        \"progress_percentage\": 100,
        \"result\": \"审查会议顺利召开，共提出5条修改意见\",
        \"measures\": \"邀请设计、工艺、造价三方参与\"
      },
      {
        \"project_id\": \"12\",
        \"project_name\": \"600KA槽上部烟气治理的技术研究\",
        \"task_id\": \"12_2_2_2_图纸/预算审查\",
        \"task_name\": \"2.2 图纸/预算审查\",
        \"work_content\": \"整理审查意见并编制修改清单\",
        \"hours_spent\": 3.0,
        \"progress_status\": \"已完成\",
        \"progress_percentage\": 100,
        \"result\": \"修改清单已发送给设计团队\"
      }
    ]
  }" > /dev/null
echo "关联日报1 - 2026-03-18 (第3周) 已创建"

# 关联第3周目标的日报2
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"report\": {
      \"report_date\": \"2026-03-19\",
      \"employee_id\": \"0001\",
      \"employee_name\": \"admin\",
      \"work_target\": \"完成招标需求审批\",
      \"key_work_tracking\": \"推进月度目标：完成设计阶段工作\",
      \"tomorrow_plan\": \"准备招标启动会议\",
      \"planned_hours\": 8.0
    },
    \"work_items\": [
      {
        \"project_id\": \"12\",
        \"project_name\": \"600KA槽上部烟气治理的技术研究\",
        \"task_id\": \"12_2_2_3_招标需求审批\",
        \"task_name\": \"2.3 招标需求审批\",
        \"work_content\": \"准备招标需求审批材料\",
        \"hours_spent\": 3.0,
        \"progress_status\": \"已完成\",
        \"progress_percentage\": 100,
        \"result\": \"审批材料已准备完成\"
      },
      {
        \"project_id\": \"12\",
        \"project_name\": \"600KA槽上部烟气治理的技术研究\",
        \"task_id\": \"12_2_2_3_招标需求审批\",
        \"task_name\": \"2.3 招标需求审批\",
        \"work_content\": \"提交招标需求至审批流程\",
        \"hours_spent\": 2.0,
        \"progress_status\": \"已完成\",
        \"progress_percentage\": 100,
        \"result\": \"已通过部门负责人审批\"
      }
    ]
  }" > /dev/null
echo "关联日报2 - 2026-03-19 (第3周) 已创建"

# 关联第4周目标的日报3
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"report\": {
      \"report_date\": \"2026-03-24\",
      \"employee_id\": \"0001\",
      \"employee_name\": \"admin\",
      \"work_target\": \"完成招标启动及公告发布\",
      \"key_work_tracking\": \"推进月度目标：完成设计阶段工作\",
      \"tomorrow_plan\": \"跟进供应商报名情况\",
      \"planned_hours\": 8.0
    },
    \"work_items\": [
      {
        \"project_id\": \"12\",
        \"project_name\": \"600KA槽上部烟气治理的技术研究\",
        \"task_id\": \"12_2_2_4_招标启动\",
        \"task_name\": \"2.4 招标启动\",
        \"work_content\": \"召开招标启动会议\",
        \"hours_spent\": 2.0,
        \"progress_status\": \"已完成\",
        \"progress_percentage\": 100,
        \"result\": \"会议顺利完成，确定招标方案\"
      },
      {
        \"project_id\": \"12\",
        \"project_name\": \"600KA槽上部烟气治理的技术研究\",
        \"task_id\": \"12_2_2_6_招标公告\",
        \"task_name\": \"2.6 招标公告\",
        \"work_content\": \"编制并发布招标公告\",
        \"hours_spent\": 3.0,
        \"progress_status\": \"已完成\",
        \"progress_percentage\": 100,
        \"result\": \"公告已在指定平台发布\",
        \"measures\": \"同时在3个平台发布扩大影响\"
      }
    ]
  }" > /dev/null
echo "关联日报3 - 2026-03-24 (第4周) 已创建"

# 关联第4周目标的日报4
curl -s -X POST "${API_BASE}/v1/daily-report/my-reports/with-items" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"report\": {
      \"report_date\": \"2026-03-25\",
      \"employee_id\": \"0001\",
      \"employee_name\": \"admin\",
      \"work_target\": \"跟进供应商报名及资格审查\",
      \"key_work_tracking\": \"推进月度目标：完成设计阶段工作\",
      \"tomorrow_plan\": \"继续供应商资格审查\",
      \"planned_hours\": 8.0
    },
    \"work_items\": [
      {
        \"project_id\": \"12\",
        \"project_name\": \"600KA槽上部烟气治理的技术研究\",
        \"task_id\": \"12_2_2_7_招标资格审查\",
        \"task_name\": \"2.7 招标资格审查\",
        \"work_content\": \"收集并审核供应商报名资料\",
        \"hours_spent\": 4.0,
        \"progress_status\": \"进行中\",
        \"progress_percentage\": 80,
        \"result\": \"已收到5家供应商报名，完成3家初审\",
        \"measures\": \"严格按照资质要求进行筛选\"
      },
      {
        \"project_id\": \"12\",
        \"project_name\": \"600KA槽上部烟气治理的技术研究\",
        \"task_id\": \"12_2_2_7_招标资格审查\",
        \"task_name\": \"2.7 招标资格审查\",
        \"work_content\": \"编制资格审查报告\",
        \"hours_spent\": 2.0,
        \"progress_status\": \"进行中\",
        \"progress_percentage\": 60,
        \"result\": \"报告框架已完成，待补充审核结果\"
      }
    ]
  }" > /dev/null
echo "关联日报4 - 2026-03-25 (第4周) 已创建"

echo ""
echo "===================="
echo "当月计划及关联日报创建完成！"
echo "月度目标ID: $MONTHLY_GOAL_ID"
echo "第3周目标ID: $WEEK3_ID"
echo "第4周目标ID: $WEEK4_ID"
echo "关联日报：4条"
echo "===================="
