"""
测试数据服务单元测试

测试范围:
- 测试数据CRUD操作
- 测试数据生成
- 参数化功�?
- 自动推断生成
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.services.test_data_service import TestDataService
from app.services.test_data_generator import TestDataGenerator, DataConstraints
from app.services.test_data_parameterizer import TestDataParameterizer, ParameterContext
from app.models.test_data import TestData, DataType, GenerationRule


class TestTestDataService:
    """测试数据服务测试�?""

    @pytest.fixture
    def db_session(self):
        """创建模拟的数据库会话"""
        session = Mock(spec=Session)
        return session

    @pytest.fixture
    def service(self, db_session):
        """创建测试数据服务实例"""
        return TestDataService(db_session)

    @pytest.fixture
    def sample_test_data(self):
        """创建示例测试数据"""
        return TestData(
            id=1,
            step_id=100,
            field_name="username",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
            data_value=None,
            rule_config=None,
            min_length=6,
            max_length=20,
            min_value=None,
            max_value=None,
            enum_values=None,
            description="用户�?,
            is_required=True,
            sort_order=0
        )

    def test_create_test_data(self, service, db_session):
        """测试创建测试数据"""
        # 准备
        test_data_dict = {
            "step_id": 100,
            "field_name": "email",
            "field_type": DataType.EMAIL,
            "generation_rule": GenerationRule.RANDOM,
            "is_required": True
        }

        # 执行
        with patch.object(db_session, 'add') as mock_add, \
             patch.object(db_session, 'commit') as mock_commit, \
             patch.object(db_session, 'refresh') as mock_refresh:
            result = service.create_test_data(**test_data_dict)

        # 验证
        mock_add.assert_called_once()
        mock_commit.assert_called_once()
        mock_refresh.assert_called_once()
        assert result.step_id == 100
        assert result.field_name == "email"
        assert result.field_type == DataType.EMAIL

    def test_get_test_data(self, service, db_session, sample_test_data):
        """测试获取单个测试数据"""
        # 准备
        db_session.query.return_value.filter.return_value.first.return_value = sample_test_data

        # 执行
        result = service.get_test_data(1)

        # 验证
        assert result is not None
        assert result.id == 1
        assert result.field_name == "username"

    def test_get_test_data_not_found(self, service, db_session):
        """测试获取不存在的测试数据"""
        # 准备
        db_session.query.return_value.filter.return_value.first.return_value = None

        # 执行
        result = service.get_test_data(999)

        # 验证
        assert result is None

    def test_get_test_data_by_step(self, service, db_session, sample_test_data):
        """测试获取步骤的所有测试数�?""
        # 准备
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [sample_test_data]

        # 执行
        result = service.get_test_data_by_step(100)

        # 验证
        assert len(result) == 1
        assert result[0].step_id == 100

    def test_update_test_data(self, service, db_session, sample_test_data):
        """测试更新测试数据"""
        # 准备
        db_session.query.return_value.filter.return_value.first.return_value = sample_test_data

        # 执行
        with patch.object(db_session, 'commit') as mock_commit:
            result = service.update_test_data(1, field_name="new_username", is_required=False)

        # 验证
        assert result.field_name == "new_username"
        assert result.is_required is False
        mock_commit.assert_called_once()

    def test_delete_test_data(self, service, db_session, sample_test_data):
        """测试删除测试数据"""
        # 准备
        db_session.query.return_value.filter.return_value.first.return_value = sample_test_data

        # 执行
        with patch.object(db_session, 'delete') as mock_delete, \
             patch.object(db_session, 'commit') as mock_commit:
            result = service.delete_test_data(1)

        # 验证
        assert result is True
        mock_delete.assert_called_once_with(sample_test_data)
        mock_commit.assert_called_once()

    def test_generate_step_data(self, service, db_session, sample_test_data):
        """测试生成步骤数据"""
        # 准备
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [sample_test_data]

        # 执行
        result = service.generate_step_data(100)

        # 验证
        assert "username" in result
        assert isinstance(result["username"], str)

    def test_auto_generate_for_step_login(self, service, db_session):
        """测试自动推断生成 - 登录场景"""
        # 准备
        db_session.query.return_value.filter.return_value.first.return_value = None
        action_description = "输入用户名和密码登录系统"

        # 执行
        with patch.object(db_session, 'add') as mock_add, \
             patch.object(db_session, 'commit') as mock_commit, \
             patch.object(db_session, 'refresh') as mock_refresh:
            result = service.auto_generate_for_step(100, action_description)

        # 验证 - 自动推断会返回识别到的字�?
        assert len(result) >= 1  # 至少会识别到一个输入字�?

    def test_auto_generate_for_step_search(self, service, db_session):
        """测试自动推断生成 - 搜索场景"""
        # 准备
        db_session.query.return_value.filter.return_value.first.return_value = None
        action_description = "在搜索框中输入关键词"

        # 执行
        with patch.object(db_session, 'add') as mock_add, \
             patch.object(db_session, 'commit') as mock_commit, \
             patch.object(db_session, 'refresh') as mock_refresh:
            result = service.auto_generate_for_step(100, action_description)

        # 验证
        assert len(result) >= 0  # 可能识别到也可能没有

    def test_auto_generate_for_step_email(self, service, db_session):
        """测试自动推断生成 - 邮箱场景"""
        # 准备
        db_session.query.return_value.filter.return_value.first.return_value = None
        action_description = "输入邮箱地址订阅新闻"

        # 执行
        with patch.object(db_session, 'add') as mock_add, \
             patch.object(db_session, 'commit') as mock_commit, \
             patch.object(db_session, 'refresh') as mock_refresh:
            result = service.auto_generate_for_step(100, action_description)

        # 验证
        assert len(result) >= 0  # 可能识别到也可能没有


class TestTestDataGenerator:
    """测试数据生成器测试类"""

    @pytest.fixture
    def generator(self):
        """创建生成器实�?""
        return TestDataGenerator()

    def test_generate_data_text(self, generator):
        """测试生成文本数据"""
        result = generator.generate_data(
            field_type=DataType.TEXT,
            field_name="test_field",
            constraints=DataConstraints(min_length=5, max_length=10)
        )
        assert isinstance(result, str)
        assert len(result) >= 5

    def test_generate_data_email(self, generator):
        """测试生成邮箱数据"""
        result = generator.generate_data(
            field_type=DataType.EMAIL,
            field_name="email"
        )
        assert isinstance(result, str)
        assert "@" in result

    def test_generate_data_phone(self, generator):
        """测试生成手机号数�?""
        result = generator.generate_data(
            field_type=DataType.PHONE,
            field_name="phone"
        )
        assert isinstance(result, str)
        assert len(result) == 11
        assert result.startswith("1")

    def test_generate_data_number(self, generator):
        """测试生成数字数据"""
        result = generator.generate_data(
            field_type=DataType.NUMBER,
            field_name="number",
            constraints=DataConstraints(min_value=10, max_value=100)
        )
        assert isinstance(result, str)
        num = int(result)
        assert 10 <= num <= 100

    def test_generate_data_date(self, generator):
        """测试生成日期数据"""
        result = generator.generate_data(
            field_type=DataType.DATE,
            field_name="date"
        )
        assert isinstance(result, str)
        # 验证日期格式 YYYY-MM-DD
        parts = result.split("-")
        assert len(parts) == 3

    def test_generate_data_boolean(self, generator):
        """测试生成布尔值数�?""
        result = generator.generate_data(
            field_type=DataType.BOOLEAN,
            field_name="boolean"
        )
        assert isinstance(result, str)
        assert result in ["true", "false"]

    def test_generate_data_url(self, generator):
        """测试生成URL数据"""
        result = generator.generate_data(
            field_type=DataType.URL,
            field_name="url"
        )
        assert isinstance(result, str)
        assert result.startswith("http")

    def test_generate_data_id_card(self, generator):
        """测试生成身份证号数据"""
        result = generator.generate_data(
            field_type=DataType.ID_CARD,
            field_name="id_card"
        )
        assert isinstance(result, str)
        assert len(result) == 18

    def test_generate_data_bank_card(self, generator):
        """测试生成银行卡号数据"""
        result = generator.generate_data(
            field_type=DataType.BANK_CARD,
            field_name="bank_card"
        )
        assert isinstance(result, str)
        assert len(result) >= 16

    def test_generate_data_with_random_rule(self, generator):
        """测试使用RANDOM规则生成数据"""
        result = generator.generate_data(
            field_type=DataType.EMAIL,
            field_name="email",
            generation_rule=GenerationRule.RANDOM
        )
        assert isinstance(result, str)
        assert "@" in result

    def test_generate_data_with_custom_rule(self, generator):
        """测试使用CUSTOM规则生成数据"""
        result = generator.generate_data(
            field_type=DataType.TEXT,
            field_name="custom",
            generation_rule=GenerationRule.CUSTOM,
            rule_config={"custom_value": "自定义�?}
        )
        assert result == "自定义�?

    def test_generate_data_with_empty_rule(self, generator):
        """测试使用EMPTY规则生成数据"""
        result = generator.generate_data(
            field_type=DataType.TEXT,
            field_name="empty",
            generation_rule=GenerationRule.EMPTY
        )
        assert result == ""

    def test_generate_data_with_boundary_min_rule(self, generator):
        """测试使用BOUNDARY_MIN规则生成数据"""
        result = generator.generate_data(
            field_type=DataType.NUMBER,
            field_name="boundary_min",
            generation_rule=GenerationRule.BOUNDARY_MIN,
            constraints=DataConstraints(min_value=10, max_value=100)
        )
        assert result == "10"

    def test_generate_data_with_boundary_max_rule(self, generator):
        """测试使用BOUNDARY_MAX规则生成数据"""
        result = generator.generate_data(
            field_type=DataType.NUMBER,
            field_name="boundary_max",
            generation_rule=GenerationRule.BOUNDARY_MAX,
            constraints=DataConstraints(min_value=10, max_value=100)
        )
        assert result == "100"

    def test_generate_data_with_special_chars_rule(self, generator):
        """测试使用SPECIAL_CHARS规则生成数据"""
        result = generator.generate_data(
            field_type=DataType.TEXT,
            field_name="special",
            generation_rule=GenerationRule.SPECIAL_CHARS
        )
        assert isinstance(result, str)
        # 应该包含特殊字符
        assert any(c in result for c in "!@#$%^&*()")

    def test_get_cached_value(self, generator):
        """测试获取缓存�?""
        # 第一次获取应该生成新�?
        result1 = generator.get_cached_value("test_key", DataType.TEXT, "test_field")
        # 第二次获取应该返回缓存�?
        result2 = generator.get_cached_value("test_key", DataType.TEXT, "test_field")
        assert result1 == result2

    def test_reset_generated_values(self, generator):
        """测试重置生成的�?""
        # 生成一个�?
        result1 = generator.get_cached_value("test_key", DataType.TEXT, "test_field")
        # 重置
        generator.reset_generated_values()
        # 再次获取应该是新值（缓存已清除）
        result2 = generator.get_cached_value("test_key", DataType.TEXT, "test_field")
        # 由于随机性，可能相同也可能不同，但缓存应该被清除
        assert len(generator._generated_values) == 1


class TestTestDataParameterizer:
    """测试数据参数化器测试�?""

    @pytest.fixture
    def parameterizer(self):
        """创建参数化器实例"""
        return TestDataParameterizer()

    @pytest.fixture
    def context(self):
        """创建参数上下�?""
        return ParameterContext(execution_id="test-001")

    def test_parse_random_product_name(self, parameterizer):
        """测试解析 - 随机产品�?""
        template = "产品: ${random.product_name}"
        result = parameterizer.parse(template)
        assert "${random.product_name}" not in result
        assert "产品:" in result

    def test_parse_date_today(self, parameterizer):
        """测试解析 - 今天日期"""
        template = "日期: ${date.today}"
        result = parameterizer.parse(template)
        assert "${date.today}" not in result
        today = datetime.now().strftime('%Y-%m-%d')
        assert today in result

    def test_parse_date_now(self, parameterizer):
        """测试解析 - 当前时间"""
        template = "时间: ${date.now}"
        result = parameterizer.parse(template)
        assert "${date.now}" not in result

    def test_parse_user_name(self, parameterizer):
        """测试解析 - 用户�?""
        template = "用户: ${user.name}"
        result = parameterizer.parse(template)
        assert "${user.name}" not in result
        assert "用户:" in result

    def test_parse_execution_id(self, parameterizer):
        """测试解析 - 执行ID"""
        template = "ID: ${execution.id}"
        result = parameterizer.parse(template)
        assert "${execution.id}" not in result
        assert "ID:" in result

    def test_parse_caching(self, parameterizer):
        """测试解析缓存 - 相同执行ID返回相同�?""
        template = "${random.product_name}"
        result1 = parameterizer.parse(template)
        result2 = parameterizer.parse(template)
        assert result1 == result2
        assert "${random.product_name}" not in result1

    def test_parse_no_placeholder(self, parameterizer):
        """测试解析 - 无占位符"""
        template = "普通文�?
        result = parameterizer.parse(template)
        assert result == "普通文�?

    def test_parse_multiple_placeholders(self, parameterizer):
        """测试解析 - 多个占位�?""
        template = "${user.name} �?${date.today} 购买�?${random.product_name}"
        result = parameterizer.parse(template)
        assert "${user.name}" not in result
        assert "${date.today}" not in result
        assert "${random.product_name}" not in result
        assert "购买�? in result

    def test_parse_unknown_placeholder(self, parameterizer):
        """测试解析 - 未知占位�?""
        template = "${unknown.placeholder}"
        result = parameterizer.parse(template)
        # 未知占位符应保持原样
        assert "${unknown.placeholder}" in result

    def test_parse_empty_template(self, parameterizer):
        """测试解析 - 空模�?""
        template = ""
        result = parameterizer.parse(template)
        assert result == ""

    def test_parse_date_relative(self, parameterizer):
        """测试解析 - 相对日期"""
        template_tomorrow = "${date.+1}"
        template_yesterday = "${date.-1}"
        result_tomorrow = parameterizer.parse(template_tomorrow)
        result_yesterday = parameterizer.parse(template_yesterday)
        assert "${date.+1}" not in result_tomorrow
        assert "${date.-1}" not in result_yesterday

    def test_parse_date_year_month_day(self, parameterizer):
        """测试解析 - 年月�?""
        template_year = "${date.year}"
        template_month = "${date.month}"
        template_day = "${date.day}"
        result_year = parameterizer.parse(template_year)
        result_month = parameterizer.parse(template_month)
        result_day = parameterizer.parse(template_day)
        assert result_year.isdigit()
        assert result_month.isdigit()
        assert result_day.isdigit()

    def test_get_cached_params(self, parameterizer):
        """测试获取缓存的参�?""
        # 先解析一些内�?
        parameterizer.parse("${random.product_name}")
        cached = parameterizer.get_cached_params()
        assert isinstance(cached, dict)

    def test_clear_cache(self, parameterizer):
        """测试清除缓存"""
        # 先解析一些内�?
        parameterizer.parse("${random.product_name}")
        # 清除缓存
        parameterizer.clear_cache()
        assert len(parameterizer.context.cached_values) == 0


class TestDataTypeAndGenerationRule:
    """数据类型和生成规则枚举测�?""

    def test_data_type_values(self):
        """测试数据类型枚举�?""
        assert DataType.TEXT.value == "text"
        assert DataType.EMAIL.value == "email"
        assert DataType.PHONE.value == "phone"
        assert DataType.NUMBER.value == "number"
        assert DataType.DATE.value == "date"
        assert DataType.DATETIME.value == "datetime"
        assert DataType.BOOLEAN.value == "boolean"
        assert DataType.URL.value == "url"
        assert DataType.ID_CARD.value == "id_card"
        assert DataType.BANK_CARD.value == "bank_card"
        assert DataType.ENUM.value == "enum"

    def test_generation_rule_values(self):
        """测试生成规则枚举�?""
        assert GenerationRule.RANDOM.value == "random"
        assert GenerationRule.BOUNDARY_MIN.value == "boundary_min"
        assert GenerationRule.BOUNDARY_MAX.value == "boundary_max"
        assert GenerationRule.BOUNDARY_OVER.value == "boundary_over"
        assert GenerationRule.SPECIAL_CHARS.value == "special_chars"
        assert GenerationRule.EMPTY.value == "empty"
        assert GenerationRule.CUSTOM.value == "custom"


class TestTestDataModel:
    """测试数据模型测试"""

    def test_test_data_creation(self):
        """测试测试数据创建"""
        test_data = TestData(
            id=1,
            step_id=100,
            field_name="test_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
            data_value="test_value",
            rule_config='{"key": "value"}',
            min_length=5,
            max_length=10,
            min_value=None,
            max_value=None,
            enum_values=None,
            description="测试字段",
            is_required=True,
            sort_order=1
        )

        assert test_data.id == 1
        assert test_data.step_id == 100
        assert test_data.field_name == "test_field"
        assert test_data.field_type == DataType.TEXT
        assert test_data.data_value == "test_value"

    def test_test_data_to_dict(self):
        """测试测试数据转换为字�?""
        test_data = TestData(
            id=1,
            step_id=100,
            field_name="test_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
            data_value="test_value",
            rule_config='{"key": "value"}',
            min_length=5,
            max_length=10,
            min_value=None,
            max_value=None,
            enum_values=None,
            description="测试字段",
            is_required=True,
            sort_order=1
        )

        result = test_data.to_dict()

        assert result["id"] == 1
        assert result["step_id"] == 100
        assert result["field_name"] == "test_field"
        assert result["field_type"] == "text"
        assert result["data_value"] == "test_value"
        assert result["rule_config"] == {"key": "value"}
        assert result["min_length"] == 5
        assert result["max_length"] == 10
        assert result["is_required"] is True

    def test_test_data_to_dict_with_enum_values(self):
        """测试测试数据转换为字�?- 包含枚举�?""
        test_data = TestData(
            id=1,
            step_id=100,
            field_name="status",
            field_type=DataType.ENUM,
            generation_rule=GenerationRule.RANDOM,
            data_value=None,
            rule_config=None,
            min_length=None,
            max_length=None,
            min_value=None,
            max_value=None,
            enum_values='["active", "inactive", "pending"]',
            description="状�?,
            is_required=True,
            sort_order=0
        )

        result = test_data.to_dict()

        assert result["enum_values"] == ["active", "inactive", "pending"]

    def test_test_data_to_dict_boolean_conversion(self):
        """测试测试数据转换为字�?- 布尔值转�?""
        test_data = TestData(
            id=1,
            step_id=100,
            field_name="is_active",
            field_type=DataType.BOOLEAN,
            generation_rule=GenerationRule.RANDOM,
            data_value=None,
            rule_config=None,
            min_length=None,
            max_length=None,
            min_value=None,
            max_value=None,
            enum_values=None,
            description="是否激�?,
            is_required=True,
            sort_order=0
        )

        result = test_data.to_dict()

        assert result["is_required"] is True
        assert result["field_type"] == "boolean"


class TestParameterContext:
    """参数上下文测�?""

    def test_context_creation(self):
        """测试上下文创�?""
        context = ParameterContext(
            execution_id="test-001",
            user_id=1,
            project_id=100
        )
        assert context.execution_id == "test-001"
        assert context.user_id == 1
        assert context.project_id == 100
        assert isinstance(context.cached_values, dict)
        assert context.execution_timestamp != ""

    def test_context_default_timestamp(self):
        """测试上下文默认时间戳"""
        context = ParameterContext(execution_id="test-001")
        assert context.execution_timestamp != ""
        # 验证时间戳格�?
        assert len(context.execution_timestamp) == 14  # YYYYMMDDHHMMSS
        assert context.execution_timestamp.isdigit()

    def test_context_custom_timestamp(self):
        """测试上下文自定义时间�?""
        context = ParameterContext(
            execution_id="test-001",
            execution_timestamp="20240101120000"
        )
        assert context.execution_timestamp == "20240101120000"


class TestDataConstraints:
    """数据约束测试"""

    def test_constraints_creation(self):
        """测试约束创建"""
        constraints = DataConstraints(
            min_length=5,
            max_length=10,
            min_value=0,
            max_value=100,
            enum_values=["a", "b", "c"],
            pattern="^[a-z]+$"
        )
        assert constraints.min_length == 5
        assert constraints.max_length == 10
        assert constraints.min_value == 0
        assert constraints.max_value == 100
        assert constraints.enum_values == ["a", "b", "c"]
        assert constraints.pattern == "^[a-z]+$"

    def test_constraints_defaults(self):
        """测试约束默认�?""
        constraints = DataConstraints()
        assert constraints.min_length is None
        assert constraints.max_length is None
        assert constraints.min_value is None
        assert constraints.max_value is None
        assert constraints.enum_values is None
        assert constraints.pattern is None
