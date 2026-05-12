"""
用户与权限模块 Schema - 用户/角色/权限的请求与响应模型

本模块定义了用户管理、角色管理、权限管理以及认证相关的所有数据契约，包括：

用户Schema分层：
- UserBase: 用户基础字段（用户名、邮箱、手机号），作为Create/Response的公共父类
- UserCreate: 创建用户请求，继承UserBase并添加密码字段
- UserUpdate: 更新用户请求，所有字段可选，支持部分更新
- UserInDB: 数据库完整用户模型，包含所有持久化字段（含is_active/is_superuser等）
- User: 用户响应模型，不含update_time等内部字段
- UserWithRoles: 带角色信息的用户响应，嵌套Role列表

角色Schema分层：
- RoleBase: 角色基础字段（名称、描述）
- RoleCreate: 创建角色请求，可附带权限列表
- RoleUpdate: 更新角色请求，所有字段可选
- Role: 角色响应模型

权限Schema分层：
- PermissionBase: 权限基础字段（名称、编码、类型、父权限ID）
- PermissionCreate: 创建权限请求，直接继承Base
- PermissionUpdate: 更新权限请求，所有字段可选
- Permission: 权限响应模型

认证辅助Schema：
- UserLogin: 用户登录请求（与auth.py中的LoginRequest功能类似，保留兼容）
- Token: JWT令牌模型
- TokenData: 令牌解码后的数据模型

与Model的对应关系：
- User系列 -> app.models.user.User
- Role系列 -> app.models.user.Role
- Permission系列 -> app.models.user.Permission
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    """
    用户基础模型

    业务用途：定义用户的核心字段，作为UserCreate/UserInDB/User的公共父类
    验证规则：用户名3-50字符，邮箱格式校验，手机号11-20位纯数字
    与Model映射：对应 User Model 的 username/email/phone 字段
    """
    username: str = Field(..., min_length=3, max_length=50, description="用户名")  # 必填，唯一标识，与User.username对应
    email: EmailStr = Field(..., description="邮箱")  # 必填，EmailStr自动校验格式，与User.email对应
    phone: Optional[str] = Field(None, min_length=11, max_length=20, description="手机号")  # 可选，11-20位，默认None表示未填写

    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号：非空时必须为纯数字"""
        if v and not v.isdigit():
            raise ValueError('手机号必须是数字')
        return v


class UserCreate(UserBase):
    """
    创建用户请求模型

    业务用途：管理员创建新用户或用户自主注册
    验证规则：继承UserBase所有规则，密码最少6位
    对应API：POST /api/v1/users/
    与Model映射：字段对应 User Model 的 username/email/phone/password_hash
    """
    password: str = Field(..., min_length=6, description="密码")  # 必填，最少6位，服务端存储为password_hash

    @validator('password')
    def validate_password(cls, v):
        """验证密码强度：最少6位"""
        if len(v) < 6:
            raise ValueError('密码长度至少6位')
        return v


class UserUpdate(BaseModel):
    """
    更新用户请求模型

    业务用途：修改用户信息，支持部分更新（PATCH语义）
    验证规则：所有字段可选，仅更新传入的字段
    对应API：PUT/PATCH /api/v1/users/{user_id}
    与Model映射：字段对应 User Model 的 email/phone/is_active
    """
    email: Optional[EmailStr] = None  # 可选，更新邮箱
    phone: Optional[str] = None  # 可选，更新手机号
    status: Optional[bool] = None  # 可选，更新激活状态，True=启用/False=禁用

    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号：非空时必须为纯数字"""
        if v and not v.isdigit():
            raise ValueError('手机号必须是数字')
        return v


class UserInDB(UserBase):
    """
    数据库中的用户完整模型

    业务用途：内部使用，包含数据库中所有用户字段，用于服务层内部传递
    不直接暴露给API，避免泄露is_superuser等敏感字段
    与Model映射：完整映射 User Model 的所有业务字段
    """
    id: int  # 用户主键ID，与User.id对应
    is_active: bool  # 账户是否激活，与User.is_active对应
    is_superuser: bool  # 是否超级管理员，与User.is_superuser对应
    create_time: datetime  # 创建时间，与User.create_time对应
    update_time: datetime  # 更新时间，与User.update_time对应

    class Config:
        # 启用ORM模式，支持从User Model直接读取属性
        from_attributes = True


class User(UserBase):
    """
    用户响应模型

    业务用途：API返回用户信息时使用，不包含update_time等内部字段
    对应API：GET /api/v1/users/{user_id}
    与Model映射：映射 User Model 的部分字段，不含password_hash/update_time
    """
    id: int  # 用户主键ID
    is_active: bool  # 账户是否激活
    is_superuser: bool  # 是否超级管理员
    create_time: datetime  # 创建时间

    class Config:
        # 启用ORM模式，支持从User Model直接读取属性
        from_attributes = True


class UserWithRoles(User):
    """
    带角色的用户响应模型

    业务用途：需要展示用户角色信息时使用，如用户详情页
    嵌套关系：继承User，额外包含roles列表（嵌套Role Schema）
    对应API：GET /api/v1/users/{user_id}（含角色信息时）
    """
    roles: List['Role'] = []  # 用户关联的角色列表，默认空列表，通过User.roles关系获取


class RoleBase(BaseModel):
    """
    角色基础模型

    业务用途：定义角色的核心字段，作为RoleCreate/RoleUpdate/Role的公共父类
    验证规则：角色名称1-50字符，描述最多200字符
    与Model映射：对应 Role Model 的 name/desc 字段
    """
    name: str = Field(..., min_length=1, max_length=50, description="角色名称")  # 必填，如"管理员"/"测试人员"
    desc: Optional[str] = Field(None, max_length=200, description="角色描述")  # 可选，角色功能说明


class RoleCreate(RoleBase):
    """
    创建角色请求模型

    业务用途：管理员创建新角色
    验证规则：继承RoleBase，可附带权限编码列表
    对应API：POST /api/v1/roles/
    与Model映射：permissions字段对应 Role Model 的 JSON 类型 permissions 列
    """
    permissions: Optional[List[str]] = Field(None, description="权限列表")  # 可选，权限编码列表，如["user:read", "user:write"]


class RoleUpdate(RoleBase):
    """
    更新角色请求模型

    业务用途：修改角色信息，支持部分更新
    验证规则：所有字段可选，覆盖父类的必填约束为可选
    对应API：PUT/PATCH /api/v1/roles/{role_id}
    """
    # 更新场景允许部分字段缺省，因此覆盖父类字段为Optional
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="角色名称")  # 可选，更新角色名称
    desc: Optional[str] = Field(None, max_length=200, description="角色描述")  # 可选，更新角色描述
    permissions: Optional[List[str]] = Field(None, description="权限列表")  # 可选，更新权限编码列表


class Role(RoleBase):
    """
    角色响应模型

    业务用途：API返回角色信息时使用
    对应API：GET /api/v1/roles/{role_id}
    与Model映射：映射 Role Model 的 id/name/desc/permissions/create_time
    """
    id: int  # 角色主键ID
    permissions: Optional[List[str]] = None  # 权限编码列表，JSON存储，可能为空
    create_time: datetime  # 创建时间

    class Config:
        # 启用ORM模式，支持从Role Model直接读取属性
        from_attributes = True


class PermissionBase(BaseModel):
    """
    权限基础模型

    业务用途：定义权限的核心字段，作为PermissionCreate/PermissionUpdate/Permission的公共父类
    验证规则：名称和编码1-50字符，类型为menu/button/api之一
    与Model映射：对应 Permission Model 的 name/code/type/parent_id 字段
    """
    name: str = Field(..., min_length=1, max_length=50, description="权限名称")  # 必填，如"用户管理"/"创建项目"
    code: str = Field(..., min_length=1, max_length=50, description="权限编码")  # 必填，唯一标识，如"user:manage"/"project:create"
    type: str = Field(..., description="权限类型：menu/button/api")  # 必填，区分菜单权限/按钮权限/接口权限
    parent_id: Optional[int] = Field(None, description="父权限ID")  # 可选，支持树形权限结构，None表示顶级权限


class PermissionCreate(PermissionBase):
    """
    创建权限请求模型

    业务用途：管理员创建新权限项
    验证规则：直接继承PermissionBase，所有字段必填（parent_id除外）
    对应API：POST /api/v1/permissions/
    """
    pass


class PermissionUpdate(PermissionBase):
    """
    更新权限请求模型

    业务用途：修改权限信息，支持部分更新
    验证规则：所有字段可选，覆盖父类的必填约束为可选
    对应API：PUT/PATCH /api/v1/permissions/{permission_id}
    """
    # 更新场景允许部分字段缺省，因此覆盖父类字段为Optional
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="权限名称")  # 可选
    code: Optional[str] = Field(None, min_length=1, max_length=50, description="权限编码")  # 可选
    type: Optional[str] = Field(None, description="权限类型：menu/button/api")  # 可选
    parent_id: Optional[int] = Field(None, description="父权限ID")  # 可选


class Permission(PermissionBase):
    """
    权限响应模型

    业务用途：API返回权限信息时使用
    对应API：GET /api/v1/permissions/{permission_id}
    与Model映射：映射 Permission Model 的 id/name/code/type/parent_id/create_time
    """
    id: int  # 权限主键ID
    create_time: datetime  # 创建时间

    class Config:
        # 启用ORM模式，支持从Permission Model直接读取属性
        from_attributes = True


class UserLogin(BaseModel):
    """
    用户登录模型

    业务用途：用户名密码登录（与auth.py中LoginRequest功能类似，保留兼容旧接口）
    对应API：POST /api/v1/auth/login
    """
    username: str = Field(..., description="用户名")  # 必填，登录标识
    password: str = Field(..., description="密码")  # 必填，明文传输


class Token(BaseModel):
    """
    Token模型

    业务用途：JWT令牌数据结构（与auth.py中TokenResponse功能类似，保留兼容旧接口）
    """
    access_token: str  # JWT访问令牌
    token_type: str  # 令牌类型，通常为"bearer"
    expires_in: int  # 有效期（秒）


class TokenData(BaseModel):
    """
    Token数据模型

    业务用途：JWT令牌解码后提取的数据，用于身份识别
    仅包含user_id，服务端根据user_id查询完整用户信息
    """
    user_id: Optional[int] = None  # 令牌中携带的用户ID，None表示无效令牌


# 解决UserWithRoles中Role前向引用的循环依赖问题
# UserWithRoles.roles引用了Role类，但Role定义在UserWithRoles之后
# update_forward_refs()在所有类定义完成后，将字符串引用替换为实际类对象
UserWithRoles.update_forward_refs()
