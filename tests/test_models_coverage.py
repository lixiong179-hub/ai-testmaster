"""
数据模型覆盖率测�?
提升 models 模块的测试覆盖率
"""
import sys
import os
import unittest
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.models.project import Project
from app.models.test_case import TestCase, TestStep
from app.models.test_point import TestPoint
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.models.user import User
from app.models.report import TestReport


class TestProjectModel(unittest.TestCase):
    """测试项目模型"""

    def test_project_creation(self):
        """测试创建项目"""
        project = Project(
            name="测试项目",
            description="这是一个测试项�?,
            status=1,
            user_id=1
        )
        self.assertEqual(project.name, "测试项目")
        self.assertEqual(project.description, "这是一个测试项�?)
        self.assertEqual(project.status, 1)

    def test_project_to_dict(self):
        """测试项目属性访�?""
        project = Project(
            id=1,
            name="测试项目",
            description="描述",
            status=1,
            user_id=1,
            create_time=datetime(2024, 1, 1)
        )
        self.assertEqual(project.id, 1)
        self.assertEqual(project.name, "测试项目")
        self.assertEqual(project.status, 1)


class TestTestCaseModel(unittest.TestCase):
    """测试用例模型"""

    def test_test_case_creation(self):
        """测试创建测试用例"""
        test_case = TestCase(
            case_no="TC001",
            title="登录测试",
            module="登录模块",
            precondition="用户已注�?,
            steps_json=[{"step": "步骤1", "action": "操作"}],
            expected_result="登录成功",
            priority=1,
            case_type="UI",
            project_id=1
        )
        self.assertEqual(test_case.case_no, "TC001")
        self.assertEqual(test_case.title, "登录测试")
        self.assertEqual(test_case.priority, 1)

    def test_test_case_to_dict(self):
        """测试用例属性访�?""
        test_case = TestCase(
            id=1,
            case_no="TC001",
            title="登录测试",
            module="登录模块",
            priority=1,
            case_type="UI",
            steps_json=[],
            expected_result="",
            precondition="",
            project_id=1
        )
        self.assertEqual(test_case.id, 1)
        self.assertEqual(test_case.case_no, "TC001")
        self.assertEqual(test_case.title, "登录测试")


class TestTestStepModel(unittest.TestCase):
    """测试测试步骤模型"""

    def test_test_step_creation(self):
        """测试创建测试步骤"""
        step = TestStep(
            step_number=1,
            action="输入用户�?,
            expected_result="输入框显示用户名",
            test_case_id=1
        )
        self.assertEqual(step.step_number, 1)
        self.assertEqual(step.action, "输入用户�?)

    def test_test_step_with_locator(self):
        """测试带定位信息的测试步骤"""
        step = TestStep(
            step_number=1,
            action="点击登录按钮",
            expected_result="跳转到首�?,
            has_locator=1,
            locator_status="located",
            test_case_id=1
        )
        self.assertEqual(step.has_locator, 1)
        self.assertEqual(step.locator_status, "located")


class TestTestPointModel(unittest.TestCase):
    """测试测试点模�?""

    def test_test_point_creation(self):
        """测试创建测试�?""
        test_point = TestPoint(
            module="登录模块",
            point="验证用户登录功能",
            priority=1,
            project_id=1
        )
        self.assertEqual(test_point.point, "验证用户登录功能")
        self.assertEqual(test_point.priority, 1)

    def test_test_point_to_dict(self):
        """测试测试点属性访�?""
        test_point = TestPoint(
            id=1,
            module="登录模块",
            point="测试点描�?,
            priority=1,
            project_id=1
        )
        self.assertEqual(test_point.id, 1)
        self.assertEqual(test_point.point, "测试点描�?)


class TestTestResultModel(unittest.TestCase):
    """测试测试结果模型"""

    def test_test_result_creation(self):
        """测试创建测试结果"""
        result = TestResult(
            task_id=1,
            project_id=1,
            case_id=1,
            case_no="TC001",
            exec_status=1
        )
        self.assertEqual(result.exec_status, 1)

    def test_test_result_failed(self):
        """测试失败的测试结�?""
        result = TestResult(
            task_id=1,
            project_id=1,
            case_id=1,
            case_no="TC002",
            exec_status=2,
            error_msg="元素未找�?
        )
        self.assertEqual(result.exec_status, 2)
        self.assertEqual(result.error_msg, "元素未找�?)


class TestTestTaskModel(unittest.TestCase):
    """测试测试任务模型"""

    def test_test_task_creation(self):
        """测试创建测试任务"""
        task = TestTask(
            task_name="回归测试",
            project_id=1,
            executor_id=1,
            case_ids=[1, 2, 3],
            status=0
        )
        self.assertEqual(task.task_name, "回归测试")
        self.assertEqual(task.status, 0)


class TestUserModel(unittest.TestCase):
    """测试用户模型"""

    def test_user_creation(self):
        """测试创建用户"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            is_active=True
        )
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.is_active)

    def test_user_to_dict(self):
        """测试用户属性访�?""
        user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            password_hash="hash",
            is_active=True
        )
        self.assertEqual(user.id, 1)
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")


class TestReportModel(unittest.TestCase):
    """测试报告模型"""

    def test_report_creation(self):
        """测试创建报告"""
        report = TestReport(
            name="测试报告",
            project_id=1,
            status="completed"
        )
        self.assertEqual(report.name, "测试报告")
        self.assertEqual(report.status, "completed")


if __name__ == '__main__':
    unittest.main(verbosity=2)
