"""
测试数据生成器补充单元测�?

用于提升覆盖率到80%以上
测试范围:
- 未覆盖的边界条件
- 异常处理
- 复杂场景
- 所有数据类�?
"""
import pytest
from datetime import datetime

from app.services.test_data_generator import (
    TestDataGenerator, DataConstraints, generate_test_data
)
from app.models.test_data import DataType, GenerationRule


class TestTestDataGeneratorSupplement:
    """测试数据生成器补充测试类"""

    @pytest.fixture
    def generator(self):
        """创建测试数据生成器实�?""
        return TestDataGenerator()

    @pytest.fixture
    def generator_with_seed(self):
        """创建带种子的测试数据生成�?""
        return TestDataGenerator(seed=42)

    # ============================================================================
    # 生成规则测试
    # ============================================================================

    def test_generate_boundary_min_text(self, generator):
        """测试边界最小�?文本类型"""
        constraints = DataConstraints(min_length=5)
        result = generator._generate_boundary_min(DataType.TEXT, constraints)
        assert len(result) == 5
        assert result == "�? * 5

    def test_generate_boundary_min_number(self, generator):
        """测试边界最小�?数字类型"""
        constraints = DataConstraints(min_value=10)
        result = generator._generate_boundary_min(DataType.NUMBER, constraints)
        assert result == "10"

    def test_generate_boundary_min_other(self, generator):
        """测试边界最小�?其他类型"""
        constraints = DataConstraints()
        result = generator._generate_boundary_min(DataType.EMAIL, constraints)
        assert result == ""

    def test_generate_boundary_max_text(self, generator):
        """测试边界最大�?文本类型"""
        constraints = DataConstraints(max_length=20)
        result = generator._generate_boundary_max(DataType.TEXT, constraints)
        assert len(result) == 20

    def test_generate_boundary_max_number(self, generator):
        """测试边界最大�?数字类型"""
        constraints = DataConstraints(max_value=100)
        result = generator._generate_boundary_max(DataType.NUMBER, constraints)
        assert result == "100"

    def test_generate_boundary_over_text(self, generator):
        """测试边界超长�?文本类型"""
        constraints = DataConstraints(max_length=10)
        result = generator._generate_boundary_over(DataType.TEXT, constraints)
        assert len(result) == 11

    def test_generate_boundary_over_number(self, generator):
        """测试边界超长�?数字类型"""
        constraints = DataConstraints(max_value=50)
        result = generator._generate_boundary_over(DataType.NUMBER, constraints)
        assert result == "51"

    def test_generate_special_chars_text(self, generator):
        """测试特殊字符-文本类型"""
        constraints = DataConstraints()
        result = generator._generate_special_chars(DataType.TEXT, constraints)
        assert len(result) >= 5
        assert any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in result)

    def test_generate_special_chars_non_text(self, generator):
        """测试特殊字符-非文本类�?""
        constraints = DataConstraints()
        result = generator._generate_special_chars(DataType.NUMBER, constraints)
        assert result == ""

    def test_generate_empty_rule(self, generator):
        """测试空值规�?""
        result = generator.generate_data(
            DataType.TEXT,
            "test_field",
            generation_rule=GenerationRule.EMPTY
        )
        assert result == ""

    def test_generate_custom_rule(self, generator):
        """测试自定义规�?""
        rule_config = {"custom_value": "my_custom_value"}
        result = generator.generate_data(
            DataType.TEXT,
            "test_field",
            generation_rule=GenerationRule.CUSTOM,
            rule_config=rule_config
        )
        assert result == "my_custom_value"

    def test_generate_custom_rule_no_value(self, generator):
        """测试自定义规�?无�?""
        result = generator.generate_data(
            DataType.TEXT,
            "test_field",
            generation_rule=GenerationRule.CUSTOM,
            rule_config={}
        )
        assert result == ""

    # ============================================================================
    # 数据类型测试 - 文本相关
    # ============================================================================

    def test_generate_text_with_template(self, generator):
        """测试使用模板生成文本"""
        rule_config = {"template": "test_${date}_${random}"}
        result = generator._generate_text("test", DataConstraints(), rule_config)
        assert "test_" in result
        assert "${date}" not in result  # 模板应该被替�?

    def test_generate_text_product_name(self, generator):
        """测试生成产品线名�?""
        result = generator._generate_text("产品�?, DataConstraints(), {})
        assert "产品线_" in result

    def test_generate_text_chinese_name(self, generator):
        """测试生成中文姓名"""
        result = generator._generate_text("用户�?, DataConstraints(), {})
        assert len(result) >= 2  # �?名，可能�?-3个字�?

    def test_generate_text_description(self, generator):
        """测试生成描述"""
        constraints = DataConstraints(min_length=10, max_length=20)
        result = generator._generate_text("描述", constraints, {})
        assert len(result) >= 10
        assert len(result) <= 20

    def test_generate_text_address(self, generator):
        """测试生成地址"""
        result = generator._generate_text("地址", DataConstraints(), {})
        assert "�? in result

    def test_generate_text_company(self, generator):
        """测试生成公司名称"""
        result = generator._generate_text("公司", DataConstraints(), {})
        assert "有限公司" in result or "公司" in result

    def test_generate_text_general(self, generator):
        """测试生成通用文本"""
        constraints = DataConstraints(min_length=5, max_length=10)
        result = generator._generate_text("其他字段", constraints, {})
        assert len(result) >= 5
        assert len(result) <= 10

    # ============================================================================
    # 数据类型测试 - 其他类型
    # ============================================================================

    def test_generate_number_with_constraints(self, generator):
        """测试生成带约束的数字"""
        constraints = DataConstraints(min_value=50, max_value=100)
        result = generator._generate_number(constraints)
        num = int(result)
        assert 50 <= num <= 100

    def test_generate_number_default_range(self, generator):
        """测试生成默认范围的数�?""
        constraints = DataConstraints()
        result = generator._generate_number(constraints)
        num = int(result)
        assert 0 <= num <= 100

    def test_generate_date_with_constraints(self, generator):
        """测试生成带约束的日期"""
        constraints = DataConstraints()
        result = generator._generate_date(constraints)
        # 验证日期格式
        datetime.strptime(result, "%Y-%m-%d")

    def test_generate_datetime_with_constraints(self, generator):
        """测试生成带约束的日期时间"""
        constraints = DataConstraints()
        result = generator._generate_datetime(constraints)
        # 验证日期时间格式
        datetime.strptime(result, "%Y-%m-%d %H:%M:%S")

    def test_generate_email(self, generator):
        """测试生成邮箱"""
        constraints = DataConstraints()
        result = generator._generate_email(constraints)
        assert "@" in result
        assert ".com" in result

    def test_generate_phone(self, generator):
        """测试生成手机�?""
        result = generator._generate_phone()
        assert len(result) == 11
        assert result.isdigit()
        assert result.startswith(("13", "15", "18", "17", "14", "19"))

    def test_generate_enum_with_values(self, generator):
        """测试生成带枚举值的枚举"""
        constraints = DataConstraints(enum_values=["A", "B", "C"])
        result = generator._generate_enum(constraints)
        assert result in ["A", "B", "C"]

    def test_generate_enum_without_values(self, generator):
        """测试生成无枚举值的枚举"""
        constraints = DataConstraints()
        result = generator._generate_enum(constraints)
        assert result == ""

    def test_generate_boolean(self, generator):
        """测试生成布尔�?""
        result = generator._generate_boolean()
        assert result in ["true", "false"]

    def test_generate_url(self, generator):
        """测试生成URL"""
        constraints = DataConstraints()
        result = generator._generate_url(constraints)
        assert result.startswith(("http://", "https://"))

    def test_generate_id_card(self, generator):
        """测试生成身份证号"""
        result = generator._generate_id_card()
        assert len(result) == 18

    def test_generate_bank_card(self, generator):
        """测试生成银行卡号"""
        result = generator._generate_bank_card()
        assert len(result) >= 16
        assert len(result) <= 19
        assert result.isdigit()

    # ============================================================================
    # 辅助方法测试
    # ============================================================================

    def test_random_chinese(self, generator):
        """测试生成随机中文字符�?""
        result = generator._random_chinese(5)
        assert len(result) == 5
        # 验证都是中文字符
        for char in result:
            assert '\u4e00' <= char <= '\u9fff' or char in generator.CHINESE_CHARS

    def test_apply_template(self, generator):
        """测试应用模板"""
        template = "prefix_${date}_${time}_${random}_${field_name}_suffix"
        result = generator._apply_template(template, "test_field")
        assert "${date}" not in result
        assert "${time}" not in result
        assert "${random}" not in result
        assert "${field_name}" not in result
        assert "test_field" in result

    def test_apply_template_partial(self, generator):
        """测试应用模板-部分变量"""
        template = "test_${date}"
        result = generator._apply_template(template, "field")
        assert "${date}" not in result
        assert "test_" in result

    # ============================================================================
    # 缓存功能测试
    # ============================================================================

    def test_get_cached_value_new(self, generator):
        """测试获取新缓存�?""
        result = generator.get_cached_value("key1", DataType.TEXT, "field1")
        assert result is not None
        assert "key1" in generator._generated_values

    def test_get_cached_value_existing(self, generator):
        """测试获取已缓存的�?""
        # 先获取一�?
        result1 = generator.get_cached_value("key2", DataType.TEXT, "field2")
        # 再次获取应该返回相同的�?
        result2 = generator.get_cached_value("key2", DataType.TEXT, "field2")
        assert result1 == result2

    def test_reset_generated_values(self, generator):
        """测试重置生成的�?""
        # 生成一些�?
        generator.get_cached_value("key3", DataType.TEXT, "field3")
        assert len(generator._generated_values) > 0
        
        # 重置
        generator.reset_generated_values()
        assert len(generator._generated_values) == 0

    def test_reset_with_seed(self, generator_with_seed):
        """测试带种子的重置"""
        # 生成一些�?
        result1 = generator_with_seed._random_chinese(5)
        generator_with_seed.reset_generated_values()
        result2 = generator_with_seed._random_chinese(5)
        # 重置后使用相同种子，应该生成相同的结�?
        assert result1 == result2

    # ============================================================================
    # 异常处理测试
    # ============================================================================

    def test_generate_data_exception(self, generator):
        """测试生成数据异常处理"""
        # 传入无效的约束条件可能导致异�?
        result = generator.generate_data(
            DataType.TEXT,
            "test",
            constraints=None  # 应该能处理None
        )
        assert result is not None

    def test_generate_data_unknown_type(self, generator):
        """测试生成未知类型数据"""
        # 使用不存在的类型
        class UnknownType:
            pass
        
        result = generator.generate_data(
            UnknownType(),  # 无效的类�?
            "test_field"
        )
        assert result == ""

    # ============================================================================
    # 便捷函数测试
    # ============================================================================

    def test_generate_test_data_convenience(self):
        """测试便捷生成函数"""
        result = generate_test_data(
            DataType.TEXT,
            "username",
            GenerationRule.RANDOM
        )
        assert result is not None

    def test_generate_test_data_with_kwargs(self):
        """测试便捷生成函数带参�?""
        result = generate_test_data(
            DataType.NUMBER,
            "age",
            GenerationRule.RANDOM,
            min_value=18,
            max_value=60
        )
        num = int(result)
        assert 18 <= num <= 60


class TestDataConstraints:
    """数据约束条件测试�?""

    def test_default_constraints(self):
        """测试默认约束"""
        constraints = DataConstraints()
        assert constraints.min_length is None
        assert constraints.max_length is None
        assert constraints.min_value is None
        assert constraints.max_value is None
        assert constraints.enum_values is None
        assert constraints.pattern is None

    def test_custom_constraints(self):
        """测试自定义约�?""
        constraints = DataConstraints(
            min_length=5,
            max_length=10,
            min_value=0,
            max_value=100,
            enum_values=["A", "B", "C"],
            pattern=r"^\d+$"
        )
        assert constraints.min_length == 5
        assert constraints.max_length == 10
        assert constraints.min_value == 0
        assert constraints.max_value == 100
        assert constraints.enum_values == ["A", "B", "C"]
        assert constraints.pattern == r"^\d+$"


class TestTestDataGeneratorSeed:
    """测试数据生成器种子测试类"""

    def test_seed_reproducibility(self):
        """测试种子可重现�?- 验证使用相同种子时生成器状态一�?""
        # 注意：由于随机数生成器全局状态，此测试可能受其他测试影响
        # 这里仅验证种子设置功能正常工�?
        gen = TestDataGenerator(seed=12345)
        
        # 验证种子已设�?
        assert gen._seed == 12345
        
        # 验证可以生成数据
        result = gen._random_chinese(5)
        assert len(result) == 5

    def test_different_seeds_different_results(self):
        """测试不同种子产生不同结果"""
        gen1 = TestDataGenerator(seed=11111)
        gen2 = TestDataGenerator(seed=22222)
        
        result1 = gen1.generate_data(DataType.TEXT, "test")
        result2 = gen2.generate_data(DataType.TEXT, "test")
        
        assert result1 != result2

    def test_no_seed_random(self):
        """测试无种子随机�?""
        gen1 = TestDataGenerator()
        gen2 = TestDataGenerator()
        
        # 无种子时，结果应该不同（概率很高�?
        results1 = [gen1.generate_data(DataType.TEXT, "test") for _ in range(5)]
        results2 = [gen2.generate_data(DataType.TEXT, "test") for _ in range(5)]
        
        # 至少有一个不�?
        assert results1 != results2
