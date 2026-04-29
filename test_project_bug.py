"""项目管理模块Bug测试脚本"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

# 1. 登录
print("=" * 50)
print("1. 登录获取Token")
response = requests.post(
    f"{BASE_URL}/auth/login",
    data={"username": "admin", "password": "test1234"}
)
data = response.json()
token = data.get("data", {}).get("access_token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print(f"Token: {token[:20]}..." if token else "获取失败")
print(f"状态码: {response.status_code}")

# 2. 创建测试项目
print("\n" + "=" * 50)
print("2. 创建测试项目")
project_data = {
    "name": f"Bug测试项目_{int(__import__('time').time())}",
    "description": "用于测试项目管理Bug",
    "project_type": "web",
    "web_env_configs": {
        "test": {
            "url": "https://test.example.com",
            "username": "tester",
            "password": "original_password"
        }
    }
}
response = requests.post(f"{BASE_URL}/project/create", json=project_data, headers=headers)
print(f"创建项目响应: {response.status_code}")
result = response.json()
print(f"响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")

if result.get("code") != 200:
    print("创建项目失败，跳过后续测试")
    exit(1)

project_id = result.get("data", {}).get("project_id")
print(f"项目ID: {project_id}")

# 3. 测试假设B: 更新配置时密码是否被双重加密
print("\n" + "=" * 50)
print("3. 测试假设B: 更新配置（测试双重加密）")
update_data = {
    "web_env_configs": {
        "test": {
            "url": "https://test.example.com",
            "username": "tester",
            "password": "new_password_after_update"
        }
    }
}
response = requests.put(
    f"{BASE_URL}/project/{project_id}/config",
    json=update_data,
    headers=headers
)
print(f"更新配置响应: {response.status_code}")
result = response.json()
print(f"响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")

# 4. 再次更新，传入已经是加密格式的密码
print("\n" + "=" * 50)
print("4. 测试假设B: 再次更新（传入已加密的密码）")

# 获取当前配置（密码应该是解密后的）
current_password = result.get("data", {}).get("web_env_configs", {}).get("test", {}).get("password")
print(f"当前密码: {current_password}")

update_data2 = {
    "web_env_configs": {
        "test": {
            "url": "https://test.example.com",
            "username": "tester",
            "password": current_password  # 传入解密后的密码
        }
    }
}
response = requests.put(
    f"{BASE_URL}/project/{project_id}/config",
    json=update_data2,
    headers=headers
)
print(f"再次更新响应: {response.status_code}")
result2 = response.json()
print(f"响应内容: {json.dumps(result2, indent=2, ensure_ascii=False)}")

# 5. 测试假设E: 配置更新是否完全覆盖
print("\n" + "=" * 50)
print("5. 测试假设E: 配置更新是否完全覆盖")

# 只更新一个环境，查看其他环境是否被清空
update_data3 = {
    "web_env_configs": {
        "staging": {
            "url": "https://staging.example.com",
            "username": "stager",
            "password": "staging_password"
        }
    }
}
response = requests.put(
    f"{BASE_URL}/project/{project_id}/config",
    json=update_data3,
    headers=headers
)
print(f"只更新staging环境: {response.status_code}")
result3 = response.json()

# 获取完整配置，查看test环境是否还在
response = requests.get(f"{BASE_URL}/project/{project_id}", headers=headers)
full_result = response.json()
print(f"获取完整配置: {response.status_code}")
print(f"完整配置: {json.dumps(full_result.get('data', {}).get('web_env_configs'), indent=2, ensure_ascii=False)}")

if full_result.get("data", {}).get("web_env_configs"):
    web_configs = full_result["data"]["web_env_configs"]
    print(f"\ntest环境是否存在: {'test' in web_configs}")
    print(f"staging环境是否存在: {'staging' in web_configs}")

print("\n" + "=" * 50)
print("测试完成!")
