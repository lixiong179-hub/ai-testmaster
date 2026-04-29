#!/usr/bin/env python3
"""测试AI生成功能"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_ai_generate():
    print("=" * 60)
    print("测试AI生成测试用例")
    print("=" * 60)
    
    data = {
        "scene": "测试用户登录功能，输入正确的用户名和密码",
        "case_type": "functional"
    }
    
    try:
        print(f"\n发送请求: {json.dumps(data, ensure_ascii=False)}")
        response = requests.post(
            f"{BASE_URL}/case/ai-generate",
            json=data,
            timeout=60
        )
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✓ AI生成测试用例成功")
            print(f"响应数据:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            if 'data' in result and result['data']:
                case = result['data']
                print(f"\n生成的测试用例:")
                print(f"  ID: {case.get('id')}")
                print(f"  名称: {case.get('name')}")
                print(f"  类型: {case.get('type')}")
                print(f"  场景: {case.get('scene')}")
                print(f"  AI生成: {case.get('ai_generated')}")
        else:
            print(f"\n✗ AI生成失败")
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"\n✗ 异常: {str(e)}")

if __name__ == "__main__":
    test_ai_generate()
