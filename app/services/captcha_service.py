"""验证码服务 - 服务端验证码的生成与校验。

本模块实现服务端验证码的生成、存储和校验功能，采用单例模式
确保全局只有一个验证码服务实例。

核心类:
    - CaptchaService: 验证码服务（单例模式）

核心实例:
    - captcha_service: 全局单例实例

安全特性:
    1. 验证码存储在服务端内存，不暴露给客户端
    2. 验证码一次性使用，校验后立即失效
    3. 验证码5分钟过期
    4. 限制同一IP的获取频率（每分钟最多10次）
    5. 校验不区分大小写

存储设计:
    - _store: 验证码存储字典 {captcha_id: (code, expire_time)}
    - _used: 已使用的captcha_id集合，防止重放攻击
    - _ip_limits: IP频率限制 {ip: [timestamp_list]}

清理策略:
    当存储的验证码数量超过100时，自动清理过期记录。
    已使用记录集合保留最近1000条，防止内存泄漏。
"""
import os
import random
import string
import time
from typing import Tuple
from collections import defaultdict
from loguru import logger


class CaptchaService:
    """验证码服务 - 单例模式，管理验证码的生成与校验。

    职责:
        - 生成随机数字验证码
        - 存储验证码并设置过期时间
        - 校验用户输入的验证码
        - IP频率限制
        - 过期验证码自动清理

    使用场景:
        - 登录页面验证码生成与校验
        - 敏感操作的二次验证

    安全设计:
        - 验证码仅存储在服务端，客户端只持有captcha_id
        - 验证码一次性使用，防止重放攻击
        - IP频率限制，防止暴力获取验证码
    """

    _instance = None
    _rate_limit: int = int(os.getenv("CAPTCHA_RATE_LIMIT", "10"))

    def __new__(cls):
        """单例模式实现，确保全局只有一个验证码服务实例。"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._store = {}  # {captcha_id: (code, expire_time)}
            cls._instance._used = set()   # 已使用的captcha_id
            cls._instance._ip_limits = defaultdict(list)  # IP频率限制
        return cls._instance

    def generate(self, length: int = 4, ip: str = "") -> Tuple[str, str]:
        """生成验证码，返回唯一ID和验证码文本。

        生成流程:
            1. 检查IP频率限制（每分钟最多10次）
            2. 生成随机数字验证码
            3. 生成唯一captcha_id
            4. 存储验证码，设置5分钟过期时间
            5. 触发过期清理（存储超过100条时）

        Args:
            length: 验证码长度，默认4位。
            ip: 客户端IP地址，用于频率限制。

        Returns:
            元组(captcha_id, captcha_code):
                - captcha_id: 验证码唯一标识，返回给客户端
                - captcha_code: 验证码文本，展示给用户

        Raises:
            Exception: IP请求频率超限。
        """
        # 检查IP频率限制（每分钟最多10次）
        current_time = time.time()
        self._ip_limits[ip] = [t for t in self._ip_limits[ip] if current_time - t < 60]

        if len(self._ip_limits[ip]) >= self._rate_limit:
            raise Exception("请求过于频繁，请稍后再试")

        self._ip_limits[ip].append(current_time)

        # 生成随机数字验证码
        chars = string.digits
        code = ''.join(random.choices(chars, k=length))

        # 生成唯一ID（32位随机字母数字组合）
        captcha_id = ''.join(random.choices(
            string.ascii_letters + string.digits,
            k=32
        ))

        # 存储验证码，5分钟过期
        expire_time = current_time + 300  # 5分钟
        self._store[captcha_id] = (code, expire_time)

        # 清理过期的验证码（每100次生成清理一次）
        if len(self._store) > 100:
            self._cleanup()

        logger.debug(f"生成验证码: id={captcha_id[:8]}..., ip={ip}")

        return captcha_id, code

    def verify(self, captcha_id: str, user_input: str, ip: str = "") -> bool:
        """校验验证码，支持一次性使用和不区分大小写。

        校验流程:
            1. 参数非空检查
            2. 已使用检查（防止重放攻击）
            3. 存在性检查
            4. 过期检查
            5. 值匹配检查（不区分大小写）
            6. 校验成功后标记为已使用

        Args:
            captcha_id: 验证码ID。
            user_input: 用户输入的验证码。
            ip: 客户端IP，用于日志记录。

        Returns:
            校验通过返回True，失败返回False。
        """
        if not captcha_id or not user_input:
            return False

        # 检查是否已使用（防止重放攻击）
        if captcha_id in self._used:
            logger.warning(f"验证码已被使用: id={captcha_id[:8]}...")
            return False

        # 获取存储的验证码
        record = self._store.get(captcha_id)
        if not record:
            logger.warning(f"验证码不存在或已过期: id={captcha_id[:8]}...")
            return False

        stored_code, expire_time = record

        # 检查是否过期
        if time.time() > expire_time:
            del self._store[captcha_id]
            logger.warning(f"验证码已过期: id={captcha_id[:8]}...")
            return False

        # 校验验证码（不区分大小写）
        is_valid = stored_code.lower() == user_input.strip().lower()

        if is_valid:
            # 标记为已使用（一次性），防止重放攻击
            self._used.add(captcha_id)
            del self._store[captcha_id]
            logger.info(f"验证码校验成功: id={captcha_id[:8]}..., ip={ip}")
        else:
            logger.warning(f"验证码校验失败: id={captcha_id[:8]}..., 输入={user_input}, 正确={stored_code}")

        return is_valid

    def _cleanup(self):
        """清理过期的验证码和过大的已使用记录集合。

        清理策略:
            - 删除所有过期的验证码记录
            - 已使用记录集合保留最近1000条
        """
        current_time = time.time()
        expired_keys = [
            k for k, (_, exp) in self._store.items()
            if current_time > exp
        ]

        for key in expired_keys:
            del self._store[key]

        # 清理已使用记录，只保留最近1000个
        if len(self._used) > 0:
            self._used = set(list(self._used)[-1000:])

        if expired_keys:
            logger.debug(f"清理过期验证码: {len(expired_keys)} 个")


# 全局单例实例
captcha_service = CaptchaService()
