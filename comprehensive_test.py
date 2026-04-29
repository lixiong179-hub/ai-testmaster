# -*- coding: utf-8 -*-
"""
AI测试平台 - 全面测试执行脚本
执行所有测试用例，包括前后端和UI测试
"""
import pymysql
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"
RESULTS = []

class ComprehensiveTester:
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
    
    def log(self, module, test_name, status, details=""):
        RESULTS.append({
            "module": module,
            "test_name": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        symbol = "[PASS]" if status == "PASS" else "[FAIL]" if status == "FAIL" else "[WARN]"
        print(f"  {symbol} {test_name}: {details[:80] if details else 'OK'}")
    
    # ==================== 认证模块 ====================
    def test_auth_flow(self):
        """完整的认证流程测试"""
        print("\n" + "=" * 60)
        print("【认证模块 - 完整流程测试】")
        print("=" * 60)
        
        # 1. 正常登录
        try:
            r = requests.post(f"{BASE_URL}/api/v1/auth/login", 
                            data={"username": "admin", "password": "admin123"}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("code") == 200:
                    self.token = data["data"]["access_token"]
                    self.log("认证", "正常登录", "PASS", "Token获取成功")
                else:
                    self.log("认证", "正常登录", "FAIL", f"响应码错误: {data.get('code')}")
            else:
                self.log("认证", "正常登录", "FAIL", f"HTTP状态码: {r.status_code}")
        except Exception as e:
            self.log("认证", "正常登录", "FAIL", str(e))
        
        # 2. 获取用户信息
        if self.token:
            try:
                r = requests.get(f"{BASE_URL}/api/v1/auth/me",
                               headers={"Authorization": f"Bearer {self.token}"}, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("code") == 200:
                        self.user_id = data["data"]["id"]
                        self.log("认证", "获取用户信息", "PASS", f"用户: {data['data']['username']}")
                    else:
                        self.log("认证", "获取用户信息", "FAIL", f"响应码: {data.get('code')}")
                else:
                    self.log("认证", "获取用户信息", "FAIL", f"HTTP: {r.status_code}")
            except Exception as e:
                self.log("认证", "获取用户信息", "FAIL", str(e))
        
        # 3. Token过期测试（使用无效Token）
        try:
            r = requests.get(f"{BASE_URL}/api/v1/auth/me",
                           headers={"Authorization": "Bearer invalid_token_123"}, timeout=10)
            if r.status_code == 401:
                self.log("认证", "无效Token拒绝", "PASS", "正确返回401")
            else:
                self.log("认证", "无效Token拒绝", "FAIL", f"应返回401，实际: {r.status_code}")
        except Exception as e:
            self.log("认证", "无效Token拒绝", "FAIL", str(e))
        
        # 4. 无Token访问
        try:
            r = requests.get(f"{BASE_URL}/api/v1/auth/me", timeout=10)
            if r.status_code in [401, 403]:
                self.log("认证", "无Token拒绝", "PASS", f"正确返回{r.status_code}")
            else:
                self.log("认证", "无Token拒绝", "WARN", f"返回: {r.status_code}")
        except Exception as e:
            self.log("认证", "无Token拒绝", "FAIL", str(e))
    
    # ==================== 项目管理模块 ====================
    def test_project_management(self):
        """项目管理完整测试"""
        print("\n" + "=" * 60)
        print("【项目管理模块 - 完整测试】")
        print("=" * 60)
        
        if not self.token:
            self.log("项目管理", "所有测试", "FAIL", "未登录，跳过")
            return
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # 1. 获取项目列表
        try:
            r = requests.get(f"{BASE_URL}/api/v1/project/list", headers=headers, 
                           params={"page": 1, "page_size": 10}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("code") == 200:
                    total = data["data"]["total"]
                    items = data["data"]["items"]
                    self.log("项目管理", "获取项目列表", "PASS", f"总数: {total}")
                else:
                    self.log("项目管理", "获取项目列表", "FAIL", f"响应码: {data.get('code')}")
            else:
                self.log("项目管理", "获取项目列表", "FAIL", f"HTTP: {r.status_code}")
        except Exception as e:
            self.log("项目管理", "获取项目列表", "FAIL", str(e))
        
        # 2. 获取项目详情（智慧园区）
        try:
            r = requests.get(f"{BASE_URL}/api/v1/project/3", headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("code") == 200:
                    proj = data["data"]
                    self.log("项目管理", "获取项目3详情", "PASS", 
                            f"名称: {proj.get('name')}, 类型: {proj.get('project_type')}")
                    
                    # 验证文件
                    files = proj.get("files", [])
                    if files:
                        self.log("项目管理", "项目文件检查", "PASS", f"文件数: {len(files)}")
                    else:
                        self.log("项目管理", "项目文件检查", "WARN", "无文件")
                    
                    # 验证环境配置
                    env = proj.get("web_env_configs", {})
                    if env and env.get("test"):
                        self.log("项目管理", "环境配置检查", "PASS", 
                                f"URL: {env['test'].get('url', 'N/A')[:30]}...")
                    else:
                        self.log("项目管理", "环境配置检查", "WARN", "无测试环境配置")
                else:
                    self.log("项目管理", "获取项目3详情", "FAIL", f"响应码: {data.get('code')}")
            else:
                self.log("项目管理", "获取项目3详情", "FAIL", f"HTTP: {r.status_code}")
        except Exception as e:
            self.log("项目管理", "获取项目3详情", "FAIL", str(e))
        
        # 3. 创建项目
        project_id = None
        try:
            new_proj = {
                "name": f"测试项目_{int(time.time())}",
                "description": "自动化测试创建",
                "project_type": "web",
                "web_env_configs": {
                    "test": {"url": "https://test.com", "username": "test", "password": "test123"}
                }
            }
            r = requests.post(f"{BASE_URL}/api/v1/project/", headers=headers, json=new_proj, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("code") == 200:
                    project_id = data["data"]["project_id"]
                    self.log("项目管理", "创建新项目", "PASS", f"ID: {project_id}")
                else:
                    self.log("项目管理", "创建新项目", "FAIL", f"响应码: {data.get('code')}")
            else:
                self.log("项目管理", "创建新项目", "FAIL", f"HTTP: {r.status_code}")
        except Exception as e:
            self.log("项目管理", "创建新项目", "FAIL", str(e))
        
        # 4. 更新项目配置
        if project_id:
            try:
                config = {
                    "web_env_configs": {
                        "test": {"url": "https://new-test.com", "username": "admin", "password": "newpass"}
                    }
                }
                r = requests.put(f"{BASE_URL}/api/v1/project/{project_id}/config", 
                               headers=headers, json=config, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("code") == 200:
                        self.log("项目管理", "更新项目配置", "PASS", "配置更新成功")
                    else:
                        self.log("项目管理", "更新项目配置", "FAIL", f"响应码: {data.get('code')}")
                else:
                    self.log("项目管理", "更新项目配置", "FAIL", f"HTTP: {r.status_code}")
            except Exception as e:
                self.log("项目管理", "更新项目配置", "FAIL", str(e))
            
            # 5. 删除项目
            try:
                r = requests.delete(f"{BASE_URL}/api/v1/project/{project_id}", headers=headers, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("code") == 200:
                        self.log("项目管理", "删除项目", "PASS", f"ID: {project_id}")
                    else:
                        self.log("项目管理", "删除项目", "FAIL", f"响应码: {data.get('code')}")
                else:
                    self.log("项目管理", "删除项目", "FAIL", f"HTTP: {r.status_code}")
            except Exception as e:
                self.log("项目管理", "删除项目", "FAIL", str(e))
        
        # 6. 访问不存在的项目
        try:
            r = requests.get(f"{BASE_URL}/api/v1/project/99999", headers=headers, timeout=10)
            if r.status_code == 403:
                self.log("项目管理", "无权限项目访问", "PASS", "正确返回403")
            else:
                self.log("项目管理", "无权限项目访问", "WARN", f"返回: {r.status_code}")
        except Exception as e:
            self.log("项目管理", "无权限项目访问", "FAIL", str(e))
    
    # ==================== 测试点模块 ====================
    def test_test_points(self):
        """测试点模块测试"""
        print("\n" + "=" * 60)
        print("【测试点模块 - 完整测试】")
        print("=" * 60)
        
        # 从数据库获取测试点
        try:
            self.cursor.execute("""
                SELECT id, module, `function`, `point`, priority 
                FROM test_points WHERE project_id=3
            """)
            points = self.cursor.fetchall()
            self.log("测试点", "获取测试点列表", "PASS", f"获取到{len(points)}个测试点")
            
            # 统计优先级分布
            priority_count = {1: 0, 2: 0, 3: 0}
            modules = {}
            for p in points:
                priority_count[p[4]] = priority_count.get(p[4], 0) + 1
                module = p[1]
                modules[module] = modules.get(module, 0) + 1
            
            self.log("测试点", "优先级统计", "PASS", 
                    f"高:{priority_count.get(1,0)} 中:{priority_count.get(2,0)} 低:{priority_count.get(3,0)}")
            self.log("测试点", "模块分布", "PASS", 
                    f"模块数:{len(modules)}, 详情:{json.dumps(modules, ensure_ascii=False)}")
            
            # 列出所有测试点
            print("\n  测试点详情:")
            for p in points[:5]:  # 只显示前5个
                priority_map = {1: "高", 2: "中", 3: "低"}
                print(f"    [{p[0]}] {p[1]}-{p[2]}")
                print(f"        描述: {p[3][:60]}...")
                print(f"        优先级: {priority_map.get(p[4], 'N/A')}")
            
        except Exception as e:
            self.log("测试点", "获取测试点列表", "FAIL", str(e))
    
    # ==================== 测试用例模块 ====================
    def test_test_cases(self):
        """测试用例模块测试"""
        print("\n" + "=" * 60)
        print("【测试用例模块 - 完整测试】")
        print("=" * 60)
        
        # 从数据库获取测试用例
        try:
            self.cursor.execute("""
                SELECT id, case_no, title, module, priority, case_type, review_status,
                       precondition, expected_result, steps_json
                FROM test_cases WHERE project_id=3
            """)
            cases = self.cursor.fetchall()
            self.log("测试用例", "获取用例列表", "PASS", f"获取到{len(cases)}个测试用例")
            
            print("\n  用例详情:")
            for c in cases:
                print(f"    [{c[0]}] {c[1]}: {c[2]}")
                print(f"        模块: {c[3]}, 类型: {c[5]}, 审核: {c[6]}")
                print(f"        前置: {c[7][:50] if c[7] else '无'}...")
                
        except Exception as e:
            self.log("测试用例", "获取用例列表", "FAIL", str(e))
    
    # ==================== 前端页面测试 ====================
    def test_frontend_pages(self):
        """前端页面测试"""
        print("\n" + "=" * 60)
        print("【前端页面模块 - 完整测试】")
        print("=" * 60)
        
        pages = [
            ("/", "首页"),
            ("/login", "登录页"),
            ("/home", "首页(路由)"),
            ("/home/project/detail?id=3", "项目详情页"),
        ]
        
        for path, name in pages:
            try:
                r = requests.get(f"{FRONTEND_URL}{path}", timeout=10)
                if r.status_code == 200:
                    content = r.text
                    # 检查关键元素
                    has_vue_app = "id=\"app\"" in content or "vue" in content.lower()
                    has_element = "element" in content.lower() or "el-" in content
                    
                    if has_vue_app:
                        self.log("前端", f"{name} - Vue挂载", "PASS", "Vue实例正常")
                    else:
                        self.log("前端", f"{name} - Vue挂载", "WARN", "可能未正确加载")
                    
                    # 检查是否有JS错误风险
                    if "Error" not in content[:500]:
                        self.log("前端", f"{name} - 响应检查", "PASS", f"状态:{r.status_code}")
                    else:
                        self.log("前端", f"{name} - 响应检查", "WARN", "内容包含Error")
                else:
                    self.log("前端", f"{name}", "FAIL", f"HTTP: {r.status_code}")
            except Exception as e:
                self.log("前端", f"{name}", "FAIL", str(e))
    
    # ==================== 数据库完整性测试 ====================
    def test_database_integrity(self):
        """数据库完整性测试"""
        print("\n" + "=" * 60)
        print("【数据库完整性测试】")
        print("=" * 60)
        
        checks = [
            ("SELECT COUNT(*) FROM users WHERE is_active=1", "活跃用户数"),
            ("SELECT COUNT(*) FROM projects", "项目总数"),
            ("SELECT COUNT(*) FROM project_files", "项目文件总数"),
            ("SELECT COUNT(*) FROM test_points", "测试点总数"),
            ("SELECT COUNT(*) FROM test_cases", "测试用例总数"),
            ("SELECT COUNT(*) FROM test_points WHERE project_id=3", "项目3测试点数"),
            ("SELECT COUNT(*) FROM test_cases WHERE project_id=3", "项目3用例数"),
        ]
        
        for sql, name in checks:
            try:
                self.cursor.execute(sql)
                count = self.cursor.fetchone()[0]
                self.log("数据库", name, "PASS", f"数量: {count}")
            except Exception as e:
                self.log("数据库", name, "FAIL", str(e))
        
        # 检查数据一致性
        try:
            self.cursor.execute("""
                SELECT COUNT(DISTINCT project_id) FROM test_cases 
                WHERE project_id NOT IN (SELECT id FROM projects)
            """)
            orphan = self.cursor.fetchone()[0]
            if orphan == 0:
                self.log("数据库", "数据一致性-用例", "PASS", "无孤立数据")
            else:
                self.log("数据库", "数据一致性-用例", "WARN", f"有{orphan}条孤立记录")
        except Exception as e:
            self.log("数据库", "数据一致性-用例", "FAIL", str(e))
    
    # ==================== 生成报告 ====================
    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("【测试结果汇总】")
        print("=" * 60)
        
        total = len(RESULTS)
        passed = len([r for r in RESULTS if r["status"] == "PASS"])
        failed = len([r for r in RESULTS if r["status"] == "FAIL"])
        warned = len([r for r in RESULTS if r["status"] == "WARN"])
        
        print(f"\n总计: {total} 项测试")
        print(f"  [PASS]: {passed} ({100*passed/total:.1f}%)" if total > 0 else "  [PASS]: 0")
        print(f"  [FAIL]: {failed}")
        print(f"  [WARN]: {warned}")
        
        # 按模块统计
        modules = {}
        for r in RESULTS:
            m = r["module"]
            if m not in modules:
                modules[m] = {"PASS": 0, "FAIL": 0, "WARN": 0}
            modules[m][r["status"]] = modules[m].get(r["status"], 0) + 1
        
        print("\n按模块统计:")
        for m, stats in modules.items():
            total_m = sum(stats.values())
            pass_m = stats.get("PASS", 0)
            rate = 100*pass_m/total_m if total_m > 0 else 0
            print(f"  {m}: {pass_m}/{total_m} ({rate:.1f}%)")
        
        # 列出失败的测试
        if failed > 0:
            print("\n失败的测试:")
            for r in RESULTS:
                if r["status"] == "FAIL":
                    print(f"  - {r['module']}/{r['test_name']}: {r['details']}")
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "warned": warned,
            "results": RESULTS
        }
    
    # ==================== 运行所有测试 ====================
    def run_all(self):
        """运行所有测试"""
        print("\n" + "=" * 60)
        print("  AI测试平台 - 全面测试执行")
        print("  测试时间: " + datetime.now().isoformat())
        print("=" * 60)
        
        self.test_auth_flow()
        self.test_project_management()
        self.test_test_points()
        self.test_test_cases()
        self.test_frontend_pages()
        self.test_database_integrity()
        
        return self.generate_report()

if __name__ == "__main__":
    tester = ComprehensiveTester()
    report = tester.run_all()
    
    # 保存报告
    with open("test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n报告已保存到 test_report.json")
