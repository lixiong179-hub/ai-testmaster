"""密钥管理模块 - 密钥生成、缓存与安全校验"""
import json
import logging
import os
import secrets
import warnings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

_logger = logging.getLogger(__name__)

_DEFAULT_PATTERNS = [
    'your-', 'your_', 'here', 'password', 'changeme',
    'example', 'test1234', 'secret', 'xxx'
]


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
        pass
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
        warnings.warn(f"无法保存密钥到文件: {e}")


def is_default_value(value: str) -> bool:
    """检查配置值是否为默认/示例值。"""
    if not value:
        return True
    value_lower = value.lower()
    return any(pattern in value_lower for pattern in _DEFAULT_PATTERNS)


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

    if not settings_instance.DATABASE_URL:
        raise ValueError(
            "DATABASE_URL 未配置！请在 .env 文件中设置 MySQL 连接字符串，"
            "例如: mysql+pymysql://user:password@localhost:3306/ai_testmaster"
        )

    if settings_instance.DATABASE_URL.startswith("sqlite"):
        raise ValueError(
            "禁止使用 SQLite 数据库！请配置 MySQL 连接字符串。"
            "项目要求必须使用 MySQL。"
        )

    if not settings_instance.AI_API_KEY and settings_instance.DEEPSEEK_API_KEY:
        settings_instance.AI_API_KEY = settings_instance.DEEPSEEK_API_KEY

    if not settings_instance.DEEPSEEK_API_KEY and settings_instance.AI_API_KEY:
        settings_instance.DEEPSEEK_API_KEY = settings_instance.AI_API_KEY

    if settings_instance.ENVIRONMENT == "prod":
        if is_default_value(settings_instance.DEEPSEEK_API_KEY):
            raise ValueError(
                "生产环境检测到DEEPSEEK_API_KEY使用了默认值！"
                "请在 .env 中配置真实的 API 密钥。"
                "获取地址: https://platform.deepseek.com/"
            )
        if len(settings_instance.JWT_SECRET_KEY) < 32:
            raise ValueError(
                "生产环境JWT_SECRET_KEY长度不足（至少32字符）！"
                "请使用强随机密钥。生成命令: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
    else:
        if is_default_value(settings_instance.DEEPSEEK_API_KEY):
            warnings.warn(
                "⚠️  DEEPSEEK_API_KEY 可能使用了默认值，AI功能可能无法正常工作。"
                "请在 .env 中配置真实的 API 密钥。",
                UserWarning
            )

    if not settings_instance.JWT_SECRET_KEY:
        settings_instance.JWT_SECRET_KEY = load_cached_key("jwt_secret_key", _key_cache_file)
    if not settings_instance.JWT_SECRET_KEY:
        if settings_instance.ENVIRONMENT == "prod":
            raise ValueError(
                "生产环境未设置JWT_SECRET_KEY，禁止自动生成！"
                "请通过环境变量 JWT_SECRET_KEY 设置强随机密钥。"
                "生成命令: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        settings_instance.JWT_SECRET_KEY = generate_secret_key()
        save_cached_key("jwt_secret_key", settings_instance.JWT_SECRET_KEY, _key_cache_file)

    if not settings_instance.ENCRYPTION_KEY:
        settings_instance.ENCRYPTION_KEY = load_cached_key("encryption_key", _key_cache_file)
    if not settings_instance.ENCRYPTION_KEY:
        if settings_instance.ENVIRONMENT == "prod":
            raise ValueError(
                "生产环境未设置ENCRYPTION_KEY，禁止自动生成！"
                "请通过环境变量 ENCRYPTION_KEY 设置加密密钥。"
                "生成命令: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        settings_instance.ENCRYPTION_KEY = generate_secret_key()
        save_cached_key("encryption_key", settings_instance.ENCRYPTION_KEY, _key_cache_file)

    if not settings_instance.ENCRYPTION_SALT:
        settings_instance.ENCRYPTION_SALT = load_cached_key("encryption_salt", _key_cache_file)
    if not settings_instance.ENCRYPTION_SALT:
        if settings_instance.ENVIRONMENT == "prod":
            raise ValueError(
                "生产环境未设置ENCRYPTION_SALT，禁止自动生成！"
                "请通过环境变量 ENCRYPTION_SALT 设置加密盐值。"
                "生成命令: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        settings_instance.ENCRYPTION_SALT = generate_secret_key()
        save_cached_key("encryption_salt", settings_instance.ENCRYPTION_SALT, _key_cache_file)

    if settings_instance.ENVIRONMENT == "prod" and (not settings_instance.CORS_ORIGINS or settings_instance.CORS_ORIGINS == "*"):
        raise ValueError(
            "生产环境必须配置 CORS_ORIGINS！禁止使用 '*' 通配符。"
            "请在 .env 中设置允许的域名，例如: CORS_ORIGINS=https://yourdomain.com"
        )
