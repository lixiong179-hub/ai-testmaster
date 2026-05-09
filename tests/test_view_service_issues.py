"""
发现潜在问题的测试用�?
针对未覆盖代码中的潜在bug进行测试
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


class TestViewServiceIssues(unittest.TestCase):
    """发现潜在问题的测�?""
    
    @classmethod
    def setUpClass(cls):
        cls.db = PrimarySessionLocal()
        cls.service = TestCaseViewService(cls.db)
        
        cls.test_project = Project(
            name=f"问题发现测试_{int(datetime.now().timestamp())}",
            description="测试潜在问题",
            status=1,
            user_id=1
        )
        cls.db.add(cls.test_project)
        cls.db.commit()
        cls.db.refresh(cls.test_project)
    
    @classmethod
    def tearDownClass(cls):
        cls.db.delete(cls.test_project)
        cls.db.commit()
        cls.db.close()
    
    def test_technical_view_with_ai_coordinate(self):
        """测试技术视图中AI坐标的处�?- 可能存在的None处理问题"""
        test_case = TestCase(
            project_id=self.test_project.id,
            case_no=f"TC_AI_COORD_{int(datetime.now().timestamp())}",
            module="AI坐标测试",
            title="AI坐标测试用例",
            precondition="",
            expected_result="",
            priority=1,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        self.db.add(test_case)
        self.db.flush()
        
        # 创建带AI坐标的步�?
        step = TestStep(
            test_case_id=test_case.id,
            step_number=1,
            action="AI识别点击",
            expected_result="点击成功",
            is_business_view=1,
            is_technical_view=1,
            has_locator=1,
            locator_status="located"
        )
        self.db.add(step)
        self.db.flush()
        
        # 创建带AI坐标的定位器
        locator = ElementLocator(
            step_id=step.id,
            css_selector=None,
            xpath=None,
            element_type="button",
            ai_coordinate={"x": 100.5, "y": 200.3, "width": 50, "height": 30},
            ai_confidence=0.92
        )
        self.db.add(locator)
        self.db.commit()
        
        try:
            # 测试是否能正确处理AI坐标
            view = self.service.get_technical_view(test_case.id)
            self.assertIsNotNone(view)
            
            step_data = view["steps"][0]
            self.assertIsNotNone(step_data["locator"])
            self.assertIsNotNone(step_data["locator"]["ai_coordinate"])
            self.assertEqual(step_data["locator"]["ai_coordinate"]["x"], 100.5)
            self.assertEqual(step_data["locator"]["ai_coordinate"]["y"], 200.3)
            
        finally:
            self.db.delete(locator)
            self.db.delete(step)
            self.db.delete(test_case)
            self.db.commit()
    
    def test_special_chars_in_action(self):
        """测试特殊字符在操作描述中的处�?- 可能存在的存储或显示问题"""
        test_case = TestCase(
            project_id=self.test_project.id,
            case_no=f"TC_SPECIAL_{int(datetime.now().timestamp())}",
            module="特殊字符测试",
            title="特殊字符测试用例",
            precondition="",
            expected_result="",
            priority=1,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        self.db.add(test_case)
        self.db.flush()
        
        # 创建包含特殊字符的步�?
        special_action = "点击'提交'按钮并输入\"测试文本\""
        step = TestStep(
            test_case_id=test_case.id,
            step_number=1,
            action=special_action,
            expected_result="成功",
            is_business_view=1,
            is_technical_view=1,
            has_locator=0,
            locator_status="pending"
        )
        self.db.add(step)
        self.db.commit()
        
        try:
            # 测试是否能正确处理特殊字�?
            business_view = self.service.get_business_view(test_case.id)
            self.assertIsNotNone(business_view)
            self.assertEqual(business_view.steps[0].action, special_action)
            
            technical_view = self.service.get_technical_view(test_case.id)
            self.assertIsNotNone(technical_view)
            self.assertEqual(technical_view["steps"][0]["action"], special_action)
            
        finally:
            self.db.delete(step)
            self.db.delete(test_case)
            self.db.commit()
    
    def test_locator_with_null_fields(self):
        """测试定位器字段为null的处�?- 可能存在的空指针问题"""
        test_case = TestCase(
            project_id=self.test_project.id,
            case_no=f"TC_NULL_{int(datetime.now().timestamp())}",
            module="空字段测�?,
            title="空字段测试用�?,
            precondition="",
            expected_result="",
            priority=1,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        self.db.add(test_case)
        self.db.flush()
        
        step = TestStep(
            test_case_id=test_case.id,
            step_number=1,
            action="测试步骤",
            expected_result="预期结果",
            is_business_view=1,
            is_technical_view=1,
            has_locator=1,
            locator_status="located"
        )
        self.db.add(step)
        self.db.flush()
        
        # 创建所有可选字段为null的定位器
        locator = ElementLocator(
            step_id=step.id,
            css_selector=None,
            xpath=None,
            element_type=None,
            ai_coordinate=None,
            ai_confidence=None
        )
        self.db.add(locator)
        self.db.commit()
        
        try:
            # 测试是否能正确处理null字段
            view = self.service.get_technical_view(test_case.id)
            self.assertIsNotNone(view)
            
            step_data = view["steps"][0]
            self.assertIsNotNone(step_data["locator"])
            self.assertIsNone(step_data["locator"]["css_selector"])
            self.assertIsNone(step_data["locator"]["xpath"])
            self.assertIsNone(step_data["locator"]["ai_coordinate"])
            
        finally:
            self.db.delete(locator)
            self.db.delete(step)
            self.db.delete(test_case)
            self.db.commit()
    
    def test_concurrent_step_numbers(self):
        """测试步骤编号不连续的情况 - 可能存在的排序或索引问题"""
        test_case = TestCase(
            project_id=self.test_project.id,
            case_no=f"TC_GAP_{int(datetime.now().timestamp())}",
            module="不连续步骤测�?,
            title="不连续步骤测试用�?,
            precondition="",
            expected_result="",
            priority=1,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        self.db.add(test_case)
        self.db.flush()
        
        # 创建不连续的步骤编号�?, 3, 5�?
        for step_num in [1, 3, 5]:
            step = TestStep(
                test_case_id=test_case.id,
                step_number=step_num,
                action=f"步骤{step_num}",
                expected_result=f"预期{step_num}",
                is_business_view=1,
                is_technical_view=1,
                has_locator=0,
                locator_status="pending"
            )
            self.db.add(step)
        
        self.db.commit()
        
        try:
            view = self.service.get_technical_view(test_case.id)
            self.assertIsNotNone(view)
            self.assertEqual(len(view["steps"]), 3)
            
            # 验证步骤顺序正确
            step_numbers = [s["step_number"] for s in view["steps"]]
            self.assertEqual(step_numbers, [1, 3, 5])
            
        finally:
            steps = self.db.query(TestStep).filter(TestStep.test_case_id == test_case.id).all()
            for step in steps:
                self.db.delete(step)
            self.db.delete(test_case)
            self.db.commit()
    
    def test_duplicate_step_numbers(self):
        """测试重复步骤编号的情�?- 可能存在的重复数据处理问�?""
        test_case = TestCase(
            project_id=self.test_project.id,
            case_no=f"TC_DUP_{int(datetime.now().timestamp())}",
            module="重复步骤测试",
            title="重复步骤测试用例",
            precondition="",
            expected_result="",
            priority=1,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        self.db.add(test_case)
        self.db.flush()
        
        # 创建相同编号的步骤（模拟数据异常�?
        for i in range(2):
            step = TestStep(
                test_case_id=test_case.id,
                step_number=1,  # 重复的编�?
                action=f"重复步骤{i+1}",
                expected_result=f"预期{i+1}",
                is_business_view=1,
                is_technical_view=1,
                has_locator=0,
                locator_status="pending"
            )
            self.db.add(step)
        
        self.db.commit()
        
        try:
            # 测试是否能处理重复步�?
            view = self.service.get_technical_view(test_case.id)
            self.assertIsNotNone(view)
            # 应该返回2个步骤（即使编号相同�?
            self.assertEqual(len(view["steps"]), 2)
            
        finally:
            steps = self.db.query(TestStep).filter(TestStep.test_case_id == test_case.id).all()
            for step in steps:
                self.db.delete(step)
            self.db.delete(test_case)
            self.db.commit()
    
    def test_very_long_content(self):
        """测试超长内容的处�?- 可能存在的性能或截断问�?""
        test_case = TestCase(
            project_id=self.test_project.id,
            case_no=f"TC_LONG_{int(datetime.now().timestamp())}",
            module="超长内容测试",
            title="超长内容测试用例",
            precondition="A" * 5000,  # 超长前置条件
            expected_result="B" * 5000,  # 超长预期结果
            priority=1,
            case_type="UI",
            generate_status=1,
            steps_json=[]
        )
        self.db.add(test_case)
        self.db.flush()
        
        step = TestStep(
            test_case_id=test_case.id,
            step_number=1,
            action="C" * 2000,  # 超长操作描述
            expected_result="D" * 2000,  # 超长预期结果
            is_business_view=1,
            is_technical_view=1,
            has_locator=0,
            locator_status="pending"
        )
        self.db.add(step)
        self.db.commit()
        
        try:
            # 测试是否能处理超长内�?
            business_view = self.service.get_business_view(test_case.id)
            self.assertIsNotNone(business_view)
            self.assertEqual(len(business_view.precondition), 5000)
            
            technical_view = self.service.get_technical_view(test_case.id)
            self.assertIsNotNone(technical_view)
            self.assertEqual(len(technical_view["steps"][0]["action"]), 2000)
            
        finally:
            self.db.delete(step)
            self.db.delete(test_case)
            self.db.commit()


if __name__ == '__main__':
    unittest.main(verbosity=2)
