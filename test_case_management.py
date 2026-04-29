#!/usr/bin/env python3
"""
测试用例管理功能测试脚本
"""
import asyncio
import json
import requests

BASE_URL = "http://localhost:8000/api/v1"

def get_response_data(response):
    """从标准化响应中提取data字段"""
    try:
        result = response.json()
        if isinstance(result, dict) and 'data' in result:
            return result.get('data')
        return result
    except:
        return None

async def test_case_management():
    """测试用例管理功能"""
    print("=" * 60)
    print("测试用例管理功能测试")
    print("=" * 60)
    
    case_id = None
    
    # 1. 测试创建测试用例
    print("\n1. 测试创建测试用例...")
    create_data = {
        "name": "用户登录功能测试",
        "type": "functional",
        "scene": "测试用户使用正确的用户名和密码登录系统",
        "steps": [
            {"step": 1, "description": "打开登录页面"},
            {"step": 2, "description": "输入正确的用户名和密码"},
            {"step": 3, "description": "点击登录按钮"}
        ],
        "expected_result": "登录成功，跳转到首页",
        "priority": "high",
        "module": "用户模块",
        "tags": ["登录", "功能测试"]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/case/",
            json=create_data
        )
        print(f"状态码: {response.status_code}")
        print(f"原始响应: {response.text[:200]}")
        if response.status_code == 200:
            result = get_response_data(response)
            print(f"解析结果: {result}")
            if result:
                print(f"✓ 创建测试用例成功")
                print(f"  用例ID: {result.get('id')}")
                print(f"  用例名称: {result.get('name')}")
                case_id = result.get('id')
            else:
                print(f"✗ 解析响应数据失败")
                return
        else:
            print(f"✗ 创建测试用例失败: {response.text}")
            return
    except Exception as e:
        print(f"✗ 创建测试用例异常: {str(e)}")
        return
    
    # 2. 测试获取测试用例列表
    print("\n2. 测试获取测试用例列表...")
    try:
        response = requests.get(
            f"{BASE_URL}/case/",
            params={"limit": 10}
        )
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = get_response_data(response)
            if result and isinstance(result, list):
                print(f"✓ 获取测试用例列表成功")
                print(f"  用例数量: {len(result)}")
                for case in result[:3]:
                    print(f"  - {case.get('name')} (ID: {case.get('id')})")
            else:
                print(f"✗ 解析响应数据失败")
        else:
            print(f"✗ 获取测试用例列表失败: {response.text}")
    except Exception as e:
        print(f"✗ 获取测试用例列表异常: {str(e)}")
    
    # 3. 测试获取单个测试用例
    print("\n3. 测试获取单个测试用例...")
    if case_id is None:
        print("⚠ 跳过：没有可用的用例ID")
    else:
        try:
            response = requests.get(f"{BASE_URL}/case/{case_id}")
            print(f"状态码: {response.status_code}")
            if response.status_code == 200:
                case = get_response_data(response)
                if case:
                    print(f"✓ 获取测试用例成功")
                    print(f"  用例名称: {case.get('name')}")
                    print(f"  用例类型: {case.get('type')}")
                    print(f"  测试场景: {case.get('scene')}")
                    print(f"  预期结果: {case.get('expected_result')}")
                else:
                    print(f"✗ 解析响应数据失败")
            else:
                print(f"✗ 获取测试用例失败: {response.text}")
        except Exception as e:
            print(f"✗ 获取测试用例异常: {str(e)}")
    
    # 4. 测试更新测试用例
    print("\n4. 测试更新测试用例...")
    if case_id is None:
        print("⚠ 跳过：没有可用的用例ID")
    else:
        update_data = {
            "name": "用户登录功能测试（已更新）",
            "priority": "medium"
        }
        
        try:
            response = requests.put(
                f"{BASE_URL}/case/{case_id}",
                json=update_data
            )
            print(f"状态码: {response.status_code}")
            if response.status_code == 200:
                case = get_response_data(response)
                if case:
                    print(f"✓ 更新测试用例成功")
                    print(f"  新名称: {case.get('name')}")
                    print(f"  新优先级: {case.get('priority')}")
                else:
                    print(f"✗ 解析响应数据失败")
            else:
                print(f"✗ 更新测试用例失败: {response.text}")
        except Exception as e:
            print(f"✗ 更新测试用例异常: {str(e)}")
    
    # 5. 测试AI生成测试用例
    print("\n5. 测试AI生成测试用例...")
    ai_generate_data = {
        "scene": "测试用户使用错误的密码登录系统",
        "case_type": "functional"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/case/ai-generate",
            json=ai_generate_data,
            timeout=60
        )
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            ai_case = get_response_data(response)
            if ai_case:
                print(f"✓ AI生成测试用例成功")
                print(f"  用例名称: {ai_case.get('name')}")
                print(f"  用例类型: {ai_case.get('type')}")
                print(f"  测试场景: {ai_case.get('scene')}")
                print(f"  AI生成标记: {ai_case.get('ai_generated')}")
            else:
                print(f"✗ 解析响应数据失败")
        else:
            print(f"✗ AI生成测试用例失败: {response.text}")
    except Exception as e:
        print(f"✗ AI生成测试用例异常: {str(e)}")
    
    # 6. 测试执行测试用例
    print("\n6. 测试执行测试用例...")
    if case_id is None:
        print("⚠ 跳过：没有可用的用例ID")
    else:
        execute_data = {
            "actual_result": "登录失败，提示密码错误",
            "status": "passed"
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/case/execute/{case_id}",
                params=execute_data
            )
            print(f"状态码: {response.status_code}")
            if response.status_code == 200:
                case = get_response_data(response)
                if case:
                    print(f"✓ 执行测试用例成功")
                    print(f"  实际结果: {case.get('actual_result')}")
                    print(f"  执行状态: {case.get('status')}")
                else:
                    print(f"✗ 解析响应数据失败")
            else:
                print(f"✗ 执行测试用例失败: {response.text}")
        except Exception as e:
            print(f"✗ 执行测试用例异常: {str(e)}")
    
    # 7. 测试删除测试用例
    print("\n7. 测试删除测试用例...")
    if case_id is None:
        print("⚠ 跳过：没有可用的用例ID")
    else:
        try:
            response = requests.delete(f"{BASE_URL}/case/{case_id}")
            print(f"状态码: {response.status_code}")
            if response.status_code == 200:
                result = get_response_data(response)
                if result:
                    print(f"✓ 删除测试用例成功")
                    print(f"  消息: {result.get('message')}")
                else:
                    print(f"✗ 解析响应数据失败")
            else:
                print(f"✗ 删除测试用例失败: {response.text}")
        except Exception as e:
            print(f"✗ 删除测试用例异常: {str(e)}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


async def test_ai_generate_with_mock():
    """测试AI生成功能（模拟模式）"""
    print("\n" + "=" * 60)
    print("AI生成测试用例功能测试（模拟模式）")
    print("=" * 60)
    
    from app.utils.ai_client import deepseek_client
    from app.core.config import settings
    
    # 检查API Key是否配置
    if not settings.DEEPSEEK_API_KEY or settings.DEEPSEEK_API_KEY == "your-deepseek-api-key-here":
        print("⚠ DeepSeek API Key未配置，跳过AI生成测试")
        print("  请在.env文件中设置DEEPSEEK_API_KEY")
        return
    
    # 测试AI生成测试用例
    print("\n测试AI生成测试用例...")
    try:
        result = await deepseek_client.generate_test_case(
            scene="测试用户注册功能",
            case_type="functional"
        )
        print(f"✓ AI生成测试用例成功")
        print(f"  用例名称: {result.get('name')}")
        print(f"  用例类型: {result.get('type')}")
        print(f"  测试场景: {result.get('scene')}")
        print(f"  预期结果: {result.get('expected_result')}")
        print(f"  测试步骤数: {len(result.get('steps', []))}")
    except Exception as e:
        print(f"✗ AI生成测试用例失败: {str(e)}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("\n请确保后端服务器正在运行: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
    print("\n开始测试...\n")
    
    # 测试REST API
    asyncio.run(test_case_management())
    
    # 测试AI生成功能
    asyncio.run(test_ai_generate_with_mock())
