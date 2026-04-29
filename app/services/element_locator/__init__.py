"""元素定位子包 - 通过Mixin组合模式实现智能元素定位能力。

本子包是元素定位服务的核心实现，ElementLocatorService通过多继承
组合各功能Mixin，实现CSS/XPath选择器生成、AI视觉识别、
智能定位策略等功能。

核心类:
    - ElementLocatorService: 元素定位服务主类

Mixin组合:
    - SmartLocateMixin: 智能定位（AI+规则混合策略）
    - SelectorGenerationMixin: 选择器生成（CSS/XPath）
    - LocatorRecordMixin: 定位结果记录与更新
    - LocatorQueryMixin: 定位信息查询

定位策略优先级:
    1. CSS选择器（精确、快速）
    2. XPath（灵活、兼容性好）
    3. AI视觉识别（兜底、通用性强）
"""
from app.services.element_locator.locator_query_mixin import LocatorQueryMixin
from app.services.element_locator.locator_record_mixin import LocatorRecordMixin
from app.services.element_locator.selector_generation_mixin import SelectorGenerationMixin
from app.services.element_locator.smart_locate_mixin import SmartLocateMixin
from sqlalchemy.orm import Session


class ElementLocatorService(
    SmartLocateMixin,
    SelectorGenerationMixin,
    LocatorRecordMixin,
    LocatorQueryMixin,
):
    """元素定位服务 - 组合智能定位、选择器生成、记录和查询能力。

    继承顺序（MRO）:
        SmartLocateMixin -> SelectorGenerationMixin
        -> LocatorRecordMixin -> LocatorQueryMixin

    使用场景:
        - 测试步骤执行时定位页面元素
        - 批量定位测试用例的所有步骤
        - 生成CSS/XPath选择器
        - AI视觉识别元素位置
    """

    def __init__(self, db: Session):
        """初始化元素定位服务。

        Args:
            db: 数据库会话，贯穿定位操作生命周期。
        """
        self.db = db


__all__ = [
    'ElementLocatorService',
    'LocatorQueryMixin',
    'LocatorRecordMixin',
    'SelectorGenerationMixin',
    'SmartLocateMixin',
]
