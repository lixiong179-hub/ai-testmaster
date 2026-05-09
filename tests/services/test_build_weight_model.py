"""
_build_weight_model() 函数单元测试

覆盖范围�?
- 5种数据源组合场景（需求文档优先权重模型）
- 边界情况：全部False
- 返回值类型验证：始终返回三元�?(weight_desc, weight_example, weight_warning)
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.ai_client import _build_weight_model


class TestBuildWeightModel:
    """_build_weight_model 函数单元测试"""

    def test_scenario_all_three_sources(self):
        """场景1：三者齐�?- 验证需�?0%/测试�?5%/UI15%"""
        has_ui = True
        has_requirement = True
        has_test_point = True

        weight_desc, weight_example, weight_warning = _build_weight_model(
            has_ui, has_requirement, has_test_point
        )

        assert "60%" in weight_desc
        assert "核心依据" in weight_desc
        assert "25%" in weight_desc
        assert "生成范围" in weight_desc
        assert "15%" in weight_desc
        assert "验收标准" in weight_desc
        assert len(weight_example) > 0
        assert weight_example is not None and weight_example.strip()
        assert weight_warning == ""

    def test_scenario_requirement_and_ui(self):
        """场景2：需�?UI - 验证需�?5%/UI25%"""
        has_ui = True
        has_requirement = True
        has_test_point = False

        weight_desc, weight_example, weight_warning = _build_weight_model(
            has_ui, has_requirement, has_test_point
        )

        assert "75%" in weight_desc
        assert "核心依据" in weight_desc
        assert "25%" in weight_desc
        assert "验收标准" in weight_desc
        assert "没有测试�? in weight_desc or "自动推断" in weight_desc
        assert weight_warning == ""

    def test_scenario_requirement_and_testpoint(self):
        """场景3：需�?测试�?- 验证需�?0%/测试�?0%"""
        has_ui = False
        has_requirement = True
        has_test_point = True

        weight_desc, weight_example, weight_warning = _build_weight_model(
            has_ui, has_requirement, has_test_point
        )

        assert "70%" in weight_desc
        assert "核心依据" in weight_desc
        assert "30%" in weight_desc
        assert "生成范围" in weight_desc
        assert "不能超出需求文档定义的功能边界" in weight_desc
        assert weight_warning == ""

    def test_scenario_requirement_only(self):
        """场景4：仅需�?- 验证100%需求权�?""
        has_ui = False
        has_requirement = True
        has_test_point = False

        weight_desc, weight_example, weight_warning = _build_weight_model(
            has_ui, has_requirement, has_test_point
        )

        assert "100%" in weight_desc
        assert "唯一" in weight_desc
        assert "逐条覆盖" in weight_desc
        assert weight_warning == ""

    def test_scenario_no_requirement_with_ui(self):
        """场景5a：无需�?有UI - 验证警告提示"""
        has_ui = True
        has_requirement = False
        has_test_point = False

        weight_desc, weight_example, weight_warning = _build_weight_model(
            has_ui, has_requirement, has_test_point
        )

        assert "缺少需求文�? in weight_desc
        assert "未提供需求文�? in weight_warning
        assert len(weight_warning) > 0

    def test_scenario_no_requirement_with_testpoint(self):
        """场景5b：无需�?有测试点 - 验证警告提示"""
        has_ui = False
        has_requirement = False
        has_test_point = True

        weight_desc, weight_example, weight_warning = _build_weight_model(
            has_ui, has_requirement, has_test_point
        )

        assert "缺少需求文�? in weight_desc
        assert "未提供需求文�? in weight_warning
        assert len(weight_warning) > 0

    def test_scenario_all_false(self):
        """边界：全部False - 返回合理默认值不报错"""
        has_ui = False
        has_requirement = False
        has_test_point = False

        result = _build_weight_model(has_ui, has_requirement, has_test_point)

        assert isinstance(result, tuple)
        assert len(result) == 3
        weight_desc, weight_example, weight_warning = result
        assert isinstance(weight_desc, str)
        assert isinstance(weight_example, str)
        assert isinstance(weight_warning, str)
        assert len(weight_desc) > 0

    def test_return_type_is_tuple(self):
        """验证返回值始终是三元�?""
        test_cases = [
            (True, True, True),
            (True, True, False),
            (True, False, True),
            (True, False, False),
            (False, True, True),
            (False, True, False),
            (False, False, True),
            (False, False, False),
        ]

        for has_ui, has_req, has_tp in test_cases:
            result = _build_weight_model(has_ui, has_req, has_tp)
            assert isinstance(result, tuple), f"Expected tuple for ({has_ui}, {has_req}, {has_tp})"
            assert len(result) == 3, f"Expected length 3 for ({has_ui}, {has_req}, {has_tp})"
