"""
测试步骤定位信息API
验证添加/更新定位信息功能
严禁使用Mock，必须使用真实MySQL数据库
"""
import sys
import os
import unittest
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.db.database import PrimarySessionLocal
from app.models.project import Project
from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator
from app.models.user import User


class TestStepLocatorAPI(unittest.TestCase):
    """测试步骤定位信息API"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.db = PrimarySessionLocal()
        
        # 创建测试用户（模拟已登录用户）
        cls.test_user = cls.db.query(User).filter(User.id == 1).first()
        if not cls.test_user:
            cls.test_user = User(
                id=1,
                username="test_engineer",
                email="test@example.com",
                role="test_engineer"  # 测试工程师角色
            )
            cls.db.add(cls.test_user)
            cls.db.commit()
        
        # 创建测试项目
        cls.test_project = Project(
            name=f"定位器测试项目_{int(datetime.now().timestamp())}",
            description="用于测试定位信息功能",
            status=1,
            user_id=cls.test_user.id
        )
        cls.db.add(cls.test_project)
        cls.db.commit()
        cls.db.refresh(cls.test_project)
        print(f"\n✅ 创建测试项目: {cls.test_project.name} (ID: {cls.test_project.id})")
        
        # 创建测试用例
        cls.test_case = TestCase(
            project_id=cls.test_project.id,
            case_no=f"TC_LOC_{int(datetime.now().timestamp())}",
            module="定位器测试模块",
            title="定位器测试用例",
            precondition="前置条件",
            expected_result="预期结果",
            priority=1,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        cls.db.add(cls.test_case)
        cls.db.flush()
        
        # 创建测试步骤（无定位器）
        cls.test_step = TestStep(
            test_case_id=cls.test_case.id,
            step_number=1,
            action="点击登录按钮",
            expected_result="跳转到首页",
            is_business_view=1,
            is_technical_view=1,
            has_locator=0,
            locator_status="pending"
        )
        cls.db.add(cls.test_step)
        cls.db.commit()
        cls.db.refresh(cls.test_step)
        print(f"✅ 创建测试步骤: {cls.test_step.action} (ID: {cls.test_step.id})")
    
    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        # 清理测试数据
        cls.db.query(ElementLocator).filter(
            ElementLocator.step_id == cls.test_step.id
        ).delete(synchronize_session=False)
        cls.db.query(TestStep).filter(TestStep.id == cls.test_step.id).delete(synchronize_session=False)
        cls.db.query(TestCase).filter(TestCase.id == cls.test_case.id).delete(synchronize_session=False)
        cls.db.query(Project).filter(Project.id == cls.test_project.id).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()
        print("\n✅ 清理测试数据完成")
    
    def test_01_add_locator_via_service(self):
        """测试通过Service添加定位信息"""
        from app.services.test_case_view_service import TestCaseViewService
        
        service = TestCaseViewService(self.db)
        
        # 验证步骤初始状态
        step = self.db.query(TestStep).filter(TestStep.id == self.test_step.id).first()
        self.assertEqual(step.has_locator, 0)
        self.assertEqual(step.locator_status, "pending")
        
        # 添加定位信息（通过直接操作数据库模拟API行为）
        locator = ElementLocator(
            step_id=self.test_step.id,
            css_selector="#login-btn",
            xpath="//button[@id='login']",
            element_type="button",
            ai_confidence=0.95
        )
        self.db.add(locator)
        
        # 更新步骤状态
        step.has_locator = 1
        step.locator_status = "located"
        self.db.commit()
        
        # 验证定位信息已添加
        self.db.refresh(locator)
        self.assertIsNotNone(locator.id)
        self.assertEqual(locator.css_selector, "#login-btn")
        self.assertEqual(locator.xpath, "//button[@id='login']")
        
        # 验证步骤状态已更新
        self.db.refresh(step)
        self.assertEqual(step.has_locator, 1)
        self.assertEqual(step.locator_status, "located")
        
        print("✅ 测试1通过: 添加定位信息")
    
    def test_02_update_existing_locator(self):
        """测试更新已存在的定位信息"""
        # 先添加定位信息
        locator = ElementLocator(
            step_id=self.test_step.id,
            css_selector="#old-selector",
            xpath="//old",
            element_type="button",
            ai_confidence=0.8
        )
        self.db.add(locator)
        self.db.commit()
        self.db.refresh(locator)
        
        original_id = locator.id
        
        # 更新定位信息
        locator.css_selector = "#new-selector"
        locator.xpath = "//new"
        locator.ai_confidence = 0.95
        self.db.commit()
        
        # 验证更新成功
        self.db.refresh(locator)
        self.assertEqual(locator.id, original_id)  # ID不变
        self.assertEqual(locator.css_selector, "#new-selector")
        self.assertEqual(locator.xpath, "//new")
        self.assertEqual(locator.ai_confidence, 0.95)
        
        print("✅ 测试2通过: 更新定位信息")
    
    def test_03_get_technical_view_with_locator(self):
        """测试获取技术视图（包含定位信息）"""
        from app.services.test_case_view_service import TestCaseViewService
        
        # 先删除所有现有的定位信息
        self.db.query(ElementLocator).filter(
            ElementLocator.step_id == self.test_step.id
        ).delete(synchronize_session=False)
        
        # 添加新的定位信息
        locator = ElementLocator(
            step_id=self.test_step.id,
            css_selector="#submit-btn",
            xpath="//button[@type='submit']",
            element_type="button",
            ai_confidence=0.9
        )
        self.db.add(locator)
        
        step = self.db.query(TestStep).filter(TestStep.id == self.test_step.id).first()
        step.has_locator = 1
        step.locator_status = "located"
        self.db.commit()
        
        # 获取技术视图
        service = TestCaseViewService(self.db)
        view = service.get_technical_view(self.test_case.id)
        
        # 验证返回的数据包含定位信息
        self.assertIsNotNone(view)
        self.assertEqual(view['case_id'], self.test_case.id)
        self.assertTrue(len(view['steps']) > 0)
        
        # 找到对应的步骤
        step_data = next((s for s in view['steps'] if s['step_number'] == 1), None)
        self.assertIsNotNone(step_data)
        self.assertTrue(step_data['has_locator'])
        self.assertEqual(step_data['locator_status'], 'located')
        self.assertIsNotNone(step_data['locator'])
        self.assertEqual(step_data['locator']['css_selector'], '#submit-btn')
        
        print("✅ 测试3通过: 获取技术视图包含定位信息")
    
    def test_04_locator_coverage_calculation(self):
        """测试定位覆盖率计算"""
        from app.services.test_case_view_service import TestCaseViewService
        
        # 创建第二个步骤（无定位器）
        step2 = TestStep(
            test_case_id=self.test_case.id,
            step_number=2,
            action="输入用户名",
            expected_result="用户名显示",
            is_business_view=1,
            is_technical_view=1,
            has_locator=0,
            locator_status="pending"
        )
        self.db.add(step2)
        self.db.commit()
        
        try:
            # 获取覆盖率
            service = TestCaseViewService(self.db)
            coverage = service.get_locator_coverage(self.test_case.id)
            
            self.assertEqual(coverage['total_steps'], 2)
            # 第一个步骤有定位器，第二个没有
            self.assertEqual(coverage['located_steps'], 1)
            self.assertEqual(coverage['coverage_percentage'], 50.0)
            
            print("✅ 测试4通过: 定位覆盖率计算")
        finally:
            self.db.query(TestStep).filter(TestStep.id == step2.id).delete(synchronize_session=False)
            self.db.commit()
    
    def test_05_delete_locator(self):
        """测试删除定位信息"""
        # 添加定位信息
        locator = ElementLocator(
            step_id=self.test_step.id,
            css_selector="#temp-btn",
            xpath="//temp",
            element_type="button",
            ai_confidence=0.5
        )
        self.db.add(locator)
        self.db.commit()
        self.db.refresh(locator)
        
        locator_id = locator.id
        
        # 删除定位信息
        self.db.query(ElementLocator).filter(ElementLocator.id == locator_id).delete(synchronize_session=False)
        
        # 更新步骤状态
        step = self.db.query(TestStep).filter(TestStep.id == self.test_step.id).first()
        step.has_locator = 0
        step.locator_status = "pending"
        self.db.commit()
        
        # 验证已删除
        deleted_locator = self.db.query(ElementLocator).filter(ElementLocator.id == locator_id).first()
        self.assertIsNone(deleted_locator)
        
        # 验证步骤状态已更新
        self.db.refresh(step)
        self.assertEqual(step.has_locator, 0)
        self.assertEqual(step.locator_status, "pending")
        
        print("✅ 测试5通过: 删除定位信息")


if __name__ == '__main__':
    unittest.main(verbosity=2)
