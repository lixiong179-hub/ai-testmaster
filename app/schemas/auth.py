"""
认证模块 Schema - 登录/注册/令牌相关的请求与响应模型

本模块定义了认证流程中所有API的数据契约，包括：
- LoginRequest: 用户登录请求，对应 POST /api/v1/auth/login
- RegisterRequest: 用户注册请求，对应 POST /api/v1/auth/register
- TokenResponse: JWT令牌响应，登录/注册成功后返回
- UserInfoResponse: 用户信息响应，获取当前用户详情时返回

与Model的对应关系：
- 认证过程不直接映射单一Model，而是操作 User Model (app.models.user.User)
- UserInfoResponse 映射 User Model 的部分字段，通过 from_attributes 支持 ORM 对象转换
"""
from pydantic import BaseModel, Field, EmailStr, model_validator
from datetime import datetime


class LoginRequest(BaseModel):
    """
    用户登录请求模型

    业务用途：用户通过用户名+密码进行身份认证
    验证规则：用户名3-50字符，密码6-100字符
    对应API：POST /api/v1/auth/login
    """
    username: str = Field(..., min_length=3, max_length=50, description="用户名")  # 必填，与User.username对应
    password: str = Field(..., min_length=6, max_length=100, description="密码")  # 必填，明文传输，服务端校验hash


class RegisterRequest(BaseModel):
    """
    用户注册请求模型

    业务用途：新用户注册账号，需确认密码一致性
    验证规则：
        - 用户名3-50字符
        - 邮箱格式校验（EmailStr）
        - 密码6-100字符
        - confirm_password 必须与 password 一致（model_validator校验）
    对应API：POST /api/v1/auth/register
    """
    username: str = Field(..., min_length=3, max_length=50, description="用户名")  # 必填，注册后作为登录标识，唯一
    email: EmailStr = Field(..., description="邮箱")  # 必填，Pydantic EmailStr自动校验格式，与User.email对应
    password: str = Field(..., min_length=6, max_length=100, description="密码")  # 必填，最小6位保证基本安全性
    confirm_password: str = Field(..., min_length=6, max_length=100, description="确认密码")  # 必填，需与password一致

    @model_validator(mode='after')
    def passwords_match(self) -> 'RegisterRequest':
        """
        模型级验证器：校验两次输入密码是否一致

        使用 mode='after' 在所有字段验证通过后执行，
        避免字段级别验证未通过时触发不必要的密码比对
        """
        if self.password != self.confirm_password:
            raise ValueError('password and confirm_password do not match')
        return self


class TokenResponse(BaseModel):
    """
    Token响应模型

    业务用途：登录/注册成功后返回JWT访问令牌
    对应API：POST /api/v1/auth/login 和 POST /api/v1/auth/register 的成功响应
    """
    access_token: str  # JWT访问令牌，前端存储后每次请求携带
    token_type: str = "bearer"  # 令牌类型，OAuth2标准默认为bearer
    expires_in: int = 1800  # 令牌有效期（秒），默认30分钟，过期后需重新登录获取


class UserInfoResponse(BaseModel):
    """
    用户信息响应模型

    业务用途：获取当前登录用户的详细信息，用于前端展示用户状态
    对应API：GET /api/v1/auth/me
    与Model映射：映射自 User Model (app.models.user.User)，不含敏感字段（password_hash等）
    """
    id: int  # 用户唯一标识，与User.id对应
    username: str  # 用户名，与User.username对应
    email: str  # 邮箱地址，与User.email对应
    is_active: bool  # 账户是否激活，与User.is_active对应，禁用用户无法登录
    created_at: datetime = Field(alias="create_time")
    roles: list[str]  # 用户角色列表，通过User.roles关系获取，用于前端权限控制

    class Config:
        from_attributes = True
        populate_by_name = True
