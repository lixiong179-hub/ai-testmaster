"""完整API测试脚本"""
import requests
import json

BASE_URL = "http://localhost:8000"

def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_health():
    print_section("健康检查")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.json()}")
        return True
    except Exception as e:
        print(f"错误: {e}")
        return False

def test_login():
    print_section("登录测试")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": "admin", "password": "password123"},
            timeout=5
        )
        print(f"状态码: {resp.status_code}")
        result = resp.json()
        print(f"响应: {json.dumps(result, ensure_ascii=False)[:200]}")
        if resp.status_code == 200 and result.get("data", {}).get("access_token"):
            return result["data"]["access_token"]
        return None
    except Exception as e:
        print(f"错误: {e}")
        return None

def test_api(token, name, method, endpoint, data=None, params=None):
    print(f"\n--- {name} ---")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        if method == "GET":
            resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=5)
        elif method == "POST":
            resp = requests.post(f"{BASE_URL}{endpoint}", headers=headers, json=data, timeout=5)
        elif method == "PUT":
            resp = requests.put(f"{BASE_URL}{endpoint}", headers=headers, json=data, timeout=5)
        elif method == "DELETE":
            resp = requests.delete(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=5)
        else:
            print(f"不支持的方法: {method}")
            return None, None

        print(f"方法: {method} {endpoint}")
        print(f"状态码: {resp.status_code}")

        try:
            result = resp.json()
            if resp.status_code >= 400:
                print(f"错误: {json.dumps(result, ensure_ascii=False)[:500]}")
            else:
                print(f"响应: {json.dumps(result, ensure_ascii=False)[:300]}")
        except:
            print(f"响应: {resp.text[:300]}")

        return resp.status_code, result
    except Exception as e:
        print(f"错误: {e}")
        return None, None

def main():
    print("=" * 60)
    print("  AI TestMaster 完整API测试")
    print("=" * 60)

    # 测试健康检查
    if not test_health():
        print("后端服务未启动！")
        return

    # 测试登录
    token = test_login()
    if not token:
        print("\n登录失败，无法继续测试！")
        return

    print(f"\n获取到Token: {token[:30]}...")

    # 测试项目API
    print_section("项目管理API")
    test_api(token, "项目列表", "GET", "/api/v1/project/list")
    test_api(token, "创建项目", "POST", "/api/v1/project/", data={
        "name": f"测试项目_{__import__('time').time():.0f}",
        "description": "这是一个测试项目",
        "project_type": "web"
    })

    # 测试测试用例API
    print_section("测试用例API")
    test_api(token, "用例列表", "GET", "/api/v1/test-case", params={"page": 1, "page_size": 10})

    # 测试测试任务API
    print_section("测试任务API")
    test_api(token, "任务列表", "GET", "/api/v1/test_task", params={"page": 1, "page_size": 10})

    # 测试报告API
    print_section("测试报告API")
    test_api(token, "报告列表", "GET", "/api/v1/report")

    # 测试文件API
    print_section("文件管理API")
    test_api(token, "文件列表", "GET", "/api/v1/file/list/3")

    # 测试用户API
    print_section("用户管理API")
    test_api(token, "用户列表", "GET", "/api/v1/user")
    test_api(token, "角色列表", "GET", "/api/v1/user/role")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
