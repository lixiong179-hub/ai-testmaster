"""密钥管理模块 - 密钥生成、缓存与安全校验"""

import json
import logging
import os
import secrets
import warnings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

_logger = logging.getLogger(__name__)

_DEFAULT_PATTERNS = ["your-", "your_", "here", "password", "changeme", "example", "test1234", "secret", "xxx"]


def _log_key_source(key_name: str, source: str, auto_generated: bool = False) -> None:
    """记录密钥来源审计日志。

    Args:
        key_name: 密钥配置项名称（如 JWT_SECRET_KEY）
        source: 密钥来源，取值为 env / cache / auto-generated
        auto_generated: 是否为本次自动生成，True 时使用 WARNING 级别并标记 AUTO_GENERATED

    日志格式：[KEY_AUDIT] key=<KEY_NAME> source=<source> [AUTO_GENERATED]
    注意：不记录密钥值本身，避免日志泄露。
    """
    if auto_generated:
        _logger.warning(f"[KEY_AUDIT] key={key_name} source={source} AUTO_GENERATED")
    else:
        _logger.info(f"[KEY_AUDIT] key={key_name} source={source}")


def generate_secret_key() -> str:
    """生成URL安全的高熵随机密钥（256位，43字符）。"""
    return secrets.token_urlsafe(32)


def load_cached_key(key_name: str, cache_file: Path) -> str:
    """从缓存文件加载指定密钥，未找到时返回空字符串。"""
    try:
        if cache_file.exists():
            cached = json.loads(cache_file.read_text())
            if key_name in cached and cached[key_name]:
                return cached[key_name]
    except Exception:
        _logger.exception("密钥缓存文件读取失败")
    return ""


def save_cached_key(key_name: str, value: str, cache_file: Path) -> None:
    """保存密钥到缓存文件，采用读取-合并-写入模式，权限0o600。"""
    try:
        cached = {}
        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text())
            except Exception:
                _logger.debug("读取密钥缓存文件失败", exc_info=True)
        cached[key_name] = value
        cache_file.write_text(json.dumps(cached))
        os.chmod(cache_file, 0o600)
    except Exception as e:
        _logger.error(f"密钥缓存文件保存失败: {e}", exc_info=True)
        warnings.warn(f"无法保存密钥到文件: {e}")


def is_default_value(value: str) -> bool:
    """检查配置值是否为默认/示例值。

    空字符串不属于弱默认值，而是"未设置"，由后续长度/非空检查处理。
    """
    if not value:
        return False
    value_lower = value.lower()
    return any(pattern in value_lower for pattern in _DEFAULT_PATTERNS)


def _validate_database_config(settings_instance) -> None:
    """数据库必须配置且禁止 SQLite。"""
    if not settings_instance.DATABASE_URL:
        raise ValueError(
            "DATABASE_URL 未配置！请在 .env 文件中设置 MySQL 连接字符串，"
            "例如: mysql+pymysql://user:password@localhost:3306/ai_testmaster"
        )
    if settings_instance.DATABASE_URL.startswith("sqlite"):
        raise ValueError("禁止使用 SQLite 数据库！请配置 MySQL 连接字符串。项目要求必须使用 MySQL。")


def _sync_ai_api_keys(settings_instance) -> None:
    """AI_API_KEY 与 DEEPSEEK_API_KEY 双向兜底。"""
    if not settings_instance.AI_API_KEY and settings_instance.DEEPSEEK_API_KEY:
        settings_instance.AI_API_KEY = settings_instance.DEEPSEEK_API_KEY
    if not settings_instance.DEEPSEEK_API_KEY and settings_instance.AI_API_KEY:
        settings_instance.DEEPSEEK_API_KEY = settings_instance.AI_API_KEY


def _validate_prod_key_strength(settings_instance, key_name: str, noun: str, weak_suffix: str = "") -> None:
    """生产环境校验单个密钥：弱默认值模式与最小长度。"""
    value = getattr(settings_instance, key_name, "") or ""
    if is_default_value(value):
        raise ValueError(
            f"生产环境{key_name}使用了弱默认值模式{weak_suffix}！"
            f"请通过环境变量 {key_name} 设置{noun}。"
            '生成命令: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    if len(value) < 32:
        raise ValueError(
            f"生产环境{key_name}长度不足（至少32字符）！"
            f'请使用{noun}。生成命令: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )


def _require_prod_deepseek_key(settings_instance) -> None:
    """生产环境必须配置真实 DEEPSEEK_API_KEY。"""
    api_key = settings_instance.DEEPSEEK_API_KEY
    if not api_key or is_default_value(api_key):
        raise ValueError(
            "生产环境DEEPSEEK_API_KEY未配置或使用了默认值！"
            "请在 .env 中配置真实的 API 密钥。"
            "获取地址: https://platform.deepseek.com/"
        )


def _warn_dev_secret_policy(settings_instance) -> None:
    """非生产环境对缺省/弱默认值密钥发出告警（不阻断启动）。"""
    api_key = settings_instance.DEEPSEEK_API_KEY
    if not api_key or is_default_value(api_key):
        warnings.warn(
            "⚠️  DEEPSEEK_API_KEY 未配置或可能使用了默认值，AI功能可能无法正常工作。请在 .env 中配置真实的 API 密钥。",
            UserWarning,
        )
    for key_name in ("JWT_SECRET_KEY", "ENCRYPTION_KEY", "ENCRYPTION_SALT"):
        key_value = getattr(settings_instance, key_name, "")
        if key_value and is_default_value(key_value):
            warnings.warn(
                f"⚠️  {key_name} 检测到弱默认值模式，生产环境将拒绝启动。请使用强随机密钥。",
                UserWarning,
            )


def _enforce_secret_policy(settings_instance) -> None:
    """生产环境严格校验密钥；非生产仅告警。"""
    if settings_instance.ENVIRONMENT != "prod":
        _warn_dev_secret_policy(settings_instance)
        return
    _require_prod_deepseek_key(settings_instance)
    # 安全收紧：JWT/加密密钥既校验长度也校验是否为弱默认值模式
    # 防止 "your-secret-key-here-padding-to-32-chars" 等绕过长度检查的弱密钥
    _validate_prod_key_strength(
        settings_instance,
        "JWT_SECRET_KEY",
        "强随机密钥",
        weak_suffix="（包含 your-/changeme/secret 等关键字）",
    )
    _validate_prod_key_strength(settings_instance, "ENCRYPTION_KEY", "强随机密钥")
    _validate_prod_key_strength(settings_instance, "ENCRYPTION_SALT", "强随机盐值")


def _ensure_single_key(
    settings_instance,
    key_name: str,
    cache_name: str,
    cache_file: Path,
    noun: str,
) -> None:
    """三级回退：环境变量 → 缓存文件 → 自动生成（生产环境禁止自动生成）。"""
    if getattr(settings_instance, key_name):
        _log_key_source(key_name, "env")
        return

    cached_value = load_cached_key(cache_name, cache_file)
    if cached_value:
        setattr(settings_instance, key_name, cached_value)
        _log_key_source(key_name, "cache")
        return

    if settings_instance.ENVIRONMENT == "prod":
        raise ValueError(
            f"生产环境未设置{key_name}，禁止自动生成！"
            f"请通过环境变量 {key_name} 设置{noun}。"
            '生成命令: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    new_value = generate_secret_key()
    setattr(settings_instance, key_name, new_value)
    save_cached_key(cache_name, new_value, cache_file)
    _log_key_source(key_name, "auto-generated", auto_generated=True)


def _validate_prod_cors(settings_instance) -> None:
    """生产环境禁止 CORS 使用 '*' 通配符。"""
    if settings_instance.ENVIRONMENT != "prod":
        return
    if not settings_instance.CORS_ORIGINS or settings_instance.CORS_ORIGINS == "*":
        raise ValueError(
            "生产环境必须配置 CORS_ORIGINS！禁止使用 '*' 通配符。"
            "请在 .env 中设置允许的域名，例如: CORS_ORIGINS=https://yourdomain.com"
        )
    if not settings_instance.CORS_ALLOW_HEADERS or settings_instance.CORS_ALLOW_HEADERS.strip() == "*":
        raise ValueError(
            "生产环境必须配置 CORS_ALLOW_HEADERS！禁止使用 '*' 通配符。"
            "请在 .env 中设置允许的请求头白名单，"
            "例如: CORS_ALLOW_HEADERS=Authorization,Content-Type,Accept,Origin"
        )


def ensure_secret_keys(settings_instance) -> None:
    """确保必要的安全密钥已设置，支持持久化到文件以跨重启复用。

    执行流程：
    1. 数据库连接校验（必填、禁止SQLite）
    2. 密钥安全性检查（生产环境严格校验，非生产仅警告）
    3. 密钥自动生成与持久化（三级回退：环境变量 → 缓存文件 → 自动生成）
    4. 生产环境CORS安全检查

    Raises:
        ValueError: 数据库未配置/使用SQLite/生产环境密钥不合规/CORS不合规
    """
    _key_cache_file = BASE_DIR / ".secret_keys"

    _validate_database_config(settings_instance)
    _sync_ai_api_keys(settings_instance)
    _enforce_secret_policy(settings_instance)

    _ensure_single_key(settings_instance, "JWT_SECRET_KEY", "jwt_secret_key", _key_cache_file, "强随机密钥")
    _ensure_single_key(settings_instance, "ENCRYPTION_KEY", "encryption_key", _key_cache_file, "加密密钥")
    _ensure_single_key(settings_instance, "ENCRYPTION_SALT", "encryption_salt", _key_cache_file, "加密盐值")

    _validate_prod_cors(settings_instance)
