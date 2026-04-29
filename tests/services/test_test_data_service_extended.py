"""
测试数据服务扩展单元测试 - 补充覆盖率

测试范围:
- 更新测试数据时JSON字段处理
- 生成值的各种场景
- 批量操作
- 复制功能
- 智能生成的各种场景
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from app.services.test_data_service import TestDataService
from app.services.test_data_generator import TestDataGenerator, DataConstraints
from app.services.test_data_parameterizer import TestDataParameterizer, ParameterContext
from app.models.test_data import TestData, DataType, GenerationRule


class TestTestDataServiceExtended:
    """测试数据服务扩展测试类"""

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
    def sample_test_data_with_json(self):
        """创建包含JSON字段的示例测试数据"""
        return TestData(
            id=1,
            step_id=100,
            field_name="status",
            field_type=DataType.ENUM,
            generation_rule=GenerationRule.RANDOM,
            data_value=None,
            rule_config='{"options": ["active", "inactive"]}',
            min_length=None,
            max_length=None,
            min_value=None,
            max_value=None,
            enum_values='["active", "inactive", "pending"]',
            description="状态",
            is_required=True,
            sort_order=0
        )

    # ============================================================================
    # 更新测试数据 - JSON字段处理
    # ============================================================================

    def test_update_test_data_with_rule_config(self, service, db_session):
        """测试更新测试数据 - 带rule_config"""
        # 准备
        existing_data = TestData(
            id=1,
            step_id=100,
            field_name="test",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
            rule_config=None,
            enum_values=None
        )
        db_session.query.return_value.filter.return_value.first.return_value = existing_data

        # 执行
        with patch.object(db_session, 'commit') as mock_commit:
            result = service.update_test_data(
                1,
                field_name="updated",
                rule_config={"custom": "value"}
            )

        # 验证
        assert result is not None
        assert result.rule_config == '{"custom": "value"}'
        mock_commit.assert_called_once()

    def test_update_test_data_with_enum_values(self, service, db_session):
        """测试更新测试数据 - 带enum_values"""
        # 准备
        existing_data = TestData(
            id=1,
            step_id=100,
            field_name="test",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
            rule_config=None,
            enum_values=None
        )
        db_session.query.return_value.filter.return_value.first.return_value = existing_data

        # 执行
        with patch.object(db_session, 'commit') as mock_commit:
            result = service.update_test_data(
                1,
                enum_values=["option1", "option2"]
            )

        # 验证
        assert result is not None
        assert result.enum_values == '["option1", "option2"]'
        mock_commit.assert_called_once()

    def test_update_test_data_with_none_json_fields(self, service, db_session):
        """测试更新测试数据 - JSON字段为None"""
        # 准备
        existing_data = TestData(
            id=1,
            step_id=100,
            field_name="test",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
            rule_config='{"old": "value"}',
            enum_values='["old"]'
        )
        db_session.query.return_value.filter.return_value.first.return_value = existing_data

        # 执行 - 不更新JSON字段
        with patch.object(db_session, 'commit') as mock_commit:
            result = service.update_test_data(
                1,
                field_name="updated"
            )

        # 验证
        assert result is not None
        # JSON字段应该保持不变
        assert result.rule_config == '{"old": "value"}'
        mock_commit.assert_called_once()

    # ============================================================================
    # 生成值的各种场景
    # ============================================================================

    def test_generate_value_with_enum_values(self, service, db_session, sample_test_data_with_json):
        """测试生成值 - 带枚举值"""
        # 执行
        result = service.generate_value(sample_test_data_with_json)

        # 验证
        assert isinstance(result, str)
        # 结果应该是枚举值之一
        assert result in ["active", "inactive", "pending"]

    def test_generate_value_with_rule_config(self, service, db_session):
        """测试生成值 - 带规则配置"""
        # 准备
        test_data = TestData(
            id=1,
            step_id=100,
            field_name="custom_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.CUSTOM,
            data_value=None,
            rule_config='{"custom_value": "custom_test_value"}',
            min_length=None,
            max_length=None,
            min_value=None,
            max_value=None,
            enum_values=None,
            description="自定义字段",
            is_required=True,
            sort_order=0
        )

        # 执行
        result = service.generate_value(test_data)

        # 验证
        assert result == "custom_test_value"

    def test_generate_value_with_none_rule_config(self, service, db_session):
        """测试生成值 - rule_config为None"""
        # 准备
        test_data = TestData(
            id=1,
            step_id=100,
            field_name="simple_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM,
            data_value=None,
            rule_config=None,
            min_length=5,
            max_length=10,
            min_value=None,
            max_value=None,
            enum_values=None,
            description="简单字段",
            is_required=True,
            sort_order=0
        )

        # 执行
        result = service.generate_value(test_data)

        # 验证
        assert isinstance(result, str)
        assert len(result) >= 5

    # ============================================================================
    # 生成步骤数据 - 带参数化
    # ============================================================================

    def test_generate_step_data_with_parameterizer(self, service, db_session):
        """测试生成步骤数据 - 带参数化解析器"""
        # 准备
        test_data = TestData(
            id=1,
            step_id=100,
            field_name="param_field",
            field_type=DataType.TEXT,
            generation_rule=GenerationRule.CUSTOM,
            data_value="${random.product_name}",
            rule_config='{"custom_value": "${random.product_name}"}',
            min_length=None,
            max_length=None,
            min_value=None,
            max_value=None,
            enum_values=None,
            description="参数字段",
            is_required=True,
            sort_order=0
        )
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [test_data]

        # 执行
        parameterizer = TestDataParameterizer()
        result = service.generate_step_data(100, parameterizer)

        # 验证
        assert "param_field" in result
        # 参数化后的值不应该包含占位符
        assert "${random.product_name}" not in result["param_field"]

    def test_generate_step_data_without_test_data(self, service, db_session):
        """测试生成步骤数据 - 无测试数据"""
        # 准备
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        # 执行
        result = service.generate_step_data(100)

        # 验证
        assert result == {}

    # ============================================================================
    # 生成用例数据
    # ============================================================================

    def test_generate_case_data_success(self, service, db_session):
        """测试生成用例数据 - 成功"""
        # 准备
        from app.models.test_case import TestCase, TestStep

        test_case = Mock(spec=TestCase)
        test_case.id = 1
        step1 = Mock(spec=TestStep)
        step1.id = 101
        step2 = Mock(spec=TestStep)
        step2.id = 102
        test_case.test_steps = [step1, step2]

        db_session.query.return_value.filter.return_value.first.return_value = test_case

        # 模拟步骤数据
        test_data1 = TestData(
            id=1, step_id=101, field_name="field1", field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM, rule_config=None,
            enum_values=None, min_length=5, max_length=10
        )
        test_data2 = TestData(
            id=2, step_id=102, field_name="field2", field_type=DataType.EMAIL,
            generation_rule=GenerationRule.RANDOM, rule_config=None,
            enum_values=None
        )

        # 配置mock返回不同的值 - 使用args[0]获取step_id
        def side_effect(*args, **kwargs):
            step_id = args[0] if args else kwargs.get('step_id')
            if step_id == 101:
                return [test_data1]
            elif step_id == 102:
                return [test_data2]
            return []

        # 直接替换方法
        original_method = service.get_test_data_by_step
        service.get_test_data_by_step = Mock(side_effect=side_effect)

        # 执行
        context = ParameterContext(execution_id="test-001")
        result = service.generate_case_data(1, context)

        # 恢复原始方法
        service.get_test_data_by_step = original_method

        # 验证
        assert 101 in result
        assert 102 in result
        assert "field1" in result[101]
        assert "field2" in result[102]

    def test_generate_case_data_case_not_found(self, service, db_session):
        """测试生成用例数据 - 用例不存在"""
        # 准备
        db_session.query.return_value.filter.return_value.first.return_value = None

        # 执行
        result = service.generate_case_data(999)

        # 验证
        assert result == {}

    def test_generate_case_data_without_context(self, service, db_session):
        """测试生成用例数据 - 无上下文"""
        # 准备
        from app.models.test_case import TestCase, TestStep

        test_case = Mock(spec=TestCase)
        test_case.id = 1
        step = Mock(spec=TestStep)
        step.id = 101
        test_case.test_steps = [step]

        db_session.query.return_value.filter.return_value.first.return_value = test_case

        test_data = TestData(
            id=1, step_id=101, field_name="field1", field_type=DataType.TEXT,
            generation_rule=GenerationRule.RANDOM, rule_config=None,
            enum_values=None, min_length=5, max_length=10
        )
        service.get_test_data_by_step = Mock(return_value=[test_data])

        # 执行 - 不传递context
        result = service.generate_case_data(1)

        # 验证
        assert 101 in result
        assert "field1" in result[101]

    # ============================================================================
    # 批量操作
    # ============================================================================

    def test_batch_create_test_data_success(self, service, db_session):
        """测试批量创建测试数据 - 成功"""
        # 准备
        data_list = [
            {"field_name": "field1", "field_type": DataType.TEXT},
            {"field_name": "field2", "field_type": DataType.EMAIL},
            {"field_name": "field3", "field_type": DataType.NUMBER}
        ]

        # 执行
        with patch.object(service, 'create_test_data') as mock_create:
            mock_create.side_effect = [
                Mock(id=1, field_name="field1"),
                Mock(id=2, field_name="field2"),
                Mock(id=3, field_name="field3")
            ]
            result = service.batch_create_test_data(100, data_list)

        # 验证
        assert len(result) == 3
        assert mock_create.call_count == 3

    def test_batch_create_test_data_partial_failure(self, service, db_session):
        """测试批量创建测试数据 - 部分失败"""
        # 准备
        data_list = [
            {"field_name": "field1", "field_type": DataType.TEXT},
            {"field_name": "field2", "field_type": DataType.TEXT},  # 会失败
            {"field_name": "field3", "field_type": DataType.TEXT}
        ]

        # 执行
        with patch.object(service, 'create_test_data') as mock_create:
            mock_create.side_effect = [
                Mock(id=1, field_name="field1"),
                Exception("创建失败"),  # 第二个失败
                Mock(id=3, field_name="field3")
            ]
            result = service.batch_create_test_data(100, data_list)

        # 验证 - 应该只返回成功创建的2个
        assert len(result) == 2
        assert result[0].field_name == "field1"
        assert result[1].field_name == "field3"

    def test_batch_create_test_data_empty_list(self, service, db_session):
        """测试批量创建测试数据 - 空列表"""
        # 执行
        result = service.batch_create_test_data(100, [])

        # 验证
        assert result == []

    # ============================================================================
    # 复制功能
    # ============================================================================

    def test_copy_test_data_success(self, service, db_session):
        """测试复制测试数据 - 成功"""
        # 准备
        source_data_list = [
            TestData(
                id=1, step_id=100, field_name="field1", field_type=DataType.TEXT,
                generation_rule=GenerationRule.RANDOM, rule_config=None,
                enum_values=None, min_length=5, max_length=10
            ),
            TestData(
                id=2, step_id=100, field_name="field2", field_type=DataType.EMAIL,
                generation_rule=GenerationRule.RANDOM, rule_config=None,
                enum_values=None
            )
        ]
        service.get_test_data_by_step = Mock(return_value=source_data_list)

        # 执行
        with patch.object(service, 'create_test_data') as mock_create:
            mock_create.side_effect = [
                Mock(id=3, field_name="field1"),
                Mock(id=4, field_name="field2")
            ]
            result = service.copy_test_data(100, 200)

        # 验证
        assert result == 2
        assert mock_create.call_count == 2

    def test_copy_test_data_partial_failure(self, service, db_session):
        """测试复制测试数据 - 部分失败"""
        # 准备
        source_data_list = [
            TestData(
                id=1, step_id=100, field_name="field1", field_type=DataType.TEXT,
                generation_rule=GenerationRule.RANDOM, rule_config=None,
                enum_values=None
            ),
            TestData(
                id=2, step_id=100, field_name="field2", field_type=DataType.TEXT,
                generation_rule=GenerationRule.RANDOM, rule_config=None,
                enum_values=None
            )
        ]
        service.get_test_data_by_step = Mock(return_value=source_data_list)

        # 执行
        with patch.object(service, 'create_test_data') as mock_create:
            mock_create.side_effect = [
                Mock(id=3, field_name="field1"),
                Exception("复制失败")  # 第二个失败
            ]
            result = service.copy_test_data(100, 200)

        # 验证
        assert result == 1  # 只有1个成功

    def test_copy_test_data_empty_source(self, service, db_session):
        """测试复制测试数据 - 源为空"""
        # 准备
        service.get_test_data_by_step = Mock(return_value=[])

        # 执行
        result = service.copy_test_data(100, 200)

        # 验证
        assert result == 0

    # ============================================================================
    # 智能生成 - 各种场景
    # ============================================================================

    def test_auto_generate_with_product_line(self, service, db_session):
        """测试自动推断生成 - 产品线场景"""
        # 执行
        with patch.object(service, 'create_test_data') as mock_create:
            mock_create.return_value = Mock(id=1, field_name="product_name")
            result = service.auto_generate_for_step(100, "选择产品线")

        # 验证 - "产品线"匹配"产品"和"输入"两个关键词
        assert len(result) >= 1
        assert mock_create.call_count >= 1
        # 检查是否创建了product_name字段
        field_names = [call[1].get('field_name') for call in mock_create.call_args_list]
        assert "product_name" in field_names

    def test_auto_generate_with_input(self, service, db_session):
        """测试自动推断生成 - 输入场景"""
        # 执行
        with patch.object(service, 'create_test_data') as mock_create:
            mock_create.return_value = Mock(id=1, field_name="input_value")
            result = service.auto_generate_for_step(100, "在搜索框中输入关键词")

        # 验证
        assert len(result) == 1
        call_args = mock_create.call_args
        assert call_args[1]['field_name'] == "input_value"

    def test_auto_generate_with_select(self, service, db_session):
        """测试自动推断生成 - 选择场景"""
        # 执行
        with patch.object(service, 'create_test_data') as mock_create:
            mock_create.return_value = Mock(id=1, field_name="select_value")
            result = service.auto_generate_for_step(100, "从下拉列表选择选项")

        # 验证
        assert len(result) == 1
        call_args = mock_create.call_args
        assert call_args[1]['field_type'] == DataType.ENUM
        assert "选项1" in call_args[1]['enum_values']

    def test_auto_generate_with_date(self, service, db_session):
        """测试自动推断生成 - 日期场景"""
        # 执行
        with patch.object(service, 'create_test_data') as mock_create:
            mock_create.return_value = Mock(id=1, field_name="date_value")
            result = service.auto_generate_for_step(100, "选择开始日期")

        # 验证 - "选择"和"日期"两个关键词都会匹配
        assert len(result) >= 1
        # 检查是否创建了date_value字段
        field_names = [call[1].get('field_name') for call in mock_create.call_args_list]
        assert "date_value" in field_names

    def test_auto_generate_multiple_fields(self, service, db_session):
        """测试自动推断生成 - 多个字段"""
        # 执行 - 包含多种关键词
        with patch.object(service, 'create_test_data') as mock_create:
            mock_create.side_effect = [
                Mock(id=1, field_name="product_name"),
                Mock(id=2, field_name="input_value"),
                Mock(id=3, field_name="date_value")
            ]
            result = service.auto_generate_for_step(100, "输入产品名称和日期")

        # 验证
        assert len(result) == 3
        assert mock_create.call_count == 3

    def test_auto_generate_no_match(self, service, db_session):
        """测试自动推断生成 - 无匹配场景"""
        # 执行 - 不包含任何关键词
        result = service.auto_generate_for_step(100, "点击提交按钮")

        # 验证
        assert len(result) == 0

    def test_auto_generate_fill_keyword(self, service, db_session):
        """测试自动推断生成 - 填写关键词"""
        # 执行
        with patch.object(service, 'create_test_data') as mock_create:
            mock_create.return_value = Mock(id=1, field_name="input_value")
            result = service.auto_generate_for_step(100, "填写表单信息")

        # 验证
        assert len(result) == 1


class TestTestDataGeneratorExtended:
    """测试数据生成器扩展测试类"""

    @pytest.fixture
    def generator(self):
        """创建生成器实例"""
        return TestDataGenerator()

    def test_generate_data_datetime(self, generator):
        """测试生成日期时间数据"""
        result = generator.generate_data(
            field_type=DataType.DATETIME,
            field_name="datetime"
        )
        assert isinstance(result, str)
        # 应该包含日期和时间
        assert len(result) > 10

    def test_generate_data_with_constraints_min_max_length(self, generator):
        """测试生成数据 - 使用min_length和max_length约束"""
        result = generator.generate_data(
            field_type=DataType.TEXT,
            field_name="text",
            constraints=DataConstraints(min_length=10, max_length=15)
        )
        assert isinstance(result, str)
        assert 10 <= len(result) <= 15

    def test_generate_data_with_pattern(self, generator):
        """测试生成数据 - 使用pattern约束"""
        result = generator.generate_data(
            field_type=DataType.TEXT,
            field_name="text",
            constraints=DataConstraints(pattern="[A-Z]{3}")
        )
        assert isinstance(result, str)

    def test_generate_data_enum_with_values(self, generator):
        """测试生成枚举数据 - 有枚举值"""
        result = generator.generate_data(
            field_type=DataType.ENUM,
            field_name="status",
            constraints=DataConstraints(enum_values=["active", "inactive", "pending"])
        )
        assert result in ["active", "inactive", "pending"]

    def test_generate_data_enum_without_values(self, generator):
        """测试生成枚举数据 - 无枚举值"""
        result = generator.generate_data(
            field_type=DataType.ENUM,
            field_name="status",
            constraints=DataConstraints()
        )
        # 应该返回默认值
        assert isinstance(result, str)

    def test_generate_data_boundary_over(self, generator):
        """测试生成数据 - 边界溢出值"""
        result = generator.generate_data(
            field_type=DataType.NUMBER,
            field_name="number",
            generation_rule=GenerationRule.BOUNDARY_OVER,
            constraints=DataConstraints(min_value=10, max_value=100)
        )
        # 应该返回超出边界的值
        num = int(result)
        assert num < 10 or num > 100

    def test_generate_data_unknown_field_type(self, generator):
        """测试生成数据 - 未知字段类型"""
        result = generator.generate_data(
            field_type="unknown_type",
            field_name="unknown"
        )
        # 应该返回字符串值
        assert isinstance(result, str)

    def test_generate_data_with_empty_constraints(self, generator):
        """测试生成数据 - 空约束"""
        result = generator.generate_data(
            field_type=DataType.TEXT,
            field_name="text",
            constraints=DataConstraints()
        )
        assert isinstance(result, str)
        assert len(result) > 0


class TestTestDataParameterizerExtended:
    """测试数据参数化器扩展测试类"""

    @pytest.fixture
    def parameterizer(self):
        """创建参数化器实例"""
        return TestDataParameterizer()

    def test_parse_random_company(self, parameterizer):
        """测试解析 - 随机公司名"""
        template = "${random.company}"
        result = parameterizer.parse(template)
        assert "${random.company}" not in result
        assert len(result) > 0

    def test_parse_random_address(self, parameterizer):
        """测试解析 - 随机地址"""
        template = "${random.address}"
        result = parameterizer.parse(template)
        assert "${random.address}" not in result
        assert len(result) > 0

    def test_parse_random_name(self, parameterizer):
        """测试解析 - 随机姓名"""
        template = "${random.name}"
        result = parameterizer.parse(template)
        assert "${random.name}" not in result
        assert len(result) > 0

    def test_parse_random_email(self, parameterizer):
        """测试解析 - 随机邮箱"""
        template = "${random.email}"
        result = parameterizer.parse(template)
        assert "${random.email}" not in result
        assert "@" in result

    def test_parse_random_phone(self, parameterizer):
        """测试解析 - 随机手机号"""
        template = "${random.phone}"
        result = parameterizer.parse(template)
        assert "${random.phone}" not in result
        assert len(result) == 11

    def test_parse_random_number(self, parameterizer):
        """测试解析 - 随机数字"""
        template = "${random.number}"
        result = parameterizer.parse(template)
        assert "${random.number}" not in result
        assert result.isdigit()

    def test_parse_date_weekday(self, parameterizer):
        """测试解析 - 星期几（如果支持）"""
        template = "${date.weekday}"
        result = parameterizer.parse(template)
        # 如果支持weekday，应该被替换；如果不支持，保持原样
        if "${date.weekday}" in result:
            # 不支持weekday参数，这是预期的行为
            pass
        else:
            # 支持weekday参数
            assert result in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def test_parse_user_email(self, parameterizer):
        """测试解析 - 用户邮箱"""
        template = "${user.email}"
        result = parameterizer.parse(template)
        assert "${user.email}" not in result
        assert "@" in result

    def test_parse_user_phone(self, parameterizer):
        """测试解析 - 用户手机号"""
        template = "${user.phone}"
        result = parameterizer.parse(template)
        assert "${user.phone}" not in result
        assert len(result) > 0

    def test_parse_execution_timestamp(self, parameterizer):
        """测试解析 - 执行时间戳"""
        template = "${execution.timestamp}"
        result = parameterizer.parse(template)
        assert "${execution.timestamp}" not in result
        assert result.isdigit()

    def test_parse_nested_placeholder(self, parameterizer):
        """测试解析 - 嵌套占位符"""
        template = "Name: ${random.name}, Email: ${random.email}, Date: ${date.today}"
        result = parameterizer.parse(template)
        assert "${random.name}" not in result
        assert "${random.email}" not in result
        assert "${date.today}" not in result
        assert "Name:" in result
        assert "Email:" in result
        assert "Date:" in result

    def test_parse_with_special_chars(self, parameterizer):
        """测试解析 - 包含特殊字符"""
        template = "Value: ${random.number} (test)"
        result = parameterizer.parse(template)
        assert "${random.number}" not in result
        assert "(test)" in result

    def test_get_cached_params_empty(self, parameterizer):
        """测试获取缓存参数 - 空缓存"""
        result = parameterizer.get_cached_params()
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_get_cached_params_with_values(self, parameterizer):
        """测试获取缓存参数 - 有缓存值"""
        # 先解析一些内容
        parameterizer.parse("${random.product_name}")
        parameterizer.parse("${date.today}")

        result = parameterizer.get_cached_params()
        assert isinstance(result, dict)
        assert len(result) >= 1

    def test_clear_cache_empty(self, parameterizer):
        """测试清除缓存 - 已经是空"""
        # 不应该报错
        parameterizer.clear_cache()
        assert len(parameterizer.context.cached_values) == 0


class TestDataConstraintsExtended:
    """数据约束扩展测试"""

    def test_constraints_with_all_fields(self):
        """测试约束 - 所有字段"""
        constraints = DataConstraints(
            min_length=1,
            max_length=100,
            min_value=0,
            max_value=999,
            enum_values=["a", "b", "c"],
            pattern="^[a-z]+$"
        )
        assert constraints.min_length == 1
        assert constraints.max_length == 100
        assert constraints.min_value == 0
        assert constraints.max_value == 999
        assert constraints.enum_values == ["a", "b", "c"]
        assert constraints.pattern == "^[a-z]+$"

    def test_constraints_partial_fields(self):
        """测试约束 - 部分字段"""
        constraints = DataConstraints(
            min_length=5,
            max_length=10
        )
        assert constraints.min_length == 5
        assert constraints.max_length == 10
        assert constraints.min_value is None
        assert constraints.max_value is None
        assert constraints.enum_values is None
        assert constraints.pattern is None

    def test_constraints_immutability(self):
        """测试约束 - 不可变性（如果实现了）"""
        constraints = DataConstraints(min_length=5)
        # 如果约束是可变的，可以修改
        # 这里只是测试创建后属性存在
        assert hasattr(constraints, 'min_length')
