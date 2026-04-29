import requests
import json

# 测试测试用例API
def test_case_api():
    base_url = "http://localhost:8000"
    
    # 先登录获取token
    login_url = f"{base_url}/api/v1/auth/login"
    login_data = {
        "username": "admin",
        "password": "password123"
    }
    
    print("1. 登录获取token...")
    try:
        response = requests.post(login_url, json=login_data)
        print(f"登录响应: {response.status_code}")
        print(f"登录数据: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            token = response.json().get('data', {}).get('access_token')
            print(f"获取到token: {token[:20]}...")
            
            # 测试获取测试用例列表
            headers = {
                "Authorization": f"Bearer {token}"
            }
            
            # 测试不同的API路径
            paths = [
                "/api/v1/case/",
                "/api/v1/case",
                "/case/",
                "/case"
            ]
            
            for path in paths:
                url = f"{base_url}{path}"
                print(f"\n2. 测试API路径: {url}")
                try:
                    response = requests.get(url, headers=headers, params={"page": 1, "page_size": 20})
                    print(f"响应状态码: {response.status_code}")
                    print(f"响应内容: {json.dumps(response.json(), indent=2)[:200]}...")
                except Exception as e:
                    print(f"请求失败: {str(e)}")
        else:
            print("登录失败!")
    except Exception as e:
        print(f"登录请求失败: {str(e)}")

if __name__ == "__main__":
    test_case_api()
