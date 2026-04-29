"""
系统测试脚本 - 测试所有功能并记录bug
"""
import requests
import json
from typing import List, Dict

BASE_URL = "http://localhost:8000"

class BugReporter:
    def __init__(self):
        self.bugs: List[Dict] = []
    
    def add_bug(self, severity: str, title: str, description: str, steps: str, expected: str, actual: str):
        """添加bug"""
        bug = {
            "severity": severity,
            "title": title,
            "description": description,
            "steps": steps,
            "expected": expected,
            "actual": actual
        }
        self.bugs.append(bug)
        print(f"\n🐛 发现Bug [{severity}]: {title}")
        print(f"   描述: {description}")
        print(f"   预期: {expected}")
        print(f"   实际: {actual}")
    
    def generate_report(self):
        """生成bug报告"""
        print("\n" + "="*80)
        print("系统Bug报告")
        print("="*80)
        print(f"总计发现 {len(self.bugs)} 个bug\n")
        
        for i, bug in enumerate(self.bugs, 1):
            print(f"\nBug #{i} - [{bug['severity']}] {bug['title']}")
            print("-" * 80)
            print(f"描述: {bug['description']}")
            print(f"步骤: {bug['steps']}")
            print(f"预期: {bug['expected']}")
            print(f"实际: {bug['actual']}")
            print()
        
        # 按严重程度统计
        severity_count = {}
        for bug in self.bugs:
            severity_count[bug['severity']] = severity_count.get(bug['severity'], 0) + 1
        
        print("\n" + "="*80)
        print("Bug统计")
        print("="*80)
        for severity, count in severity_count.items():
            print(f"{severity}: {count}")
        
        return self.bugs

def test_login(reporter: BugReporter):
    """测试登录功能"""
    print("\n" + "="*80)
    print("测试登录功能")
    print("="*80)
    
    # 测试1: 正常登录
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
            "username": "admin",
            "password": "password123"
        })
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'access_token' in data['data']:
                print("✓ 正常登录成功")
                return data['data']['access_token']
            else:
                reporter.add_bug(
                    severity="high",
                    title="登录接口返回token字段错误",
                    description="登录成功但返回数据中没有access_token字段",
                    steps="1. 使用admin/password123登录\n2. 查看返回数据",
                    expected="返回数据包含data.access_token字段",
                    actual=f"返回数据: {data}"
                )
        else:
            reporter.add_bug(
                severity="high",
                title="登录接口返回错误状态码",
                description=f"登录请求返回状态码 {response.status_code}",
                steps="1. 使用admin/password123登录\n2. 查看响应状态码",
                expected="返回200状态码",
                actual=f"返回状态码: {response.status_code}"
            )
    except Exception as e:
        reporter.add_bug(
            severity="high",
            title="登录接口连接失败",
            description=f"连接登录接口时发生异常: {str(e)}",
            steps="1. 访问登录接口",
            expected="成功连接接口",
            actual=f"连接失败: {str(e)}"
        )
    
    return None

def test_case_list(reporter: BugReporter, token: str):
    """测试用例列表"""
    print("\n" + "="*80)
    print("测试用例列表")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/case/", headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                print(f"✓ 获取用例列表成功，共 {len(data['data'].get('items', []))} 条")
            else:
                reporter.add_bug(
                    severity="medium",
                    title="用例列表接口返回格式不一致",
                    description="用例列表接口返回数据格式不符合预期",
                    steps="1. 获取用例列表\n2. 查看返回数据",
                    expected="返回数据包含data字段",
                    actual=f"返回数据: {data}"
                )
        else:
            reporter.add_bug(
                severity="medium",
                title="用例列表接口返回错误",
                description=f"用例列表接口返回状态码 {response.status_code}",
                steps="1. 获取用例列表",
                expected="返回200状态码",
                actual=f"返回状态码: {response.status_code}"
            )
    except Exception as e:
        reporter.add_bug(
            severity="medium",
            title="用例列表接口连接失败",
            description=f"连接用例列表接口时发生异常: {str(e)}",
            steps="1. 访问用例列表接口",
            expected="成功连接接口",
            actual=f"连接失败: {str(e)}"
        )

def test_ai_generate(reporter: BugReporter, token: str):
    """测试AI生成功能"""
    print("\n" + "="*80)
    print("测试AI生成功能")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/case/ai-generate",
            headers=headers,
            json={
                "scene": "测试用户登录功能",
                "case_type": "functional"
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                print("✓ AI生成测试用例成功")
                case = data['data']
                if not case.get('name'):
                    reporter.add_bug(
                        severity="medium",
                        title="AI生成的用例缺少name字段",
                        description="AI生成的测试用例没有name字段",
                        steps="1. 调用AI生成接口\n2. 查看返回数据",
                        expected="生成的用例包含name字段",
                        actual=f"返回数据: {case}"
                    )
                if not case.get('steps'):
                    reporter.add_bug(
                        severity="medium",
                        title="AI生成的用例缺少steps字段",
                        description="AI生成的测试用例没有steps字段或steps为空",
                        steps="1. 调用AI生成接口\n2. 查看返回数据",
                        expected="生成的用例包含steps字段",
                        actual=f"返回数据: {case}"
                    )
            else:
                reporter.add_bug(
                    severity="high",
                    title="AI生成接口返回格式错误",
                    description="AI生成接口返回数据格式不符合预期",
                    steps="1. 调用AI生成接口\n2. 查看返回数据",
                    expected="返回数据包含data字段",
                    actual=f"返回数据: {data}"
                )
        else:
            reporter.add_bug(
                severity="high",
                title="AI生成接口返回错误",
                description=f"AI生成接口返回状态码 {response.status_code}",
                steps="1. 调用AI生成接口",
                expected="返回200状态码",
                actual=f"返回状态码: {response.status_code}, 响应: {response.text}"
            )
    except requests.exceptions.Timeout:
        reporter.add_bug(
            severity="medium",
            title="AI生成接口超时",
            description="AI生成接口响应超时",
            steps="1. 调用AI生成接口\n2. 等待响应",
            expected="在60秒内返回结果",
            actual="请求超时"
        )
    except Exception as e:
        reporter.add_bug(
            severity="high",
            title="AI生成接口连接失败",
            description=f"连接AI生成接口时发生异常: {str(e)}",
            steps="1. 访问AI生成接口",
            expected="成功连接接口",
            actual=f"连接失败: {str(e)}"
        )

def test_case_crud(reporter: BugReporter, token: str):
    """测试用例CRUD操作"""
    print("\n" + "="*80)
    print("测试用例CRUD操作")
    print("="*80)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 测试创建用例
    try:
        create_data = {
            "name": "测试用例-自动化测试",
            "type": "functional",
            "scene": "测试创建用例功能",
            "steps": [
                {
                    "step_number": 1,
                    "action": "打开用例创建页面",
                    "expected_result": "页面正常显示"
                }
            ],
            "expected_result": "用例创建成功",
            "priority": "medium",
            "tags": ["自动化测试"]
        }
        response = requests.post(f"{BASE_URL}/api/v1/case", headers=headers, json=create_data)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                case_id = data['data'].get('id')
                print(f"✓ 创建用例成功，ID: {case_id}")
                
                # 测试获取用例详情
                detail_response = requests.get(f"{BASE_URL}/api/v1/case/{case_id}", headers=headers)
                if detail_response.status_code == 200:
                    print("✓ 获取用例详情成功")
                else:
                    reporter.add_bug(
                        severity="medium",
                        title="获取用例详情接口返回错误",
                        description=f"获取用例详情接口返回状态码 {detail_response.status_code}",
                        steps=f"1. 创建用例(ID: {case_id})\n2. 获取用例详情",
                        expected="返回200状态码",
                        actual=f"返回状态码: {detail_response.status_code}"
                    )
                
                # 测试更新用例
                update_data = create_data.copy()
                update_data['name'] = "测试用例-自动化测试-已更新"
                update_response = requests.put(f"{BASE_URL}/api/v1/case/{case_id}", headers=headers, json=update_data)
                if update_response.status_code == 200:
                    print("✓ 更新用例成功")
                else:
                    reporter.add_bug(
                        severity="medium",
                        title="更新用例接口返回错误",
                        description=f"更新用例接口返回状态码 {update_response.status_code}",
                        steps=f"1. 创建用例(ID: {case_id})\n2. 更新用例",
                        expected="返回200状态码",
                        actual=f"返回状态码: {update_response.status_code}"
                    )
                
                # 测试删除用例
                delete_response = requests.delete(f"{BASE_URL}/api/v1/case/{case_id}", headers=headers)
                if delete_response.status_code == 200:
                    print("✓ 删除用例成功")
                else:
                    reporter.add_bug(
                        severity="medium",
                        title="删除用例接口返回错误",
                        description=f"删除用例接口返回状态码 {delete_response.status_code}",
                        steps=f"1. 创建用例(ID: {case_id})\n2. 删除用例",
                        expected="返回200状态码",
                        actual=f"返回状态码: {delete_response.status_code}"
                    )
            else:
                reporter.add_bug(
                    severity="high",
                    title="创建用例接口返回格式错误",
                    description="创建用例接口返回数据格式不符合预期",
                    steps="1. 创建用例\n2. 查看返回数据",
                    expected="返回数据包含data字段",
                    actual=f"返回数据: {data}"
                )
        else:
            reporter.add_bug(
                severity="high",
                title="创建用例接口返回错误",
                description=f"创建用例接口返回状态码 {response.status_code}",
                steps="1. 创建用例",
                expected="返回200状态码",
                actual=f"返回状态码: {response.status_code}, 响应: {response.text}"
            )
    except Exception as e:
        reporter.add_bug(
            severity="high",
            title="用例CRUD操作连接失败",
            description=f"执行用例CRUD操作时发生异常: {str(e)}",
            steps="1. 执行用例CRUD操作",
            expected="成功执行操作",
            actual=f"操作失败: {str(e)}"
        )

def main():
    """主测试函数"""
    print("\n" + "="*80)
    print("AI TestMaster 系统测试")
    print("="*80)
    
    reporter = BugReporter()
    
    # 测试登录
    token = test_login(reporter)
    
    if token:
        # 测试用例列表
        test_case_list(reporter, token)
        
        # 测试AI生成
        test_ai_generate(reporter, token)
        
        # 测试用例CRUD
        test_case_crud(reporter, token)
    else:
        print("\n⚠️  登录失败，跳过需要认证的测试")
    
    # 生成bug报告
    bugs = reporter.generate_report()
    
    # 保存bug报告到文件
    with open("bug_report.json", "w", encoding="utf-8") as f:
        json.dump(bugs, f, ensure_ascii=False, indent=2)
    print("\nBug报告已保存到 bug_report.json")

if __name__ == "__main__":
    main()
