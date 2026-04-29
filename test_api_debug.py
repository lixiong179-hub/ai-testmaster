"""测试后端API接口"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.json()}")
        return True
    except Exception as e:
        print(f"错误: {e}")
        return False

def test_login():
    """测试登录"""
    print("\n=== 测试登录 ===")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": "admin", "password": "password123"},
            timeout=5
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.json()}")
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("access_token")
        return None
    except Exception as e:
        print(f"错误: {e}")
        return None

def test_api(token, endpoint, method="GET", data=None, params=None):
    """测试API"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        if method == "GET":
            resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params, timeout=5)
        else:
            resp = requests.post(f"{BASE_URL}{endpoint}", headers=headers, json=data, timeout=5)
        return resp.status_code, resp.json()
    except Exception as e:
        return None, {"error": str(e)}

def test_projects(token):
    """测试项目API"""
    print("\n=== 测试项目列表 ===")
    code, resp = test_api(token, "/api/v1/projects")
    print(f"状态码: {code}")
    print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)[:500]}")
    return code, resp

def test_requirements(token):
    """测试需求API"""
    print("\n=== 测试需求列表 ===")
    code, resp = test_api(token, "/api/v1/requirement-links")
    print(f"状态码: {code}")
    print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)[:500]}")
    return code, resp

def test_test_cases(token):
    """测试用例API"""
    print("\n=== 测试用例列表 ===")
    code, resp = test_api(token, "/api/v1/test-cases", params={"page": 1, "page_size": 10})
    print(f"状态码: {code}")
    print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)[:500]}")
    return code, resp

def test_tasks(token):
    """测试任务API"""
    print("\n=== 测试任务列表 ===")
    code, resp = test_api(token, "/api/v1/test-tasks")
    print(f"状态码: {code}")
    print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)[:500]}")
    return code, resp

def test_reports(token):
    """测试报告API"""
    print("\n=== 测试报告列表 ===")
    code, resp = test_api(token, "/api/v1/reports")
    print(f"状态码: {code}")
    print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)[:500]}")
    return code, resp

def test_users(token):
    """测试用户API"""
    print("\n=== 测试用户列表 ===")
    code, resp = test_api(token, "/api/v1/users")
    print(f"状态码: {code}")
    print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)[:500]}")
    return code, resp

if __name__ == "__main__":
    print("=" * 60)
    print("AI TestMaster API 测试")
    print("=" * 60)

    # 测试健康检查
    test_health()

    # 测试登录
    token = test_login()
    if not token:
        print("\n登录失败，无法继续测试其他接口")
        exit(1)

    print(f"\n获取到Token: {token[:20]}...")

    # 测试各个API
    test_projects(token)
    test_requirements(token)
    test_test_cases(token)
    test_tasks(token)
    test_reports(token)
    test_users(token)

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
