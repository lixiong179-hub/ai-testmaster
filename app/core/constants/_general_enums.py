from enum import Enum, IntEnum


class ViewVisibility(IntEnum):
    HIDDEN = 0
    VISIBLE = 1


class ResponseCode(IntEnum):
    SUCCESS = 200
    VALIDATION_ERROR = 400
    PARAMETER_ERROR = 400
    NOT_FOUND = 404
    PERMISSION_DENIED = 403
    UNAUTHORIZED = 401
    TOKEN_EXPIRED = 401
    FILE_ERROR = 400
    DUPLICATE_ERROR = 409
    DATABASE_ERROR = 500
    API_ERROR = 500
    SERVER_ERROR = 500


class HTTPStatus(IntEnum):
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404


class Environment(str, Enum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"
