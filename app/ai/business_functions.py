"""
AI 业务函数统一入口模块

本模块是 AI 业务函数的新统一入口，提供测试用例生成、需求分析、前置条件解析等
业务能力的导出。外部调用方应统一通过本模块导入业务函数：

    from app.ai.business_functions import generate_test_case_enhanced

设计说明：
    - 业务函数的实际定义仍位于 app/utils/ai_client_enhanced 等子模块中，
      本模块负责聚合导出，为调用方提供稳定的 app.ai 命名空间导入路径。
    - OpenAIClient（app.ai.openai_client.OpenAIClient）已内置 LRU 缓存能力，
      业务函数内部通过 get_ai_client / OpenAIClient 与模型交互。
    - 异常体系（AIServiceError 等）从 app.ai.exceptions 重导出，
      便于调用方在统一命名空间下捕获 AI 异常。
    - 过渡期 app/utils/ai_client.py 从本模块重导出，保持向后兼容。

依赖关系：
    - app.ai.exceptions : 异常体系
    - app.ai.base : AIClientBase、客户端工厂
    - app.utils.ai_client_enhanced : 业务函数实现
    - app.utils.ai_client_parser : JSON 解析工具
    - app.utils.ai_client_formatter : 格式归一化
    - app.utils.ai_client_prompt : 提示词构建
"""
from app.ai.exceptions import (
    AIServiceError,
    AIAuthenticationError,
    AIRateLimitError,
    AIPermissionError,
    AINotFoundError,
    AITimeoutError,
    AIResponseParseError,
    AIResponseFormatError,
    _detect_ai_error,
)
from app.ai.base import AIClientBase, get_ai_client
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
    """AI 客户端统一入口类（兼容旧版 AIClient）

    通过 Mixin 多重继承组合各层能力：
        - AIStreamMixin: 流式响应处理
        - AITestCaseMixin: 测试用例生成业务逻辑
        - AIClientBase: 底层通信、缓存、异常处理
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
