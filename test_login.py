import requests

BASE_URL = 'http://localhost:8000'

# 测试登录
print('='*50)
print('1. 测试登录 (admin/admin123)')
print('='*50)

data = {'username': 'admin', 'password': 'admin123'}
try:
    resp = requests.post(f'{BASE_URL}/api/v1/auth/login', data=data)
    print(f'Status: {resp.status_code}')
    result = resp.json()
    print(f'Response: {result}')

    if 'data' in result and 'access_token' in result['data']:
        token = result['data']['access_token']
        print(f'Token获取成功')

        # 保存token供后续使用
        with open('.test_token', 'w') as f:
            f.write(token)
        print('Token已保存')
    else:
        print('Token获取失败')
except Exception as e:
    print(f'Error: {e}')
