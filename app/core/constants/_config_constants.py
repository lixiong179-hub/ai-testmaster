from enum import Enum, IntEnum
from typing import List, Tuple

from app.core.constants._test_case_enums import (
    TestCasePriority,
    TestCaseType,
    TestCaseGenerateStatus,
    TestCaseReviewStatus,
)


DEFAULT_PRIORITY = TestCasePriority.MEDIUM
DEFAULT_CASE_TYPE = TestCaseType.UI_AUTOMATION
DEFAULT_AI_FALLBACK_CASE_TYPE = TestCaseType.MANUAL
DEFAULT_GENERATE_STATUS = TestCaseGenerateStatus.GENERATING
DEFAULT_REVIEW_STATUS = TestCaseReviewStatus.PENDING


from app.utils.file_utils import SUPPORTED_FILE_TYPES

FileExtension = Enum(
    'FileExtension',
    {ext.upper(): ext for ext in SUPPORTED_FILE_TYPES},
    type=str
)

ALLOWED_EXTENSIONS: List[str] = list(SUPPORTED_FILE_TYPES.keys())


class TimeoutConfig(IntEnum):
    DEFAULT_API = 30
    AI_API = 180
    UPLOAD = 60
    EXPORT = 60


class PaginationConfig(IntEnum):
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    MIN_PAGE_SIZE = 1


class SecurityConfig(IntEnum):
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 480
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7
    MIN_PASSWORD_LENGTH = 6
    MAX_LOGIN_ATTEMPTS = 5
    ACCOUNT_LOCKOUT_MINUTES = 30


LOGIN_KEYWORDS: List[str] = ["登录", "用户名", "密码", "验证码", "login", "username", "password"]

AUTH_FAILURE_KEYWORDS: Tuple[str, ...] = (
    "unauthorized", "forbidden", "permission", "认证失败", "无权限", "权限", "登录",
    "invalid", "incorrect", "expired", "token"
)
