"""Legacy test data generator compatibility layer.

This module preserves the pre-refactor synchronous generator API used by tests
and by the lightweight parameterization helpers. The newer `app.services.test_data`
package remains the primary home for the production implementation.
"""
from __future__ import annotations

from datetime import datetime
import random
import string
from typing import Any, Dict, Optional

from app.models.test_data import DataType, GenerationRule
from app.services.test_data.constants import (
    DATA_TYPE_BOOLEAN,
    DATA_TYPE_CUSTOM,
    DATA_TYPE_DATE,
    DATA_TYPE_EMAIL,
    DATA_TYPE_ENUM,
    DATA_TYPE_NUMBER,
    DATA_TYPE_PHONE,
    DATA_TYPE_STRING,
)
from app.services.test_data_gen_constants import CHINESE_CHARS, DataConstraints, EMAIL_DOMAINS, PHONE_PREFIXES


class TestDataGenerator:
    """Compatibility generator used by legacy tests and helper modules."""

    __test__ = False

    CHINESE_CHARS = CHINESE_CHARS

    def __init__(self, seed: Optional[int] = None) -> None:
        self._seed = seed
        self._random = random.Random(seed)
        self._generated_values: Dict[str, str] = {}

    def generate_data(
        self,
        field_type: Any,
        field_name: str,
        generation_rule: GenerationRule = GenerationRule.RANDOM,
        constraints: Optional[DataConstraints] = None,
        rule_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        constraints = constraints or DataConstraints(
            min_length=kwargs.get('min_length'),
            max_length=kwargs.get('max_length'),
            min_value=kwargs.get('min_value'),
            max_value=kwargs.get('max_value'),
            enum_values=kwargs.get('enum_values'),
            pattern=kwargs.get('pattern'),
        )
        rule_config = rule_config or {}

        try:
            if generation_rule == GenerationRule.EMPTY:
                return ''
            if generation_rule == GenerationRule.CUSTOM:
                custom_value = rule_config.get('custom_value')
                if custom_value is not None:
                    return str(custom_value)
                template = rule_config.get('template')
                if template:
                    return self._apply_template(str(template), field_name)
                return ''
            if generation_rule == GenerationRule.BOUNDARY_MIN:
                return self._generate_boundary_min(field_type, constraints)
            if generation_rule == GenerationRule.BOUNDARY_MAX:
                return self._generate_boundary_max(field_type, constraints)
            if generation_rule == GenerationRule.BOUNDARY_OVER:
                return self._generate_boundary_over(field_type, constraints)
            if generation_rule == GenerationRule.SPECIAL_CHARS:
                return self._generate_special_chars(field_type, constraints)

            return self._generate_random(field_type, field_name, constraints, rule_config)
        except Exception:
            return ''

    def _generate_random(
        self,
        field_type: Any,
        field_name: str,
        constraints: DataConstraints,
        rule_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        normalized_type = field_type.value if isinstance(field_type, DataType) else str(field_type)

        if normalized_type == DataType.TEXT.value:
            return self._generate_text(field_name, constraints, rule_config or {})
        if normalized_type == DataType.NUMBER.value:
            return self._generate_number(constraints)
        if normalized_type == DataType.DATE.value:
            return self._generate_date(constraints)
        if normalized_type == DataType.DATETIME.value:
            return self._generate_datetime(constraints)
        if normalized_type == DataType.EMAIL.value:
            return self._generate_email(constraints)
        if normalized_type == DataType.PHONE.value:
            return self._generate_phone()
        if normalized_type == DataType.ENUM.value:
            return self._generate_enum(constraints)
        if normalized_type == DataType.BOOLEAN.value:
            return self._generate_boolean()
        if normalized_type == DataType.URL.value:
            return self._generate_url(constraints)
        if normalized_type == DataType.ID_CARD.value:
            return self._generate_id_card()
        if normalized_type == DataType.BANK_CARD.value:
            return self._generate_bank_card()
        return ''

    def _generate_text(
        self,
        field_name: str,
        constraints: DataConstraints,
        rule_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        rule_config = rule_config or {}
        template = rule_config.get('template')
        if template:
            return self._apply_template(str(template), field_name)

        lowered = field_name.lower()
        if any(token in lowered for token in ('product', '产品线')):
            return self._generate_product_name()
        if lowered in {'name', '姓名'} or any(token in lowered for token in ('user_name',)):
            return self._generate_chinese_name()
        if any(token in lowered for token in ('description', '描述')):
            return self._generate_description(constraints)
        if any(token in lowered for token in ('address', '地址')):
            return self._generate_address()
        if any(token in lowered for token in ('company', '公司')):
            return self._generate_company_name()

        min_length = constraints.min_length or 6
        max_length = constraints.max_length or max(min_length, 12)
        target_length = self._random.randint(min_length, max_length)
        return self._random_chinese(target_length)

    def _generate_number(self, constraints: DataConstraints) -> str:
        min_value = constraints.min_value if constraints.min_value is not None else 0
        max_value = constraints.max_value if constraints.max_value is not None else 100
        if min_value > max_value:
            min_value, max_value = max_value, min_value
        return str(self._random.randint(min_value, max_value))

    def _generate_date(self, constraints: DataConstraints) -> str:
        return datetime.now().strftime('%Y-%m-%d')

    def _generate_datetime(self, constraints: DataConstraints) -> str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _generate_email(self, constraints: DataConstraints) -> str:
        username = ''.join(self._random.choices(string.ascii_lowercase + string.digits, k=8))
        return f'{username}@{self._random.choice(EMAIL_DOMAINS)}'

    def _generate_phone(self) -> str:
        suffix = ''.join(self._random.choices(string.digits, k=8))
        return f'{self._random.choice(PHONE_PREFIXES)}{suffix}'

    def _generate_enum(self, constraints: DataConstraints) -> str:
        if not constraints.enum_values:
            return ''
        return str(self._random.choice(constraints.enum_values))

    def _generate_boolean(self) -> str:
        return self._random.choice(['true', 'false'])

    def _generate_url(self, constraints: DataConstraints) -> str:
        slug = ''.join(self._random.choices(string.ascii_lowercase + string.digits, k=6))
        return f'https://example.com/{slug}'

    def _generate_id_card(self) -> str:
        return ''.join(self._random.choices(string.digits, k=18))

    def _generate_bank_card(self) -> str:
        length = self._random.randint(16, 19)
        return ''.join(self._random.choices(string.digits, k=length))

    def _generate_boundary_min(self, field_type: Any, constraints: DataConstraints) -> str:
        normalized_type = field_type.value if isinstance(field_type, DataType) else str(field_type)
        if normalized_type == DataType.TEXT.value:
            return '测' * (constraints.min_length or 1)
        if normalized_type == DataType.NUMBER.value:
            return str(constraints.min_value if constraints.min_value is not None else 0)
        return ''

    def _generate_boundary_max(self, field_type: Any, constraints: DataConstraints) -> str:
        normalized_type = field_type.value if isinstance(field_type, DataType) else str(field_type)
        if normalized_type == DataType.TEXT.value:
            return '测' * (constraints.max_length or max(constraints.min_length or 1, 10))
        if normalized_type == DataType.NUMBER.value:
            return str(constraints.max_value if constraints.max_value is not None else 100)
        return ''

    def _generate_boundary_over(self, field_type: Any, constraints: DataConstraints) -> str:
        normalized_type = field_type.value if isinstance(field_type, DataType) else str(field_type)
        if normalized_type == DataType.TEXT.value:
            overflow_length = (constraints.max_length or max(constraints.min_length or 1, 10)) + 1
            return '测' * overflow_length
        if normalized_type == DataType.NUMBER.value:
            if constraints.max_value is not None:
                return str(constraints.max_value + 1)
            if constraints.min_value is not None:
                return str(constraints.min_value - 1)
            return '101'
        return ''

    def _generate_special_chars(self, field_type: Any, constraints: DataConstraints) -> str:
        normalized_type = field_type.value if isinstance(field_type, DataType) else str(field_type)
        if normalized_type != DataType.TEXT.value:
            return ''
        chars = '!@#$%^&*()'
        return ''.join(self._random.choice(chars) for _ in range(6))

    def _apply_template(self, template: str, field_name: str) -> str:
        now = datetime.now()
        replacements = {
            '${field_name}': field_name,
            '${date}': now.strftime('%Y%m%d'),
            '${time}': now.strftime('%H%M%S'),
            '${random}': ''.join(self._random.choices(string.digits, k=4)),
        }
        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)
        return result

    def _random_chinese(self, length: int) -> str:
        return ''.join(self._random.choice(self.CHINESE_CHARS) for _ in range(max(length, 0)))

    def _generate_product_name(self) -> str:
        return f"产品线_{datetime.now().strftime('%Y%m%d')}_{''.join(self._random.choices(string.digits, k=4))}"

    def _generate_chinese_name(self) -> str:
        surnames = '赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨'
        given_length = self._random.choice([1, 2])
        return self._random.choice(surnames) + self._random_chinese(given_length)

    def _generate_description(self, constraints: DataConstraints) -> str:
        min_length = constraints.min_length or 10
        max_length = constraints.max_length or max(min_length, 20)
        base = '这是一个用于测试的数据描述'
        while len(base) < max_length:
            base += '，包含更多上下文信息'
        target_length = self._random.randint(min_length, max_length)
        return base[:target_length]

    def _generate_address(self) -> str:
        city = self._random.choice(['北京市', '上海市', '广州市', '深圳市', '杭州市'])
        road = self._random.choice(['科技路', '创新大道', '人民路', '解放路'])
        number = self._random.randint(1, 999)
        return f'{city}{road}{number}号'

    def _generate_company_name(self) -> str:
        prefix = self._random_chinese(self._random.choice([2, 3, 4]))
        return f'{prefix}科技有限公司'

    def get_cached_value(self, key: str, field_type: Any, field_name: str, **kwargs: Any) -> str:
        if key not in self._generated_values:
            self._generated_values[key] = self.generate_data(field_type, field_name, **kwargs)
        return self._generated_values[key]

    def reset_generated_values(self) -> None:
        self._generated_values.clear()
        if self._seed is not None:
            self._random = random.Random(self._seed)


def create_test_data_generator(seed: Optional[int] = None) -> TestDataGenerator:
    """Legacy factory preserved for compatibility."""

    return TestDataGenerator(seed=seed)


def generate_test_data(
    field_type: Any,
    field_name: str,
    generation_rule: GenerationRule = GenerationRule.RANDOM,
    constraints: Optional[DataConstraints] = None,
    rule_config: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    """Legacy convenience wrapper used by tests."""

    generator = TestDataGenerator(seed=kwargs.pop('seed', None))
    return generator.generate_data(
        field_type=field_type,
        field_name=field_name,
        generation_rule=generation_rule,
        constraints=constraints,
        rule_config=rule_config,
        **kwargs,
    )


__all__ = [
    'TestDataGenerator',
    'DataConstraints',
    'create_test_data_generator',
    'generate_test_data',
    'DATA_TYPE_STRING',
    'DATA_TYPE_NUMBER',
    'DATA_TYPE_EMAIL',
    'DATA_TYPE_PHONE',
    'DATA_TYPE_DATE',
    'DATA_TYPE_ENUM',
    'DATA_TYPE_BOOLEAN',
    'DATA_TYPE_CUSTOM',
]
