"""
测试登录和完整的AI生成测试用例流程
"""
import requests
import json
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = 'http://localhost:8000'
HEADERS = {"Content-Type": "application/json"}


def print_step(step, msg):
    print(f"\n{'='*60}")
    print(f"Step {step}: {msg}")
    print('='*60)


def test_login():
    """Test login"""
    print_step(1, "User Login")

    # Try test1234 first (confirmed correct password)
    passwords = ['test1234', 'admin', 'admin123', 'password', 'password123', 'test123', 'admin888', 'root']

    for pwd in passwords:
        data = {'username': 'admin', 'password': pwd}
        try:
            resp = requests.post(f'{BASE_URL}/api/v1/auth/login', data=data)
            print(f"  Try '{pwd}': {resp.status_code}")
            if resp.status_code == 200:
                result = resp.json()
                if 'data' in result and 'access_token' in result['data']:
                    token = result['data']['access_token']
                    print(f"SUCCESS! Password found: {pwd}")
                    with open('.test_token', 'w') as f:
                        f.write(token)
                    return token
        except Exception as e:
            print(f"  Try {pwd}: {e}")

    return None


def test_project(token):
    """Test project"""
    print_step(2, "Get/Create Project")

    headers = {"Authorization": f"Bearer {token}"}

    # Get project list
    try:
        resp = requests.get(f'{BASE_URL}/api/v1/project/list', headers=headers)
        print(f"Get projects: {resp.status_code}")
        if resp.status_code == 200:
            result = resp.json()
            print(f"Response: {json.dumps(result, ensure_ascii=False)[:300]}")
            if 'data' in result and 'items' in result['data']:
                projects = result['data']['items']
                if projects:
                    print(f"Found {len(projects)} projects")
                    return projects[0]['id']
    except Exception as e:
        print(f"Get projects failed: {e}")

    # Create new project
    print("Creating new project...")
    project_data = {
        "name": f"TestProject_{int(time.time())}",
        "description": "AI Test Case Generation Project",
        "project_type": "web"
    }
    try:
        resp = requests.post(f'{BASE_URL}/api/v1/project/create', json=project_data, headers=headers)
        print(f"Create project: {resp.status_code}")
        if resp.status_code == 200:
            result = resp.json()
            print(f"Response: {json.dumps(result, ensure_ascii=False)[:300]}")
            if 'data' in result and 'project_id' in result['data']:
                project_id = result['data']['project_id']
                print(f"Project created! ID: {project_id}")
                return project_id
    except Exception as e:
        print(f"Create project failed: {e}")

    return None


def test_ai_generate(token, project_id):
    """Test AI generate test cases"""
    print_step(3, "AI Generate Test Cases")

    headers = {"Authorization": f"Bearer {token}"}

    # Check requirement link API
    print("\n3.1 Check requirement link API...")
    try:
        resp = requests.get(f'{BASE_URL}/api/v1/requirement-link/list/{project_id}', headers=headers)
        print(f"  Requirement links: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  {resp.text[:200]}")
    except Exception as e:
        print(f"  Failed: {e}")

    # AI generate test cases
    print("\n3.2 Call AI generate API...")
    generate_data = {
        "project_id": project_id,
        "description": "Test user login functionality",
        "case_type": "功能测试",
        "priority": 1
    }
    try:
        resp = requests.post(
            f'{BASE_URL}/api/v1/test-case/ai-generate',
            json=generate_data,
            headers=headers,
            timeout=120
        )
        print(f"  Status: {resp.status_code}")
        result = resp.json()
        print(f"  Response: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
        return result
    except requests.exceptions.Timeout:
        print("  Request timeout (AI generation may take longer)")
        return None
    except Exception as e:
        print(f"  Failed: {e}")
        return None


def main():
    print("="*60)
    print("  AI TestMaster - Test Case Generation Flow Test")
    print("="*60)

    # 1. Login
    token = test_login()
    if not token:
        print("\n[FAIL] Login failed, stopping test")
        return

    # 2. Get/Create project
    project_id = test_project(token)
    if not project_id:
        print("\n[FAIL] Cannot get/create project, stopping test")
        return

    # 3. AI generate test cases
    result = test_ai_generate(token, project_id)

    print("\n" + "="*60)
    print("  Test Complete")
    print("="*60)


if __name__ == "__main__":
    main()
