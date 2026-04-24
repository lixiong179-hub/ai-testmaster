import requests
import json
import time

# 1. 登录获取token
login_url = "http://localhost:3000/api/v1/auth/login"
login_data = {
    "username": "admin",
    "password": "admin123"
}
print("正在登录...")
login_response = requests.post(login_url, json=login_data)
print(f"登录响应: {login_response.status_code}")
login_result = login_response.json()
print(f"登录结果: {json.dumps(login_result, indent=2, ensure_ascii=False)}")

if login_response.status_code != 200:
    print("登录失败！")
    exit(1)

token = login_result["data"]["access_token"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 2. 调用解析接口
parse_url = "http://localhost:3000/api/v1/ui-prototype/parse"
parse_data = {
    "screen_ids": [14]
}
print("\n正在调用解析接口...")
print(f"请求数据: {json.dumps(parse_data, ensure_ascii=False)}")

start_time = time.time()
parse_response = requests.post(parse_url, json=parse_data, headers=headers)
end_time = time.time()

print(f"\n解析响应: {parse_response.status_code}")
print(f"耗时: {end_time - start_time:.2f}秒")
print(f"响应内容: {json.dumps(parse_response.json(), indent=2, ensure_ascii=False)}")
