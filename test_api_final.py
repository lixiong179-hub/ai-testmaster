import requests
import json

print("=== 最终测试 API ===")

# 登录
resp = requests.post("http://localhost:8000/api/v1/auth/login", 
    json={"username": "admin", "password": "admin123"}, timeout=5)
print(f"登录: {resp.status_code}")

if resp.status_code == 200:
    token = resp.json()["data"]["access_token"]
    
    # 调用解析 API - 使用 screen 14
    resp = requests.post("http://localhost:8000/api/v1/ui-prototype/parse",
        json={"screen_ids": [14], "prototype_project_id": 2, "parse_mode": "text"},
        headers={"Authorization": f"Bearer {token}"}, timeout=30)
    
    print(f"解析: {resp.status_code}")
    result = resp.json()
    print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
    
    if result.get("data"):
        d = result["data"]
        print(f"\n解析结果: 成功={d.get('success')}, 失败={d.get('failed')}")
        for r in d.get('results', []):
            print(f"  屏幕 {r['screen_id']}: success={r['success']}, message={r['message']}")