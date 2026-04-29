"""完整测试项目管理模块"""
import requests
import json

BASE_URL = "http://localhost:8001/api/v1"

# 1. 登录
print("=" * 60)
print("1. 登录")
response = requests.post(f"{BASE_URL}/auth/login", data={"username": "admin", "password": "test1234"})
token = response.json()["data"]["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"登录成功: {response.status_code == 200}")

# 2. 创建项目（带初始配置）
print("\n" + "=" * 60)
print("2. 创建项目（带初始配置）")
project_data = {
    "name": f"完整测试项目_{int(__import__('time').time())}",
    "description": "测试密码加密和配置合并",
    "project_type": "web",
    "web_env_configs": {
        "test": {"url": "https://test.com", "username": "user1", "password": "password1"},
        "prod": {"url": "https://prod.com", "username": "admin", "password": "password2"}
    }
}
response = requests.post(f"{BASE_URL}/project/create", json=project_data, headers=headers)
project_id = response.json()["data"]["project_id"]
print(f"创建项目: {response.status_code == 200}, ID={project_id}")

# 3. 验证初始密码已加密存储
print("\n" + "=" * 60)
print("3. 验证初始密码已加密存储")
response = requests.get(f"{BASE_URL}/project/{project_id}", headers=headers)
data = response.json()["data"]
test_password = data["web_env_configs"]["test"]["password"]
prod_password = data["web_env_configs"]["prod"]["password"]
print(f"test密码(解密后): {test_password}")
print(f"prod密码(解密后): {prod_password}")

# 4. 测试BugB - 验证双重加密防护
print("\n" + "=" * 60)
print("4. 测试BugB - 双重加密防护")
# 获取当前密码并再次更新
update_data = {
    "web_env_configs": {
        "test": {"url": "https://test.com", "username": "user1", "password": test_password}
    }
}
response = requests.put(f"{BASE_URL}/project/{project_id}/config", json=update_data, headers=headers)
response = requests.get(f"{BASE_URL}/project/{project_id}", headers=headers)
new_password = response.json()["data"]["web_env_configs"]["test"]["password"]
print(f"更新后密码: {new_password}")
print(f"密码一致性: {test_password == new_password}")
print(f"密码未被双重加密: {not new_password.startswith('gAAAAAgAAAA')}")

# 5. 测试BugE - 验证配置合并而非覆盖
print("\n" + "=" * 60)
print("5. 测试BugE - 配置合并")
# 只更新staging环境
update_data = {
    "web_env_configs": {
        "staging": {"url": "https://staging.com", "username": "stager", "password": "staging_pass"}
    }
}
response = requests.put(f"{BASE_URL}/project/{project_id}/config", json=update_data, headers=headers)
response = requests.get(f"{BASE_URL}/project/{project_id}", headers=headers)
all_configs = response.json()["data"]["web_env_configs"]
print(f"test环境保留: {'test' in all_configs}")
print(f"prod环境保留: {'prod' in all_configs}")
print(f"staging环境新增: {'staging' in all_configs}")
print(f"test密码仍正确: {all_configs['test']['password'] == 'password1'}")
print(f"prod密码仍正确: {all_configs['prod']['password'] == 'password2'}")

print("\n" + "=" * 60)
print("测试完成!")
