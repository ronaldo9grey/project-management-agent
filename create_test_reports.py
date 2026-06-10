#!/usr/bin/env python3
"""
使用智能解析 API 创建测试日报数据
"""
import json
import requests

BASE_URL = "http://localhost:8000/api/v1"
USERNAME = "0001"
PASSWORD = "Yjy@2026pr"

def login():
    """登录获取 token"""
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": USERNAME, "password": PASSWORD}
    )
    result = resp.json()
    if result.get("code") == 200:
        return result["data"]["access_token"]
    raise Exception(f"登录失败: {result}")

def smart_parse(token, text):
    """智能解析工作文本"""
    resp = requests.post(
        f"{BASE_URL}/ai-daily/smart-parse",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": text}
    )
    return resp.json()

def create_report(token, report_data, parse_result):
    """从解析结果创建日报"""
    work_items = parse_result["data"]["work_items"]
    
    # 为工作事项添加项目ID
    matched_projects = {p["name"]: p["id"] for p in parse_result["data"]["matched_projects"]}
    for item in work_items:
        if item["project_name"] in matched_projects:
            item["project_id"] = str(matched_projects[item["project_name"]])
    
    resp = requests.post(
        f"{BASE_URL}/ai-daily/create-from-parse",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "report_date": report_data["date"],
            "work_items": work_items,
            "work_target": report_data.get("work_target", ""),
            "tomorrow_plan": report_data.get("tomorrow_plan", "")
        }
    )
    return resp.json()

def main():
    print("=" * 60)
    print("智能解析日报测试")
    print("=" * 60)
    
    # 登录
    token = login()
    print(f"\n✅ 登录成功: {USERNAME}")
    
    # 读取测试数据
    with open("/home/ubuntu/.openclaw/workspace/test_daily_reports.json") as f:
        test_data = json.load(f)
    
    results = []
    for i, report in enumerate(test_data, 1):
        print(f"\n{'='*50}")
        print(f"📝 测试数据 {i}: {report['date']}")
        print(f"{'='*50}")
        print(f"原文: {report['text'][:50]}...")
        
        # 智能解析
        parse_result = smart_parse(token, report["text"])
        
        matched = parse_result["data"]["matched_projects"]
        unmatched = parse_result["data"]["unmatched_projects"]
        warnings = parse_result["data"]["warnings"]
        work_items = parse_result["data"]["work_items"]
        
        print(f"\n✅ 匹配项目 ({len(matched)}个):")
        for p in matched:
            print(f"   - [{p['id']}] {p['name']} (置信度: {p.get('confidence', 1.0)})")
        
        if unmatched:
            print(f"\n⚠️ 未匹配项目 ({len(unmatched)}个):")
            for p in unmatched:
                print(f"   - {p}")
        
        if warnings:
            print(f"\n⚠️ 警告信息:")
            for w in warnings:
                print(f"   - {w}")
        
        print(f"\n📋 工作事项 ({len(work_items)}个):")
        for item in work_items:
            print(f"   - [{item['project_name']}] {item['task_name'][:30]}...")
            print(f"     工时: {item['hours_spent']}h, 进度: {item['progress_percentage']}%")
        
        # 创建日报
        create_result = create_report(token, report, parse_result)
        if create_result.get("code") == 200:
            print(f"\n✅ 日报创建成功: ID={create_result['data']['report_id']}")
            results.append({"date": report["date"], "status": "success", "warnings": warnings})
        else:
            print(f"\n❌ 日报创建失败: {create_result.get('message')}")
            results.append({"date": report["date"], "status": "failed", "error": create_result.get("message")})
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    with_warnings = sum(1 for r in results if r.get("warnings"))
    
    print(f"✅ 成功: {success}")
    print(f"❌ 失败: {failed}")
    print(f"⚠️ 有警告: {with_warnings}")
    
    # 显示异常场景
    print("\n📋 异常场景详情:")
    for r in results:
        if r.get("warnings"):
            print(f"  {r['date']}: {len(r['warnings'])} 个警告")

if __name__ == "__main__":
    main()
