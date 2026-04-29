"""
全局配置模块 - 多环境配置支持（dev/test/prod）

本模块是AI测试平台的配置中心，负责管理所有运行时参数，包括数据库连接、
Redis缓存、JWT认证、数据加密、AI模型接入、CORS跨域等核心配置。

核心类/函数概览：
    - parse_list(): 将字符串或列表类型的配置值统一解析为列表
    - _generate_secret_key(): 生成URL安全的高熵随机密钥
    - Settings: 全局配置基类，包含所有配置项定义及密钥管理逻辑
    - DevSettings: 开发环境配置（DEBUG=True, CORS=*, 日志级别DEBUG）
    - TestSettings: 测试环境配置（DEBUG=False, 日志级别INFO）
    - ProdSettings: 生产环境配置（严格安全检查, 日志级别WARNING）
    - get_settings(): 根据ENVIRONMENT环境变量选择对应配置类实例化
    - init_directories(): 初始化上传目录等文件系统结构

依赖关系：
    - pydantic_settings.BaseSettings: 配置项的类型校验与.env文件加载
    - app.utils.file_utils.SUPPORTED_FILE_TYPES: 文件上传扩展名白名单
    - 标准库: os, json, secrets, logging, pathlib

安全说明：
    - 生产环境强制校验JWT密钥长度、API密钥有效性、CORS域名白名单
    - 敏感密钥支持持久化到.secret_keys文件（权限0o600），避免重启后失效
    - 禁止使用SQLite，强制MySQL连接
"""
from pydantic_settings import BaseSettings
from typing import Optional, List, Union
import os
import logging
import json
import secrets
from pathlib import Path
from app.utils.file_utils import SUPPORTED_FILE_TYPES

_logger = logging.getLogger(__name__)

# 项目根目录，用于定位uploads等相对路径资源
# Path(__file__)为当前文件路径，向上三级到达项目根目录（app/core/config.py -> app/core -> app -> 项目根）
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def parse_list(value: Union[str, List]) -> List[str]:
    """将配置值统一解析为字符串列表。

    环境变量和.env文件中的列表值通常以字符串形式传入，本函数负责
    将其转换为Python列表，支持JSON数组格式和逗号分隔格式。

    Args:
        value: 待解析的配置值，支持以下三种输入：
            - list: 直接返回（无需转换）
            - str(JSON格式): 如 '["a","b","c"]'，尝试JSON解析
            - str(逗号分隔): 如 "a, b, c"，按逗号拆分并去除空白

    Returns:
        List[str]: 解析后的字符串列表。若输入类型无法识别则返回空列表。

    Examples:
        >>> parse_list(["a", "b"])
        ['a', 'b']
        >>> parse_list('["a","b"]')
        ['a', 'b']
        >>> parse_list("a, b, c")
        ['a', 'b', 'c']
        >>> parse_list(123)
        []
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            # 优先尝试JSON解析，适用于从环境变量传入的JSON数组字符串
            return json.loads(value)
        except json.JSONDecodeError:
            # JSON解析失败时，按逗号分隔处理（兼容简单列表配置）
            return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _generate_secret_key() -> str:
    """生成URL安全的高熵随机密钥。

    使用secrets模块生成43字符长度的URL安全Base64编码随机字符串，
    对应256位（32字节）的随机数据，适用于JWT签名密钥、加密密钥等安全场景。

    Returns:
        str: 43字符长度的URL安全随机字符串（token_urlsafe(32)的输出长度）。
    """
    return secrets.token_urlsafe(32)


class Settings(BaseSettings):
    """全局配置基类，定义所有运行时参数及密钥管理逻辑。

    本类是AI测试平台的配置中心，所有配置项均可通过以下方式设置（优先级从高到低）：
        1. 环境变量（最高优先级，生产环境推荐方式）
        2. .env文件（开发环境推荐方式）
        3. 类属性默认值（最低优先级，作为兜底）

    设计意图：
        - 使用pydantic BaseSettings实现类型安全的配置管理
        - 配置项按功能分组（数据库/Redis/JWT/加密/AI/CORS等），便于维护
        - 敏感密钥通过_ensure_secret_keys()实现自动生成与持久化
        - 生产环境通过严格校验防止不安全配置上线

    关键属性：
        - DATABASE_URL: 数据库连接串（必填，禁止SQLite）
        - JWT_SECRET_KEY: JWT签名密钥（空值时自动生成并持久化）
        - ENCRYPTION_KEY/ENCRYPTION_SALT: 数据加密密钥与盐值
        - DEEPSEEK_API_KEY: AI功能核心API密钥
        - CORS_ORIGINS: 跨域白名单（生产环境禁止通配符）

    使用场景：
        - 应用启动时通过get_settings()获取全局配置单例
        - 各模块通过 from app.core.config import settings 引用配置
        - 配置变更后需重启应用生效（非热加载）

    注意：
        - 本类不应直接实例化，应通过DevSettings/TestSettings/ProdSettings子类使用
        - _ensure_secret_keys()在模块加载时自动调用，确保密钥可用
    """

    # ==================== 基本配置 ====================
    # 应用标识与运行模式，ENVIRONMENT决定使用哪套环境配置
    APP_NAME: str = "AI测试平台"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False  # 调试模式，生产环境必须为False
    ENVIRONMENT: str = "dev"  # 运行环境标识：dev(开发)/test(测试)/prod(生产)

    # ==================== 数据库配置 ====================
    # 使用MySQL作为主数据库，禁止SQLite（不支持并发、无事务完整性）
    # DATABASE_URL格式：mysql+pymysql://user:password@host:port/database
    DATABASE_URL: str = ""  # 必须在.env中配置，空值启动时会抛出ValueError
    DATABASE_URL_SLAVE: Optional[str] = None  # 从库连接串，用于读写分离（可选）
    DB_POOL_SIZE: int = 20  # 连接池大小，根据并发量调整
    DB_POOL_TIMEOUT: int = 30  # 获取连接的超时时间（秒）
    DB_MAX_OVERFLOW: int = 10  # 超出连接池大小后允许的最大溢出连接数

    # ==================== Redis配置（用于Celery异步任务） ====================
    # Redis作为Celery的消息代理和结果后端，同时可用于缓存层
    REDIS_URL: str = "redis://localhost:6379/0"  # Redis连接串，格式：redis://host:port/db
    REDIS_MAX_CONNECTIONS: int = 50  # Redis连接池最大连接数

    # ==================== JWT配置 ====================
    # JSON Web Token认证配置，用于用户登录态管理
    # 安全要求：生产环境JWT_SECRET_KEY必须从环境变量设置，禁止自动生成
    JWT_SECRET_KEY: str = ""  # JWT签名密钥，空值时_ensure_secret_keys()自动生成并持久化
    JWT_ALGORITHM: str = "HS256"  # JWT签名算法，HS256为对称加密（性能优于RS256）
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 访问令牌有效期（分钟），短期令牌降低泄露风险
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 刷新令牌有效期（天），用于无感续期

    # ==================== 加密配置 ====================
    # 用于敏感数据（如密码）的对称加密，基于Fernet算法
    # 安全要求：生产环境ENCRYPTION_KEY和ENCRYPTION_SALT必须从环境变量设置
    ENCRYPTION_KEY: str = ""  # 密码加密密钥，空值时自动生成并持久化到.secret_keys
    ENCRYPTION_SALT: str = ""  # 加密盐值，增强密钥推导安全性，空值时自动生成

    # ==================== 文件存储配置 ====================
    # 控制文件上传的存储路径、大小限制和类型白名单
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")  # 通用上传目录
    UI_PROTOTYPE_UPLOAD_DIR: str = str(BASE_DIR / "uploads" / "ui_prototypes")  # UI原型文件上传目录
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 单文件最大100MB（100 * 1024 * 1024字节）
    ALLOWED_EXTENSIONS: str = ",".join(SUPPORTED_FILE_TYPES.keys())  # 允许的文件扩展名，逗号分隔

    # ==================== ZIP批量上传配置 ====================
    # 防止ZIP炸弹攻击：限制ZIP包内文件数量和总大小
    MAX_ZIP_ENTRIES: int = 200  # ZIP包内最大文件数，防止解压炸弹
    MAX_ZIP_TOTAL_SIZE: int = 500 * 1024 * 1024  # ZIP包内图片总大小限制500MB

    # ==================== 支持的图片扩展名 ====================
    # AI视觉识别支持的图片格式，用于UI原型解析等场景
    SUPPORTED_IMAGE_EXTENSIONS: list = ["png", "jpg", "jpeg", "gif", "webp", "bmp"]

    # ==================== DeepSeek API配置 ====================
    # DeepSeek是AI测试用例生成的核心模型，用于需求分析、用例生成等
    DEEPSEEK_API_KEY: str = ""  # DeepSeek API密钥，生产环境必须配置
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1/chat/completions"  # API端点
    DEEPSEEK_MODEL: str = "deepseek-chat"  # 使用的模型名称
    DEEPSEEK_MAX_TOKENS: int = 2048  # 单次请求最大token数，控制输出长度和成本
    DEEPSEEK_TEMPERATURE: float = 0.7  # 生成温度（0-1），越高越随机，0.7平衡创造性与准确性

    # ==================== Pipeline AI 抽象层配置 ====================
    # M1-T08: Pipeline 统一 AI 调用抽象层配置
    AI_MODEL_NAME: str = "deepseek-chat"  # Pipeline 主模型名称
    AI_FALLBACK_MODEL_NAME: str = "deepseek-chat"  # Pipeline 备用模型名称（主模型失败时切换）
    AI_TOKEN_BUDGET_PER_RUN: int = 100000  # 单次 Pipeline Run 的 Token 预算上限
    AI_TEMPERATURE: float = 0.7  # Pipeline 默认生成温度
    AI_MAX_TOKENS: int = 2048  # Pipeline 默认最大输出 Token 数
    AI_MAX_RETRIES: int = 3  # Pipeline AI 调用最大重试次数

    # ==================== 用例生命周期配置 ====================
    # LifecycleService 状态机相关配置
    LIFECYCLE_DEPRECATE_COOLDOWN_HOURS: int = 24  # deprecated → archived 冷却时间（小时）
    AUTO_APPROVE_MIN_GRADE: str = "A"  # pending_review → active 自动通过最低先验等级，M1阶段默认A，后续可调为B

    # ==================== 视觉模型配置（AI视觉识别） ====================
    # 支持多模型动态切换: kimi, qwen, zhipu, baidu, doubao, mimo
    # 用于UI原型截图的元素识别与结构解析，不同模型在准确率和成本上有差异

    # 默认使用的视觉模型，通过VISION_MODEL_DEFAULT切换
    VISION_MODEL_DEFAULT: str = "mimo"
    UI_PARSER_MODE: str = "text"  # UI解析模式：text(文本模式)/vision(视觉模式)

    # Kimi (Moonshot) - 月之暗面，128K上下文，适合复杂UI分析
    KIMI_API_KEY: str = ""
    KIMI_MODEL: str = "moonshot-v1-128k-vision-preview"

    # 通义千问 (阿里云) - 默认视觉模型，性价比高，中文识别优秀
    QWEN_API_KEY: str = ""
    QWEN_MODEL: str = "qwen-vl-plus"

    # 智谱GLM - 清华系模型，多模态能力强
    ZHIPU_API_KEY: str = ""
    ZHIPU_MODEL: str = "glm-4v-plus"

    # 文心一言 (百度) - 百度大模型，企业级稳定性
    BAIDU_API_KEY: str = ""
    BAIDU_MODEL: str = "ernie-bot-4"

    # 豆包 (字节跳动) - 字节大模型，32K上下文
    DOUBAO_API_KEY: str = ""
    DOUBAO_MODEL: str = "doubao-vision-pro-32k"

    # MiMo (小米) - 小米自研多模态大模型，OpenAI兼容API，支持图片理解
    MIMO_API_KEY: str = ""
    MIMO_MODEL: str = "mimo-v2.5"
    MIMO_BASE_URL: str = "https://token-plan-cn.xiaomimimo.com/v1"

    # ==================== AI自愈配置 ====================
    # AI自愈功能：当测试步骤执行失败时，AI自动尝试修复定位器或操作
    AI_SELF_HEALING_ENABLED: bool = False  # 是否启用AI自愈（默认关闭，需配置Browserbase）
    AI_SELF_HEALING_MAX_RETRIES: int = 1  # 单步骤最大自愈重试次数
    STAGEHAND_MODEL: str = "gpt-4o"  # Stagehand自愈使用的LLM模型
    BROWSERBASE_API_KEY: str = ""  # Browserbase云浏览器API密钥
    BROWSERBASE_PROJECT_ID: str = ""  # Browserbase项目ID

    # ==================== Playwright MCP配置 ====================
    # MCP(Model Context Protocol)：AI通过协议控制浏览器执行测试步骤
    PLAYWRIGHT_MCP_ENABLED: bool = True  # 是否启用Playwright MCP服务
    PLAYWRIGHT_MCP_SERVER_PORT: int = 3000  # MCP服务监听端口
    MCP_TEXT_LLM_MODEL: str = "deepseek-chat"  # MCP文本处理使用的LLM模型

    # ==================== MCP直执配置 ====================
    # MCP直执：AI生成的操作指令直接通过MCP执行，无需人工确认
    MCP_DIRECT_EXECUTION_ENABLED: bool = False  # 是否启用MCP直执（默认关闭，需评估安全性）
    MCP_EXECUTION_OPERATION_TYPES: str = "click,type,hover,select"  # 允许直执的操作类型白名单
    AUTO_PARSE_PRECONDITION: bool = True  # 是否自动解析测试前置条件

    # ==================== Celery配置 ====================
    # Celery分布式任务队列，用于AI用例生成等耗时操作的异步执行
    CELERY_BROKER_URL: str = ""  # 消息代理URL，空值时使用REDIS_URL
    CELERY_RESULT_BACKEND: str = ""  # 结果后端URL，空值时使用REDIS_URL
    CELERY_TASK_SERIALIZER: str = "json"  # 任务序列化格式
    CELERY_RESULT_SERIALIZER: str = "json"  # 结果序列化格式
    CELERY_ACCEPT_CONTENT: str = "json"  # 接受的内容类型
    CELERY_TIMEZONE: str = "Asia/Shanghai"  # Celery时区，与业务时区保持一致
    CELERY_ENABLE_UTC: bool = False  # 禁用UTC，使用本地时区

    # ==================== CORS配置 ====================
    # 跨域资源共享配置，控制前端域名对后端API的访问权限
    # 安全要求：生产环境禁止使用通配符"*"，必须显式配置允许的域名
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"  # 允许的来源域名
    CORS_ALLOW_CREDENTIALS: bool = True  # 允许携带Cookie（需与前端withCredentials配合）
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,DELETE,OPTIONS"  # 允许的HTTP方法
    CORS_ALLOW_HEADERS: str = "*"  # 允许的请求头

    # ==================== 日志配置 ====================
    LOG_LEVEL: str = "INFO"  # 日志级别：DEBUG/INFO/WARNING/ERROR/CRITICAL
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # 日志格式

    class Config:
        """Pydantic配置元数据。

        控制BaseSettings的行为：.env文件路径、编码、大小写敏感等。
        """
        env_file = ".env"  # 环境变量文件路径（项目根目录下）
        env_file_encoding = "utf-8"  # .env文件编码
        case_sensitive = True  # 配置项大小写敏感（DATABASE_URL与database_url不同）

    @property
    def allowed_extensions_list(self) -> List[str]:
        """获取允许的文件扩展名列表。

        将ALLOWED_EXTENSIONS字符串（逗号分隔）解析为Python列表，
        便于在文件上传校验逻辑中使用。

        Returns:
            List[str]: 允许的文件扩展名列表，如 ['png', 'jpg', 'pdf']。
        """
        return parse_list(self.ALLOWED_EXTENSIONS)

    @property
    def cors_origins_list(self) -> List[str]:
        """获取CORS允许的来源域名列表。

        将CORS_ORIGINS字符串解析为列表，供FastAPI CORSMiddleware使用。

        Returns:
            List[str]: 允许的域名列表，如 ['http://localhost:5173', 'http://localhost:3000']。
        """
        return parse_list(self.CORS_ORIGINS)

    @property
    def cors_allow_methods_list(self) -> List[str]:
        """获取CORS允许的HTTP方法列表。

        Returns:
            List[str]: 允许的HTTP方法列表，如 ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']。
        """
        return parse_list(self.CORS_ALLOW_METHODS)

    @property
    def cors_allow_headers_list(self) -> List[str]:
        """获取CORS允许的请求头列表。

        Returns:
            List[str]: 允许的请求头列表，如 ['*'] 表示允许所有头。
        """
        return parse_list(self.CORS_ALLOW_HEADERS)

    @property
    def celery_accept_content_list(self) -> List[str]:
        """获取Celery接受的内容类型列表。

        Returns:
            List[str]: 内容类型列表，如 ['json']。
        """
        return parse_list(self.CELERY_ACCEPT_CONTENT)

    def _ensure_secret_keys(self) -> None:
        """确保必要的安全密钥已设置，支持持久化到文件以跨重启复用。

        本方法是配置初始化的核心安全检查逻辑，执行以下流程：

        1. 数据库连接校验：
           - 检查DATABASE_URL是否为空（必须配置）
           - 禁止使用SQLite（不支持并发、无事务完整性）

        2. 密钥安全性检查：
           - 生产环境：强制校验API密钥非默认值、JWT密钥长度>=32字符
           - 非生产环境：检测到默认值时发出警告（不阻断启动）

        3. 密钥自动生成与持久化（三级回退策略）：
           - 第一优先级：环境变量/.env文件中已设置的值
           - 第二优先级：从.secret_keys缓存文件加载（跨重启复用）
           - 第三优先级：自动生成新密钥并保存到.secret_keys文件

        4. 生产环境CORS安全检查：
           - 禁止CORS_ORIGINS为空或使用通配符"*"

        密钥缓存文件(.secret_keys)说明：
           - 存储位置：项目根目录/.secret_keys
           - 文件权限：0o600（仅所有者可读写）
           - 存储内容：JWT密钥、加密密钥、加密盐值的JSON映射
           - 安全注意：该文件应加入.gitignore，禁止提交到版本控制

        Raises:
            ValueError: 当以下情况发生时抛出：
                - DATABASE_URL为空
                - DATABASE_URL使用SQLite协议
                - 生产环境DEEPSEEK_API_KEY使用默认值
                - 生产环境JWT_SECRET_KEY长度不足32字符
                - 生产环境CORS_ORIGINS为空或使用通配符
        """
        import warnings

        # 密钥缓存文件路径，位于项目根目录
        # 该文件存储自动生成的密钥，避免每次重启后密钥变化导致已签发的JWT失效
        _key_cache_file = BASE_DIR / ".secret_keys"

        def _load_cached_key(key_name: str) -> str:
            """从缓存文件加载指定密钥。

            读取.secret_keys文件中的JSON数据，返回指定key_name对应的值。
            文件不存在或解析失败时返回空字符串，触发后续的自动生成流程。

            Args:
                key_name: 密钥在缓存文件中的键名，如 'jwt_secret_key'。

            Returns:
                str: 缓存的密钥值，未找到时返回空字符串。
            """
            try:
                if _key_cache_file.exists():
                    import json
                    cached = json.loads(_key_cache_file.read_text())
                    if key_name in cached and cached[key_name]:
                        return cached[key_name]
            except Exception:
                # 文件读取或JSON解析失败，静默忽略
                # 原因：缓存文件非必需，失败后可重新生成密钥
                pass
            return ""

        def _save_cached_key(key_name: str, value: str) -> None:
            """保存密钥到缓存文件，实现跨重启复用。

            采用"读取-合并-写入"模式，保留文件中已有的其他密钥。
            写入后设置文件权限为0o600（仅所有者可读写），防止密钥泄露。

            Args:
                key_name: 密钥在缓存文件中的键名。
                value: 要保存的密钥值。
            """
            try:
                import json
                cached = {}
                if _key_cache_file.exists():
                    try:
                        # 读取已有缓存，保留其他密钥
                        cached = json.loads(_key_cache_file.read_text())
                    except Exception:
                        pass
                cached[key_name] = value
                _key_cache_file.write_text(json.dumps(cached))
                # 设置文件权限为仅所有者可读写（0o600），防止其他用户读取密钥
                os.chmod(_key_cache_file, 0o600)
            except Exception as e:
                warnings.warn(f"无法保存密钥到文件: {e}")

        # ==================== 数据库连接校验 ====================
        # 数据库是系统核心依赖，必须正确配置才能启动
        if not self.DATABASE_URL:
            raise ValueError(
                "DATABASE_URL 未配置！请在 .env 文件中设置 MySQL 连接字符串，"
                "例如: mysql+pymysql://user:password@localhost:3306/ai_testmaster"
            )

        # 禁止SQLite：不支持并发写入、无完整事务、无外键约束，不符合生产要求
        if self.DATABASE_URL.startswith("sqlite"):
            raise ValueError(
                "禁止使用 SQLite 数据库！请配置 MySQL 连接字符串。"
                "项目要求必须使用 MySQL。"
            )

        # ==================== 安全性检查：检测默认/示例值 ====================
        # 常见的默认值模式，用于检测用户是否忘记修改配置
        _default_patterns = [
            'your-', 'your_', 'here', 'password', 'changeme',
            'example', 'test1234', 'secret', 'xxx'
        ]

        def _is_default_value(value: str) -> bool:
            """检查配置值是否为默认/示例值。

            通过匹配常见的占位符模式（如'your-'、'changeme'等），
            检测用户是否忘记修改配置文件中的示例值。

            Args:
                value: 待检查的配置值。

            Returns:
                bool: True表示可能是默认值，False表示已正确配置。
            """
            if not value:
                return True
            value_lower = value.lower()
            return any(pattern in value_lower for pattern in _default_patterns)

        # ==================== API密钥安全性检查 ====================
        # 根据环境严格程度不同：生产环境强制阻断，开发环境仅警告
        if self.ENVIRONMENT == "prod":
            # 生产环境：API密钥使用默认值将导致AI功能不可用，强制报错
            if _is_default_value(self.DEEPSEEK_API_KEY):
                raise ValueError(
                    "生产环境检测到DEEPSEEK_API_KEY使用了默认值！"
                    "请在 .env 中配置真实的 API 密钥。"
                    "获取地址: https://platform.deepseek.com/"
                )

            # JWT密钥长度不足易被暴力破解，32字符为最低安全要求
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "生产环境JWT_SECRET_KEY长度不足（至少32字符）！"
                    "请使用强随机密钥。生成命令: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
        else:
            # 非生产环境：仅发出警告，不阻断启动
            if _is_default_value(self.DEEPSEEK_API_KEY):
                warnings.warn(
                    "⚠️  DEEPSEEK_API_KEY 可能使用了默认值，AI功能可能无法正常工作。"
                    "请在 .env 中配置真实的 API 密钥。",
                    UserWarning
                )

        # ==================== JWT密钥检查（三级回退策略） ====================
        # 回退顺序：环境变量值 -> 缓存文件值 -> 自动生成新值
        if not self.JWT_SECRET_KEY:
            self.JWT_SECRET_KEY = _load_cached_key("jwt_secret_key")
        if not self.JWT_SECRET_KEY:
            # 缓存中也没有，自动生成（生产环境发出警告）
            if self.ENVIRONMENT == "prod":
                warnings.warn(
                    "生产环境未设置JWT_SECRET_KEY，将使用自动生成的密钥。"
                    "建议在生产环境设置JWT_SECRET_KEY环境变量。",
                    UserWarning
                )
            self.JWT_SECRET_KEY = _generate_secret_key()
            _save_cached_key("jwt_secret_key", self.JWT_SECRET_KEY)

        # ==================== 加密密钥检查（三级回退策略） ====================
        # 用于Fernet对称加密，加密用户密码等敏感数据
        if not self.ENCRYPTION_KEY:
            self.ENCRYPTION_KEY = _load_cached_key("encryption_key")
        if not self.ENCRYPTION_KEY:
            if self.ENVIRONMENT == "prod":
                warnings.warn(
                    "生产环境未设置ENCRYPTION_KEY，将使用自动生成的密钥。"
                    "警告：首次生成后密钥会持久化到 .secret_keys 文件。",
                    UserWarning
                )
            self.ENCRYPTION_KEY = _generate_secret_key()
            _save_cached_key("encryption_key", self.ENCRYPTION_KEY)

        # ==================== 加密盐值检查（三级回退策略） ====================
        # 盐值用于密钥推导函数，增强加密安全性，防止彩虹表攻击
        if not self.ENCRYPTION_SALT:
            self.ENCRYPTION_SALT = _load_cached_key("encryption_salt")
        if not self.ENCRYPTION_SALT:
            if self.ENVIRONMENT == "prod":
                warnings.warn(
                    "生产环境未设置ENCRYPTION_SALT，将使用随机盐值。"
                    "警告：首次生成后会持久化到 .secret_keys 文件。",
                    UserWarning
                )
            self.ENCRYPTION_SALT = _generate_secret_key()
            _save_cached_key("encryption_salt", self.ENCRYPTION_SALT)

        # ==================== 生产环境CORS安全检查 ====================
        # CORS通配符意味着任何网站都可调用本站API，存在CSRF风险
        if self.ENVIRONMENT == "prod" and (not self.CORS_ORIGINS or self.CORS_ORIGINS == "*"):
            raise ValueError(
                "生产环境必须配置 CORS_ORIGINS！禁止使用 '*' 通配符。"
                "请在 .env 中设置允许的域名，例如: CORS_ORIGINS=https://yourdomain.com"
            )


class DevSettings(Settings):
    """开发环境配置。

    设计意图：为本地开发提供最宽松的配置，降低环境搭建门槛。
    - 开启DEBUG模式，显示详细错误信息
    - CORS允许所有来源，方便前端跨域调试
    - 日志级别DEBUG，输出最详细的运行信息

    安全说明：
        - 本配置仅用于本地开发，禁止部署到任何共享环境
        - CORS通配符"*"在生产环境是严重安全漏洞
    """

    DEBUG: bool = True
    ENVIRONMENT: str = "dev"
    LOG_LEVEL: str = "DEBUG"
    CORS_ORIGINS: str = "*"  # 开发环境允许所有来源，便于前后端联调


class TestSettings(Settings):
    """测试环境配置。

    设计意图：模拟生产环境行为，但保留适度的调试信息。
    - 关闭DEBUG模式，与生产环境行为一致
    - 日志级别INFO，保留关键运行信息便于排查测试失败
    - CORS需显式配置，但校验不如生产环境严格

    使用场景：CI/CD流水线、自动化测试、预发布验证。
    """

    DEBUG: bool = False
    ENVIRONMENT: str = "test"
    LOG_LEVEL: str = "INFO"


class ProdSettings(Settings):
    """生产环境配置。

    设计意图：最高安全等级的配置，所有安全检查均以最严格标准执行。
    - 关闭DEBUG模式，隐藏错误详情防止信息泄露
    - 日志级别WARNING，仅记录警告和错误，减少日志量
    - CORS必须显式配置白名单，空值或通配符将导致启动失败

    安全要求：
        - JWT_SECRET_KEY必须通过环境变量设置且长度>=32字符
        - DEEPSEEK_API_KEY必须配置真实值
        - CORS_ORIGINS必须配置具体域名，禁止通配符
        - ENCRYPTION_KEY和ENCRYPTION_SALT建议通过环境变量设置

    部署注意：
        - 所有敏感配置应通过系统环境变量注入，不要写入.env文件
        - .secret_keys文件应设置0o600权限并加入.gitignore
    """

    DEBUG: bool = False
    ENVIRONMENT: str = "prod"
    LOG_LEVEL: str = "WARNING"
    CORS_ORIGINS: str = ""  # 生产环境必须显式配置，否则_ensure_secret_keys()报错


# 根据环境变量选择配置
def get_settings() -> Settings:
    """根据ENVIRONMENT环境变量获取对应环境的配置实例。

    本函数是配置对象的工厂方法，根据环境变量选择不同的配置子类实例化。
    环境变量未设置时默认使用开发环境配置。

    Returns:
        Settings: 对应环境的配置对象实例：
            - ENVIRONMENT=prod -> ProdSettings（生产环境，严格安全检查）
            - ENVIRONMENT=test -> TestSettings（测试环境，适度安全检查）
            - 其他/未设置 -> DevSettings（开发环境，宽松配置）

    Raises:
        无直接异常，但实例化后的_ensure_secret_keys()可能抛出ValueError。
    """
    env = os.getenv("ENVIRONMENT", "dev")

    if env == "prod":
        return ProdSettings()
    elif env == "test":
        return TestSettings()
    else:
        return DevSettings()


# 全局配置单例，应用启动时创建一次，各模块通过import引用
settings = get_settings()
# 确保安全密钥已设置：校验必填项、自动生成缺失密钥、持久化到缓存文件
settings._ensure_secret_keys()


# 初始化目录结构
def init_directories() -> None:
    """初始化项目所需的文件系统目录结构。

    在应用启动时调用，确保上传目录、UI原型目录等必要的文件系统路径存在。
    目录不存在时自动创建（含父目录），已存在时跳过。

    Returns:
        None（正常）或空列表（异常时）。返回值包含创建/确认的目录路径列表。

    注意：
        - /tmp/ui_prototypes为临时目录，系统重启后可能丢失
        - UI_PROTOTYPE_UPLOAD_DIR通过getattr安全访问，兼容配置项缺失的情况
    """
    try:
        upload_dir = Path(settings.UPLOAD_DIR).resolve()
        ui_prototype_dir = Path(getattr(settings, 'UI_PROTOTYPE_UPLOAD_DIR', '/tmp/ui_prototypes')).resolve()
        temp_ui_prototype_dir = Path('/tmp/ui_prototypes').resolve()  # 临时目录，用于UI原型临时处理
        directories = [upload_dir, ui_prototype_dir, temp_ui_prototype_dir]

        for directory in directories:
            if not directory.exists():
                # parents=True: 父目录不存在时一并创建
                # exist_ok=True: 目录已存在时不抛异常
                directory.mkdir(parents=True, exist_ok=True)
                _logger.info(f"创建目录: {directory}")

        return directories
    except Exception as e:
        _logger.error(f"初始化目录失败: {e}")
        return []
