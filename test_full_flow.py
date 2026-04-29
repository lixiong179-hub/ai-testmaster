"""
完整测试 AI 生成测试用例流程
"""
import requests
import json
import time

BASE_URL = 'http://localhost:8000'

print("="*60)
print("AI TestMaster - Full Flow Test")
print("="*60)

# 1. 登录
print("\n[Step 1] Login")
resp = requests.post(
    f'{BASE_URL}/api/v1/auth/login',
    data={'username': 'admin', 'password': 'password123'}
)
if resp.status_code != 200:
    print("Login failed!")
    exit(1)

token = resp.json()['data']['access_token']
headers = {"Authorization": f"Bearer {token}"}
print(f"Login OK! Token: {token[:50]}...")

# 2. 获取项目
print("\n[Step 2] Get Project")
resp = requests.get(f'{BASE_URL}/api/v1/project/list', headers=headers)
print(f"Projects: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    if 'data' in data and 'items' in data['data']:
        projects = data['data']['items']
        if projects:
            project_id = projects[0]['id']
            print(f"Found project: ID={project_id}, Name={projects[0]['name']}")
        else:
            print("No projects, creating one...")
            resp = requests.post(f'{BASE_URL}/api/v1/project/create',
                json={"name": f"TestProject_{int(time.time())}", "description": "Test"},
                headers=headers)
            project_id = resp.json()['data']['project_id']
            print(f"Created project: ID={project_id}")
    else:
        project_id = None
        print("Unexpected response format")
else:
    project_id = None

if not project_id:
    print("Cannot get/create project!")
    exit(1)

# 3. 测试需求链接API
print("\n[Step 3] Test Requirement Link API")
resp = requests.get(f'{BASE_URL}/api/v1/requirement-link/list/{project_id}', headers=headers)
print(f"Requirement links: {resp.status_code}")
if resp.status_code == 200:
    print(f"Response: {resp.text[:300]}")
else:
    print(f"Error: {resp.text[:200]}")

# 4. 测试 AI 生成测试用例
print("\n[Step 4] Test AI Generate Test Cases")
print("Note: This may take a while (DeepSeek API call)...")

generate_data = {
    "project_id": project_id,
    "description": "Test user login functionality: username/password validation, error handling",
    "case_type": "功能测试",
    "priority": 1
}

try:
    resp = requests.post(
        f'{BASE_URL}/api/v1/test-case/ai-generate',
        json=generate_data,
        headers=headers,
        timeout=180
    )
    print(f"AI Generate: {resp.status_code}")
    print(f"Response: {json.dumps(resp.json(), ensure_ascii=False, indent=2)[:1000]}")
except Exception as e:
    print(f"Error: {e}")
