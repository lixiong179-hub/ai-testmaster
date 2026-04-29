import requests
import json

# 模拟前端登录请求
def test_frontend_login():
    url = "http://localhost:8000/api/v1/auth/login"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    data = {
        "username": "admin",
        "password": "password123"
    }
    
    print("模拟前端登录请求...")
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Data: {json.dumps(data, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("\n✅ 登录成功!")
            print(f"Access Token: {response.json().get('data', {}).get('access_token')}")
        else:
            print("\n❌ 登录失败!")
    except Exception as e:
        print(f"\n❌ 请求失败: {str(e)}")

if __name__ == "__main__":
    test_frontend_login()
