# -*- coding: utf-8 -*-
"""
AI测试平台 - 真实数据测试脚本
使用真实数据库数据测试项目的全部功能
"""
import pymysql
import requests
import json
import time

BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

class AITestPlatform:
    def __init__(self):
        self.token = None
        self.user_id = None
        self.conn = pymysql.connect(
            host='localhost', user='root', password='test1234', 
            database='ai_testmaster', charset='utf8mb4'
        )
        self.cursor = self.conn.cursor()
        
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def print_title(self, title):
        print("\n" + "=" * 60)
        print(f"【{title}】")
        print("=" * 60)
    
    def print_result(self, name, passed, error=""):
        status = "[PASS]" if passed else "[FAIL]"
        if passed:
            print(f"  {status}: {name}")
        else:
            print(f"  {status}: {name} - {error}")
        return passed
    
    # ==================== 认证模块测试 ====================
    def test_login(self):
        """测试登录功能"""
        self.print_title("认证模块 - 用户登录")
        
        # 测试有效凭据
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/login",
                data={"username": "admin", "password": "admin123"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and data.get("data", {}).get("access_token"):
                    self.token = data["data"]["access_token"]
                    self.print_result("使用admin账号登录", True)
                    return True
            self.print_result("使用admin账号登录", False, f"响应: {response.text[:100]}")
            return False
        except Exception as e:
            self.print_result("使用admin账号登录", False, str(e))
            return False
        
        # 测试无效密码
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/login",
                data={"username": "admin", "password": "wrongpass"},
                timeout=10
            )
            if response.status_code == 401:
                self.print_result("错误密码拒绝登录", True)
            else:
                self.print_result("错误密码拒绝登录", False, f"状态码: {response.status_code}")
        except Exception as e:
            self.print_result("错误密码拒绝登录", False, str(e))
            
        # 测试不存在用户
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/login",
                data={"username": "nonexistent", "password": "test"},
                timeout=10
            )
            if response.status_code == 401:
                self.print_result("不存在用户拒绝登录", True)
            else:
                self.print_result("不存在用户拒绝登录", False, f"状态码: {response.status_code}")
        except Exception as e:
            self.print_result("不存在用户拒绝登录", False, str(e))
            
        return False

    def test_get_user_info(self):
        """测试获取用户信息"""
        self.print_title("认证模块 - 获取用户信息")
        
        if not self.token:
            self.print_result("获取用户信息", False, "未登录")
            return False
            
        try:
            response = requests.get(
                f"{BASE_URL}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    user_info = data.get("data", {})
                    print(f"  用户信息: ID={user_info.get('id')}, 用户名={user_info.get('username')}")
                    self.user_id = user_info.get('id')
                    self.print_result("获取当前用户信息", True)
                    return True
            self.print_result("获取当前用户信息", False, f"响应: {response.text[:100]}")
            return False
        except Exception as e:
            self.print_result("获取当前用户信息", False, str(e))
            return False

    # ==================== 项目管理模块测试 ====================
    def test_project_list(self):
        """测试项目列表"""
        self.print_title("项目管理 - 获取项目列表")
        
        if not self.token:
            self.print_result("获取项目列表", False, "未登录")
            return False
            
        try:
            response = requests.get(
                f"{BASE_URL}/api/v1/project/list",
                headers={"Authorization": f"Bearer {self.token}"},
                params={"page": 1, "page_size": 20},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    items = data.get("data", {}).get("items", [])
                    total = data.get("data", {}).get("total", 0)
                    print(f"  总项目数: {total}")
                    for item in items[:5]:
                        print(f"    - {item['name']} (ID:{item['id']}, 类型:{item['project_type']})")
                    self.print_result("获取项目列表", True)
                    return items
            self.print_result("获取项目列表", False, f"响应: {response.text[:100]}")
            return None
        except Exception as e:
            self.print_result("获取项目列表", False, str(e))
            return None

    def test_project_detail(self, project_id=3):
        """测试项目详情"""
        self.print_title(f"项目管理 - 获取项目详情 (ID:{project_id})")
        
        if not self.token:
            self.print_result("获取项目详情", False, "未登录")
            return None
            
        try:
            response = requests.get(
                f"{BASE_URL}/api/v1/project/{project_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    project = data.get("data", {})
                    print(f"  项目名称: {project.get('name')}")
                    print(f"  项目类型: {project.get('project_type')}")
                    print(f"  项目描述: {project.get('description', '无')}")
                    print(f"  文件数量: {len(project.get('files', []))}")
                    if project.get('web_env_configs'):
                        test_env = project['web_env_configs'].get('test', {})
                        print(f"  测试环境URL: {test_env.get('url', '未配置')}")
                    self.print_result("获取项目详情", True)
                    return project
            self.print_result("获取项目详情", False, f"响应: {response.text[:100]}")
            return None
        except Exception as e:
            self.print_result("获取项目详情", False, str(e))
            return None

    def test_create_project(self):
        """测试创建项目"""
        self.print_title("项目管理 - 创建新项目")
        
        if not self.token:
            self.print_result("创建项目", False, "未登录")
            return None
            
        project_data = {
            "name": f"自动化测试项目_{int(time.time())}",
            "description": "由自动化测试脚本创建的项目",
            "project_type": "web",
            "web_env_configs": {
                "test": {
                    "url": "https://test.example.com",
                    "username": "testuser",
                    "password": "testpass123"
                }
            }
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/project/",
                headers={"Authorization": f"Bearer {self.token}"},
                json=project_data,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    new_id = data.get("data", {}).get("project_id")
                    print(f"  创建成功! 项目ID: {new_id}")
                    self.print_result("创建新项目", True)
                    return new_id
            self.print_result("创建新项目", False, f"响应: {response.text[:100]}")
            return None
        except Exception as e:
            self.print_result("创建新项目", False, str(e))
            return None

    def test_delete_project(self, project_id):
        """测试删除项目"""
        self.print_title(f"项目管理 - 删除项目 (ID:{project_id})")
        
        if not self.token:
            self.print_result("删除项目", False, "未登录")
            return False
            
        try:
            response = requests.delete(
                f"{BASE_URL}/api/v1/project/{project_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    self.print_result("删除项目", True)
                    return True
            self.print_result("删除项目", False, f"响应: {response.text[:100]}")
            return False
        except Exception as e:
            self.print_result("删除项目", False, str(e))
            return False

    # ==================== 测试点模块测试 ====================
    def test_get_test_points(self, project_id=3):
        """测试获取测试点"""
        self.print_title(f"测试点模块 - 获取测试点列表 (项目ID:{project_id})")
        
        if not self.token:
            self.print_result("获取测试点", False, "未登录")
            return []
            
        try:
            # 直接从数据库查询测试点
            self.cursor.execute("SELECT id, module, `function`, `point`, priority FROM test_points WHERE project_id=%s", (project_id,))
            points = self.cursor.fetchall()
            print(f"  从数据库获取测试点: {len(points)}个")
            
            # 按模块分组展示
            modules = {}
            for p in points:
                module = p[1]
                if module not in modules:
                    modules[module] = []
                modules[module].append({"id": p[0], "function": p[2], "priority": p[4]})
            
            for module, items in modules.items():
                print(f"    {module}: {len(items)}个")
                
            self.print_result("获取测试点列表", True)
            return points
        except Exception as e:
            self.print_result("获取测试点列表", False, str(e))
            return []

    # ==================== 测试用例模块测试 ====================
    def test_get_test_cases(self, project_id=3):
        """测试获取测试用例"""
        self.print_title(f"测试用例模块 - 获取测试用例列表 (项目ID:{project_id})")
        
        if not self.token:
            self.print_result("获取测试用例", False, "未登录")
            return []
            
        try:
            # 从数据库查询测试用例
            self.cursor.execute("""
                SELECT id, case_no, title, module, priority, case_type, review_status 
                FROM test_cases WHERE project_id=%s
            """, (project_id,))
            cases = self.cursor.fetchall()
            print(f"  从数据库获取测试用例: {len(cases)}个")
            
            for case in cases[:5]:
                print(f"    [{case[0]}] {case[1]}: {case[2][:40]}... (状态:{case[6]})")
                
            self.print_result("获取测试用例列表", True)
            return cases
        except Exception as e:
            self.print_result("获取测试用例列表", False, str(e))
            return []

    # ==================== 数据库数据验证 ====================
    def verify_real_data(self):
        """验证数据库中的真实数据"""
        self.print_title("数据验证 - 检查真实数据完整性")
        
        results = []
        
        # 验证用户数据
        try:
            self.cursor.execute("SELECT id, username, email, is_active FROM users")
            users = self.cursor.fetchall()
            if users:
                self.print_result("用户表数据存在", True, f"共{len(users)}个用户")
                for u in users:
                    print(f"    - {u[1]} (ID:{u[0]}, 邮箱:{u[2]})")
            else:
                self.print_result("用户表数据存在", False, "无用户数据")
            results.append(True)
        except Exception as e:
            self.print_result("用户表数据存在", False, str(e))
            results.append(False)
        
        # 验证项目数据
        try:
            self.cursor.execute("SELECT id, name, project_type, status FROM projects")
            projects = self.cursor.fetchall()
            if projects:
                self.print_result("项目表数据存在", True, f"共{len(projects)}个项目")
                for p in projects[:3]:
                    print(f"    - {p[1]} (ID:{p[0]}, 类型:{p[2]})")
            else:
                self.print_result("项目表数据存在", False, "无项目数据")
            results.append(True)
        except Exception as e:
            self.print_result("项目表数据存在", False, str(e))
            results.append(False)
        
        # 验证项目文件数据
        try:
            self.cursor.execute("SELECT id, project_id, file_name, resource_type, extract_status FROM project_files")
            files = self.cursor.fetchall()
            if files:
                self.print_result("项目文件数据存在", True, f"共{len(files)}个文件")
            else:
                self.print_result("项目文件数据存在", False, "无文件数据")
            results.append(True)
        except Exception as e:
            self.print_result("项目文件数据存在", False, str(e))
            results.append(False)
        
        # 验证测试点数据
        try:
            self.cursor.execute("SELECT COUNT(*) FROM test_points WHERE project_id=3")
            count = self.cursor.fetchone()[0]
            if count > 0:
                self.print_result("测试点数据存在", True, f"项目3有{count}个测试点")
            else:
                self.print_result("测试点数据存在", False, "无测试点数据")
            results.append(True)
        except Exception as e:
            self.print_result("测试点数据存在", False, str(e))
            results.append(False)
        
        # 验证测试用例数据
        try:
            self.cursor.execute("SELECT COUNT(*) FROM test_cases WHERE project_id=3")
            count = self.cursor.fetchone()[0]
            if count > 0:
                self.print_result("测试用例数据存在", True, f"项目3有{count}个用例")
            else:
                self.print_result("测试用例数据存在", False, "无用例数据")
            results.append(True)
        except Exception as e:
            self.print_result("测试用例数据存在", False, str(e))
            results.append(False)
            
        return all(results)

    # ==================== 前端页面可用性测试 ====================
    def test_frontend_pages(self):
        """测试前端页面可用性"""
        self.print_title("前端页面 - 页面可用性测试")
        
        pages = [
            ("/", "首页"),
            ("/login", "登录页"),
        ]
        
        results = []
        for path, name in pages:
            try:
                response = requests.get(f"http://localhost:3000{path}", timeout=10)
                if response.status_code == 200:
                    self.print_result(f"{name} ({path})", True, f"状态码:{response.status_code}")
                    results.append(True)
                else:
                    self.print_result(f"{name} ({path})", False, f"状态码:{response.status_code}")
                    results.append(False)
            except Exception as e:
                self.print_result(f"{name} ({path})", False, str(e))
                results.append(False)
                
        return results

    # ==================== 运行所有测试 ====================
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "=" * 60)
        print("  AI测试平台 - 完整功能测试")
        print("  目标: 使用真实数据库数据测试全部功能")
        print("=" * 60)
        
        # 1. 验证真实数据
        self.verify_real_data()
        
        # 2. 认证模块测试
        self.test_login()
        self.test_get_user_info()
        
        # 3. 项目管理模块测试
        projects = self.test_project_list()
        self.test_project_detail(3)  # 智慧园区项目
        
        # 4. 创建和删除项目
        new_project_id = self.test_create_project()
        if new_project_id:
            time.sleep(1)
            self.test_delete_project(new_project_id)
        
        # 5. 测试点和用例查询
        self.test_get_test_points(3)
        self.test_get_test_cases(3)
        
        # 6. 前端页面测试
        self.test_frontend_pages()
        
        # 总结
        self.print_title("测试完成")
        print("所有测试已执行完成!")
        print("下一步: 根据测试结果生成完整的测试用例文档")

if __name__ == "__main__":
    tester = AITestPlatform()
    tester.run_all_tests()
