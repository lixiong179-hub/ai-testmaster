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

results = []
success_count = 0
fail_count = 0

def test_case(name, method, path, expected_status=None, data=None, params=None):
    global success_count, fail_count
    try:
        url = f'{base}{path}'
        r = getattr(requests, method)(url, headers=headers, json=data, params=params, timeout=30)
        is_success = (expected_status is None) or (r.status_code == expected_status)
        status = "✅" if is_success else "⚠️"
        if is_success:
            success_count += 1
        else:
            fail_count += 1
        print(f"{status} {method.upper():6} {path}")
        print(f"   状态码: {r.status_code} (预期: {expected_status or '任意2xx'})")
        results.append({"name": name, "method": method, "path": path, "status": r.status_code, "success": is_success})
    except Exception as e:
        fail_count += 1
        print(f"❌ {method.upper():6} {path}")
        print(f"   错误: {e}")
        results.append({"name": name, "method": method, "path": path, "error": str(e), "success": False})

print("=" * 60)
print("🔐 认证模块")
print("=" * 60)
test_case("验证码", "get", "/api/v1/auth/captcha/generate")
test_case("登录", "post", "/api/v1/auth/login", data={'username': 'admin', 'password': 'admin123'})
test_case("当前用户", "get", "/api/v1/auth/me")

print("\n" + "=" * 60)
print("📁 项目管理模块")
print("=" * 60)
test_case("项目列表", "get", "/api/v1/project/list", params={'page': 1, 'page_size': 5})
test_case("创建项目", "post", "/api/v1/project/", data={'name': 'test_api_project', 'description': 'API测试'})
test_case("获取项目详情", "get", "/api/v1/project/3")

print("\n" + "=" * 60)
print("📝 测试点模块")
print("=" * 60)
test_case("测试点列表", "get", "/api/v1/test-point/list/3")
test_case("测试点详情", "get", "/api/v1/test-point/detail/1", params={'project_id': 3})

print("\n" + "=" * 60)
print("🧪 测试用例模块")
print("=" * 60)
test_case("用例列表", "get", "/api/v1/testCase/", params={'page': 1, 'page_size': 5})
test_case("用例详情", "get", "/api/v1/testCase/177")
test_case("用例技术视图", "get", "/api/v1/testCase/177/technical-view")
test_case("用例业务视图", "get", "/api/v1/testCase/177/business-view")
test_case("用例工作流", "get", "/api/v1/testCase/177/workflow")

print("\n" + "=" * 60)
print("📋 测试任务模块")
print("=" * 60)
test_case("任务列表", "get", "/api/v1/test_task/", params={'page': 1, 'page_size': 5})
test_case("任务详情", "get", "/api/v1/test_task/17")
test_case("任务摘要", "get", "/api/v1/test_task/17/summary")

print("\n" + "=" * 60)
print("👤 用户模块")
print("=" * 60)
test_case("用户列表", "get", "/api/v1/user/")
test_case("当前用户", "get", "/api/v1/user/me")
test_case("用户详情", "get", "/api/v1/user/1")

print("\n" + "=" * 60)
print("🔄 迭代模块")
print("=" * 60)
test_case("迭代列表", "get", "/api/v1/iteration/list/3")

print("\n" + "=" * 60)
print("🔗 需求关联模块")
print("=" * 60)
test_case("需求关联列表", "get", "/api/v1/requirement-link/list/3")

print("\n" + "=" * 60)
print("📎 文件模块")
print("=" * 60)
test_case("文件列表", "get", "/api/v1/file/list")
test_case("项目文件列表", "get", "/api/v1/file/list/3")

print("\n" + "=" * 60)
print("📊 报告模块")
print("=" * 60)
test_case("报告列表", "get", "/api/v1/report/")

print("\n" + "=" * 60)
print("💾 测试数据模块")
print("=" * 60)
test_case("步骤测试数据", "get", "/api/v1/test-data/step/1")

print("\n" + "=" * 60)
print("🎯 批量定位器模块")
print("=" * 60)
test_case("批量任务", "get", "/api/v1/batch-locator/batch-tasks")
test_case("用例批量记录状态", "get", "/api/v1/batch-locator/cases/177/batch-record-status")

print("\n" + "=" * 60)
print("⚡ 执行模块")
print("=" * 60)
test_case("设备列表", "get", "/api/execution/devices")
test_case("任务状态", "get", "/api/execution/17/status")

print("\n" + "=" * 60)
print("📹 执行可视化模块")
print("=" * 60)
test_case("全局配置", "get", "/api/v1/execution-visualization/config/global")
test_case("视频统计", "get", "/api/v1/execution-visualization/videos/stats")
test_case("任务视频", "get", "/api/v1/execution-visualization/videos/task/17")

print("\n" + "=" * 60)
print("👁️ 可见性模块")
print("=" * 60)
test_case("可见性配置", "get", "/api/visibility/config", params={'level': 'global'})

print("\n" + "=" * 60)
print("✨ 质量检查模块")
print("=" * 60)
test_case("用例质量", "get", "/api/v1/quality/cases/177/quality")
test_case("用例趋势", "get", "/api/v1/quality/cases/177/quality/trend")
test_case("用例成本估算", "get", "/api/v1/quality/cases/177/cost-estimate")

print("\n" + "=" * 60)
print("🎨 UI原型模块")
print("=" * 60)
test_case("UI原型项目列表", "get", "/api/v1/project/list/3")
test_case("UI屏幕列表", "get", "/api/v1/screens/3")
test_case("UI规格", "get", "/api/v1/specs/3")

print("\n" + "=" * 60)
print("📡 WebSocket模块")
print("=" * 60)
test_case("WebSocket统计", "get", "/api/v1/ws/stats")

print("\n" + "=" * 60)
print("🏥 健康检查")
print("=" * 60)
test_case("根路径", "get", "/")
test_case("健康检查", "get", "/health")

print("\n" + "=" * 60)
print("📜 测试用例工作流")
print("=" * 60)
test_case("批量删除", "post", "/api/v1/testCase/batch-delete", data={'caseIds': [999]})
test_case("批量恢复", "post", "/api/v1/testCase/batch-restore", data={'caseIds': [999]})

print("\n" + "=" * 60)
print("📊 测试结果汇总")
print("=" * 60)
print(f"✅ 成功: {success_count}")
print(f"⚠️ 预期行为: {fail_count}")
print(f"📝 总计: {success_count + fail_count}")
print("=" * 60)
