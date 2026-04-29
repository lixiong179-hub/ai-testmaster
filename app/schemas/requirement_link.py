"""
需求链接模块 Schema - 需求链接和UI原型图链接的请求与响应模型

本模块定义了外部需求资源链接管理的数据契约，支持带认证的外部资源访问，包括：

枚举类型：
- LinkTypeEnum: 链接类型枚举（需求文档/UI原型图/API文档/其他）
- AuthTypeEnum: 认证类型枚举（无认证/Basic Auth/Bearer Token/API Key/Cookie）

链接Schema分层：
- RequirementLinkBase: 链接基础字段（名称/类型/URL/认证/缓存配置）
- RequirementLinkCreate: 创建链接请求，含完整认证配置
- RequirementLinkUpdate: 更新链接请求，所有字段可选
- RequirementLinkResponse: 链接响应模型（认证脱敏）
- RequirementLinkDetailResponse: 链接详情响应（完整认证配置，仅管理员可见）

认证配置Schema：
- AuthConfigResponse: 认证配置响应（脱敏，仅显示是否有凭据）

列表与操作Schema：
- RequirementLinkListRequest: 链接列表查询请求
- RequirementLinkListResponse: 链接列表分页响应
- FetchContentRequest: 获取链接内容请求
- FetchContentResponse: 获取链接内容响应

用例生成上下文Schema：
- LinkContextRequest: 测试用例生成上下文请求
- LinkContextResponse: 测试用例生成上下文响应

与Model的对应关系：
- RequirementLink系列 -> app.models.requirement_link.RequirementLink
- 认证配置 -> RequirementLink.auth_config_encrypted (加密JSON字段)
- 缓存内容 -> RequirementLink.cached_content (Text字段)
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class LinkTypeEnum(str, Enum):
    """
    链接类型枚举

    业务用途：标识链接指向的资源类型，影响内容解析策略
    与Model映射：对应 RequirementLink.link_type 字段
    """
    REQUIREMENT = "requirement"  # 需求文档，如PRD/SRS/用户故事
    UI_MOCKUP = "ui_mockup"  # UI原型图，如Axure/Figma链接
    API_DOC = "api_doc"  # API文档，如Swagger/YApi
    OTHER = "other"  # 其他


class AuthTypeEnum(str, Enum):
    """
    认证类型枚举

    业务用途：标识访问链接资源时所需的认证方式
    与Model映射：对应 RequirementLink.auth_type 字段
    """
    NONE = "none"  # 无认证，公开可访问
    BASIC = "basic"  # Basic Auth (用户名+密码)
    BEARER = "bearer"  # Bearer Token
    API_KEY = "api_key"  # API Key
    COOKIE = "cookie"  # Cookie认证


class RequirementLinkBase(BaseModel):
    """
    需求链接基础模型

    业务用途：定义需求链接的核心字段，作为Create/Response的公共父类
    验证规则：
        - 链接名称1-200字符必填
        - 链接地址1-1000字符，必须以http/https/ftp开头
        - 缓存过期时间5-1440分钟
    与Model映射：对应 RequirementLink Model 的 link_name/link_type/link_url/auth_type/description/cache_expire_minutes 字段
    """
    link_name: str = Field(..., min_length=1, max_length=200, description="链接名称")  # 必填，如"需求文档_v1.2"/"Axure原型"
    link_type: LinkTypeEnum = Field(..., description="链接类型")  # 必填，区分资源类型
    link_url: str = Field(..., min_length=1, max_length=1000, description="链接地址")  # 必填，外部资源URL
    auth_type: AuthTypeEnum = Field(default=AuthTypeEnum.NONE, description="认证类型")  # 默认无认证
    description: Optional[str] = Field(None, max_length=1000, description="链接描述")  # 可选，链接说明
    cache_expire_minutes: int = Field(default=60, ge=5, le=1440, description="缓存过期时间（分钟）")  # 默认60分钟，最少5分钟，最多24小时

    @field_validator('link_url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """
        校验链接地址格式

        确保URL以标准协议开头，防止相对路径或非法格式
        """
        if not v.startswith(('http://', 'https://', 'ftp://')):
            raise ValueError('链接地址必须以 http://, https:// 或 ftp:// 开头')
        return v


class RequirementLinkCreate(RequirementLinkBase):
    """
    创建需求链接请求模型

    业务用途：添加外部需求资源链接，支持多种认证方式
    验证规则：继承Base，认证配置字段根据auth_type选择填写
    对应API：POST /api/v1/requirement-links/
    与Model映射：认证配置字段组合后加密存储到 RequirementLink.auth_config_encrypted
    """
    project_id: int = Field(..., description="项目ID")  # 必填，链接所属项目

    # 认证配置（根据auth_type提供不同的字段）
    # Basic Auth
    username: Optional[str] = Field(None, max_length=100, description="Basic Auth 用户名")  # 可选，auth_type=basic时使用
    password: Optional[str] = Field(None, max_length=200, description="Basic Auth 密码")  # 可选，auth_type=basic时使用

    # Bearer Token / API Key
    token: Optional[str] = Field(None, max_length=500, description="Token/Bearer Token")  # 可选，auth_type=bearer时使用
    api_key: Optional[str] = Field(None, max_length=500, description="API Key")  # 可选，auth_type=api_key时使用
    api_key_header: str = Field("X-API-Key", max_length=50, description="API Key的Header名称")  # 默认X-API-Key，auth_type=api_key时使用

    # Cookie认证
    cookie: Optional[str] = Field(None, max_length=1000, description="Cookie字符串")  # 可选，auth_type=cookie时使用


class RequirementLinkUpdate(BaseModel):
    """
    更新需求链接请求模型

    业务用途：修改链接信息，支持部分更新
    验证规则：所有字段可选
    对应API：PUT/PATCH /api/v1/requirement-links/{link_id}
    """
    link_name: Optional[str] = Field(None, min_length=1, max_length=200, description="链接名称")  # 可选
    link_type: Optional[LinkTypeEnum] = Field(None, description="链接类型")  # 可选
    link_url: Optional[str] = Field(None, min_length=1, max_length=1000, description="链接地址")  # 可选
    auth_type: Optional[AuthTypeEnum] = Field(None, description="认证类型")  # 可选
    description: Optional[str] = Field(None, max_length=1000, description="链接描述")  # 可选
    is_active: Optional[bool] = Field(None, description="是否启用")  # 可选，软删除/恢复
    cache_expire_minutes: Optional[int] = Field(None, ge=5, le=1440, description="缓存过期时间")  # 可选

    # 认证配置
    username: Optional[str] = Field(None, max_length=100, description="Basic Auth 用户名")  # 可选
    password: Optional[str] = Field(None, max_length=200, description="Basic Auth 密码")  # 可选
    token: Optional[str] = Field(None, max_length=500, description="Token")  # 可选
    api_key: Optional[str] = Field(None, max_length=500, description="API Key")  # 可选
    api_key_header: Optional[str] = Field(None, max_length=50, description="API Key的Header名称")  # 可选
    cookie: Optional[str] = Field(None, max_length=1000, description="Cookie字符串")  # 可选


class AuthConfigResponse(BaseModel):
    """
    认证配置响应模型（脱敏）

    业务用途：返回认证配置时脱敏处理，仅显示认证类型和是否有凭据
    安全考虑：不返回具体的密码/Token等敏感值，防止信息泄露
    """
    auth_type: AuthTypeEnum  # 认证类型
    has_credentials: bool  # 是否有凭据（不显示具体值），True=已配置/False=未配置

    class Config:
        # 启用ORM模式
        from_attributes = True


class RequirementLinkResponse(BaseModel):
    """
    需求链接响应模型

    业务用途：API返回链接信息时使用，认证配置已脱敏
    对应API：GET /api/v1/requirement-links/{link_id}
    与Model映射：映射 RequirementLink Model 的所有业务字段，auth_config脱敏处理
    """
    id: int  # 链接主键ID
    project_id: int  # 所属项目ID
    link_name: str  # 链接名称
    link_type: str  # 链接类型
    link_url: str  # 链接地址
    auth_type: str  # 认证类型
    auth_config: Optional[AuthConfigResponse] = None  # 脱敏后的认证配置，仅显示是否有凭据
    description: Optional[str]  # 链接描述
    is_active: bool  # 是否启用
    last_fetch_time: Optional[datetime]  # 最后获取时间
    last_fetch_status: Optional[str]  # 最后获取状态：success/failed
    cached_content: Optional[str] = None  # 缓存内容预览（可能为空或截断）
    cache_expire_minutes: int  # 缓存过期时间
    created_by: Optional[int]  # 创建人ID
    create_time: datetime  # 创建时间
    update_time: datetime  # 更新时间

    class Config:
        # 启用ORM模式，支持从RequirementLink Model直接读取属性
        from_attributes = True


class RequirementLinkDetailResponse(RequirementLinkResponse):
    """
    需求链接详情响应模型（包含完整认证配置，仅管理员可见）

    业务用途：管理员查看链接完整信息，包括认证凭据
    安全考虑：此响应包含敏感信息，仅限管理员权限访问
    对应API：GET /api/v1/requirement-links/{link_id}/detail（需管理员权限）
    """
    auth_config: Optional[Dict[str, Any]] = None  # 完整认证配置，包含凭据详情

    class Config:
        # 启用ORM模式
        from_attributes = True


class RequirementLinkListRequest(BaseModel):
    """
    需求链接列表查询请求模型

    业务用途：分页查询需求链接，支持按类型和状态筛选
    验证规则：project_id必填，分页参数有边界约束
    对应API：GET /api/v1/requirement-links/
    """
    project_id: int = Field(..., description="项目ID")  # 必填，项目隔离查询
    link_type: Optional[LinkTypeEnum] = Field(None, description="链接类型筛选")  # 可选，按类型筛选
    is_active: Optional[bool] = Field(None, description="是否启用筛选")  # 可选，按启用状态筛选
    page: int = Field(1, ge=1, description="页码")  # 页码，默认第1页
    page_size: int = Field(10, ge=1, le=100, description="每页数量")  # 每页数量，默认10，最大100


class RequirementLinkListResponse(BaseModel):
    """
    需求链接列表分页响应模型

    业务用途：返回链接分页查询结果
    对应API：GET /api/v1/requirement-links/ 的响应
    """
    total: int  # 符合条件的链接总数
    items: List[RequirementLinkResponse]  # 当前页的链接列表
    page: int  # 当前页码
    page_size: int  # 每页数量


class FetchContentRequest(BaseModel):
    """
    获取链接内容请求模型

    业务用途：触发获取外部链接的内容，用于AI分析
    对应API：POST /api/v1/requirement-links/fetch
    """
    link_id: int = Field(..., description="链接ID")  # 必填，要获取内容的链接
    force_refresh: bool = Field(default=False, description="是否强制刷新缓存")  # 默认False，使用缓存；True则重新获取


class FetchContentResponse(BaseModel):
    """
    获取链接内容响应模型

    业务用途：返回链接获取的结果，包含内容和缓存状态
    对应API：POST /api/v1/requirement-links/fetch 的响应
    """
    success: bool  # 是否获取成功
    content: Optional[str] = None  # 可选，获取到的内容
    content_type: Optional[str] = None  # 可选，内容类型：html/markdown/json/text
    message: str  # 结果消息
    cached: bool = False  # 是否来自缓存，默认False


class LinkContextRequest(BaseModel):
    """
    测试用例生成上下文请求模型

    业务用途：收集需求链接、UI链接和测试点的上下文，用于AI生成测试用例
    对应API：POST /api/v1/requirement-links/context
    """
    project_id: int = Field(..., description="项目ID")  # 必填，项目隔离
    requirement_link_ids: Optional[List[int]] = Field(None, description="需求文档链接ID列表")  # 可选，指定需求链接
    ui_link_ids: Optional[List[int]] = Field(None, description="UI原型图链接ID列表")  # 可选，指定UI链接
    test_point_ids: Optional[List[int]] = Field(None, description="测试点ID列表")  # 可选，指定测试点
    force_refresh: bool = Field(default=False, description="是否强制刷新缓存")  # 默认False


class LinkContextResponse(BaseModel):
    """
    测试用例生成上下文响应模型

    业务用途：返回AI生成测试用例所需的完整上下文信息
    对应API：POST /api/v1/requirement-links/context 的响应
    嵌套关系：整合了需求文档内容、UI描述和测试点信息
    """
    requirement_content: str = Field(default="", description="需求文档内容汇总")  # 所有需求文档的合并内容
    ui_descriptions: List[Dict[str, Any]] = Field(default_factory=list, description="UI原型图描述列表")  # 各UI原型的描述信息
    test_points: List[Dict[str, Any]] = Field(default_factory=list, description="测试点列表")  # 测试点信息
    links_used: List[int] = Field(default_factory=list, description="使用的链接ID列表")  # 实际使用的链接ID
    message: str  # 结果消息
    success: bool  # 是否成功
