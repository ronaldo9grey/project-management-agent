#!/usr/bin/env python3
"""
AI洞察定时生成脚本

用法：
    python generate_insight.py --period morning   # 凌晨生成
    python generate_insight.py --period noon      # 中午生成
"""

import argparse
import httpx
import sys
from datetime import datetime

# API配置
API_BASE = "http://127.0.0.1:3001/agent/api/agent"
ADMIN_TOKEN = "your_admin_token_here"  # 需要替换为实际的admin token

def get_admin_token():
    """获取admin token（从环境变量或配置文件）"""
    import os
    
    # 优先从环境变量
    token = os.environ.get("ADMIN_TOKEN")
    if token:
        return token
    
    # 其次从配置文件
    config_file = "/home/ubuntu/.openclaw/workspace/project-agent-v2/scripts/.admin_token"
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            return f.read().strip()
    
    # 最后使用硬编码（仅用于测试，生产环境不推荐）
    return "test_token"


def generate_insight(period: str = "morning") -> bool:
    """
    调用API生成洞察
    
    参数：
    - period: "morning" 或 "noon"
    
    返回：是否成功
    """
    token = get_admin_token()
    url = f"{API_BASE}/dashboard/insight/generate?period={period}"
    
    print(f"[{datetime.now()}] 开始生成AI洞察，时段: {period}")
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
        
        if response.status_code == 200:
            data = response.json()
            print(f"[{datetime.now()}] ✅ 生成成功")
            print(f"    ID: {data.get('id')}")
            print(f"    时段: {data.get('period')}")
            print(f"    内容长度: {len(data.get('content', ''))}")
            return True
        else:
            print(f"[{datetime.now()}] ❌ 生成失败: {response.status_code}")
            print(f"    响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"[{datetime.now()}] ❌ 异常: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI洞察定时生成")
    parser.add_argument(
        "--period",
        choices=["morning", "noon"],
        default="morning",
        help="生成时段：morning 或 noon"
    )
    
    args = parser.parse_args()
    
    success = generate_insight(args.period)
    sys.exit(0 if success else 1)
