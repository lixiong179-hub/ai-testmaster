"""
Comprehensive API test script to find bugs in the backend
"""
import requests
import json

BASE_URL = 'http://127.0.0.1:8000/api/v1'

# Login first
print('='*60)
print('STEP 1: Login')
print('='*60)
login_data = {'username': 'admin', 'password': 'admin123'}
r = requests.post(f'{BASE_URL}/auth/login', data=login_data, timeout=10)
print(f'Status: {r.status_code}')

if r.status_code != 200:
    print(f'Login failed: {r.text}')
    exit(1)

data = r.json()
token = data['data']['access_token']
headers = {'Authorization': f'Bearer {token}'}
print(f'Login successful! Token: {token[:30]}...')
print()

# Test each API endpoint
def test_endpoint(method, path, name, data=None, params=None):
    print('-'*60)
    print(f'TEST: {name}')
    print(f'Method: {method} | Path: {path}')
    print('-'*60)

    try:
        if method == 'GET':
            r = requests.get(f'{BASE_URL}{path}', headers=headers, params=params, timeout=10)
        elif method == 'POST':
            r = requests.post(f'{BASE_URL}{path}', headers=headers, json=data, timeout=10)
        elif method == 'PUT':
            r = requests.put(f'{BASE_URL}{path}', headers=headers, json=data, timeout=10)
        elif method == 'DELETE':
            r = requests.delete(f'{BASE_URL}{path}', headers=headers, timeout=10)

        print(f'Status: {r.status_code}')
        print(f'Response: {r.text[:800]}')

        if r.status_code >= 400:
            print(f'ERROR: {r.text[:500]}')
            return False
        return True
    except Exception as e:
        print(f'EXCEPTION: {str(e)}')
        return False
    finally:
        print()

# Test project endpoints
print('='*60)
print('TESTING: Project Endpoints')
print('='*60)

test_endpoint('GET', '/project/list', 'Get Project List')
test_endpoint('GET', '/project/3', 'Get Project Detail')  # Use an existing project ID
test_endpoint('POST', '/project', 'Create Project', {'name': 'Test Project 2', 'description': 'Test'})

# Test file endpoints
print('='*60)
print('TESTING: File Endpoints')
print('='*60)

test_endpoint('GET', '/file/list', 'Get File List')
test_endpoint('GET', '/file/1', 'Get File Detail')

# Test task endpoints (using correct path: /test_task not /test-task)
print('='*60)
print('TESTING: Task Endpoints')
print('='*60)

test_endpoint('GET', '/test_task', 'Get Task List')
test_endpoint('GET', '/test_task/1', 'Get Task Detail')

# Test test point endpoints
print('='*60)
print('TESTING: Test Point Endpoints')
print('='*60)

test_endpoint('GET', '/test-point/list', 'Get Test Point List')

# Test user endpoints
print('='*60)
print('TESTING: User Endpoints')
print('='*60)

test_endpoint('GET', '/user/me', 'Get Current User')
test_endpoint('GET', '/user/list', 'Get User List')

# Test report endpoints
print('='*60)
print('TESTING: Report Endpoints')
print('='*60)

test_endpoint('GET', '/report/list?project_id=3', 'Get Report List')

# Test test-case endpoints
print('='*60)
print('TESTING: Test Case Endpoints')
print('='*60)

test_endpoint('GET', '/test-case?project_id=3', 'Get Test Case List')

print('='*60)
print('TEST COMPLETE')
print('='*60)
