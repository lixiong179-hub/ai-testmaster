"""测试数据生成Mixin - 实现各类数据类型的随机/边界/特殊值生成。
"""
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any
from loguru import logger
from app.models.test_data import DataType
from app.services.test_data_gen_constants import DataConstraints, CHINESE_CHARS, EMAIL_DOMAINS, PHONE_PREFIXES


class TestDataGenMixin:
    def _generate_random(
        self,
        field_type: DataType,
        field_name: str,
        constraints: DataConstraints,
        rule_config: Dict[str, Any]
    ) -> str:
        generators = {
            DataType.TEXT: lambda: self._generate_text(field_name, constraints, rule_config),
            DataType.NUMBER: lambda: self._generate_number(constraints),
            DataType.DATE: lambda: self._generate_date(constraints),
            DataType.DATETIME: lambda: self._generate_datetime(constraints),
            DataType.EMAIL: lambda: self._generate_email(constraints),
            DataType.PHONE: lambda: self._generate_phone(),
            DataType.ENUM: lambda: self._generate_enum(constraints),
            DataType.BOOLEAN: lambda: self._generate_boolean(),
            DataType.URL: lambda: self._generate_url(constraints),
            DataType.ID_CARD: lambda: self._generate_id_card(),
            DataType.BANK_CARD: lambda: self._generate_bank_card(),
        }
        generator = generators.get(field_type)
        if generator:
            return generator()
        logger.warning(f"未知的字段类型: {field_type}")
        return ""

    def _generate_text(self, field_name: str, constraints: DataConstraints, rule_config: Dict[str, Any]) -> str:
        template = rule_config.get("template")
        if template:
            return self._apply_template(template, field_name)
        if "产品线" in field_name or "产品" in field_name:
            return self._generate_product_name()
        elif "名称" in field_name or "名字" in field_name:
            return self._generate_chinese_name()
        elif "描述" in field_name or "说明" in field_name:
            return self._generate_description(constraints)
        elif "地址" in field_name:
            return self._generate_address()
        elif "公司" in field_name:
            return self._generate_company_name()
        else:
            min_len = constraints.min_length or 5
            max_len = constraints.max_length or 20
            length = random.randint(min_len, max_len)
            return self._random_chinese(length)

    def _generate_product_name(self) -> str:
        date_str = datetime.now().strftime("%Y%m%d")
        random_num = random.randint(100, 999)
        return f"产品线_{date_str}_{random_num}"

    def _generate_chinese_name(self) -> str:
        surnames = ["张", "王", "李", "刘", "陈", "杨", "黄", "赵", "周", "吴", "徐", "孙", "马", "朱", "胡", "郭", "何", "林", "罗", "高"]
        names = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "勇", "艳", "杰", "娟", "涛", "明", "超", "秀英", "华", "鹏"]
        return random.choice(surnames) + random.choice(names)

    def _generate_description(self, constraints: DataConstraints) -> str:
        min_len = constraints.min_length or 10
        max_len = constraints.max_length or 50
        length = random.randint(min_len, max_len)
        return self._random_chinese(length)

    def _generate_address(self) -> str:
        provinces = ["北京", "上海", "广东", "浙江", "江苏", "山东", "河南", "四川", "湖北", "湖南"]
        cities = ["市", "县", "区"]
        streets = ["街道", "路", "街", "大道"]
        addr = random.choice(provinces)
        addr += random.choice(cities)
        addr += self._random_chinese(3)
        addr += random.choice(streets)
        addr += str(random.randint(1, 999)) + "号"
        return addr

    def _generate_company_name(self) -> str:
        prefixes = ["北京", "上海", "深圳", "杭州", "广州", "成都"]
        names = ["科技", "信息", "网络", "软件", "智能", "创新", "未来", "互联"]
        suffixes = ["有限公司", "科技有限公司", "信息有限公司", "网络有限公司"]
        return random.choice(prefixes) + self._random_chinese(2) + random.choice(names) + random.choice(suffixes)

    def _generate_number(self, constraints: DataConstraints) -> str:
        min_val = constraints.min_value or 0
        max_val = constraints.max_value or 100
        return str(random.randint(min_val, max_val))

    def _generate_date(self, constraints: DataConstraints) -> str:
        days_offset = random.randint(-365, 365)
        date = datetime.now() + timedelta(days=days_offset)
        return date.strftime("%Y-%m-%d")

    def _generate_datetime(self, constraints: DataConstraints) -> str:
        days_offset = random.randint(-365, 365)
        hours_offset = random.randint(0, 23)
        minutes_offset = random.randint(0, 59)
        dt = datetime.now() + timedelta(days=days_offset, hours=hours_offset, minutes=minutes_offset)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _generate_email(self, constraints: DataConstraints) -> str:
        username_length = random.randint(6, 12)
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=username_length))
        domain = random.choice(EMAIL_DOMAINS)
        return f"{username}@{domain}"

    def _generate_phone(self) -> str:
        prefix = random.choice(PHONE_PREFIXES)
        suffix = ''.join(random.choices(string.digits, k=8))
        return prefix + suffix

    def _generate_enum(self, constraints: DataConstraints) -> str:
        if constraints.enum_values:
            return random.choice(constraints.enum_values)
        return ""

    def _generate_boolean(self) -> str:
        return str(random.choice([True, False])).lower()

    def _generate_url(self, constraints: DataConstraints) -> str:
        protocols = ["http", "https"]
        domains = ["example.com", "test.com", "demo.com"]
        paths = ["", "/path", "/api/v1", "/test/page"]
        protocol = random.choice(protocols)
        domain = random.choice(domains)
        path = random.choice(paths)
        return f"{protocol}://www.{domain}{path}"

    def _generate_id_card(self) -> str:
        area_code = random.choice(["110101", "310101", "440106", "500101", "510107"])
        birth_date = (datetime.now() - timedelta(days=random.randint(365*18, 365*60))).strftime("%Y%m%d")
        sequence = ''.join(random.choices(string.digits, k=3))
        check_code = random.choice(string.digits + "X")
        return area_code + birth_date + sequence + check_code

    def _generate_bank_card(self) -> str:
        prefixes = ["622202", "622848", "621700", "623668"]
        prefix = random.choice(prefixes)
        suffix_length = random.choice([10, 13])
        suffix = ''.join(random.choices(string.digits, k=suffix_length))
        return prefix + suffix

    def _generate_boundary_min(self, field_type: DataType, constraints: DataConstraints) -> str:
        if field_type == DataType.TEXT:
            min_len = constraints.min_length or 1
            return "测" * min_len
        elif field_type == DataType.NUMBER:
            min_val = constraints.min_value or 0
            return str(min_val)
        return ""

    def _generate_boundary_max(self, field_type: DataType, constraints: DataConstraints) -> str:
        if field_type == DataType.TEXT:
            max_len = constraints.max_length or 50
            return "测" * max_len
        elif field_type == DataType.NUMBER:
            max_val = constraints.max_value or 100
            return str(max_val)
        return ""

    def _generate_boundary_over(self, field_type: DataType, constraints: DataConstraints) -> str:
        if field_type == DataType.TEXT:
            max_len = constraints.max_length or 50
            return "测" * (max_len + 1)
        elif field_type == DataType.NUMBER:
            max_val = constraints.max_value or 100
            return str(max_val + 1)
        return ""

    def _generate_special_chars(self, field_type: DataType, constraints: DataConstraints) -> str:
        if field_type != DataType.TEXT:
            return ""
        special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        length = random.randint(5, 20)
        return ''.join(random.choices(special_chars, k=length))

    def _random_chinese(self, length: int) -> str:
        return ''.join(random.choices(CHINESE_CHARS, k=length))

    def _apply_template(self, template: str, field_name: str) -> str:
        now = datetime.now()
        result = template
        result = result.replace("${date}", now.strftime("%Y%m%d"))
        result = result.replace("${time}", now.strftime("%H%M%S"))
        result = result.replace("${random}", str(random.randint(100, 999)))
        result = result.replace("${field_name}", field_name)
        return result
