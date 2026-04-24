"""
加密工具模块

提供基于Fernet对称加密的密码加密和解密功能，用于安全存储敏感数据（如数据库连接密码、
第三方API密钥等）。

安全设计要点：
1. 密钥派生：使用PBKDF2-HMAC-SHA256算法从ENCRYPTION_KEY派生Fernet密钥，
   迭代次数100000次，有效抵御暴力破解
2. 盐值隔离：ENCRYPTION_SALT与密钥分离存储，即使密钥泄露也无法直接解密
3. 环境区分：生产环境强制要求配置ENCRYPTION_KEY和ENCRYPTION_SALT，
   开发环境允许自动生成（仅用于本地调试）
4. 明文检测：解密时通过"gAAAAA"前缀识别Fernet密文格式，
   兼容历史遗留的明文密码数据
5. 安全失败：加密/解密失败时抛出ValueError，绝不返回明文或部分数据

核心函数：
    - encrypt_password: 加密明文密码
    - decrypt_password: 解密密文密码
    - mask_password: 掩码显示密码（日志脱敏）

依赖：
    - cryptography.fernet: Fernet对称加密实现
    - cryptography.hazmat.primitives.kdf.pbkdf2: PBKDF2密钥派生
    - app.core.config.settings: 加密密钥和盐值配置
"""
import base64
import os
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from loguru import logger


def _get_encryption_config() -> tuple:
    """获取加密配置（密钥和盐值）

    从全局settings读取ENCRYPTION_KEY和ENCRYPTION_SALT。
    生产环境未配置时抛出ValueError，开发环境自动生成随机值并输出警告。

    Returns:
        tuple: (encryption_key_bytes, encryption_salt_bytes) 编码后的密钥和盐值

    Raises:
        ValueError: 生产环境未配置ENCRYPTION_KEY或ENCRYPTION_SALT
    """
    from app.core.config import settings

    encryption_key = settings.ENCRYPTION_KEY
    encryption_salt = settings.ENCRYPTION_SALT

    # 如果没有配置，在开发/测试环境生成随机值
    if not encryption_key:
        if settings.ENVIRONMENT == "dev":
            logger.warning("未设置ENCRYPTION_KEY，使用自动生成的密钥（仅开发环境）")
            encryption_key = secrets.token_urlsafe(32)
        else:
            raise ValueError("生产环境必须设置ENCRYPTION_KEY环境变量")

    if not encryption_salt:
        if settings.ENVIRONMENT == "dev":
            logger.warning("未设置ENCRYPTION_SALT，使用随机盐值（仅开发环境）")
            encryption_salt = secrets.token_urlsafe(16)
        else:
            raise ValueError("生产环境必须设置ENCRYPTION_SALT环境变量")

    return encryption_key.encode(), encryption_salt.encode()


def _get_fernet() -> Fernet:
    """获取Fernet加密实例

    使用PBKDF2-HMAC-SHA256从ENCRYPTION_KEY派生32字节密钥，
    再编码为Fernet所需的URL安全base64格式。
    每次调用都重新派生，确保配置变更后立即生效。

    Returns:
        Fernet: 配置好的Fernet加密实例
    """
    encryption_key, salt = _get_encryption_config()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(encryption_key))
    return Fernet(key)


def encrypt_password(plain_password: str) -> str:
    """
    加密密码
    
    Args:
        plain_password: 明文密码
        
    Returns:
        加密后的密码（base64格式）
        
    Example:
        >>> encrypted = encrypt_password("my_password")
        >>> print(encrypted)  # 'gAAAAAB...'
    """
    if not plain_password:
        return ""
    
    try:
        f = _get_fernet()
        encrypted = f.encrypt(plain_password.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"密码加密失败: {e}")
        raise ValueError(f"密码加密失败，拒绝存储明文密码: {e}") from e


def decrypt_password(encrypted_password: str) -> str:
    """
    解密密码
    
    Args:
        encrypted_password: 加密后的密码
        
    Returns:
        明文密码
        
    Example:
        >>> plain = decrypt_password("gAAAAAB...")
        >>> print(plain)  # 'my_password'
    """
    if not encrypted_password:
        return ""
    
    if not encrypted_password.startswith("gAAAAA"):
        logger.warning("检测到非加密格式的密码数据，可能为历史遗留明文")
        return encrypted_password
    
    try:
        f = _get_fernet()
        decrypted = f.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"密码解密失败: {e}")
        raise ValueError(f"密码解密失败: {e}") from e


def mask_password(password: str) -> str:
    """掩码显示密码

    用于日志输出和API响应中的密码脱敏，始终返回固定掩码字符串。
    不论输入是明文还是密文，都统一返回"******"，避免通过掩码长度推断密码信息。

    Args:
        password: 密码（明文或密文）

    Returns:
        str: 固定6位星号掩码字符串，空输入返回空字符串
    """
    if not password:
        return ""
    return "******"


# 便捷函数别名，提供更简洁的调用方式
encrypt = encrypt_password
decrypt = decrypt_password


def verify_password(plain_password: str, encrypted_password: str) -> bool:
    """兼容旧测试导出的密码校验函数。"""

    if not plain_password and not encrypted_password:
        return True

    try:
        return decrypt_password(encrypted_password) == plain_password
    except Exception:
        return False
