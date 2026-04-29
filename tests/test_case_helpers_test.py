"""
测试用例工具函数测试

专门测试我们重构的测试用例转换逻辑
"""
import sys
import os
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.test_case_helpers import (
    _build_step_response,
    convert_steps_to_response,
    convert_ai_steps_to_response,
    build_test_case_response
)


class TestStepConversion:
    """测试步骤转换函数"""

    def test_build_step_response_basic(self):
        """测试基本步骤响应构建"""
        step = {
            "step": "点击登录按钮",
            "action": "click",
            "param": "admin",
            "expected_result": "登录成功"
        }
        
        result = _build_step_response(step)
        
        assert result["step"] == "click"
        assert result["action"] == "click"
        assert result["param"] == "admin"
        assert result["expected_result"] == "登录成功"

    def test_build_step_response_with_step_number(self):
        """测试带步骤号的响应构建"""
        step = {
            "step": "输入用户名",
            "action": "input",
            "param": "test_user",
            "expected_result": "用户名输入成功"
        }
        
        result = _build_step_response(step, step_number=1)
        
        assert result["step_number"] == 1
        assert result["step"] == "input"
        assert result["action"] == "input"

    def test_build_step_response_with_description(self):
        """测试带description字段的步骤"""
        step = {
            "description": "验证页面加载",
            "expected_result": "页面加载成功"
        }
        
        result = _build_step_response(step)
        
        assert result["step"] == "验证页面加载"
        assert result["action"] == "验证页面加载"

    def test_build_step_response_defaults(self):
        """测试默认值处理"""
        step = {}
        
        result = _build_step_response(step)
        
        assert result["step"] == "执行"
        assert result["action"] == "执行"
        assert result["param"] == ""
        assert result["expected_result"] == ""
        assert result["test_data"] == {}

    def test_convert_steps_to_response(self):
        """测试转换数据库步骤转换"""
        steps_json = [
            {
                "step": "步骤1",
                "action": "输入用户名",
                "param": "admin",
                "expected_result": "用户名输入成功"
            },
            {
                "step": "步骤2",
                "action": "输入密码",
                "param": "123456",
                "expected_result": "密码输入成功"
            }
        ]
        
        result = convert_steps_to_response(steps_json)
        
        assert len(result) == 2
        assert result[0]["step_number"] == 1
        assert result[0]["action"] == "输入用户名"
        assert result[1]["step_number"] == 2
        assert result[1]["action"] == "输入密码"

    def test_convert_steps_to_response_with_step_number(self):
        """测试带step_number字段的步骤"""
        steps_json = [
            {
                "step_number": 5,
                "step": "自定义步骤号",
                "action": "测试",
                "param": "test"
            }
        ]
        
        result = convert_steps_to_response(steps_json)
        
        assert result[0]["step_number"] == 5

    def test_convert_steps_to_response_empty(self):
        """测试空输入"""
        result = convert_steps_to_response(None)
        assert result == []
        
        result = convert_steps_to_response([])
        assert result == []

    def test_convert_ai_steps_to_response(self):
        """测试AI生成步骤转换"""
        ai_steps = [
            {
                "step": "AI步骤1",
                "action": "click",
                "param": "ai_param1",
                "expected_result": "AI预期1"
            },
            {
                "step": "AI步骤2",
                "action": "input",
                "param": "ai_param2",
                "expected_result": "AI预期2"
            }
        ]
        
        result = convert_ai_steps_to_response(ai_steps)
        
        assert len(result) == 2
        assert result[0]["step"] == "click"
        assert result[0]["action"] == "click"
        assert result[0]["param"] == "ai_param1"
        assert result[1]["step"] == "input"
        assert result[1]["action"] == "input"
        assert result[1]["param"] == "ai_param2"


class MockTestCase:
    """模拟TestCase模型的模拟类"""
    def __init__(self):
        self.id = 1
        self.project_id = 100
        self.case_no = "TEST-001"
        self.module = "用户登录"
        self.title = "用户登录测试"
        self.precondition = "系统已启动"
        self.steps_json = [
            {
                "step": "步骤1",
                "action": "输入用户名",
                "param": "admin",
                "expected_result": "用户名输入成功"
            }
        ]
        self.expected_result = "登录成功"
        self.priority = 1
        self.case_type = "UI"
        self.exec_script = None
        self.generate_status = 1
        self.create_time = datetime(2024, 1, 1, 12, 0, 0)


class TestBuildTestCaseResponse:
    """测试用例响应构建"""

    def test_build_test_case_response(self):
        """测试构建测试用例响应"""
        mock_case = MockTestCase()
        
        result = build_test_case_response(mock_case)
        
        assert result["id"] == 1
        assert result["project_id"] == 100
        assert result["case_no"] == "TEST-001"
        assert result["module"] == "用户登录"
        assert result["title"] == "用户登录测试"
        assert result["precondition"] == "系统已启动"
        assert len(result["steps"]) == 1
        assert result["expected_result"] == "登录成功"
        assert result["priority"] == 1
        assert result["case_type"] == "UI"
        assert result["generate_status"] == 1
        assert result["create_time"] == "2024-01-01T12:00:00"

    def test_build_test_case_response_no_create_time(self):
        """测试无创建时间的情况"""
        mock_case = MockTestCase()
        mock_case.create_time = None
        
        result = build_test_case_response(mock_case)
        
        assert result["create_time"] is None

    def test_build_test_case_response_missing_fields(self):
        """测试缺失字段的情况"""
        class SimpleMockCase:
            def __init__(self):
                self.id = 2
                self.project_id = 200
                self.title = "简单测试"
                self.priority = 2
        
        simple_case = SimpleMockCase()
        
        result = build_test_case_response(simple_case)
        
        assert result["id"] == 2
        assert result["project_id"] == 200
        assert result["title"] == "简单测试"
        assert result["priority"] == 2
        assert result["case_no"] == ""
        assert result["module"] == ""
        assert result["precondition"] == ""
        assert result["steps"] == []
        assert result["expected_result"] == ""
        assert result["case_type"] == ""
        assert result["exec_script"] == ""
        assert result["generate_status"] == 0
        assert result["create_time"] is None
