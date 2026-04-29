"""
测试数据生成器服务

提供多种类型的测试数据生成功能
支持随机数据、边界值数据、参数化数据
"""
import random
import string
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
from loguru import logger

from app.models.test_data import DataType, GenerationRule


@dataclass
class DataConstraints:
    """数据约束条件"""
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    enum_values: Optional[List[str]] = None
    pattern: Optional[str] = None


class TestDataGenerator:
    """
    测试数据生成器

    支持生成以下类型的测试数据：
    - 文本(text)
    - 数字(number)
    - 日期(date)
    - 日期时间(datetime)
    - 邮箱(email)
    - 手机号(phone)
    - 枚举(enum)
    - 布尔值(boolean)
    - URL(url)
    - 身份证号(id_card)
    - 银行卡号(bank_card)
    """

    # 常用中文字符集
    CHINESE_CHARS = "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取完举色或"

    # 常用邮箱域名
    EMAIL_DOMAINS = ["example.com", "test.com", "demo.com", "mail.com", "email.com"]

    # 手机号段
    PHONE_PREFIXES = ["138", "139", "137", "136", "135", "134", "159", "158", "157", "150", "151", "152", "188", "187", "182", "183", "184", "178", "130", "131", "132", "156", "155", "186", "185", "176", "133", "153", "189", "180", "181", "177"]

    def __init__(self, seed: Optional[int] = None):
        """
        初始化测试数据生成器

        Args:
            seed: 随机数种子，用于生成可重现的测试数据
        """
        self._generated_values: Dict[str, Any] = {}  # 用于保持同一次执行中参数值一致
        self._seed = seed
        if seed is not None:
            random.seed(seed)

    def generate_data(
        self,
        field_type: DataType,
        field_name: str,
        generation_rule: GenerationRule = GenerationRule.RANDOM,
        constraints: Optional[DataConstraints] = None,
        rule_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成测试数据

        Args:
            field_type: 字段类型
            field_name: 字段名称
            generation_rule: 生成规则
            constraints: 约束条件
            rule_config: 规则配置

        Returns:
            生成的数据值
        """
        constraints = constraints or DataConstraints()
        rule_config = rule_config or {}

        try:
            # 根据生成规则选择生成方法
            if generation_rule == GenerationRule.BOUNDARY_MIN:
                return self._generate_boundary_min(field_type, constraints)
            elif generation_rule == GenerationRule.BOUNDARY_MAX:
                return self._generate_boundary_max(field_type, constraints)
            elif generation_rule == GenerationRule.BOUNDARY_OVER:
                return self._generate_boundary_over(field_type, constraints)
            elif generation_rule == GenerationRule.SPECIAL_CHARS:
                return self._generate_special_chars(field_type, constraints)
            elif generation_rule == GenerationRule.EMPTY:
                return ""
            elif generation_rule == GenerationRule.CUSTOM:
                return rule_config.get("custom_value", "")
            else:  # RANDOM
                return self._generate_random(field_type, field_name, constraints, rule_config)

        except Exception as e:
            logger.error(f"生成测试数据失败: field_type={field_type}, field_name={field_name}, error={e}")
            return ""

    def _generate_random(
        self,
        field_type: DataType,
        field_name: str,
        constraints: DataConstraints,
        rule_config: Dict[str, Any]
    ) -> str:
        """生成随机数据"""
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
        else:
            logger.warning(f"未知的字段类型: {field_type}")
            return ""

    def _generate_text(self, field_name: str, constraints: DataConstraints, rule_config: Dict[str, Any]) -> str:
        """生成文本数据"""
        # 检查是否有特定的生成模板
        template = rule_config.get("template")
        if template:
            return self._apply_template(template, field_name)

        # 根据字段名称智能生成
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
            # 通用文本
            min_len = constraints.min_length or 5
            max_len = constraints.max_length or 20
            length = random.randint(min_len, max_len)
            return self._random_chinese(length)

    def _generate_product_name(self) -> str:
        """生成产品线名称"""
        date_str = datetime.now().strftime("%Y%m%d")
        random_num = random.randint(100, 999)
        return f"产品线_{date_str}_{random_num}"

    def _generate_chinese_name(self) -> str:
        """生成中文姓名"""
        surnames = ["张", "王", "李", "刘", "陈", "杨", "黄", "赵", "周", "吴", "徐", "孙", "马", "朱", "胡", "郭", "何", "林", "罗", "高"]
        names = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "勇", "艳", "杰", "娟", "涛", "明", "超", "秀英", "华", "鹏"]
        return random.choice(surnames) + random.choice(names)

    def _generate_description(self, constraints: DataConstraints) -> str:
        """生成描述文本"""
        min_len = constraints.min_length or 10
        max_len = constraints.max_length or 50
        length = random.randint(min_len, max_len)
        return self._random_chinese(length)

    def _generate_address(self) -> str:
        """生成地址"""
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
        """生成公司名称"""
        prefixes = ["北京", "上海", "深圳", "杭州", "广州", "成都"]
        names = ["科技", "信息", "网络", "软件", "智能", "创新", "未来", "互联"]
        suffixes = ["有限公司", "科技有限公司", "信息有限公司", "网络有限公司"]

        return random.choice(prefixes) + self._random_chinese(2) + random.choice(names) + random.choice(suffixes)

    def _generate_number(self, constraints: DataConstraints) -> str:
        """生成数字"""
        min_val = constraints.min_value or 0
        max_val = constraints.max_value or 100
        return str(random.randint(min_val, max_val))

    def _generate_date(self, constraints: DataConstraints) -> str:
        """生成日期"""
        days_offset = random.randint(-365, 365)
        date = datetime.now() + timedelta(days=days_offset)
        return date.strftime("%Y-%m-%d")

    def _generate_datetime(self, constraints: DataConstraints) -> str:
        """生成日期时间"""
        days_offset = random.randint(-365, 365)
        hours_offset = random.randint(0, 23)
        minutes_offset = random.randint(0, 59)
        dt = datetime.now() + timedelta(days=days_offset, hours=hours_offset, minutes=minutes_offset)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _generate_email(self, constraints: DataConstraints) -> str:
        """生成邮箱"""
        username_length = random.randint(6, 12)
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=username_length))
        domain = random.choice(self.EMAIL_DOMAINS)
        return f"{username}@{domain}"

    def _generate_phone(self) -> str:
        """生成手机号"""
        prefix = random.choice(self.PHONE_PREFIXES)
        suffix = ''.join(random.choices(string.digits, k=8))
        return prefix + suffix

    def _generate_enum(self, constraints: DataConstraints) -> str:
        """生成枚举值"""
        if constraints.enum_values:
            return random.choice(constraints.enum_values)
        return ""

    def _generate_boolean(self) -> str:
        """生成布尔值"""
        return str(random.choice([True, False])).lower()

    def _generate_url(self, constraints: DataConstraints) -> str:
        """生成URL"""
        protocols = ["http", "https"]
        domains = ["example.com", "test.com", "demo.com"]
        paths = ["", "/path", "/api/v1", "/test/page"]

        protocol = random.choice(protocols)
        domain = random.choice(domains)
        path = random.choice(paths)

        return f"{protocol}://www.{domain}{path}"

    def _generate_id_card(self) -> str:
        """生成身份证号（简化版，校验码可能不正确）"""
        # 简化的身份证号生成
        area_code = random.choice(["110101", "310101", "440106", "500101", "510107"])
        birth_date = (datetime.now() - timedelta(days=random.randint(365*18, 365*60))).strftime("%Y%m%d")
        sequence = ''.join(random.choices(string.digits, k=3))
        # 简化校验码计算（仅用于测试，非真实校验）
        check_code = random.choice(string.digits + "X")
        return area_code + birth_date + sequence + check_code

    def _generate_bank_card(self) -> str:
        """生成银行卡号"""
        # 简化的银行卡号生成（16-19位）
        prefixes = ["622202", "622848", "621700", "623668"]
        prefix = random.choice(prefixes)
        suffix_length = random.choice([10, 13])
        suffix = ''.join(random.choices(string.digits, k=suffix_length))
        return prefix + suffix

    def _generate_boundary_min(self, field_type: DataType, constraints: DataConstraints) -> str:
        """生成边界值-最小"""
        if field_type == DataType.TEXT:
            min_len = constraints.min_length or 1
            return "测" * min_len  # 使用中文字符
        elif field_type == DataType.NUMBER:
            min_val = constraints.min_value or 0
            return str(min_val)
        else:
            return ""

    def _generate_boundary_max(self, field_type: DataType, constraints: DataConstraints) -> str:
        """生成边界值-最大"""
        if field_type == DataType.TEXT:
            max_len = constraints.max_length or 50
            return "测" * max_len  # 使用中文字符
        elif field_type == DataType.NUMBER:
            max_val = constraints.max_value or 100
            return str(max_val)
        else:
            return ""

    def _generate_boundary_over(self, field_type: DataType, constraints: DataConstraints) -> str:
        """生成边界值-超长"""
        if field_type == DataType.TEXT:
            max_len = constraints.max_length or 50
            return "测" * (max_len + 1)  # 使用中文字符
        elif field_type == DataType.NUMBER:
            max_val = constraints.max_value or 100
            return str(max_val + 1)
        else:
            return ""

    def _generate_special_chars(self, field_type: DataType, constraints: DataConstraints) -> str:
        """生成特殊字符（仅适用于文本类型）"""
        if field_type != DataType.TEXT:
            # 非文本类型返回空值
            return ""
        special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        length = random.randint(5, 20)
        return ''.join(random.choices(special_chars, k=length))

    def _random_chinese(self, length: int) -> str:
        """生成随机中文字符串"""
        return ''.join(random.choices(self.CHINESE_CHARS, k=length))

    def _apply_template(self, template: str, field_name: str) -> str:
        """应用模板生成数据"""
        # 替换模板变量
        now = datetime.now()
        result = template
        result = result.replace("${date}", now.strftime("%Y%m%d"))
        result = result.replace("${time}", now.strftime("%H%M%S"))
        result = result.replace("${random}", str(random.randint(100, 999)))
        result = result.replace("${field_name}", field_name)
        return result

    def get_cached_value(self, param_key: str, field_type: DataType, field_name: str) -> str:
        """
        获取缓存的参数值（同一次执行中保持一致）

        Args:
            param_key: 参数键（如 "product_name"）
            field_type: 字段类型
            field_name: 字段名称

        Returns:
            缓存的值（如果不存在则生成并缓存）
        """
        if param_key not in self._generated_values:
            # 生成新值并缓存
            self._generated_values[param_key] = self.generate_data(
                field_type=field_type,
                field_name=field_name,
                generation_rule=GenerationRule.RANDOM
            )
        return self._generated_values[param_key]

    def reset_generated_values(self):
        """重置已生成的值（用于新的测试执行）"""
        self._generated_values.clear()
        # 如果有种子，重新设置以保持可重现性
        if self._seed is not None:
            random.seed(self._seed)


# 便捷函数
def generate_test_data(
    field_type: DataType,
    field_name: str,
    generation_rule: GenerationRule = GenerationRule.RANDOM,
    **kwargs
) -> str:
    """
    生成测试数据的便捷函数

    Args:
        field_type: 字段类型
        field_name: 字段名称
        generation_rule: 生成规则
        **kwargs: 其他参数

    Returns:
        生成的数据值
    """
    generator = TestDataGenerator()
    return generator.generate_data(field_type, field_name, generation_rule)
