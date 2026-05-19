"""环境配置档案 - 开发/测试/生产环境配置类"""
from app.core.config import Settings


class DevSettings(Settings):
    """开发环境配置 - DEBUG模式、CORS通配符、日志级别DEBUG。"""

    DEBUG: bool = True
    ENVIRONMENT: str = "dev"
    LOG_LEVEL: str = "DEBUG"
    CORS_ORIGINS: str = "*"


class TestSettings(Settings):
    """测试环境配置 - 关闭DEBUG、日志级别INFO、适度安全检查。"""

    DEBUG: bool = False
    ENVIRONMENT: str = "test"
    LOG_LEVEL: str = "INFO"


class ProdSettings(Settings):
    """生产环境配置 - 最高安全等级、严格校验、日志级别WARNING。"""

    DEBUG: bool = False
    ENVIRONMENT: str = "prod"
    LOG_LEVEL: str = "WARNING"
    CORS_ORIGINS: str = ""
