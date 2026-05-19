"""
JWT令牌工具模块

提供JWT（JSON Web Token）的生成、验证和刷新功能，用于用户认证和授权。
采用双令牌机制：access_token（短期访问令牌）+ refresh_token（长期刷新令牌）。

令牌体系设计：
    - access_token: 短期令牌（默认配置的分钟级过期），用于API请求认证
    - refresh_token: 长期令牌（默认配置的天级过期），仅用于刷新access_token
    - 令牌类型通过payload中的"type"字段区分，防止refresh_token被当作access_token使用

安全设计：
    - 密码哈希使用bcrypt算法（通过passlib），自动处理盐值
    - JWT签名使用HS256算法，密钥从settings.JWT_SECRET_KEY读取
    - 令牌包含iat（签发时间）和exp（过期时间）标准声明
    - 使用timezone-aware UTC时间，兼容Python 3.12+（替代已弃用的utcnow）

核心函数：
    - create_access_token: 创建访问令牌
    - create_refresh_token: 创建刷新令牌
    - decode_token: 解码令牌
    - verify_access_token: 验证访问令牌
    - verify_refresh_token: 验证刷新令牌
    - refresh_access_token: 使用refresh_token刷新access_token
    - verify_password: 验证明文密码与哈希是否匹配
    - get_password_hash: 生成密码的bcrypt哈希

依赖：
    - python-jose[cryptography]: JWT编解码
    - passlib[bcrypt]: 密码哈希与验证
    - app.core.config.settings: JWT密钥、算法、过期时间配置
    - app.core.exception.AuthenticationError: 认证异常
"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exception import AuthenticationError
from app.utils.db_time import utcnow

# 密码加密上下文 — 使用bcrypt算法，自动处理版本迁移
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _encode_token(*, data: dict, token_type: str, expires_delta: timedelta) -> str:
    """编码JWT令牌的内部方法

    在payload中添加标准声明（exp过期时间、iat签发时间、type令牌类型），
    然后使用HS256算法签名。

    Args:
        data: 自定义payload数据（通常包含sub=用户ID）
        token_type: 令牌类型（"access"或"refresh"）
        expires_delta: 过期时间增量

    Returns:
        str: 编码后的JWT字符串
    """
    to_encode = data.copy()
    expire = utcnow() + expires_delta
    to_encode.update(
        {
            "exp": expire,
            "iat": utcnow(),
            "type": token_type,
        }
    )
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """创建访问令牌（type=access）

    Args:
        data: 自定义payload数据（通常包含sub=用户ID）
        expires_delta: 自定义过期时间，未指定时使用settings中的默认值

    Returns:
        str: 编码后的access JWT字符串
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    return _encode_token(data=data, token_type="access", expires_delta=expires_delta)


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """创建刷新令牌（type=refresh）

    Args:
        data: 自定义payload数据（通常包含sub=用户ID）
        expires_delta: 自定义过期时间，未指定时使用settings中的默认值

    Returns:
        str: 编码后的refresh JWT字符串
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    return _encode_token(data=data, token_type="refresh", expires_delta=expires_delta)

# 解码令牌
def decode_token(token: str) -> dict:
    """解码JWT令牌

    使用settings中配置的密钥和算法验证签名并解码令牌。
    不区分令牌类型，仅验证签名和过期时间。

    Args:
        token: JWT令牌字符串

    Returns:
        dict: 解码后的payload字典

    Raises:
        AuthenticationError: 令牌无效、过期或签名验证失败
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise AuthenticationError("Token无效") from e


def verify_access_token(token: str) -> dict:
    """验证访问令牌并返回payload

    解码令牌后额外验证type字段必须为"access"，防止refresh_token被当作access_token使用。

    Args:
        token: JWT令牌字符串

    Returns:
        dict: 验证通过的payload字典

    Raises:
        AuthenticationError: 令牌无效或类型不匹配
    """
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationError("Token类型错误：需要access token")
    return payload


def verify_refresh_token(token: str) -> dict:
    """验证刷新令牌并返回payload

    解码令牌后额外验证type字段必须为"refresh"，防止access_token被用于刷新操作。

    Args:
        token: JWT令牌字符串

    Returns:
        dict: 验证通过的payload字典

    Raises:
        AuthenticationError: 令牌无效或类型不匹配
    """
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise AuthenticationError("Token类型错误：需要refresh token")
    return payload


def refresh_access_token(refresh_token: str) -> str:
    """使用refresh_token刷新access_token

    验证refresh_token有效后，从中提取用户标识（sub），
    生成新的access_token。实现令牌无感续期。

    Args:
        refresh_token: 刷新令牌字符串

    Returns:
        str: 新的access JWT字符串

    Raises:
        AuthenticationError: refresh_token无效或缺少sub字段
    """
    from loguru import logger

    payload = verify_refresh_token(refresh_token)
    sub = payload.get("sub")
    if not sub:
        raise AuthenticationError("Token无效：缺少sub")

    logger.info(f"用户 {sub} 刷新了访问令牌")
    return create_access_token({"sub": str(sub)})

# 验证密码
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与bcrypt哈希是否匹配

    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的bcrypt哈希值

    Returns:
        bool: 匹配返回True，不匹配返回False
    """
    return pwd_context.verify(plain_password, hashed_password)

# 获取密码哈希
def get_password_hash(password: str) -> str:
    """生成密码的bcrypt哈希值

    passlib自动生成随机盐值并嵌入哈希结果中，无需单独存储盐值。

    Args:
        password: 明文密码

    Returns:
        str: bcrypt哈希字符串
    """
    return pwd_context.hash(password)
