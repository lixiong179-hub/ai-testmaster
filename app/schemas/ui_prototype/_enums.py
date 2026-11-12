from enum import StrEnum


class UISourceEnum(StrEnum):
    UPLOAD = "upload"
    FETCH = "fetch"
    EXTRACT = "extract"


class ParseStatusEnum(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatusEnum(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UILinkAuthType(StrEnum):
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    COOKIE = "cookie"


UI_LINK_SOURCE_OPTIONS: list[dict] = [
    {"label": "直接上传", "value": UISourceEnum.UPLOAD.value},
    {"label": "URL抓取", "value": UISourceEnum.FETCH.value},
    {"label": "自动提取", "value": UISourceEnum.EXTRACT.value},
]
