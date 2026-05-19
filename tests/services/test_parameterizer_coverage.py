"""
参数化器覆盖率补充测试

目标：将覆盖率提升到95%以上
"""
import pytest
from unittest.mock import Mock, patch

from app.services.test_data_parameterizer import (
    TestDataParameterizer,
    ParameterContext,
    parse_parameters,
    create_parameter_context
)


class TestParameterizerCoverage:
    """参数化器覆盖率测试"""

    @pytest.fixture
    def parameterizer(self):
        """创建参数化器实例"""
        return TestDataParameterizer()

    def test_parse_empty_text(self, parameterizer):
        """测试解析 - 空文本"""
        result = parameterizer.parse("")
        assert result == ""

    def test_parse_none_text(self, parameterizer):
        """测试解析 - None文本"""
        result = parameterizer.parse(None)
        assert result is None

    def test_parse_exception_handling(self, parameterizer):
        """测试解析 - 异常处理"""
        # 通过mock让replace_param函数抛出异常
        with patch.object(parameterizer, '_resolve_param', side_effect=Exception("测试异常")):
            result = parameterizer.parse("${random.number}")
        # 应该返回原始文本或包含占位符的文本
        assert "${random.number}" in result or result == "${random.number}"

    def test_resolve_param_invalid_format(self, parameterizer):
        """测试解析参数 - 无效格式（没有点号）"""
        result = parameterizer._resolve_param("invalid")
        assert "${invalid}" in result

    def test_resolve_param_unknown_namespace(self, parameterizer):
        """测试解析参数 - 未知命名空间"""
        result = parameterizer._resolve_param("unknown.param")
        assert "${unknown.param}" in result

    def test_resolve_param_handler_exception(self, parameterizer):
        """测试解析参数 - 处理器异常"""
        # mock一个会抛出异常的处理器
        with patch.dict(parameterizer._param_handlers, {'test': lambda x: 1/0}):
            result = parameterizer._resolve_param("test.param")
        assert "${test.param}" in result

    def test_handle_date_param_yesterday(self, parameterizer):
        """测试处理date参数 - 昨天"""
        result = parameterizer._handle_date_param("yesterday")
        assert len(result) == 10  # YYYY-MM-DD

    def test_handle_date_param_tomorrow(self, parameterizer):
        """测试处理date参数 - 明天"""
        result = parameterizer._handle_date_param("tomorrow")
        assert len(result) == 10  # YYYY-MM-DD

    def test_handle_date_param_time(self, parameterizer):
        """测试处理date参数 - 时间"""
        result = parameterizer._handle_date_param("time")
        assert len(result) == 8  # HH:MM:SS

    def test_handle_date_param_timestamp(self, parameterizer):
        """测试处理date参数 - 时间戳"""
        result = parameterizer._handle_date_param("timestamp")
        assert result.isdigit()

    def test_handle_user_param_id(self, parameterizer):
        """测试处理user参数 - ID"""
        result = parameterizer._handle_user_param("id")
        assert result.isdigit()

    def test_handle_user_param_unknown(self, parameterizer):
        """测试处理user参数 - 未知参数"""
        result = parameterizer._handle_user_param("unknown")
        assert "${user.unknown}" in result

    def test_handle_project_param_name(self, parameterizer):
        """测试处理project参数 - 名称"""
        result = parameterizer._handle_project_param("name")
        assert result == "测试项目"

    def test_handle_project_param_id(self, parameterizer):
        """测试处理project参数 - ID"""
        result = parameterizer._handle_project_param("id")
        assert result.isdigit()

    def test_handle_project_param_code(self, parameterizer):
        """测试处理project参数 - 代码"""
        result = parameterizer._handle_project_param("code")
        assert result == "TEST"

    def test_handle_project_param_unknown(self, parameterizer):
        """测试处理project参数 - 未知参数"""
        result = parameterizer._handle_project_param("unknown")
        assert "${project.unknown}" in result

    def test_handle_random_param_phone(self, parameterizer):
        """测试处理random参数 - 手机号"""
        result = parameterizer._handle_random_param("phone")
        assert len(result) == 11
        assert result.startswith("1")

    def test_handle_random_param_email(self, parameterizer):
        """测试处理random参数 - 邮箱"""
        result = parameterizer._handle_random_param("email")
        assert "@" in result

    def test_handle_random_param_name(self, parameterizer):
        """测试处理random参数 - 姓名"""
        result = parameterizer._handle_random_param("name")
        assert len(result) > 0

    def test_handle_random_param_company(self, parameterizer):
        """测试处理random参数 - 公司"""
        result = parameterizer._handle_random_param("company")
        assert len(result) > 0

    def test_handle_random_param_number(self, parameterizer):
        """测试处理random参数 - 数字"""
        result = parameterizer._handle_random_param("number")
        assert result.isdigit()

    def test_handle_random_param_address(self, parameterizer):
        """测试处理random参数 - 地址"""
        result = parameterizer._handle_random_param("address")
        assert len(result) > 0

    def test_handle_random_param_id_card(self, parameterizer):
        """测试处理random参数 - 身份证"""
        result = parameterizer._handle_random_param("id_card")
        assert len(result) == 18

    def test_handle_random_param_bank_card(self, parameterizer):
        """测试处理random参数 - 银行卡"""
        result = parameterizer._handle_random_param("bank_card")
        assert len(result) >= 16

    def test_handle_random_param_url(self, parameterizer):
        """测试处理random参数 - URL"""
        result = parameterizer._handle_random_param("url")
        assert result.startswith("http")

    def test_handle_random_param_boolean(self, parameterizer):
        """测试处理random参数 - 布尔值"""
        result = parameterizer._handle_random_param("boolean")
        assert result in ["true", "false"]

    def test_handle_random_param_text(self, parameterizer):
        """测试处理random参数 - 文本"""
        result = parameterizer._handle_random_param("text")
        assert len(result) > 0

    def test_handle_random_param_unknown(self, parameterizer):
        """测试处理random参数 - 未知参数"""
        result = parameterizer._handle_random_param("unknown")
        assert "${random.unknown}" in result

    def test_parse_with_project_param(self, parameterizer):
        """测试解析 - project参数"""
        template = "项目: ${project.name}"
        result = parameterizer.parse(template)
        assert "${project.name}" not in result
        assert "项目:" in result

    def test_parse_with_execution_param(self, parameterizer):
        """测试解析 - execution参数"""
        template = "执行ID: ${execution.id}"
        result = parameterizer.parse(template)
        assert "${execution.id}" not in result
        assert "执行ID:" in result

    def test_parse_with_user_param(self, parameterizer):
        """测试解析 - user参数"""
        template = "用户: ${user.name}"
        result = parameterizer.parse(template)
        assert "${user.name}" not in result
        assert "用户:" in result

    def test_parse_with_date_yesterday(self, parameterizer):
        """测试解析 - 昨天日期"""
        template = "昨天: ${date.yesterday}"
        result = parameterizer.parse(template)
        assert "${date.yesterday}" not in result
        assert "昨天:" in result

    def test_parse_with_date_tomorrow(self, parameterizer):
        """测试解析 - 明天日期"""
        template = "明天: ${date.tomorrow}"
        result = parameterizer.parse(template)
        assert "${date.tomorrow}" not in result
        assert "明天:" in result

    def test_parse_with_date_time(self, parameterizer):
        """测试解析 - 时间"""
        template = "时间: ${date.time}"
        result = parameterizer.parse(template)
        assert "${date.time}" not in result
        assert "时间:" in result

    def test_parse_with_date_timestamp(self, parameterizer):
        """测试解析 - 时间戳"""
        template = "时间戳: ${date.timestamp}"
        result = parameterizer.parse(template)
        assert "${date.timestamp}" not in result
        assert "时间戳:" in result

    def test_parse_with_random_phone(self, parameterizer):
        """测试解析 - 随机手机号"""
        template = "手机: ${random.phone}"
        result = parameterizer.parse(template)
        assert "${random.phone}" not in result
        assert "手机:" in result

    def test_parse_with_random_email(self, parameterizer):
        """测试解析 - 随机邮箱"""
        template = "邮箱: ${random.email}"
        result = parameterizer.parse(template)
        assert "${random.email}" not in result
        assert "邮箱:" in result

    def test_parse_with_random_company(self, parameterizer):
        """测试解析 - 随机公司"""
        template = "公司: ${random.company}"
        result = parameterizer.parse(template)
        assert "${random.company}" not in result
        assert "公司:" in result

    def test_parse_with_random_address(self, parameterizer):
        """测试解析 - 随机地址"""
        template = "地址: ${random.address}"
        result = parameterizer.parse(template)
        assert "${random.address}" not in result
        assert "地址:" in result

    def test_parse_with_random_id_card(self, parameterizer):
        """测试解析 - 随机身份证"""
        template = "身份证: ${random.id_card}"
        result = parameterizer.parse(template)
        assert "${random.id_card}" not in result
        assert "身份证:" in result

    def test_parse_with_random_bank_card(self, parameterizer):
        """测试解析 - 随机银行卡"""
        template = "银行卡: ${random.bank_card}"
        result = parameterizer.parse(template)
        assert "${random.bank_card}" not in result
        assert "银行卡:" in result

    def test_parse_with_random_url(self, parameterizer):
        """测试解析 - 随机URL"""
        template = "URL: ${random.url}"
        result = parameterizer.parse(template)
        assert "${random.url}" not in result
        assert "URL:" in result

    def test_parse_with_random_boolean(self, parameterizer):
        """测试解析 - 随机布尔值"""
        template = "布尔: ${random.boolean}"
        result = parameterizer.parse(template)
        assert "${random.boolean}" not in result
        assert "布尔:" in result

    def test_parse_with_random_text(self, parameterizer):
        """测试解析 - 随机文本"""
        template = "文本: ${random.text}"
        result = parameterizer.parse(template)
        assert "${random.text}" not in result
        assert "文本:" in result

    def test_parse_with_unknown_namespace(self, parameterizer):
        """测试解析 - 未知命名空间"""
        template = "未知: ${unknown.param}"
        result = parameterizer.parse(template)
        assert "${unknown.param}" in result

    def test_parse_with_invalid_param_format(self, parameterizer):
        """测试解析 - 无效参数格式"""
        template = "无效: ${invalid}"
        result = parameterizer.parse(template)
        assert "${invalid}" in result

    def test_parse_caching_mechanism(self, parameterizer):
        """测试解析 - 缓存机制"""
        # 第一次解析
        result1 = parameterizer.parse("${random.number}")
        # 第二次解析相同参数
        result2 = parameterizer.parse("${random.number}")
        # 应该使用缓存，结果相同
        assert result1 == result2

    def test_parse_multiple_different_params(self, parameterizer):
        """测试解析 - 多个不同参数"""
        template = "${random.number} ${random.email} ${date.today}"
        result = parameterizer.parse(template)
        assert "${random.number}" not in result
        assert "${random.email}" not in result
        assert "${date.today}" not in result


class TestParameterContextCoverage:
    """参数上下文覆盖率测试"""

    def test_context_with_user_id(self):
        """测试上下文 - 带用户ID"""
        context = ParameterContext(
            execution_id="test-001",
            user_id=123,
            project_id=None
        )
        assert context.user_id == 123
        assert context.project_id is None

    def test_context_with_project_id(self):
        """测试上下文 - 带项目ID"""
        context = ParameterContext(
            execution_id="test-001",
            user_id=None,
            project_id=456
        )
        assert context.user_id is None
        assert context.project_id == 456

    def test_context_with_both_ids(self):
        """测试上下文 - 带用户ID和项目ID"""
        context = ParameterContext(
            execution_id="test-001",
            user_id=123,
            project_id=456
        )
        assert context.user_id == 123
        assert context.project_id == 456


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_parse_parameters_without_context(self):
        """测试便捷函数 - 无上下文"""
        result = parse_parameters("${date.today}")
        assert "${date.today}" not in result

    def test_parse_parameters_with_context(self):
        """测试便捷函数 - 带上下文"""
        context = ParameterContext(execution_id="test-001")
        result = parse_parameters("${execution.id}", context)
        assert "${execution.id}" not in result

    def test_create_parameter_context_default(self):
        """测试创建上下文 - 默认参数"""
        context = create_parameter_context()
        assert context.execution_id.startswith("EXEC_")
        assert context.user_id is None
        assert context.project_id is None

    def test_create_parameter_context_with_params(self):
        """测试创建上下文 - 带参数"""
        context = create_parameter_context(
            execution_id="custom-id",
            user_id=123,
            project_id=456
        )
        assert context.execution_id == "custom-id"
        assert context.user_id == 123
        assert context.project_id == 456
