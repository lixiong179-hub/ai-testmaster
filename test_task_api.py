import requests
import json

# 测试测试任务API
def test_task_api():
    base_url = "http://localhost:8001"
    
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
            
            # 测试创建测试任务
            headers = {
                "Authorization": f"Bearer {token}"
            }
            
            # 先创建一个项目
            project_url = f"{base_url}/api/v1/project/create"
            project_data = {
                "name": "测试任务项目",
                "description": "用于测试任务的项目"
            }
            print("\n2. 创建测试项目...")
            response = requests.post(project_url, headers={**headers, "Content-Type": "application/json"}, json=project_data)
            print(f"创建项目响应: {response.status_code}")
            print(f"创建项目数据: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 200:
                project_id = response.json().get('data', {}).get('project_id')
                print(f"项目ID: {project_id}")
                
                # 测试创建测试任务
                task_url = f"{base_url}/api/v1/test-task"
                params = {
                    "project_id": project_id,
                    "name": "测试任务",
                    "description": "测试任务描述"
                }
                print(f"\n3. 创建测试任务...")
                print(f"请求URL: {task_url}")
                print(f"请求参数: {params}")
                response = requests.post(task_url, headers=headers, params=params)
                print(f"创建任务响应: {response.status_code}")
                print(f"创建任务数据: {json.dumps(response.json(), indent=2)}")
            else:
                print("创建项目失败!")
        else:
            print("登录失败!")
    except Exception as e:
        print(f"请求失败: {str(e)}")

if __name__ == "__main__":
    test_task_api()
