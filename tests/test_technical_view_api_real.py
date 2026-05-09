"""
技术视图API真实测试
严禁使用Mock，必须使用真实MySQL数据库测�?
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

import unittest
from datetime import datetime

from app.models.element_locator import ElementLocator
from app.db.database import PrimarySessionLocal
from app.services.test_case_view_service import TestCaseViewService
from app.models.project import Project
from app.models.test_case import TestCase, TestStep


class TestTechnicalViewAPIReal(unittest.TestCase):
    """技术视图API真实测试�?""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.db = PrimarySessionLocal()
        cls.service = TestCaseViewService(cls.db)
        
        # 创建测试项目
        cls.test_project = Project(
            name=f"技术视图测试项目_{int(datetime.now().timestamp())}",
            description="用于测试技术视图API",
            status=1,
            user_id=1
        )
        cls.db.add(cls.test_project)
        cls.db.commit()
        cls.db.refresh(cls.test_project)
        print(f"\n�?创建测试项目: {cls.test_project.name} (ID: {cls.test_project.id})")
        
        # 创建测试用例
        cls.test_case = TestCase(
            project_id=cls.test_project.id,
            case_no=f"TC_TECH_{int(datetime.now().timestamp())}",
            module="技术视图测试模�?,
            title="技术视图测试用�?,
            precondition="1. 系统已登录\n2. 网络连接正常",
            expected_result="操作成功，页面跳转正�?,
            priority=1,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        cls.db.add(cls.test_case)
        cls.db.flush()
        
        # 创建测试步骤（部分有定位信息，部分没有）
        steps_data = [
            {
                "action": "打开登录页面",
                "expected": "页面加载成功",
                "has_locator": 1,
                "locator_status": "located",
                "css": "input#username",
                "xpath": "//input[@id='username']",
                "elem_type": "input"
            },
            {
                "action": "输入用户�?,
                "expected": "用户名显示正�?,
                "has_locator": 1,
                "locator_status": "located",
                "css": "input#username",
                "xpath": "//input[@id='username']",
                "elem_type": "input"
            },
            {
                "action": "点击登录按钮",
                "expected": "登录成功，跳转首�?,
                "has_locator": 0,
                "locator_status": "pending",
                "css": None,
                "xpath": None,
                "elem_type": None
            }
        ]
        
        for i, data in enumerate(steps_data, 1):
            step = TestStep(
                test_case_id=cls.test_case.id,
                step_number=i,
                action=data["action"],
                expected_result=data["expected"],
                is_business_view=1,
                is_technical_view=1,
                has_locator=data["has_locator"],
                locator_status=data["locator_status"]
            )
            cls.db.add(step)
            cls.db.flush()
            
            # 为有定位的步骤添加定位信�?
            if data["has_locator"] == 1:
                locator = ElementLocator(
                    step_id=step.id,
                    css_selector=data["css"],
                    xpath=data["xpath"],
                    element_type=data["elem_type"],
                    ai_confidence=0.95
                )
                cls.db.add(locator)
        
        cls.db.commit()
        cls.db.refresh(cls.test_case)
        print(f"�?创建测试用例: {cls.test_case.title} (ID: {cls.test_case.id})")
    
    @classmethod
    def tearDownClass(cls):
        """测试类清�?""
        try:
            # 删除定位信息
            steps = cls.db.query(TestStep).filter(
                TestStep.test_case_id == cls.test_case.id
            ).all()
            for step in steps:
                cls.db.query(ElementLocator).filter(
                    ElementLocator.step_id == step.id
                ).delete()
                cls.db.delete(step)
            
            # 删除测试用例和项�?
            cls.db.delete(cls.test_case)
            cls.db.delete(cls.test_project)
            cls.db.commit()
            print("�?清理测试数据完成")
        except Exception as e:
            cls.db.rollback()
            print(f"⚠️ 清理测试数据失败: {e}")
        finally:
            cls.db.close()
    
    def test_01_get_technical_view_success(self):
        """测试1: 成功获取技术视�?""
        view_data = self.service.get_technical_view(self.test_case.id)
        
        self.assertIsNotNone(view_data)
        self.assertEqual(view_data["case_id"], self.test_case.id)
        self.assertEqual(view_data["case_no"], self.test_case.case_no)
        self.assertEqual(view_data["title"], self.test_case.title)
        self.assertEqual(view_data["module"], self.test_case.module)
        self.assertEqual(view_data["priority"], self.test_case.priority)
        self.assertEqual(view_data["case_type"], self.test_case.case_type)
        
        # 验证步骤
        self.assertEqual(len(view_data["steps"]), 3)
        
        # 验证第一个步骤有定位信息
        step1 = view_data["steps"][0]
        self.assertEqual(step1["step_number"], 1)
        self.assertEqual(step1["action"], "打开登录页面")
        self.assertTrue(step1["has_locator"])
        self.assertEqual(step1["locator_status"], "located")
        self.assertIsNotNone(step1["locator"])
        self.assertEqual(step1["locator"]["css_selector"], "input#username")
        self.assertEqual(step1["locator"]["xpath"], "//input[@id='username']")
        
        # 验证第三个步骤没有定位信�?
        step3 = view_data["steps"][2]
        self.assertEqual(step3["step_number"], 3)
        self.assertFalse(step3["has_locator"])
        self.assertEqual(step3["locator_status"], "pending")
        self.assertIsNone(step3["locator"])
        
        # 验证定位覆盖�?
        self.assertAlmostEqual(view_data["locator_coverage"], 66.67, places=1)  # 2/3 = 66.67%
        
        print("�?测试1通过: 成功获取技术视�?)
    
    def test_02_get_technical_view_not_found(self):
        """测试2: 获取不存在用例的技术视�?""
        view_data = self.service.get_technical_view(999999)
        self.assertIsNone(view_data)
        print("�?测试2通过: 验证不存在用�?)
    
    def test_03_get_locator_coverage(self):
        """测试3: 获取定位覆盖率统�?""
        coverage = self.service.get_locator_coverage(self.test_case.id)
        
        self.assertEqual(coverage["total_steps"], 3)
        self.assertEqual(coverage["located_steps"], 2)
        self.assertEqual(coverage["pending_steps"], 1)
        self.assertEqual(coverage["failed_steps"], 0)
        self.assertAlmostEqual(coverage["coverage_percentage"], 66.67, places=1)
        
        print("�?测试3通过: 获取定位覆盖率统�?)
    
    def test_04_technical_view_filter_by_flag(self):
        """测试4: 验证只返回is_technical_view=1的步�?""
        # 创建一个is_technical_view=0的步�?
        hidden_step = TestStep(
            test_case_id=self.test_case.id,
            step_number=4,
            action="隐藏步骤",
            expected_result="不应该显�?,
            is_business_view=1,
            is_technical_view=0,  # 不显示在技术视�?
            has_locator=1,
            locator_status="located"
        )
        self.db.add(hidden_step)
        self.db.commit()
        
        # 获取技术视�?
        view_data = self.service.get_technical_view(self.test_case.id)
        
        # 验证只有3个步骤（不包含隐藏的�?
        self.assertEqual(len(view_data["steps"]), 3)
        step_numbers = [s["step_number"] for s in view_data["steps"]]
        self.assertNotIn(4, step_numbers)
        
        # 清理
        self.db.delete(hidden_step)
        self.db.commit()
        
        print("�?测试4通过: 验证技术视图过�?)
    
    def test_05_empty_steps_coverage(self):
        """测试5: 空步骤的覆盖�?""
        # 创建一个没有步骤的测试用例
        empty_case = TestCase(
            project_id=self.test_project.id,
            case_no=f"TC_EMPTY_{int(datetime.now().timestamp())}",
            module="空步骤模�?,
            title="空步骤测试用�?,
            precondition="",
            expected_result="",
            priority=2,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        self.db.add(empty_case)
        self.db.commit()
        self.db.refresh(empty_case)
        
        # 获取覆盖�?
        coverage = self.service.get_locator_coverage(empty_case.id)
        self.assertEqual(coverage["total_steps"], 0)
        self.assertEqual(coverage["coverage_percentage"], 0.0)
        
        # 获取技术视�?
        view_data = self.service.get_technical_view(empty_case.id)
        self.assertEqual(len(view_data["steps"]), 0)
        self.assertEqual(view_data["locator_coverage"], 0.0)
        
        # 清理
        self.db.delete(empty_case)
        self.db.commit()
        
        print("�?测试5通过: 空步骤覆盖率")


if __name__ == '__main__':
    unittest.main(verbosity=2)
