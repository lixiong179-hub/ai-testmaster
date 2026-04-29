"""
AI客户端主入口模块

本模块是AI服务的统一对外接口，采用Facade模式将分层设计的子模块聚合为一个简洁的API。
所有外部调用应通过本模块的 AIClient 类或 ai_client 单例进行，无需直接引用子模块。

分层设计概览：
    - ai_client_core:   基础层 — 异常体系、缓存机制、OpenAI客户端工厂
    - ai_client_parser: 解析层 — JSON修复、测试点提取、类型推断
    - ai_client_prompt: 提示层 — 权重模型构建、输入清洗、UI规格描述
    - ai_client_stream: 流式层 — SSE流式响应处理、进度推送
    - ai_client_test_case: 业务层 — 测试用例生成（由AITestCaseMixin提供）
    - ai_client_enhanced: 增强层 — 增强版用例生成、需求分析流式接口
    - ai_client_formatter: 格式化层 — 新旧格式归一化

核心类：
    - AIClient: 继承 AIStreamMixin + AITestCaseMixin + AIClientBase，对外暴露完整能力
    - ai_client: 全局单例，推荐直接使用

依赖关系：
    ai_client_core → ai_client_parser → ai_client_prompt → ai_client_stream
                  → ai_client_test_case → ai_client_enhanced → ai_client_formatter
"""
from app.utils.ai_client_core import (
    AIServiceError,
    AIAuthenticationError,
    AIRateLimitError,
    AIPermissionError,
    AINotFoundError,
    AITimeoutError,
    AIResponseParseError,
    AIResponseFormatError,
    _detect_ai_error,
    AIClientBase,
    get_ai_client,
)
from app.utils.ai_client_test_case import AITestCaseMixin
from app.utils.ai_client_stream import AIStreamMixin
from app.utils.ai_client_parser import (
    fix_common_json_issues,
    clean_json_string,
    extract_json_objects_fallback,
    parse_test_point_object,
    extract_value,
    infer_test_category,
    infer_action_type,
    extract_input_value_from_expected,
)
from app.utils.ai_client_formatter import (
    normalize_new_format,
    normalize_old_format,
)
from app.utils.ai_client_prompt import (
    build_weight_model,
    sanitize_input,
    build_ui_spec_description,
    build_ui_specs_description,
    build_project_env_info,
)
from app.utils.ai_client_enhanced import (
    generate_test_case_enhanced,
    generate_test_case,
    analyze_requirements_stream,
    generate_test_case_stream,
    parse_precondition_to_steps,
)


# 向后兼容别名：保留旧代码中以下划线前缀引用的入口
_normalize_new_format = normalize_new_format
_normalize_old_format = normalize_old_format
_build_weight_model = build_weight_model


class AIClient(AIStreamMixin, AITestCaseMixin, AIClientBase):
    """AI客户端统一入口类

    通过Mixin多重继承组合各层能力：
        - AIStreamMixin: 流式响应处理（需求分析流式、用例生成流式）
        - AITestCaseMixin: 测试用例生成业务逻辑
        - AIClientBase: 底层通信、缓存、异常处理

    使用方式：
        from app.utils.ai_client import ai_client
        result = await ai_client.analyze_requirements_stream(content)
    """
    pass


# 全局单例，整个应用共享同一客户端实例（含缓存）
ai_client = AIClient()


__all__ = [
    "AIServiceError",
    "AIAuthenticationError",
    "AIRateLimitError",
    "AIPermissionError",
    "AINotFoundError",
    "AITimeoutError",
    "AIResponseParseError",
    "AIResponseFormatError",
    "_detect_ai_error",
    "AIClient",
    "ai_client",
    "get_ai_client",
    "fix_common_json_issues",
    "clean_json_string",
    "extract_json_objects_fallback",
    "parse_test_point_object",
    "extract_value",
    "infer_test_category",
    "infer_action_type",
    "extract_input_value_from_expected",
    "normalize_new_format",
    "normalize_old_format",
    "_normalize_new_format",
    "_normalize_old_format",
    "build_weight_model",
    "_build_weight_model",
    "sanitize_input",
    "build_ui_spec_description",
    "build_ui_specs_description",
    "build_project_env_info",
    "generate_test_case_enhanced",
    "generate_test_case",
    "analyze_requirements_stream",
    "generate_test_case_stream",
    "parse_precondition_to_steps",
]
