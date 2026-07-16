"""环境配置档案 - 开发/测试/生产环境配置类"""
from app.core.config import Settings


class DevSettings(Settings):
    """开发环境配置 - DEBUG模式、日志级别DEBUG。

    安全收紧：不再默认 CORS_ORIGINS="*"，继承基类 localhost 白名单
    (5173/3000)。如需联调其他源，通过环境变量 CORS_ORIGINS 显式配置。
    生产环境由 key_management.ensure_secret_keys 强制校验禁止 "*"。
    """

    DEBUG: bool = True
    ENVIRONMENT: str = "dev"
    LOG_LEVEL: str = "DEBUG"


class TestSettings(Settings):
    """测试环境配置 - 关闭DEBUG、日志级别INFO、适度安全检查。"""

    __test__ = False
    DEBUG: bool = False
    ENVIRONMENT: str = "test"
    LOG_LEVEL: str = "INFO"


class ProdSettings(Settings):
    """生产环境配置 - 最高安全等级、严格校验、日志级别WARNING。"""

    DEBUG: bool = False
    ENVIRONMENT: str = "prod"
    LOG_LEVEL: str = "WARNING"
    CORS_ORIGINS: str = ""
