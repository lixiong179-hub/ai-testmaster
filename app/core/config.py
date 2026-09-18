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
    # ========== 安全合规 Phase 1A：JWT RS256 升级（add-security-compliance Task 1） ==========
    # RSA 私钥（PEM 格式，用于 RS256 签名），多行字符串通过环境变量或文件路径注入
    JWT_PRIVATE_KEY: str = ""
    # RSA 公钥（PEM 格式，用于 RS256 验签），可分发给微服务独立验签
    JWT_PUBLIC_KEY: str = ""
    # RSA 私钥/公钥文件路径（优先级低于 JWT_PRIVATE_KEY/JWT_PUBLIC_KEY，便于 KMS 注入）
    JWT_PRIVATE_KEY_PATH: str = ""
    JWT_PUBLIC_KEY_PATH: str = ""
    # 目标签名算法：RS256（生产强制，迁移期通过 JWT_ALGORITHM 兼容旧 HS256 token）
    JWT_PREFERRED_ALGORITHM: str = "RS256"
    # 登录失败锁定策略：5 次失败后锁定 15 分钟
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCK_MINUTES: int = 15

    ENCRYPTION_KEY: str = ""
    ENCRYPTION_SALT: str = ""

    ADMIN_INITIAL_PASSWORD: str = ""
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    UI_PROTOTYPE_UPLOAD_DIR: str = str(BASE_DIR / "uploads" / "ui_prototypes")
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024
    ALLOWED_EXTENSIONS: str = ",".join(SUPPORTED_FILE_TYPES.keys())

    # ── 对象存储（Phase 1 Task 1：后端无状态化）──
    # 业务用途：多实例水平扩展时切换至 S3/MinIO，避免本地 uploads 目录不一致
    # 边界场景：STORAGE_BACKEND=local 时仅使用 STORAGE_LOCAL_ROOT_DIR
    STORAGE_BACKEND: str = "local"  # 可选值: local / s3
    STORAGE_LOCAL_ROOT_DIR: str = ""  # 留空则回退到 UPLOAD_DIR
    S3_ENDPOINT_URL: str = ""  # 兼容 MinIO，如 http://minio:9000
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = True

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
    # 单次自愈调用 Token 上限：超限熔断，避免单步推理拖垮整体执行
    AI_SELF_HEALING_TOKEN_LIMIT: int = 2000
    # 日预算：自愈体系单日 Token 消耗硬上限，超限降级为 rollback/skip 策略
    AI_SELF_HEALING_DAILY_TOKEN_BUDGET: int = 500000
    # 置信度阈值：低于此值的自愈决策标记 low_confidence=True 进入人工复核通道
    AI_SELF_HEALING_CONFIDENCE_THRESHOLD: float = 0.7
    # load_delay 失败类型的重试等待秒数：避免瞬时加载抖动误判为定位失败
    AI_SELF_HEALING_RETRY_WAIT_SECONDS: int = 2

    # ========== Agent 架构 Phase 1 配置（add-agent-architecture Task 2） ==========
    # 全局总开关：False 时所有 Agent 端点返回 503，已运行的会话仍可查询
    AI_AGENT_ENABLED: bool = True
    # 单次 LLM 调用 Token 上限：超限熔断本轮迭代，避免单步推理拖垮整体会话
    AI_AGENT_TOKEN_LIMIT: int = 4000
    # 日预算：单 Agent 单项目单日 Token 消耗硬上限，超限降级为非 AI 策略
    AI_AGENT_DAILY_TOKEN_BUDGET: int = 1000000
    # 最大迭代轮数：超过则强制终止会话并标记 status=failed
    AI_AGENT_MAX_ITERATIONS: int = 20
    # 循环检测阈值：最近 N 次工具调用 hash 重复时触发循环检测熔断
    AI_AGENT_LOOP_DETECTION_THRESHOLD: int = 3
    # 熔断器阈值：连续失败次数超过此值时熔断器转为 open 状态
    AI_AGENT_CIRCUIT_BREAKER_THRESHOLD: int = 5
    # 熔断器恢复秒数：open 状态持续时间，到期后转 half_open 允许 1 次试探
    AI_AGENT_CIRCUIT_BREAKER_RECOVERY_SECONDS: int = 300
    # 历史消息数：构建 LLM 上下文时保留的最近消息条数，避免上下文爆炸
    AI_AGENT_HISTORY_MESSAGE_COUNT: int = 10
    # MCP Server 总开关：False 时 /api/v1/mcp/* 端点返回 503
    AI_AGENT_MCP_SERVER_ENABLED: bool = False
    STAGEHAND_MODEL: str = "gpt-4o"
    BROWSERBASE_API_KEY: str = ""
    BROWSERBASE_PROJECT_ID: str = ""

    # ========== Visual AI 引擎 Phase 2 配置（add-visual-ai-engine Task 2） ==========
    # 全局总开关：False 时所有 Visual AI 端点返回 503，测试执行跳过视觉校验步骤
    VISUAL_AI_ENABLED: bool = True
    # 默认 Match Level：新基线未指定时使用，strict=像素级严格对比
    VISUAL_AI_DEFAULT_MATCH_LEVEL: str = "strict"
    # 像素差异阈值：diff_percentage < 此值时自动审批为 auto_approved，避免微小噪声触发人工审批
    VISUAL_AI_AUTO_APPROVE_THRESHOLD: float = 0.1
    # LLM 语义对比触发阈值：diff_percentage >= 此值时才调用 LLM 语义分析，降低 Token 成本
    VISUAL_AI_LLM_ANALYSIS_THRESHOLD: float = 5.0
    # 单次 LLM 语义分析 Token 上限
    VISUAL_AI_LLM_TOKEN_LIMIT: int = 2000
    # Visual AI 日 Token 预算：单项目单日累计消耗上限，超限降级为仅像素对比
    # 独立于 Agent 日预算，避免视觉分析挤占 Agent 配额
    VISUAL_AI_DAILY_TOKEN_BUDGET: int = 500000
    # 基线图片存储路径前缀：StorageBackend 中的 key 前缀，按项目隔离
    VISUAL_AI_BASELINE_PATH_PREFIX: str = "visual-ai/baselines"
    # Diff 图片存储路径前缀
    VISUAL_AI_DIFF_PATH_PREFIX: str = "visual-ai/diffs"
    # 基线最大版本数：超过此值时自动清理最旧的非活跃版本
    VISUAL_AI_MAX_BASELINE_VERSIONS: int = 10

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

    # ========== Phase 3 安全合规：CSRF/HSTS/CSP 防护（Task 13） ==========
    # HSTS：强制 HTTPS，仅生产环境启用（开发环境 http 会导致浏览器拒绝）
    SECURITY_HSTS_ENABLED: bool = True
    SECURITY_HSTS_MAX_AGE: int = 31536000  # 1 年
    SECURITY_HSTS_INCLUDE_SUBDOMAINS: bool = True
    SECURITY_HSTS_PRELOAD: bool = False
    # CSP：内容安全策略，限制资源加载来源，防 XSS/数据注入
    SECURITY_CSP_ENABLED: bool = True
    SECURITY_CSP_POLICY: str = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    # CSRF：基于 Origin/Referer 校验 + 双提交 Cookie 模式
    # 业务背景：JWT 通过 Authorization 头传递，CSRF 风险低；但 Cookie 模式下需强制校验
    SECURITY_CSRF_ENABLED: bool = True
    # 安全方法豁免（RFC 7231：GET/HEAD/OPTIONS/TRACE 不应产生副作用）
    SECURITY_CSRF_EXEMPT_METHODS: str = "GET,HEAD,OPTIONS"
    # 路径豁免：SAML ACS 端点由 IdP POST SAMLResponse，无法携带 CSRF token，
    # 已通过 RelayState 实现 CSRF 防护；OIDC callback 为 GET 不在此列
    SECURITY_CSRF_EXEMPT_PATHS: str = "/api/v1/auth/saml/acs"
    # CSRF token 请求头名称（前后端约定）
    SECURITY_CSRF_TOKEN_HEADER: str = "X-CSRF-Token"
    # CSRF token Cookie 名称（双提交 Cookie 模式）
    SECURITY_CSRF_COOKIE_NAME: str = "csrf_token"

    # ========== Phase 3 安全合规：KMS 信封加密（Task 12） ==========
    # 业务用途：敏感字段（如 API Key、第三方凭据）使用信封加密存储
    # 信封加密：DEK（数据加密密钥）加密数据，KEK（主密钥）加密 DEK，DEK 内存缓存
    # 是否启用 KMS 信封加密（开发环境可关闭，直接明文存储）
    KMS_ENABLED: bool = False
    # KEK 来源：local（本地密钥）/ env（环境变量）/ aws-kms（AWS KMS，后续扩展）
    KMS_KEK_SOURCE: str = "local"
    # 本地 KEK 密钥（Base64 编码 32 字节 AES-256 密钥），生产环境必须通过环境变量设置
    KMS_LOCAL_KEK: str = ""
    # DEK 内存缓存 TTL（秒），避免每次解密都重新生成 DEK
    KMS_DEK_CACHE_TTL: int = 300  # 5 分钟

    # ========== Phase 3 安全合规：OIDC SSO 适配（Task 5） ==========
    # 业务用途：对接企业 IdP（Google/Azure AD/Okta/Keycloak 等），实现单点登录
    # 边界场景：OIDC_SSO_ENABLED=False 时所有 /auth/oidc/* 端点返回 503
    # 多 IdP 支持：通过 OIDC_IDP_CONFIGS（JSON）配置多个 IdP，按 provider 参数选择
    OIDC_SSO_ENABLED: bool = False
    # 默认 IdP 标识（用于 /auth/oidc/login 不带 provider 参数时选择默认 IdP）
    OIDC_DEFAULT_PROVIDER: str = "default"
    # IdP 配置列表（JSON 数组），每项含：provider/client_id/client_secret/issuer/discovery_url/scopes/redirect_uri
    # 示例：[{"provider":"google","client_id":"xxx","client_secret":"yyy","issuer":"https://accounts.google.com","scopes":"openid email profile","redirect_uri":"https://app.example.com/api/v1/auth/oidc/callback"}]
    OIDC_IDP_CONFIGS: str = "[]"
    # OIDC 回调后创建用户时的默认域名后缀（用于生成 username/email）
    OIDC_DEFAULT_DOMAIN: str = "sso.local"
    # OIDC 登录后签发的 access_token TTL（分钟），默认复用 JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    OIDC_ACCESS_TOKEN_TTL_MINUTES: int = 60
    # OIDC state 参数 TTL（秒），用于 CSRF 防护（授权码流程必需）
    OIDC_STATE_TTL_SECONDS: int = 600
    # 是否允许 OIDC 登录用户绕过 MFA（企业 IdP 已强制 MFA 时可设为 True）
    OIDC_BYPASS_MFA: bool = False
    # OIDC 用户名前缀（避免与本地账号冲突，如 "sso_" 前缀）
    OIDC_USERNAME_PREFIX: str = "sso_"
    # 是否允许 OIDC 用户首次登录自动注册（False 时仅允许已绑定的用户登录）
    OIDC_AUTO_PROVISION: bool = True

    # ========== Phase 3 安全合规：SAML 2.0 SSO SP 适配（Task 4） ==========
    # 业务用途：对接企业 SAML IdP（Okta/Azure AD/ADFS 等），实现 SP 发起的 SSO
    # 边界场景：SAML_SSO_ENABLED=False 时所有 /auth/saml/* 端点返回 503
    # 多 IdP 支持：通过 SAML_IDP_CONFIGS（JSON）配置多个 IdP，按 provider 参数选择
    SAML_SSO_ENABLED: bool = False
    # 默认 IdP 标识（用于 /auth/saml/login 不带 provider 参数时选择默认 IdP）
    SAML_DEFAULT_PROVIDER: str = "default"
    # SP 实体 ID（EntityID），通常为 https://app.example.com/api/v1/auth/saml/metadata
    SAML_SP_ENTITY_ID: str = ""
    # SP ACS URL（Assertion Consumer Service），IdP POST SAML Response 到此 URL
    SAML_SP_ACS_URL: str = ""
    # SP SLO URL（Single Logout Service），IdP POST LogoutRequest/Response 到此 URL
    SAML_SP_SLO_URL: str = ""
    # SP X.509 证书（PEM 格式，用于签名 AuthnRequest / 解密断言）
    SAML_SP_X509_CERT: str = ""
    # SP 私钥（PEM 格式，用于签名 AuthnRequest / 解密断言）
    SAML_SP_PRIVATE_KEY: str = ""
    # IdP 配置列表（JSON 数组），每项含：
    # provider/entity_id/sso_url/slo_url/x509_cert/nameid_format/sign_authn_request/want_assertions_signed
    SAML_IDP_CONFIGS: str = "[]"
    # SAML 登录后签发的 access_token TTL（分钟）
    SAML_ACCESS_TOKEN_TTL_MINUTES: int = 60
    # SAML RelayState 参数 TTL（秒），用于 CSRF 防护与请求上下文保持
    SAML_RELAYSTATE_TTL_SECONDS: int = 600
    # 是否允许 SAML 登录用户绕过 MFA（企业 IdP 已强制 MFA 时可设为 True）
    SAML_BYPASS_MFA: bool = False
    # SAML 用户名前缀（避免与本地账号冲突）
    SAML_USERNAME_PREFIX: str = "saml_"
    # 是否允许 SAML 用户首次登录自动注册（False 时仅允许已绑定的用户登录）
    SAML_AUTO_PROVISION: bool = True

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # ── MySQL 读写分离（Phase 1 Task 2：可扩展性）──
    # 业务用途：GET 类只读端点路由至从库，主库写压力下降 ≥60%
    # 边界场景：未配置 DATABASE_URL_SLAVE 时自动退化为主库，零行为变更
    # 主从延迟告警阈值（秒）：超过则触发告警，但仍允许走从库
    REPLICA_LAG_WARN_SECONDS: float = 0.5
    # 主从延迟降级阈值（秒）：超过则读请求自动降级走主库，避免脏读
    REPLICA_LAG_DEGRADE_SECONDS: float = 2.0
    # 延迟探测周期（秒）：从库 SHOW REPLICA STATUS 采样间隔
    REPLICA_LAG_PROBE_INTERVAL_SECONDS: int = 15
    # 写后读一致性窗口（秒）：写操作后 N 秒内的读强制走主库
    READ_AFTER_WRITE_WINDOW_SECONDS: float = 5.0
    # 读写分离总开关：False 时所有读请求走主库（灰度回退用）
    READ_WRITE_SPLIT_ENABLED: bool = True

    # ── 分布式执行引擎 Celery（Phase 1 Task 3）──
    # 【已冻结 2026-09-18】整套 Celery 基础设施从未接线（默认关闭且全库无 .delay() 调用），
    # 代码已移至 app/tasks/_frozen/，依赖亦从 requirements.txt 移除。
    # 以下配置键保留仅为兼容既有 .env / 部署配置，当前无代码读取；
    # 恢复方法见 app/tasks/_frozen/README.md。参见《架构优化与简化分析》§4 R0-2。
    # 业务用途：测试任务分布式调度，≥50 并发，Worker 水平扩展
    # 边界场景：CELERY_ENABLED=False 时端点走同步执行路径（灰度回退用）
    CELERY_ENABLED: bool = False
    # Celery broker/backend URL，默认复用 Redis（DB 0=broker，DB 2=backend）
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    # Worker 并发数：gevent/eventlet 池推荐 CPU*2
    CELERY_WORKER_CONCURRENCY: int = 4
    # Worker 预取数：长任务场景设为 1 避免饿死队列
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1
    # 任务硬超时（秒）：超时强制终止
    CELERY_TASK_TIME_LIMIT: int = 3600
    # 任务软超时（秒）：超时抛 SoftTimeLimitExceeded，任务可捕获清理
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3000
    # 任务最大重试次数
    CELERY_TASK_MAX_RETRIES: int = 3
    # 任务确认时机：True 表示执行完成后才确认（崩溃任务重投）
    CELERY_TASK_ACKS_LATE: bool = True
    # Beat 调度周期（秒）：pipeline_timeout_check 等任务执行间隔
    CELERY_BEAT_PIPELINE_TIMEOUT_INTERVAL: int = 3600

    # ── 任务超时监控（P1 E-08：超时任务自动停止）──
    # 业务用途：后台定时检测 RUNNING 状态任务，超过阈值自动标记 FAILED 并记录原因，
    #          防止僵死任务长期占用执行线程与连接资源
    # 边界场景：TIMEOUT_CHECK_INTERVAL<=0 时监控不启动（灰度关闭用）；
    #          start_time 为 NULL 的任务（未启动）不参与超时判定
    # 任务执行超时阈值（秒），默认 30 分钟
    TASK_TIMEOUT_SECONDS: int = 1800
    # 超时检测轮询间隔（秒），默认 60 秒
    TIMEOUT_CHECK_INTERVAL: int = 60

    # ── 智能调度 v1 Test Impact Analysis（Phase 1 Task 4）──
    # 业务用途：分析代码变更识别受影响测试，回归时间缩短 ≥50%
    # 边界场景：TIA_ENABLED=False 时全量执行用例（灰度回退用）
    TIA_ENABLED: bool = False
    # TIA 调度降级阈值：缩减比例低于此值时回退全量执行（避免收益过低）
    TIA_MIN_REDUCTION_RATIO: float = 0.2
    # 单次测试用例平均执行时长（秒），用于估算节省时间
    TIA_AVG_TEST_DURATION_SECONDS: float = 5.0
    # git diff 默认基准版本（相对当前 HEAD）
    TIA_GIT_BASE_REF: str = "HEAD~1"
    # git diff 默认目标版本
    TIA_GIT_TARGET_REF: str = "HEAD"

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

    @property
    def csrf_exempt_methods_list(self) -> List[str]:
        """获取CSRF豁免的HTTP方法列表（大写）。"""
        return [m.upper().strip() for m in parse_list(self.SECURITY_CSRF_EXEMPT_METHODS)]

    @property
    def csrf_exempt_paths_list(self) -> List[str]:
        """获取CSRF豁免的路径列表（精确匹配，去除空白）。

        业务用途：SAML ACS 等 IdP 回调端点由外部 POST，无法携带 CSRF token，
        已通过 RelayState/state 机制实现 CSRF 防护。
        """
        return [p.strip() for p in parse_list(self.SECURITY_CSRF_EXEMPT_PATHS) if p.strip()]

    @property
    def hsts_header_value(self) -> str:
        """构造 HSTS 响应头值：max-age=...; includeSubDomains; preload。"""
        if not self.SECURITY_HSTS_ENABLED:
            return ""
        parts = [f"max-age={self.SECURITY_HSTS_MAX_AGE}"]
        if self.SECURITY_HSTS_INCLUDE_SUBDOMAINS:
            parts.append("includeSubDomains")
        if self.SECURITY_HSTS_PRELOAD:
            parts.append("preload")
        return "; ".join(parts)

    @property
    def oidc_idp_configs_list(self) -> List[dict]:
        """解析 OIDC_IDP_CONFIGS 为 IdP 配置字典列表。

        每项结构：{"provider": str, "client_id": str, "client_secret": str,
                 "issuer": str, "discovery_url": str, "scopes": str, "redirect_uri": str}
        """
        if not self.OIDC_IDP_CONFIGS:
            return []
        try:
            configs = parse_list(self.OIDC_IDP_CONFIGS)
            return [c for c in configs if isinstance(c, dict) and c.get("provider")]
        except Exception:
            return []

    def get_oidc_provider_config(self, provider: str) -> Optional[dict]:
        """按 provider 标识查找 IdP 配置。

        Args:
            provider: IdP 标识（如 google/azure/okta）

        Returns:
            Optional[dict]: 匹配的 IdP 配置；未找到返回 None
        """
        for cfg in self.oidc_idp_configs_list:
            if cfg.get("provider") == provider:
                return cfg
        return None

    @property
    def saml_idp_configs_list(self) -> List[dict]:
        """解析 SAML_IDP_CONFIGS 为 IdP 配置字典列表。

        每项结构：{"provider": str, "entity_id": str, "sso_url": str,
                 "slo_url": str, "x509_cert": str, "nameid_format": str}
        """
        if not self.SAML_IDP_CONFIGS:
            return []
        try:
            configs = parse_list(self.SAML_IDP_CONFIGS)
            return [c for c in configs if isinstance(c, dict) and c.get("provider")]
        except Exception:
            return []

    def get_saml_provider_config(self, provider: str) -> Optional[dict]:
        """按 provider 标识查找 SAML IdP 配置。

        Args:
            provider: IdP 标识（如 okta/azure/adfs）

        Returns:
            Optional[dict]: 匹配的 IdP 配置；未找到返回 None
        """
        for cfg in self.saml_idp_configs_list:
            if cfg.get("provider") == provider:
                return cfg
        return None

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
