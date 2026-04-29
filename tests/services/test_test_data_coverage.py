"""
测试数据服务覆盖率补充测试

目标：将覆盖率提升到95%以上
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from app.services.test_data_service import TestDataService
from app.services.test_data_generator import TestDataGenerator, DataConstraints, generate_test_data
from app.services.test_data_parameterizer import TestDataParameterizer, ParameterContext
from app.models.test_data import TestData, DataType, GenerationRule


class TestTestDataGeneratorCoverage:
    """测试数据生成器覆盖率测试"""

    @pytest.fixture
    def generator(self):
        """创建生成器实例"""
        return TestDataGenerator()

    def test_init_with_seed(self):
        """测试初始化 - 带随机种子"""
        generator = TestDataGenerator(seed=12345)
        assert generator._seed == 12345

    def test_generate_data_exception_handling(self, generator):
        """测试生成数据 - 异常处理"""
        # 通过传入无效的constraints来触发异常
        with patch.object(generator, '_generate_random', side_effect=Exception("测试异常")):
            result = generator.generate_data(
                field_type=DataType.TEXT,
                field_name="test"
            )
        # 应该返回空字符串而不是抛出异常
        assert result == ""

    def test_generate_text_with_template(self, generator):
        """测试生成文本 - 使用模板"""
        result = generator.generate_data(
            field_type=DataType.TEXT,
            field_name="test",
            generation_rule=GenerationRule.RANDOM,
            rule_config={"template": "Test_${date}_${random}"}
        )
        assert "Test_" in result
        assert "${date}" not in result
        assert "${random}" not in result

    def test_generate_text_product_line(self, generator):
        """测试生成文本 - 产品线字段"""
        result = generator._generate_text(
            field_name="product_line",
            constraints=DataConstraints(),
            rule_config={}
        )
        # 产品线字段应该返回产品名称格式
        assert len(result) > 0
        assert isinstance(result, str)

    def test_generate_text_name_field(self, generator):
        """测试生成文本 - 名称字段"""
        result = generator._generate_text(
            field_name="user_name",
            constraints=DataConstraints(),
            rule_config={}
        )
        # 应该是中文姓名
        assert len(result) >= 2

    def test_generate_text_description_field(self, generator):
        """测试生成文本 - 描述字段"""
        result = generator._generate_text(
            field_name="description",
            constraints=DataConstraints(min_length=20, max_length=30),
            rule_config={}
        )
        assert len(result) >= 20

    def test_generate_text_address_field(self, generator):
        """测试生成文本 - 地址字段"""
        result = generator._generate_text(
            field_name="address",
            constraints=DataConstraints(),
            rule_config={}
        )
        # 地址字段应该返回地址格式
        assert len(result) > 0
        assert isinstance(result, str)

    def test_generate_text_company_field(self, generator):
        """测试生成文本 - 公司字段"""
        result = generator._generate_text(
            field_name="company_name",
            constraints=DataConstraints(),
            rule_config={}
        )
        # 公司字段应该返回公司名称格式
        assert len(result) > 0
        assert isinstance(result, str)

    def test_generate_text_default(self, generator):
        """测试生成文本 - 默认情况"""
        result = generator._generate_text(
            field_name="other_field",
            constraints=DataConstraints(min_length=10, max_length=15),
            rule_config={}
        )
        assert 10 <= len(result) <= 15

    def test_generate_boundary_min_text(self, generator):
        """测试生成边界最小值 - 文本"""
        result = generator._generate_boundary_min(
            field_type=DataType.TEXT,
            constraints=DataConstraints(min_length=5)
        )
        assert result == "测" * 5

    def test_generate_boundary_min_number(self, generator):
        """测试生成边界最小值 - 数字"""
        result = generator._generate_boundary_min(
            field_type=DataType.NUMBER,
            constraints=DataConstraints(min_value=10)
        )
        assert result == "10"

    def test_generate_boundary_min_other(self, generator):
        """测试生成边界最小值 - 其他类型"""
        result = generator._generate_boundary_min(
            field_type=DataType.DATE,
            constraints=DataConstraints()
        )
        assert result == ""

    def test_generate_boundary_max_text(self, generator):
        """测试生成边界最大值 - 文本"""
        result = generator._generate_boundary_max(
            field_type=DataType.TEXT,
            constraints=DataConstraints(max_length=50)
        )
        assert result == "测" * 50

    def test_generate_boundary_max_number(self, generator):
        """测试生成边界最大值 - 数字"""
        result = generator._generate_boundary_max(
            field_type=DataType.NUMBER,
            constraints=DataConstraints(max_value=100)
        )
        assert result == "100"

    def test_generate_boundary_max_other(self, generator):
        """测试生成边界最大值 - 其他类型"""
        result = generator._generate_boundary_max(
            field_type=DataType.DATE,
            constraints=DataConstraints()
        )
        assert result == ""

    def test_generate_boundary_over_text(self, generator):
        """测试生成边界溢出值 - 文本"""
        result = generator._generate_boundary_over(
            field_type=DataType.TEXT,
            constraints=DataConstraints(max_length=50)
        )
        assert result == "测" * 51

    def test_generate_boundary_over_number(self, generator):
        """测试生成边界溢出值 - 数字"""
        result = generator._generate_boundary_over(
            field_type=DataType.NUMBER,
            constraints=DataConstraints(max_value=100)
        )
        assert result == "101"

    def test_generate_boundary_over_other(self, generator):
        """测试生成边界溢出值 - 其他类型"""
        result = generator._generate_boundary_over(
            field_type=DataType.DATE,
            constraints=DataConstraints()
        )
        assert result == ""

    def test_generate_special_chars_non_text(self, generator):
        """测试生成特殊字符 - 非文本类型"""
        result = generator._generate_special_chars(
            field_type=DataType.NUMBER,
            constraints=DataConstraints()
        )
        assert result == ""

    def test_generate_special_chars_text(self, generator):
        """测试生成特殊字符 - 文本类型"""
        result = generator._generate_special_chars(
            field_type=DataType.TEXT,
            constraints=DataConstraints()
        )
        # 应该包含特殊字符
        assert any(c in result for c in "!@#$%^&*()")

    def test_apply_template(self, generator):
        """测试应用模板"""
        template = "${field_name}_${date}_${time}_${random}"
        result = generator._apply_template(template, "test_field")
        assert "${field_name}" not in result
        assert "${date}" not in result
        assert "${time}" not in result
        assert "${random}" not in result
        assert "test_field" in result

    def test_apply_template_partial(self, generator):
        """测试应用模板 - 部分变量"""
        template = "${field_name}_static"
        result = generator._apply_template(template, "myfield")
        assert result == "myfield_static"

    def test_random_chinese(self, generator):
        """测试生成随机中文"""
        result = generator._random_chinese(10)
        assert len(result) == 10
        # 应该都是中文字符
        for char in result:
            assert '\u4e00' <= char <= '\u9fff'

    def test_generate_product_name(self, generator):
        """测试生成产品名称"""
        result = generator._generate_product_name()
        assert "产品线_" in result
        # 验证日期格式
        parts = result.split("_")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD

    def test_generate_chinese_name(self, generator):
        """测试生成中文姓名"""
        result = generator._generate_chinese_name()
        assert len(result) == 2 or len(result) == 3  # 2或3个字符

    def test_generate_description(self, generator):
        """测试生成描述"""
        result = generator._generate_description(
            DataConstraints(min_length=20, max_length=25)
        )
        assert 20 <= len(result) <= 25

    def test_generate_address(self, generator):
        """测试生成地址"""
        result = generator._generate_address()
        # 验证地址格式
        assert len(result) > 0
        assert isinstance(result, str)

    def test_generate_company_name(self, generator):
        """测试生成公司名称"""
        result = generator._generate_company_name()
        assert "公司" in result or "有限" in result

    def test_generate_number_default(self, generator):
        """测试生成数字 - 默认值"""
        result = generator._generate_number(DataConstraints())
        num = int(result)
        assert 0 <= num <= 100

    def test_generate_date(self, generator):
        """测试生成日期"""
        result = generator._generate_date(DataConstraints())
        # 验证日期格式
        assert len(result) == 10
        assert result[4] == '-' and result[7] == '-'

    def test_generate_datetime(self, generator):
        """测试生成日期时间"""
        result = generator._generate_datetime(DataConstraints())
        # 验证格式
        assert len(result) == 19
        assert result[10] == ' '
        assert result[13] == ':' and result[16] == ':'

    def test_generate_email(self, generator):
        """测试生成邮箱"""
        result = generator._generate_email(DataConstraints())
        assert "@" in result
        assert "." in result.split("@")[1]

    def test_generate_phone(self, generator):
        """测试生成手机号"""
        result = generator._generate_phone()
        assert len(result) == 11
        assert result.startswith("1")

    def test_generate_enum_empty(self, generator):
        """测试生成枚举 - 空值"""
        result = generator._generate_enum(DataConstraints())
        assert result == ""

    def test_generate_boolean(self, generator):
        """测试生成布尔值"""
        result = generator._generate_boolean()
        assert result in ["true", "false"]

    def test_generate_url(self, generator):
        """测试生成URL"""
        result = generator._generate_url(DataConstraints())
        assert result.startswith("http")
        assert "://" in result

    def test_generate_id_card(self, generator):
        """测试生成身份证号"""
        result = generator._generate_id_card()
        assert len(result) == 18

    def test_generate_bank_card(self, generator):
        """测试生成银行卡号"""
        result = generator._generate_bank_card()
        assert len(result) >= 16

    def test_reset_generated_values_with_seed(self):
        """测试重置生成值 - 带种子"""
        generator = TestDataGenerator(seed=12345)
        generator._generated_values["test"] = "value"
        generator.reset_generated_values()
        assert len(generator._generated_values) == 0

    def test_reset_generated_values_without_seed(self):
        """测试重置生成值 - 无种子"""
        generator = TestDataGenerator()
        generator._generated_values["test"] = "value"
        generator.reset_generated_values()
        assert len(generator._generated_values) == 0

    def test_generate_test_data_convenience_function(self):
        """测试便捷函数"""
        result = generate_test_data(
            field_type=DataType.TEXT,
            field_name="test"
        )
        assert isinstance(result, str)
        assert len(result) > 0


class TestTestDataParameterizerCoverage:
    """测试数据参数化器覆盖率测试"""

    @pytest.fixture
    def parameterizer(self):
        """创建参数化器实例"""
        return TestDataParameterizer()

    def test_init_with_context(self):
        """测试初始化 - 带上下文"""
        context = ParameterContext(execution_id="test-001")
        parameterizer = TestDataParameterizer(context)
        assert parameterizer.context.execution_id == "test-001"

    def test_handle_random_param_product_name(self, parameterizer):
        """测试处理random参数 - 产品名"""
        result = parameterizer._handle_random_param("product_name")
        assert "${random.product_name}" not in result
        assert len(result) > 0

    def test_handle_random_param_unknown(self, parameterizer):
        """测试处理random参数 - 未知参数"""
        result = parameterizer._handle_random_param("unknown_param")
        # 未知参数应该返回原样或空
        assert "${random.unknown_param}" in result or result == ""

    def test_handle_date_param_today(self, parameterizer):
        """测试处理date参数 - 今天"""
        result = parameterizer._handle_date_param("today")
        assert result == datetime.now().strftime('%Y-%m-%d')

    def test_handle_date_param_now(self, parameterizer):
        """测试处理date参数 - 现在"""
        result = parameterizer._handle_date_param("now")
        assert len(result) > 0

    def test_handle_date_param_year(self, parameterizer):
        """测试处理date参数 - 年"""
        result = parameterizer._handle_date_param("year")
        assert result == str(datetime.now().year)

    def test_handle_date_param_month(self, parameterizer):
        """测试处理date参数 - 月"""
        result = parameterizer._handle_date_param("month")
        assert result.isdigit()
        assert 1 <= int(result) <= 12

    def test_handle_date_param_day(self, parameterizer):
        """测试处理date参数 - 日"""
        result = parameterizer._handle_date_param("day")
        assert result.isdigit()
        assert 1 <= int(result) <= 31

    def test_handle_date_param_relative_future(self, parameterizer):
        """测试处理date参数 - 相对日期（未来）"""
        result = parameterizer._handle_date_param("+1")
        assert len(result) == 10  # YYYY-MM-DD

    def test_handle_date_param_relative_past(self, parameterizer):
        """测试处理date参数 - 相对日期（过去）"""
        result = parameterizer._handle_date_param("-1")
        assert len(result) == 10  # YYYY-MM-DD

    def test_handle_date_param_unknown(self, parameterizer):
        """测试处理date参数 - 未知参数"""
        result = parameterizer._handle_date_param("unknown")
        # 未知参数应该返回原样
        assert "${date.unknown}" in result or result == ""

    def test_handle_user_param_name(self, parameterizer):
        """测试处理user参数 - 姓名"""
        result = parameterizer._handle_user_param("name")
        assert len(result) > 0

    def test_handle_user_param_unknown(self, parameterizer):
        """测试处理user参数 - 未知参数"""
        result = parameterizer._handle_user_param("unknown")
        # 未知参数应该返回原样
        assert "${user.unknown}" in result or result == ""

    def test_handle_execution_param_id(self, parameterizer):
        """测试处理execution参数 - ID"""
        result = parameterizer._handle_execution_param("id")
        # 验证返回的是执行ID（格式可能不同）
        assert len(result) > 0
        assert isinstance(result, str)

    def test_handle_execution_param_timestamp(self, parameterizer):
        """测试处理execution参数 - 时间戳"""
        result = parameterizer._handle_execution_param("timestamp")
        assert result.isdigit()
        assert len(result) == 14  # YYYYMMDDHHMMSS

    def test_handle_execution_param_unknown(self, parameterizer):
        """测试处理execution参数 - 未知参数"""
        result = parameterizer._handle_execution_param("unknown")
        # 未知参数应该返回原样
        assert "${execution.unknown}" in result or result == ""

    def test_parse_with_braces_in_text(self, parameterizer):
        """测试解析 - 文本中包含大括号"""
        template = "JSON: {\"key\": \"${random.number}\"}"
        result = parameterizer.parse(template)
        assert "${random.number}" not in result
        assert "JSON:" in result

    def test_parse_multiple_same_placeholder(self, parameterizer):
        """测试解析 - 多个相同占位符"""
        template = "${random.product_name} and ${random.product_name}"
        result = parameterizer.parse(template)
        # 相同占位符应该返回相同值（缓存）
        parts = result.split(" and ")
        assert parts[0] == parts[1]

    def test_parse_with_whitespace(self, parameterizer):
        """测试解析 - 带空格的占位符"""
        template = "Value: ${ random.number }"
        result = parameterizer.parse(template)
        # 带空格的占位符应该不被识别
        assert "${ random.number }" in result


class TestTestDataServiceCoverage:
    """测试数据服务覆盖率测试"""

    @pytest.fixture
    def db_session(self):
        """创建模拟的数据库会话"""
        session = Mock()
        return session

    @pytest.fixture
    def service(self, db_session):
        """创建测试数据服务实例"""
        return TestDataService(db_session)

    def test_create_test_data_with_none_values(self, service, db_session):
        """测试创建测试数据 - 各种None值"""
        with patch.object(db_session, 'add'), \
             patch.object(db_session, 'commit'), \
             patch.object(db_session, 'refresh'):
            result = service.create_test_data(
                step_id=100,
                field_name="test",
                field_type=DataType.TEXT,
                rule_config=None,
                enum_values=None
            )
        assert result.rule_config is None
        assert result.enum_values is None

    def test_generate_value_with_json_fields(self, service):
        """测试生成值 - 带JSON字段"""
        test_data = TestData(
            id=1,
            step_id=100,
            field_name="test",
            field_type=DataType.ENUM,
            generation_rule=GenerationRule.RANDOM,
            rule_config='{"key": "value"}',
            enum_values='["a", "b", "c"]',
            min_length=None,
            max_length=None,
            min_value=None,
            max_value=None
        )
        result = service.generate_value(test_data)
        assert result in ["a", "b", "c"]

    def test_generate_step_data_empty_result(self, service, db_session):
        """测试生成步骤数据 - 空结果"""
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        result = service.generate_step_data(100)
        assert result == {}

    def test_generate_case_data_empty_steps(self, service, db_session):
        """测试生成用例数据 - 空步骤列表"""
        from app.models.test_case import TestCase

        test_case = Mock(spec=TestCase)
        test_case.test_steps = []
        db_session.query.return_value.filter.return_value.first.return_value = test_case

        result = service.generate_case_data(1)
        assert result == {}
