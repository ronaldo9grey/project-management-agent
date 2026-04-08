#!/bin/bash
# 项目智能体定时推送脚本

# 激活虚拟环境
cd /home/ubuntu/.openclaw/workspace/project-agent/backend
source venv/bin/activate
export HF_ENDPOINT='https://hf-mirror.com'

# 获取token
TOKEN=$(curl -s -X POST "http://localhost:3000/api/agent/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=Yjy@2026pr" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

if [ -z "$TOKEN" ]; then
    echo "获取token失败"
    exit 1
fi

# 根据参数执行不同推送
case "$1" in
    morning)
        echo "执行早上预警推送..."
        curl -s -X POST "http://localhost:3000/api/agent/dashboard/test-morning-push" \
            -H "Authorization: Bearer $TOKEN"
        echo ""
        ;;
    afternoon)
        echo "执行下午日报提醒..."
        curl -s -X POST "http://localhost:3000/api/agent/dashboard/test-afternoon-push" \
            -H "Authorization: Bearer $TOKEN"
        echo ""
        ;;
    *)
        echo "用法: $0 {morning|afternoon}"
        exit 1
        ;;
esac
