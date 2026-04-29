# -*- coding: utf-8 -*-
import pymysql
import requests
import json

# 数据库连接
conn = pymysql.connect(host='localhost', user='root', password='test1234', database='ai_testmaster', charset='utf8mb4')
cursor = conn.cursor()

print("=" * 60)
print("【项目ID:3 - 智慧园区测试点分析】")
print("=" * 60)

# 查询测试点 (注意: function是保留字，需要用反引号)
cursor.execute("SELECT id, module, `function`, `point`, priority FROM test_points WHERE project_id=3")
points = cursor.fetchall()
print(f"\n共有 {len(points)} 个测试点:\n")

# 按模块分组
modules = {}
for p in points:
    module = p[1]
    if module not in modules:
        modules[module] = []
    modules[module].append({"id": p[0], "function": p[2], "point": p[3], "priority": p[4]})

for module, items in modules.items():
    print(f"【{module}】({len(items)}个测试点)")
    for item in items:
        priority_text = {1: "高", 2: "中", 3: "低"}.get(item['priority'], "未知")
        print(f"  [{item['id']}] {item['function']} - {item['point'][:50]}... (优先级:{priority_text})")
    print()

# 优先级统计
priority_stats = {1: 0, 2: 0, 3: 0}
for p in points:
    priority_stats[p[4]] = priority_stats.get(p[4], 0) + 1
print("优先级分布:")
print(f"  高(1): {priority_stats[1]}个")
print(f"  中(2): {priority_stats[2]}个")
print(f"  低(3): {priority_stats[3]}个")

conn.close()

print("\n" + "=" * 60)
print("【API认证测试】")
print("=" * 60)

# 测试登录API
try:
    response = requests.post(
        "http://localhost:8000/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=10
    )
    print(f"\n登录API响应:")
    print(f"  状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"  响应数据: {json.dumps(data, ensure_ascii=False)[:200]}...")
        if data.get("code") == 200 and data.get("data", {}).get("access_token"):
            token = data["data"]["access_token"]
            print(f"  Token获取成功: {token[:30]}...")
            
            # 测试获取项目列表
            print("\n" + "=" * 60)
            print("【获取项目列表API测试】")
            print("=" * 60)
            headers = {"Authorization": f"Bearer {token}"}
            proj_response = requests.get("http://localhost:8000/api/v1/project/list", headers=headers, timeout=10)
            print(f"\n项目列表API响应:")
            print(f"  状态码: {proj_response.status_code}")
            if proj_response.status_code == 200:
                proj_data = proj_response.json()
                print(f"  总数: {proj_data.get('data', {}).get('total', 0)}")
                items = proj_data.get('data', {}).get('items', [])
                print(f"  前5个:")
                for item in items[:5]:
                    print(f"    - {item['name']} (ID:{item['id']}, 类型:{item['project_type']})")
    else:
        print(f"  错误: {response.text[:200]}")
except Exception as e:
    print(f"  请求失败: {e}")
