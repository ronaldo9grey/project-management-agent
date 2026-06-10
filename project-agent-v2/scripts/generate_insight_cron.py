#!/usr/bin/env python3
"""AI洞察定时生成 - 供crontab调用"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/project-agent-v2/backend')

import httpx
import os
from datetime import datetime

def get_admin_token():
    config_file = "/home/ubuntu/.openclaw/workspace/project-agent-v2/scripts/.admin_token"
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            return f.read().strip()
    return None

def generate_insight(period: str) -> bool:
    token = get_admin_token()
    if not token:
        print(f"[{datetime.now()}] ❌ 未找到admin token")
        return False
    
    url = f"http://127.0.0.1:3001/agent/api/agent/dashboard/insight/generate?period={period}"
    
    print(f"[{datetime.now()}] 开始生成AI洞察，时段: {period}")
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers={"Authorization": f"Bearer {token}"})
        
        if response.status_code == 200:
            data = response.json()
            print(f"[{datetime.now()}] ✅ 生成成功，ID: {data.get('id')}")
            return True
        else:
            print(f"[{datetime.now()}] ❌ 失败: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as e:
        print(f"[{datetime.now()}] ❌ 异常: {e}")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", required=True, choices=["morning", "noon"])
    args = parser.parse_args()
    
    success = generate_insight(args.period)
    sys.exit(0 if success else 1)
