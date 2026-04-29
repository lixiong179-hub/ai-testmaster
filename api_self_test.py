import requests
import json
import traceback
from typing import Dict, List, Any

base = 'http://localhost:8000'

class APITester:
    def __init__(self):
        self.base = base
        self.token = None
        self.errors = []
        self.success_count = 0
        self.fail_count = 0
        self.test_results = []

    def get_token(self):
        try:
            r = requests.post(f'{self.base}/api/v1/auth/login', json={'username': 'admin', 'password': 'admin123'}, timeout=10)
            data = r.json()
            if 'data' in data and 'access_token' in data['data']:
                self.token = data['data']['access_token']
                return self.token
            self.errors.append(f"[Auth] 获取Token失败: {data}")
            return None
        except Exception as e:
            self.errors.append(f"[Auth] 获取Token异常: {e}")
            return None

    def get_headers(self):
        if self.token:
            return {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
        return {'Content-Type': 'application/json'}

    def test_api(self, method, path, expected_status=None, data=None, params=None, description="", check_error=True):
        try:
            url = f'{self.base}{path}'
            headers = self.get_headers()
            r = getattr(requests, method)(url, headers=headers, json=data, params=params, timeout=30)
            status_ok = r.status_code < 400
            if expected_status:
                status_ok = r.status_code == expected_status

            result = {
                "method": method.upper(),
                "path": path,
                "status": r.status_code,
                "description": description,
                "success": status_ok
            }

            try:
                response_data = r.json()
                result["response"] = response_data
            except:
                result["response"] = r.text[:200]

            if not status_ok:
                self.fail_count += 1
                result["error"] = f"状态码{r.status_code}不符合预期"
                self.errors.append(f"[FAIL] {method.upper()} {path} -> {r.status_code}: {r.text[:200]}")
                if check_error:
                    print(f'❌ FAIL {method.upper()} {path} [{description}] -> {r.status_code}: {r.text[:100]}')
            else:
                self.success_count += 1
                print(f'✅ OK   {method.upper()} {path} [{description}] -> {r.status_code}')

            self.test_results.append(result)
            return r
        except Exception as e:
            self.fail_count += 1
            error_msg = f"{type(e).__name__}: {e}"
            self.errors.append(f"[ERROR] {method.upper()} {path} -> {error_msg}")
            print(f'💥 ERROR {method.upper()} {path} [{description}] -> {error_msg}')
            self.test_results.append({
                "method": method.upper(),
                "path": path,
                "description": description,
                "success": False,
                "error": error_msg
            })
            return None

    def run_tests(self):
        print("=" * 80)
        print("🔐 认证模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/auth/captcha/generate', description="获取验证码")
        self.test_api('post', '/api/v1/auth/login', data={'username': 'admin', 'password': 'admin123'}, description="登录")
        self.test_api('get', '/api/v1/auth/me', description="获取当前用户")

        token = self.get_token()
        if not token:
            print("\n⚠️ 无法获取Token，后续测试跳过认证检查")
        else:
            print(f"\n✅ Token获取成功: {token[:20]}...")

        print("\n" + "=" * 80)
        print("📁 项目管理模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/project/list', description="获取项目列表")
        self.test_api('post', '/api/v1/project/', data={'name': 'test_project_api', 'description': 'test'}, description="创建项目")
        self.test_api('get', '/api/v1/project/1', description="获取项目详情")

        print("\n" + "=" * 80)
        print("📝 测试点模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/test-point/list/1', description="获取测试点列表")
        self.test_api('get', '/api/v1/test-point/1', description="获取测试点详情")

        print("\n" + "=" * 80)
        print("🧪 测试用例模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/testCase/', description="获取测试用例列表")
        self.test_api('post', '/api/v1/testCase/', data={'project_id': 1, 'title': 'test_case_api', 'type': 'functional'}, description="创建测试用例")
        self.test_api('get', '/api/v1/testCase/1', description="获取测试用例详情")

        print("\n" + "=" * 80)
        print("📋 测试任务模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/test_task/', description="获取测试任务列表")
        self.test_api('post', '/api/v1/test_task/', data={'project_id': 1, 'task_name': 'test_task_api', 'case_ids': []}, description="创建测试任务")
        self.test_api('get', '/api/v1/test_task/1', description="获取测试任务详情")

        print("\n" + "=" * 80)
        print("👤 用户模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/user/', description="获取用户列表")
        self.test_api('get', '/api/v1/user/me', description="获取当前用户信息")

        print("\n" + "=" * 80)
        print("🔄 迭代模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/iteration/list/1', description="获取迭代列表")

        print("\n" + "=" * 80)
        print("🔗 需求关联模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/requirement-link/list/1', description="获取需求关联列表")

        print("\n" + "=" * 80)
        print("📎 文件模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/file/list', description="获取文件列表")

        print("\n" + "=" * 80)
        print("📊 报告模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/report/', description="获取报告列表")

        print("\n" + "=" * 80)
        print("💾 测试数据模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/test-data/1', description="获取测试数据")
        self.test_api('post', '/api/v1/test-data/', data={'step_id': 1, 'field_name': 'test', 'field_type': 'text'}, description="创建测试数据")

        print("\n" + "=" * 80)
        print("🎯 批量定位器模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/batch-locator/batch-tasks', description="获取批量定位任务")

        print("\n" + "=" * 80)
        print("⚡ 执行模块")
        print("=" * 80)
        self.test_api('get', '/api/execution/devices', description="获取设备列表")

        print("\n" + "=" * 80)
        print("📹 执行可视化模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/execution-visualization/config/global', description="获取可视化配置")
        self.test_api('get', '/api/v1/execution-visualization/videos/stats', description="获取视频统计")

        print("\n" + "=" * 80)
        print("👁️ 可见性模块")
        print("=" * 80)
        self.test_api('get', '/api/visibility/config', description="获取可见性配置")

        print("\n" + "=" * 80)
        print("✨ 质量检查模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/quality/cases/1/quality', description="获取用例质量")

        print("\n" + "=" * 80)
        print("🎨 UI原型模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/ui-prototype/project/list/1', description="获取UI原型项目列表")

        print("\n" + "=" * 80)
        print("📡 WebSocket模块")
        print("=" * 80)
        self.test_api('get', '/api/v1/ws/stats', description="获取WebSocket统计")

        print("\n" + "=" * 80)
        print("🏥 健康检查")
        print("=" * 80)
        self.test_api('get', '/', description="根路径")
        self.test_api('get', '/health', description="健康检查")

        print("\n" + "=" * 80)
        print("📜 测试用例工作流")
        print("=" * 80)
        self.test_api('post', '/api/v1/testCase/batch-delete', data={'caseIds': [1]}, description="批量删除用例")
        self.test_api('post', '/api/v1/testCase/batch-restore', data={'caseIds': [1]}, description="批量恢复用例")

    def print_summary(self):
        print("\n" + "=" * 80)
        print("📊 测试结果汇总")
        print("=" * 80)
        print(f"✅ 成功: {self.success_count}")
        print(f"❌ 失败: {self.fail_count}")
        print(f"📝 总计: {self.success_count + self.fail_count}")

        if self.errors:
            print("\n" + "=" * 80)
            print("❌ 错误详情")
            print("=" * 80)
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error}")

        return {
            "success": self.success_count,
            "fail": self.fail_count,
            "errors": self.errors,
            "results": self.test_results
        }

if __name__ == "__main__":
    tester = APITester()
    tester.run_tests()
    summary = tester.print_summary()

    with open('api_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n📄 详细结果已保存到 api_test_results.json")
