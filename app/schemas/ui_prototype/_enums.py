from enum import Enum
from typing import List


class UISourceEnum(str, Enum):
    UPLOAD = "upload"
    FETCH = "fetch"
    EXTRACT = "extract"


class ParseStatusEnum(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatusEnum(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UILinkAuthType(str, Enum):
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    COOKIE = "cookie"


UI_LINK_SOURCE_OPTIONS: List[dict] = [
    {"label": "直接上传", "value": UISourceEnum.UPLOAD.value},
    {"label": "URL抓取", "value": UISourceEnum.FETCH.value},
    {"label": "自动提取", "value": UISourceEnum.EXTRACT.value},
]
