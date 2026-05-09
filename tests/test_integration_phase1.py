"""
第一阶段前后端联调测试（端到端测试）

测试原则（强制执行）�?
1. 真实执行优先：所有测试必须使用真实环境，严禁使用Mock
2. 覆盖率要求：联调测试必须覆盖所有核心业务流�?
3. 测试准确性：测试通过率必�?100%
4. 发现问题优先：测试的目的是发现代码问�?

注意：这些测试使用真实MySQL数据库和真实API调用
"""
import sys
import os
import unittest
import requests
import time
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.db.database import PrimarySessionLocal
from app.models.project import Project
from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator
from app.models.user import User

# API基础URL
BASE_URL = "http://localhost:8000"


def _backend_available():
    """检查后端服务是否可�?""
    try:
        return requests.get(f"{BASE_URL}/api/v1/auth/login", timeout=2).status_code < 500
    except (requests.ConnectionError, requests.Timeout):
        return False


_BACKEND_OK = _backend_available()


@unittest.skipIf(not _BACKEND_OK, f"后端服务不可�?({BASE_URL})，请先启�?FastAPI 服务")
class TestIntegrationPhase1(unittest.TestCase):
    """
    第一阶段联调测试
    验证前后端功能完整性和数据一致�?
    """
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化 - 创建测试数据"""
        cls.db = PrimarySessionLocal()
        
        # 创建测试用户
        cls.test_user = cls.db.query(User).filter(User.id == 1).first()
        if not cls.test_user:
            cls.test_user = User(
                id=1,
                username="test_engineer",
                email="test@example.com",
                role="test_engineer"
            )
            cls.db.add(cls.test_user)
            cls.db.commit()
        
        # 创建测试项目
        cls.test_project = Project(
            name=f"联调测试项目_{int(datetime.now().timestamp())}",
            description="用于联调测试的项�?,
            status=1,
            user_id=cls.test_user.id,
            project_type="web",
            web_env_configs={"test": {"url": "https://example.com", "username": "admin", "password": "admin123"}}
        )
        cls.db.add(cls.test_project)
        cls.db.commit()
        cls.db.refresh(cls.test_project)
        print(f"\n�?创建测试项目: {cls.test_project.name} (ID: {cls.test_project.id})")
        
        # 创建测试用例
        cls.test_case = TestCase(
            project_id=cls.test_project.id,
            case_no=f"TC_INT_{int(datetime.now().timestamp())}",
            module="联调测试模块",
            title="联调测试用例",
            precondition="前置条件",
            expected_result="预期结果",
            priority=1,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        cls.db.add(cls.test_case)
        cls.db.flush()
        
        # 创建测试步骤
        for i in range(1, 4):
            step = TestStep(
                test_case_id=cls.test_case.id,
                step_number=i,
                action=f"操作步骤{i}",
                expected_result=f"预期结果{i}",
                is_business_view=1,
                is_technical_view=1,
                has_locator=0,
                locator_status="pending"
            )
            cls.db.add(step)
        
        cls.db.commit()
        cls.db.refresh(cls.test_case)
        print(f"�?创建测试用例: {cls.test_case.title} (ID: {cls.test_case.id})")
    
    @classmethod
    def tearDownClass(cls):
        """测试类清�?""
        # 清理测试数据
        cls.db.query(ElementLocator).filter(
            ElementLocator.step_id.in_(
                cls.db.query(TestStep.id).filter(TestStep.test_case_id == cls.test_case.id)
            )
        ).delete(synchronize_session=False)
        cls.db.query(TestStep).filter(TestStep.test_case_id == cls.test_case.id).delete(synchronize_session=False)
        cls.db.query(TestCase).filter(TestCase.id == cls.test_case.id).delete(synchronize_session=False)
        cls.db.query(Project).filter(Project.id == cls.test_project.id).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()
        print("\n�?清理测试数据完成")
    
    # ==================== Task 0: 项目配置联调测试 ====================
    
    def test_01_project_config_api(self):
        """联调测试1: 项目被测对象配置API"""
        print("\n🧪 联调测试1: 项目被测对象配置API")
        
        # 测试获取被测对象信息
        response = requests.get(f"{BASE_URL}/api/projects/{self.test_project.id}/test-object")
        self.assertEqual(response.status_code, 200, "获取被测对象信息应该返回200")
        
        data = response.json()
        self.assertEqual(data.get('project_type', data.get('test_object_type', '')), 'web', "项目类型应该为web")
        env_configs = data.get('web_env_configs', {})
        test_env = env_configs.get('test', {}) if isinstance(env_configs, dict) else {}
        self.assertEqual(test_env.get('url', data.get('test_object_url', '')), 'https://example.com', "URL应该匹配")

        # 测试更新被测对象信息
        update_data = {
            'project_type': 'web',
            'web_env_configs': {"test": {"url": "https://updated-example.com", "username": "updated_admin", "password": "updated_password"}}
        }
        response = requests.put(
            f"{BASE_URL}/api/projects/{self.test_project.id}/test-object",
            json=update_data
        )
        self.assertEqual(response.status_code, 200, "更新被测对象信息应该返回200")
        
        # 验证更新成功
        response = requests.get(f"{BASE_URL}/api/projects/{self.test_project.id}/test-object")
        data = response.json()
        env_configs = data.get('web_env_configs', {})
        test_env = env_configs.get('test', {}) if isinstance(env_configs, dict) else {}
        self.assertEqual(test_env.get('url', ''), 'https://updated-example.com', "URL应该已更�?)

        # 恢复原始数据
        requests.put(f"{BASE_URL}/api/projects/{self.test_project.id}/test-object", json={
            'project_type': 'web',
            'web_env_configs': {"test": {"url": "https://example.com", "username": "admin", "password": "admin123"}}
        })
        
        print("�?联调测试1通过: 项目被测对象配置API")
    
    # ==================== Task 6: 用例双视图联调测�?====================
    
    def test_02_business_view_api(self):
        """联调测试2: 业务视图API"""
        print("\n🧪 联调测试2: 业务视图API")
        
        # 测试获取业务视图
        response = requests.get(f"{BASE_URL}/api/test-case/{self.test_case.id}/business-view")
        self.assertEqual(response.status_code, 200, "获取业务视图应该返回200")
        
        data = response.json()
        self.assertEqual(data['case_id'], self.test_case.id, "case_id应该匹配")
        self.assertEqual(data['title'], self.test_case.title, "标题应该匹配")
        self.assertTrue(len(data['steps']) > 0, "应该有步�?)
        
        # 验证步骤数据
        step = data['steps'][0]
        self.assertIn('step_number', step, "步骤应该有step_number")
        self.assertIn('action', step, "步骤应该有action")
        self.assertIn('expected_result', step, "步骤应该有expected_result")
        
        print("�?联调测试2通过: 业务视图API")
    
    def test_03_technical_view_api(self):
        """联调测试3: 技术视图API"""
        print("\n🧪 联调测试3: 技术视图API")
        
        # 测试获取技术视�?
        response = requests.get(f"{BASE_URL}/api/test-case/{self.test_case.id}/technical-view")
        self.assertEqual(response.status_code, 200, "获取技术视图应该返�?00")
        
        data = response.json()
        self.assertEqual(data['case_id'], self.test_case.id, "case_id应该匹配")
        self.assertIn('locator_coverage', data, "应该包含locator_coverage")
        self.assertIn('steps', data, "应该包含steps")
        
        # 验证步骤包含技术信�?
        if data['steps']:
            step = data['steps'][0]
            self.assertIn('has_locator', step, "步骤应该有has_locator")
            self.assertIn('locator_status', step, "步骤应该有locator_status")
        
        print("�?联调测试3通过: 技术视图API")
    
    def test_04_view_switch_consistency(self):
        """联调测试4: 业务视图和技术视图数据一致�?""
        print("\n🧪 联调测试4: 视图数据一致�?)
        
        # 获取业务视图
        business_response = requests.get(f"{BASE_URL}/api/test-case/{self.test_case.id}/business-view")
        business_data = business_response.json()
        
        # 获取技术视�?
        technical_response = requests.get(f"{BASE_URL}/api/test-case/{self.test_case.id}/technical-view")
        technical_data = technical_response.json()
        
        # 验证基本信息一�?
        self.assertEqual(business_data['case_id'], technical_data['case_id'], "case_id应该一�?)
        self.assertEqual(business_data['title'], technical_data['title'], "标题应该一�?)
        self.assertEqual(business_data['case_no'], technical_data['case_no'], "case_no应该一�?)
        
        # 验证步骤数量一�?
        self.assertEqual(
            len(business_data['steps']),
            len(technical_data['steps']),
            "步骤数量应该一�?
        )
        
        print("�?联调测试4通过: 视图数据一致�?)
    
    # ==================== Excel导入导出联调测试 ====================
    
    def test_05_export_to_excel(self):
        """联调测试5: 导出双视图格式Excel"""
        print("\n🧪 联调测试5: 导出双视图格式Excel")
        
        import tempfile
        import pandas as pd
        
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, 'test_export.xlsx')
        
        try:
            # 调用导出API
            response = requests.post(
                f"{BASE_URL}/api/test-case/{self.test_case.id}/export-excel",
                stream=True
            )
            self.assertEqual(response.status_code, 200, "导出Excel应该返回200")
            
            # 保存文件
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 验证文件存在
            self.assertTrue(os.path.exists(temp_path), "Excel文件应该存在")
            
            # 验证文件内容
            xl = pd.ExcelFile(temp_path)
            self.assertIn('用例信息', xl.sheet_names, "应该有用例信息sheet")
            self.assertIn('测试步骤', xl.sheet_names, "应该有测试步骤sheet")
            
            # 验证用例信息
            case_info = pd.read_excel(temp_path, sheet_name='用例信息')
            self.assertEqual(len(case_info), 1, "应该有一条用例信�?)
            
            print("�?联调测试5通过: 导出双视图格式Excel")
        finally:
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    def test_06_export_functional_excel(self):
        """联调测试6: 导出功能用例Excel（第三方格式�?""
        print("\n🧪 联调测试6: 导出功能用例Excel")
        
        import tempfile
        import pandas as pd
        
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, 'test_functional.xlsx')
        
        try:
            # 调用导出API
            response = requests.post(
                f"{BASE_URL}/api/test-case/export-functional-excel",
                json={'case_ids': [self.test_case.id]},
                stream=True
            )
            self.assertEqual(response.status_code, 200, "导出功能用例Excel应该返回200")
            
            # 保存文件
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 验证文件存在
            self.assertTrue(os.path.exists(temp_path), "Excel文件应该存在")
            
            # 验证文件内容
            df = pd.read_excel(temp_path)
            self.assertGreater(len(df), 0, "应该至少有一条用�?)
            self.assertIn('标题', df.columns, "应该有标题列")
            self.assertIn('步骤描述', df.columns, "应该有步骤描述列")
            
            print("�?联调测试6通过: 导出功能用例Excel")
        finally:
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    def test_07_import_from_excel(self):
        """联调测试7: 从Excel导入用例"""
        print("\n🧪 联调测试7: 从Excel导入用例")
        
        import tempfile
        import pandas as pd
        
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, 'test_import.xlsx')
        
        try:
            # 创建测试Excel文件
            with pd.ExcelWriter(temp_path, engine='openpyxl') as writer:
                case_df = pd.DataFrame([{
                    '用例编号': f'IMPORT_{int(datetime.now().timestamp())}',
                    '用例标题': '导入测试用例',
                    '所属模�?: '导入测试',
                    '前置条件': '前置条件',
                    '预期结果': '预期结果',
                    '优先�?: 1,
                    '总步骤数': 2
                }])
                case_df.to_excel(writer, sheet_name='用例信息', index=False)
                
                steps_df = pd.DataFrame([
                    {
                        '步骤编号': 1,
                        '操作步骤': '第一步操�?,
                        '预期结果': '第一步预�?,
                        '业务视图': '�?,
                        '技术视�?: '�?,
                        '已定�?: '�?,
                        '定位状�?: 'pending',
                        'CSS选择�?: '',
                        'XPath': '',
                        '元素类型': ''
                    },
                    {
                        '步骤编号': 2,
                        '操作步骤': '第二步操�?,
                        '预期结果': '第二步预�?,
                        '业务视图': '�?,
                        '技术视�?: '�?,
                        '已定�?: '�?,
                        '定位状�?: 'pending',
                        'CSS选择�?: '',
                        'XPath': '',
                        '元素类型': ''
                    }
                ])
                steps_df.to_excel(writer, sheet_name='测试步骤', index=False)
            
            # 调用导入API
            with open(temp_path, 'rb') as f:
                files = {'file': ('test_import.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
                data = {'project_id': self.test_project.id}
                response = requests.post(
                    f"{BASE_URL}/api/test-case/import-excel",
                    files=files,
                    data=data
                )
            
            self.assertEqual(response.status_code, 200, "导入Excel应该返回200")
            
            result = response.json()
            self.assertIn('case_id', result, "应该返回case_id")
            
            # 验证导入的数�?
            imported_case_id = result['case_id']
            case = self.db.query(TestCase).filter(TestCase.id == imported_case_id).first()
            self.assertIsNotNone(case, "导入的用例应该存�?)
            self.assertEqual(case.title, '导入测试用例', "标题应该匹配")
            self.assertEqual(len(case.test_steps), 2, "应该�?个步�?)
            
            # 清理导入的数�?
            self.db.query(TestStep).filter(TestStep.test_case_id == imported_case_id).delete(synchronize_session=False)
            self.db.query(TestCase).filter(TestCase.id == imported_case_id).delete(synchronize_session=False)
            self.db.commit()
            
            print("�?联调测试7通过: 从Excel导入用例")
        finally:
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    # ==================== 定位信息联调测试 ====================
    
    def test_08_add_step_locator(self):
        """联调测试8: 添加步骤定位信息"""
        print("\n🧪 联调测试8: 添加步骤定位信息")
        
        # 获取一个测试步�?
        step = self.db.query(TestStep).filter(TestStep.test_case_id == self.test_case.id).first()
        self.assertIsNotNone(step, "应该存在测试步骤")
        
        # 调用添加定位信息API
        locator_data = {
            'css_selector': '#submit-button',
            'xpath': '//button[@id="submit"]',
            'element_type': 'button'
        }
        response = requests.post(
            f"{BASE_URL}/api/test-case/steps/{step.id}/locator",
            json=locator_data
        )
        self.assertEqual(response.status_code, 200, "添加定位信息应该返回200")
        
        result = response.json()
        self.assertIn('locator_id', result, "应该返回locator_id")
        self.assertEqual(result['css_selector'], '#submit-button', "CSS选择器应该匹�?)
        
        # 验证数据库中的数�?
        self.db.refresh(step)
        self.assertEqual(step.has_locator, 1, "步骤应该标记为有定位�?)
        self.assertEqual(step.locator_status, 'located', "定位状态应该为located")
        
        # 验证定位器记�?
        locator = self.db.query(ElementLocator).filter(ElementLocator.step_id == step.id).first()
        self.assertIsNotNone(locator, "应该存在定位器记�?)
        self.assertEqual(locator.css_selector, '#submit-button', "CSS选择器应该匹�?)
        
        print("�?联调测试8通过: 添加步骤定位信息")
    
    def test_09_update_step_locator(self):
        """联调测试9: 更新步骤定位信息"""
        print("\n🧪 联调测试9: 更新步骤定位信息")
        
        # 获取一个已有定位器的步�?
        step = self.db.query(TestStep).filter(TestStep.test_case_id == self.test_case.id).first()
        
        # 先添加定位信�?
        locator_data = {
            'css_selector': '#old-button',
            'xpath': '//button[@id="old"]',
            'element_type': 'button'
        }
        requests.post(f"{BASE_URL}/api/test-case/steps/{step.id}/locator", json=locator_data)
        
        # 更新定位信息
        update_data = {
            'css_selector': '#new-button',
            'xpath': '//button[@id="new"]',
            'element_type': 'submit'
        }
        response = requests.post(
            f"{BASE_URL}/api/test-case/steps/{step.id}/locator",
            json=update_data
        )
        self.assertEqual(response.status_code, 200, "更新定位信息应该返回200")
        
        result = response.json()
        self.assertIn('locator_id', result, "应该返回locator_id")
        self.assertEqual(result['css_selector'], '#new-button', "CSS选择器应该已更新")
        
        # 验证数据库中的数据已更新
        self.db.refresh(step)
        locator = self.db.query(ElementLocator).filter(ElementLocator.step_id == step.id).first()
        self.assertEqual(locator.css_selector, '#new-button', "CSS选择器应该已更新")
        self.assertEqual(locator.element_type, 'submit', "元素类型应该已更�?)
        
        print("�?联调测试9通过: 更新步骤定位信息")
    
    def test_10_locator_coverage_api(self):
        """联调测试10: 定位覆盖率API"""
        print("\n🧪 联调测试10: 定位覆盖率API")
        
        # 给部分步骤添加定位信�?
        steps = self.db.query(TestStep).filter(TestStep.test_case_id == self.test_case.id).all()
        for i, step in enumerate(steps):
            if i == 0:  # 只给第一个步骤添加定位器
                locator_data = {
                    'css_selector': f'#btn-{i}',
                    'xpath': f'//button[{i}]',
                    'element_type': 'button'
                }
                requests.post(
                    f"{BASE_URL}/api/test-case/steps/{step.id}/locator",
                    json=locator_data
                )
        
        # 调用覆盖率API
        response = requests.get(f"{BASE_URL}/api/test-case/{self.test_case.id}/locator-coverage")
        self.assertEqual(response.status_code, 200, "获取覆盖率应该返�?00")
        
        data = response.json()
        self.assertIn('total_steps', data, "应该包含total_steps")
        self.assertIn('located_steps', data, "应该包含located_steps")
        self.assertIn('coverage_percentage', data, "应该包含coverage_percentage")
        
        # 验证覆盖率计算正确（3个步骤，1个有定位�?= 33.33%�?
        self.assertEqual(data['total_steps'], 3, "总步骤数应该�?")
        self.assertEqual(data['located_steps'], 1, "已定位步骤数应该�?")
        self.assertAlmostEqual(data['coverage_percentage'], 33.33, places=1, msg="覆盖率应该约�?3.33%")
        
        print("�?联调测试10通过: 定位覆盖率API")
    
    # ==================== 视图配置联调测试 ====================
    
    def test_11_update_step_view_config(self):
        """联调测试11: 更新步骤视图配置"""
        print("\n🧪 联调测试11: 更新步骤视图配置")
        
        step = self.db.query(TestStep).filter(TestStep.test_case_id == self.test_case.id).first()
        
        # 更新视图配置
        config_data = {
            'is_business_view': 0,
            'is_technical_view': 1
        }
        response = requests.put(
            f"{BASE_URL}/api/test-case/steps/{step.id}/view-config",
            json=config_data
        )
        self.assertEqual(response.status_code, 200, "更新视图配置应该返回200")
        
        result = response.json()
        self.assertTrue(result['success'], "更新应该成功")
        
        # 验证数据库中的数据已更新
        self.db.refresh(step)
        self.assertEqual(step.is_business_view, 0, "业务视图应该�?")
        self.assertEqual(step.is_technical_view, 1, "技术视图应该为1")
        
        print("�?联调测试11通过: 更新步骤视图配置")
    
    def test_12_batch_update_view_config(self):
        """联调测试12: 批量更新视图配置"""
        print("\n🧪 联调测试12: 批量更新视图配置")
        
        # 批量更新为技术视图不可见
        response = requests.put(
            f"{BASE_URL}/api/test-case/{self.test_case.id}/batch-view-config",
            json={'view_type': 'technical', 'visible': False}
        )
        self.assertEqual(response.status_code, 200, "批量更新应该返回200")
        
        result = response.json()
        self.assertIn('updated_count', result, "应该返回updated_count")
        self.assertGreater(result['updated_count'], 0, "应该至少更新一个步�?)
        
        # 验证数据库中的数据已更新
        steps = self.db.query(TestStep).filter(TestStep.test_case_id == self.test_case.id).all()
        for step in steps:
            self.assertEqual(step.is_technical_view, 0, "技术视图应该都�?")
        
        print("�?联调测试12通过: 批量更新视图配置")
    
    def test_13_view_statistics_api(self):
        """联调测试13: 视图统计API"""
        print("\n🧪 联调测试13: 视图统计API")
        
        response = requests.get(f"{BASE_URL}/api/test-case/{self.test_case.id}/view-statistics")
        self.assertEqual(response.status_code, 200, "获取视图统计应该返回200")
        
        data = response.json()
        self.assertIn('total_steps', data, "应该包含total_steps")
        self.assertIn('business_view_steps', data, "应该包含business_view_steps")
        self.assertIn('technical_view_steps', data, "应该包含technical_view_steps")
        self.assertIn('locator_coverage', data, "应该包含locator_coverage")
        
        print("�?联调测试13通过: 视图统计API")
    
    # ==================== 导出格式联调测试 ====================
    
    def test_14_export_markdown(self):
        """联调测试14: 导出Markdown格式"""
        print("\n🧪 联调测试14: 导出Markdown格式")
        
        response = requests.get(f"{BASE_URL}/api/test-case/{self.test_case.id}/export-markdown")
        self.assertEqual(response.status_code, 200, "导出Markdown应该返回200")
        
        content = response.text
        self.assertIn(self.test_case.title, content, "应该包含用例标题")
        self.assertIn('##', content, "应该是Markdown格式")
        
        print("�?联调测试14通过: 导出Markdown格式")
    
    def test_15_export_html(self):
        """联调测试15: 导出HTML格式"""
        print("\n🧪 联调测试15: 导出HTML格式")
        
        response = requests.get(f"{BASE_URL}/api/test-case/{self.test_case.id}/export-html")
        self.assertEqual(response.status_code, 200, "导出HTML应该返回200")
        
        content = response.text
        self.assertIn('<!DOCTYPE html>', content, "应该是HTML格式")
        self.assertIn(self.test_case.title, content, "应该包含用例标题")
        
        print("�?联调测试15通过: 导出HTML格式")
    
    def test_16_export_python(self):
        """联调测试16: 导出Python脚本"""
        print("\n🧪 联调测试16: 导出Python脚本")
        
        response = requests.get(f"{BASE_URL}/api/test-case/{self.test_case.id}/export-python")
        self.assertEqual(response.status_code, 200, "导出Python应该返回200")
        
        content = response.text
        self.assertIn('import pytest', content, "应该包含pytest导入")
        self.assertIn('async def test_', content, "应该包含测试函数")
        
        print("�?联调测试16通过: 导出Python脚本")
    
    def test_17_export_json(self):
        """联调测试17: 导出JSON格式"""
        print("\n🧪 联调测试17: 导出JSON格式")
        
        response = requests.get(f"{BASE_URL}/api/test-case/{self.test_case.id}/export-json")
        self.assertEqual(response.status_code, 200, "导出JSON应该返回200")
        
        data = response.json()
        self.assertIn('case_id', data, "应该包含case_id")
        self.assertIn('steps', data, "应该包含steps")
        
        print("�?联调测试17通过: 导出JSON格式")


if __name__ == '__main__':
    unittest.main(verbosity=2)
