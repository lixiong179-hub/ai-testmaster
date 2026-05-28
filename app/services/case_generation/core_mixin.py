"""用例生成核心Mixin - 内容安全处理与便捷函数。

本模块提供用例生成的核心基础设施，包括内容安全清洗和常量定义。
作为CoreMixin被TestCaseGenerationService组合使用。

核心类:
    - ContentSanitizer: 内容安全清洗工具，防止Prompt注入攻击
    - CoreMixin: 核心Mixin，继承ContextMixin的上下文构建能力

常量定义:
    - DEFAULT_TEST_POINT_PAGE_SIZE: 测试点默认分页大小(100)
    - MAX_TEST_POINT_PAGE_SIZE: 测试点最大分页大小(500)
    - TEST_CATEGORY_UI_AUTO: UI自动化测试分类标识
    - TEST_CATEGORY_MANUAL: 手工测试分类标识
    - TEST_CATEGORY_API_AUTO: API自动化测试分类标识

依赖关系:
    - app.services.case_generation.context_mixin: ContextMixin上下文构建
"""
import re
import html
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.services.case_generation.context_mixin import (
    ContextMixin,
    DEFAULT_TEST_POINT_PAGE_SIZE,
)

# 用例分类常量，用于标识用例的执行方式
TEST_CATEGORY_UI_AUTO = "ui_automation"
TEST_CATEGORY_MANUAL = "manual"
TEST_CATEGORY_API_AUTO = "api_automation"


class ContentSanitizer:
    """内容安全清洗工具 - 防止Prompt注入攻击与内容截断。

    职责:
        - 过滤AI Prompt注入模式（system指令、模板注入等）
        - 移除Markdown代码块标记和HTML标签
        - 对内容进行HTML转义
        - 截断过长内容防止Token溢出
        - 日志友好的内容摘要

    安全设计:
        采用多层过滤策略：
        1. 移除代码块标记（防止AI误解析为指令）
        2. 移除HTML标签（防止XSS注入到Prompt）
        3. HTML转义特殊字符
        4. 正则匹配已知注入模式并替换为[已过滤]
        5. 长度截断并标注原始长度

    使用场景:
        - 清洗用户输入的需求文档内容
        - 清洗UI描述文本
        - 生成日志友好的内容摘要
    """

    # 已知的Prompt注入模式列表
    INJECTION_PATTERNS = [
        r'```system', r'```prompt', r'忽略.*指令', r'忽略.*规则',
        r'你是一个.*而不是', r'你现在是', r'/system', r'<system>', r'{{.*}}',
    ]

    @classmethod
    def sanitize(cls, content: str, max_length: int = 10000) -> str:
        """清洗内容，防止Prompt注入并截断过长文本。

        清洗流程:
            1. 移除代码块标记（json/yaml/xml/markdown/prompt/system）
            2. 移除剩余代码块标记
            3. 移除HTML标签
            4. HTML转义特殊字符
            5. 过滤已知注入模式
            6. 截断过长内容

        Args:
            content: 待清洗的原始内容。
            max_length: 最大允许长度，默认10000字符。

        Returns:
            清洗后的安全内容字符串。
        """
        if not content:
            return ""
        # 移除代码块标记，防止AI误解析为指令
        content = re.sub(r'```(?:json|yaml|xml|markdown|prompt|system)', '', content, flags=re.IGNORECASE)
        content = re.sub(r'```', '', content)
        # 移除HTML标签，防止XSS注入
        content = re.sub(r'<[^>]+>', '', content)
        # HTML转义特殊字符
        content = html.escape(content)
        # 过滤已知的Prompt注入模式
        for pattern in cls.INJECTION_PATTERNS:
            content = re.sub(pattern, '[已过滤]', content, flags=re.IGNORECASE)
        # 截断过长内容，防止Token溢出
        if len(content) > max_length:
            content = content[:max_length] + f"\n\n[内容已截断，原长度: {len(content)}字符]"
        return content

    @classmethod
    def sanitize_for_log(cls, content: str, max_length: int = 200) -> str:
        """生成日志友好的内容摘要，压缩空白并截断。

        Args:
            content: 原始内容。
            max_length: 摘要最大长度，默认200字符。

        Returns:
            压缩空白后的截断内容。
        """
        if not content:
            return ""
        # 压缩换行和制表符为空格，适合单行日志输出
        content = re.sub(r'[\n\r\t]+', ' ', content)
        if len(content) > max_length:
            return content[:max_length] + "..."
        return content


class CoreMixin(ContextMixin):
    """用例生成核心Mixin - 聚合需求文档、UI原型和测试点数据。

    职责:
        - 继承ContextMixin的上下文构建能力
        - 提供内容安全清洗工具（ContentSanitizer）
        - 定义用例分类常量

    设计意图:
        作为TestCaseGenerationService的核心Mixin，组合上下文构建、
        安全清洗和常量定义能力。

    使用场景:
        被TestCaseGenerationService通过多继承组合，
        在生成流程中提供完整的上下文和安全处理能力。
    """
    pass


async def get_test_case_context(
    db: Session,
    project_id: int,
    user_id: int,
    requirement_file_ids: Optional[List[int]] = None,
    ui_file_ids: Optional[List[int]] = None,
    ui_screen_ids: Optional[List[int]] = None,
    test_point_ids: Optional[List[int]] = None,
    test_point_page: int = 1,
    test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE
) -> Dict[str, Any]:
    """便捷函数 - 获取用例生成上下文，无需手动创建服务实例。

    内部创建TestCaseGenerationService实例并调用get_context_for_generation，
    适用于只需获取上下文而不执行生成的场景。

    Args:
        db: 数据库会话。
        project_id: 项目ID。
        user_id: 用户ID。
        requirement_file_ids: 需求文件ID列表，可选。
        ui_file_ids: UI文件ID列表，可选。
        ui_screen_ids: UI屏幕ID列表，可选。
        test_point_ids: 测试点ID列表，可选。
        test_point_page: 测试点分页页码，默认1。
        test_point_page_size: 测试点分页大小，默认100。

    Returns:
        上下文字典，结构同ContextMixin.get_context_for_generation。
    """
    from app.services.test_case_generation import TestCaseGenerationService
    service = TestCaseGenerationService(db)
    return await service.get_context_for_generation(
        project_id=project_id, user_id=user_id,
        requirement_file_ids=requirement_file_ids, ui_file_ids=ui_file_ids,
        ui_screen_ids=ui_screen_ids, test_point_ids=test_point_ids,
        test_point_page=test_point_page, test_point_page_size=test_point_page_size
    )
