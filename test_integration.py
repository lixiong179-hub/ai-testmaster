"""API集成测试"""
import requests

BASE_URL = "http://localhost:8000/api/v1"

# 登录获取token
print("=" * 50)
print("1. 登录测试")
response = requests.post(
    f"{BASE_URL}/auth/login",
    data={"username": "admin", "password": "test1234"}
)
print(f"状态码: {response.status_code}")
data = response.json()
token = data.get("data", {}).get("access_token")
print(f"Token获取: {'成功' if token else '失败'}")
headers = {"Authorization": f"Bearer {token}"}

# 测试获取项目列表
print("\n" + "=" * 50)
print("2. 获取项目列表")
response = requests.get(f"{BASE_URL}/project/list", headers=headers)
print(f"状态码: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"项目数量: {len(data.get('data', {}).get('items', []))}")

# 测试创建项目
print("\n" + "=" * 50)
print("3. 创建项目")
import time
project_data = {
    "name": f"API测试项目_{int(time.time())}",
    "description": "API集成测试创建",
    "project_type": "web"
}
response = requests.post(f"{BASE_URL}/project/create", json=project_data, headers=headers)
print(f"状态码: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    project_id = data.get("data", {}).get("project_id")
    print(f"项目ID: {project_id}")

# 测试获取任务列表
print("\n" + "=" * 50)
print("4. 获取任务列表")
response = requests.get(f"{BASE_URL}/test_task", headers=headers)
print(f"状态码: {response.status_code}")

# 测试创建任务
print("\n" + "=" * 50)
print("5. 创建测试任务")
task_data = {
    "project_id": project_id if response.status_code != 200 else 1,
    "task_name": f"API测试任务_{int(time.time())}",
    "description": "API集成测试",
    "case_ids": []
}
response = requests.post(f"{BASE_URL}/test_task", json=task_data, headers=headers)
print(f"状态码: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    task_id = data.get("data", {}).get("task_id")
    print(f"任务ID: {task_id}")

print("\n" + "=" * 50)
print("API集成测试完成!")
