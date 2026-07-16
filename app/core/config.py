"""全局配置模块 - 多环境配置支持（dev/test/prod）

本模块是AI测试平台的配置中心，负责管理所有运行时参数。
密钥管理逻辑已拆分至 app.core.key_management，
环境配置类已拆分至 app.core.settings_profiles。
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional, List, Union
import os
import logging
import json
from pathlib import Path
from app.utils.file_utils import SUPPORTED_FILE_TYPES

_logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def parse_list(value: Union[str, List]) -> List[str]:
    """将配置值统一解析为字符串列表，支持JSON数组和逗号分隔格式。"""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [item.strip() for item in value.split(",") if item.strip()]
    return []


class Settings(BaseSettings):
    """全局配置基类，定义所有运行时参数。

    配置项可通过以下方式设置（优先级从高到低）：
    1. 环境变量（最高优先级）
    2. .env文件
    3. 类属性默认值（兜底）
    """

    APP_NAME: str = "AI测试平台"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "dev"

    DATABASE_URL: str = ""
    DATABASE_URL_SLAVE: Optional[str] = None
    # 兼容旧配置：DB_POOL_SIZE/DB_MAX_OVERFLOW 仍生效，作为 async 引擎默认值
    DB_POOL_SIZE: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_MAX_OVERFLOW: int = 10
    # 性能优化：同步引擎实际负载低（仅遗留端点与 CLI 使用），独立下调避免连接池翻倍
    DB_SYNC_POOL_SIZE: int = 5
    DB_SYNC_MAX_OVERFLOW: int = 5
    # 异步引擎为 ASGI 主路径，显式配置便于调优
    DB_ASYNC_POOL_SIZE: int = 20
    DB_ASYNC_MAX_OVERFLOW: int = 10

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50

    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    # 安全收紧：access token 60 分钟过期，配合 refresh_token（7 天）实现无感续期。
    # 原值 480 分钟（8 小时）泄露窗口过大，违反最小权限原则。
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ENCRYPTION_KEY: str = ""
    ENCRYPTION_SALT: str = ""

    ADMIN_INITIAL_PASSWORD: str = ""
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    UI_PROTOTYPE_UPLOAD_DIR: str = str(BASE_DIR / "uploads" / "ui_prototypes")
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024
    ALLOWED_EXTENSIONS: str = ",".join(SUPPORTED_FILE_TYPES.keys())

    MAX_ZIP_ENTRIES: int = 200
    MAX_ZIP_TOTAL_SIZE: int = 500 * 1024 * 1024

    SUPPORTED_IMAGE_EXTENSIONS: list = ["png", "jpg", "jpeg", "gif", "webp", "bmp"]

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    DEEPSEEK_MAX_TOKENS: int = 2048
    DEEPSEEK_TEMPERATURE: float = 0.3

    AI_MODEL_NAME: str = "deepseek-v4-flash"
    AI_FALLBACK_MODEL_NAME: str = "deepseek-v4-flash"
    AI_API_KEY: str = ""
    AI_BASE_URL: str = "https://api.deepseek.com"
    AI_TOKEN_BUDGET_PER_RUN: int = 100000
    AI_TEMPERATURE: float = 0.3
    AI_MAX_TOKENS: int = 2048
    AI_MAX_RETRIES: int = 3
    AI_CASE_GENERATION_CONCURRENCY: int = 3
    AI_CASE_GENERATION_MAX_TOKENS: int = 4096
    AI_CASE_GENERATION_MAX_TOKENS_FULL: int = 8192
    # 性能优化：单次 AI 调用硬超时，避免 75s+ 长尾阻塞 worker
    AI_CALL_TIMEOUT_SECONDS: int = 30
    # 质量反馈循环最大重生成轮数：推理模型下每轮 25-55s，3 轮可能 200s+，收敛到 1 轮
    AI_QUALITY_FEEDBACK_MAX_ROUNDS: int = 1
    UI_PARSE_CONCURRENCY: int = 3
    PIPELINE_PAUSE_TIMEOUT_DAYS: int = 7

    LIFECYCLE_DEPRECATE_COOLDOWN_HOURS: int = 24
    ARCHIVE_RETENTION_DAYS: int = 180
    CLEANUP_AUDIT_LOG_DAYS: int = 365
    BACKUP_DIR: str = "/tmp/ai-testmaster-backup"
    AUTO_APPROVE_MIN_GRADE: str = "A"

    POSTERIOR_MIN_EXECUTIONS: int = 3
    POSTERIOR_REVIEW_WEIGHT: float = 0.5
    POSTERIOR_EXECUTION_WEIGHT: float = 0.3
    POSTERIOR_MODIFICATION_WEIGHT: float = 0.2
    POSTERIOR_COMPUTE_BATCH_SIZE: int = 200

    XMIND_AI_TIMEOUT: int = 90
    XMIND_AI_MAX_WORKERS: int = 4
    XMIND_AI_BATCH_SIZE: int = 10
    XMIND_AI_MAX_TOKENS: int = 8192
    XMIND_AI_PREVIEW_SAMPLE: int = 10

    @field_validator(
        "XMIND_AI_TIMEOUT", "XMIND_AI_MAX_WORKERS",
        "XMIND_AI_BATCH_SIZE", "XMIND_AI_MAX_TOKENS",
        "XMIND_AI_PREVIEW_SAMPLE",
    )
    @classmethod
    def _xmind_ai_positive(cls, v: int, info) -> int:
        if v <= 0:
            raise ValueError(f"{info.field_name} must be positive, got {v}")
        return v

    VISION_MODEL_DEFAULT: str = "qwen"
    VISION_MAX_TOKENS: int = 4096
    UI_PARSER_MODE: str = "text"

    KIMI_API_KEY: str = ""
    KIMI_MODEL: str = "moonshot-v1-128k-vision-preview"

    QWEN_API_KEY: str = ""
    QWEN_MODEL: str = "qwen3-vl-235b-a22b-thinking"

    PARSE_MODE_TEXT: str = "text"
    PARSE_MODE_VISION: str = "vision"

    ZHIPU_API_KEY: str = ""
    ZHIPU_MODEL: str = "glm-4v-plus"

    BAIDU_API_KEY: str = ""
    BAIDU_MODEL: str = "ernie-bot-4"

    DOUBAO_API_KEY: str = ""
    DOUBAO_MODEL: str = "doubao-vision-pro-32k"

    MIMO_API_KEY: str = ""
    MIMO_MODEL: str = "mimo-v2.5"
    MIMO_BASE_URL: str = "https://token-plan-cn.xiaomimimo.com/v1"

    TEXT_MODEL_DEFAULT: str = "deepseek"
    TEXT_MODEL_API_KEY: str = ""
    TEXT_MODEL_API_URL: str = "https://api.deepseek.com"
    TEXT_MODEL_NAME: str = "deepseek-v4-flash"

    AI_SELF_HEALING_ENABLED: bool = False
    AI_SELF_HEALING_MAX_RETRIES: int = 1
    STAGEHAND_MODEL: str = "gpt-4o"
    BROWSERBASE_API_KEY: str = ""
    BROWSERBASE_PROJECT_ID: str = ""

    PLAYWRIGHT_MCP_ENABLED: bool = True
    PLAYWRIGHT_MCP_SERVER_PORT: int = 3000
    MCP_TEXT_LLM_MODEL: str = "deepseek-v4-flash"

    MCP_DIRECT_EXECUTION_ENABLED: bool = False
    MCP_EXECUTION_OPERATION_TYPES: str = "click,type,hover,select"
    AUTO_PARSE_PRECONDITION: bool = True

    # 网址驱动快速测试：站点探索 BFS 深度上限，避免爬取过深拖慢首份报告
    URL_QUICK_TEST_MAX_DEPTH: int = 3
    # 单页加载超时（秒），超时跳过该页不阻断整体探索
    URL_QUICK_TEST_PAGE_TIMEOUT: int = 30
    # SiteMap Redis 缓存 TTL（秒），默认 1 天避免重复爬取同源站点
    URL_QUICK_TEST_CACHE_TTL: int = 86400
    # 危险路径黑名单，命中即跳过避免触发登出/删除等破坏性操作
    URL_QUICK_TEST_BLACKLIST: list = ["/logout", "/delete", "/reset"]
    # 用例生成 AI 调用 max_tokens：DeepSeek v4-flash 等推理模型先消耗 reasoning_tokens
    # 再产出 content，2048 不足以同时容纳推理与用例 JSON 输出（spec BUG 2 根因）。
    # 与 AI_MAX_TOKENS 全局默认解耦，独立调整不影响其他 AI 路径。
    URL_QUICK_TEST_AI_MAX_TOKENS: int = 4096

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,DELETE,OPTIONS"
    # 安全收紧：显式允许的请求头白名单，禁止 "*" 通配符以缩小 CSRF/请求走私攻击面。
    # 如需扩展，通过环境变量 CORS_ALLOW_HEADERS 追加（逗号分隔）。
    CORS_ALLOW_HEADERS: str = "Authorization,Content-Type,Accept,Origin,X-Requested-With,X-CSRF-Token,X-Request-ID"

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @property
    def allowed_extensions_list(self) -> List[str]:
        """获取允许的文件扩展名列表。"""
        return parse_list(self.ALLOWED_EXTENSIONS)

    @property
    def cors_origins_list(self) -> List[str]:
        """获取CORS允许的来源域名列表。"""
        return parse_list(self.CORS_ORIGINS)

    @property
    def cors_allow_methods_list(self) -> List[str]:
        """获取CORS允许的HTTP方法列表。"""
        return parse_list(self.CORS_ALLOW_METHODS)

    @property
    def cors_allow_headers_list(self) -> List[str]:
        """获取CORS允许的请求头列表。"""
        return parse_list(self.CORS_ALLOW_HEADERS)

    def _ensure_secret_keys(self) -> None:
        """确保必要的安全密钥已设置，委托给 key_management.ensure_secret_keys。"""
        from app.core.key_management import ensure_secret_keys
        ensure_secret_keys(self)


from app.core.key_management import generate_secret_key as _generate_secret_key
from app.core.settings_profiles import DevSettings, TestSettings, ProdSettings


def get_settings() -> Settings:
    """根据ENVIRONMENT环境变量获取对应环境的配置实例。"""
    env = os.getenv("ENVIRONMENT", "dev")
    if env == "prod":
        return ProdSettings()
    elif env == "test":
        return TestSettings()
    else:
        return DevSettings()


settings = get_settings()
settings._ensure_secret_keys()


def init_directories() -> None:
    """初始化项目所需的文件系统目录结构。"""
    try:
        upload_dir = Path(settings.UPLOAD_DIR).resolve()
        ui_prototype_dir = Path(settings.UI_PROTOTYPE_UPLOAD_DIR).resolve()
        directories = [upload_dir, ui_prototype_dir]

        for directory in directories:
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                _logger.info(f"创建目录: {directory}")

        return directories
    except Exception as e:
        _logger.error(f"初始化目录失败: {e}")
        return []
