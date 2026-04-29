"""测试登录"""
import requests

BASE_URL = "http://localhost:8001/api/v1"

print("测试登录:")
response = requests.post(
    f"{BASE_URL}/auth/login",
    data={"username": "admin", "password": "test1234"}
)

print(f"状态码: {response.status_code}")
print(f"响应: {response.json()}")

if response.status_code == 200:
    token = response.json().get("data", {}).get("access_token")
    print(f"\nToken: {token[:30]}...")

    # 测试创建项目
    print("\n测试创建项目:")
    headers = {"Authorization": f"Bearer {token}"}
    project_data = {
        "name": f"API测试项目_{int(__import__('time').time())}",
        "description": "API集成测试",
        "project_type": "web"
    }
    response = requests.post(f"{BASE_URL}/project/create", json=project_data, headers=headers)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")

    if response.status_code == 200:
        project_id = response.json().get("data", {}).get("project_id")

        # 测试更新配置
        print("\n测试更新配置:")
        update_data = {
            "web_env_configs": {
                "test": {
                    "url": "https://test.example.com",
                    "username": "tester",
                    "password": "new_password"
                }
            }
        }
        response = requests.put(f"{BASE_URL}/project/{project_id}/config", json=update_data, headers=headers)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
