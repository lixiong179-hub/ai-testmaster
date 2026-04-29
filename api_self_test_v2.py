import requests
import json

base = 'http://localhost:8000'

def get_token():
    r = requests.post(f'{base}/api/v1/auth/login', json={'username': 'admin', 'password': 'admin123'}, timeout=10)
    data = r.json()
    if 'data' in data and 'access_token' in data['data']:
        return data['data']['access_token']
    print(f"获取Token失败: {data}")
    return None

token = get_token()
if not token:
    print("无法获取Token，退出")
    exit(1)

headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

print(f"Token: {token[:30]}...")

print("\n=== 认证模块 ===")
print("\n1. GET /api/v1/auth/me")
r = requests.get(f'{base}/api/v1/auth/me', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 项目管理模块 ===")
print("\n2. GET /api/v1/project/list")
r = requests.get(f'{base}/api/v1/project/list', headers=headers, params={'page': 1, 'page_size': 10})
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:300]}")

print("\n=== 测试点模块 ===")
print("\n3. GET /api/v1/test-point/list/1")
r = requests.get(f'{base}/api/v1/test-point/list/1', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 测试用例模块 ===")
print("\n4. GET /api/v1/testCase/")
r = requests.get(f'{base}/api/v1/testCase/', headers=headers, params={'page': 1, 'page_size': 10})
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 测试任务模块 ===")
print("\n5. GET /api/v1/test_task/")
r = requests.get(f'{base}/api/v1/test_task/', headers=headers, params={'page': 1, 'page_size': 10})
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 用户模块 ===")
print("\n6. GET /api/v1/user/me")
r = requests.get(f'{base}/api/v1/user/me', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 迭代模块 ===")
print("\n7. GET /api/v1/iteration/list/1 (需要项目属于当前用户)")
r = requests.get(f'{base}/api/v1/iteration/list/1', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 需求关联模块 ===")
print("\n8. GET /api/v1/requirement-link/list/1 (需要项目属于当前用户)")
r = requests.get(f'{base}/api/v1/requirement-link/list/1', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 文件模块 ===")
print("\n9. GET /api/v1/file/list")
r = requests.get(f'{base}/api/v1/file/list', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 报告模块 ===")
print("\n10. GET /api/v1/report/")
r = requests.get(f'{base}/api/v1/report/', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 测试数据模块 ===")
print("\n11. GET /api/v1/test-data/999 (不存在的ID)")
r = requests.get(f'{base}/api/v1/test-data/999', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 批量定位器模块 ===")
print("\n12. GET /api/v1/batch-locator/batch-tasks")
r = requests.get(f'{base}/api/v1/batch-locator/batch-tasks', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 执行模块 ===")
print("\n13. GET /api/execution/devices")
r = requests.get(f'{base}/api/execution/devices', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 执行可视化模块 ===")
print("\n14. GET /api/v1/execution-visualization/config/global")
r = requests.get(f'{base}/api/v1/execution-visualization/config/global', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n15. GET /api/v1/execution-visualization/videos/stats")
r = requests.get(f'{base}/api/v1/execution-visualization/videos/stats', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 可见性模块 ===")
print("\n16. GET /api/visibility/config?level=global")
r = requests.get(f'{base}/api/visibility/config', headers=headers, params={'level': 'global'})
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 质量检查模块 ===")
print("\n17. GET /api/v1/quality/cases/999/quality (不存在的用例)")
r = requests.get(f'{base}/api/v1/quality/cases/999/quality', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== UI原型模块 ===")
print("\n18. GET /api/v1/project (检查UI原型项目路由)")
r = requests.get(f'{base}/api/v1/project', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== WebSocket模块 ===")
print("\n19. GET /api/v1/ws/stats")
r = requests.get(f'{base}/api/v1/ws/stats', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 健康检查 ===")
print("\n20. GET /")
r = requests.get(f'{base}/')
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n21. GET /health")
r = requests.get(f'{base}/health')
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n=== 测试用例工作流 ===")
print("\n22. POST /api/v1/testCase/batch-delete")
r = requests.post(f'{base}/api/v1/testCase/batch-delete', headers=headers, json={'caseIds': [999]})
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n23. POST /api/v1/testCase/batch-restore")
r = requests.post(f'{base}/api/v1/testCase/batch-restore', headers=headers, json={'caseIds': [999]})
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n" + "=" * 60)
print("API自测完成!")
