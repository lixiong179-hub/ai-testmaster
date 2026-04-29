"""
UI原型模块 Schema - UI原型图/屏幕/链接/解析的请求与响应模型

本模块定义了UI原型图全生命周期的数据契约，支持多种UI工具（摹客、蓝湖、Figma、Axure等），包括：

枚举类型：
- UISourceEnum: UI原型来源枚举（摹客/蓝湖/Figma/Axure/Sketch/Adobe XD/手工上传/其他）
- ParseStatusEnum: 解析状态枚举（待解析/解析中/已完成/失败）
- ReviewStatusEnum: 审核状态枚举（待审核/已通过/已拒绝）

原型项目Schema：
- UIPrototypeProjectBase: 原型项目基础字段
- UIPrototypeProjectCreate: 创建原型项目请求
- UIPrototypeProjectResponse: 原型项目响应

屏幕Schema：
- UIScreenBase: 屏幕基础字段
- UIScreenCreate: 创建屏幕请求
- UIScreenResponse: 屏幕响应
- UIScreenDetailResponse: 屏幕详情响应（含完整ui_spec）
- UIScreenListResponse: 屏幕列表分页响应
- UIScreenReviewRequest: 审核屏幕请求

解析操作Schema：
- UIScreenParseRequest: 解析屏幕请求
- UIScreenParseResponse: 解析屏幕响应
- UIFlowGenerateRequest: 生成页面流转请求
- UIFlowGenerateResponse: 生成页面流转响应

用例生成辅助Schema：
- UISpecForCaseGeneration: 用于生成测试用例的UI规格

上传Schema：
- UIPrototypeUploadRequest: UI原型上传请求

UI工具链接Schema：
- UILinkAuthType: 认证类型枚举
- UILinkBase/UILinkCreate/UILinkUpdate/UILinkResponse: 链接CRUD
- UIFetchRequest/UIFetchResponse: 抓取链接内容

与Model的对应关系：
- UIPrototypeProject系列 -> app.models.ui_prototype.UIPrototypeProject
- UIScreen系列 -> app.models.ui_prototype.UIPrototypeScreen
- UILink系列 -> 存储在UIPrototypeScreen的source/原型项目关联中
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class UISourceEnum(str, Enum):
    """
    UI原型来源枚举

    业务用途：标识UI原型图的来源工具，影响解析策略
    与Model映射：对应 UIPrototypeScreen.source 和 UIPrototypeProject.source 字段
    """
    MOCKINGBOT = "mockingbot"  # 摹客
    LANNHU = "lannhu"  # 蓝湖
    FIGMA = "figma"  # Figma
    AXURE = "axure"  # Axure
    SKETCH = "sketch"  # Sketch
    ADOBE_XD = "adobe_xd"  # Adobe XD
    MANUAL = "manual"  # 手工上传
    OTHER = "other"  # 其他


class ParseStatusEnum(str, Enum):
    """
    解析状态枚举

    业务用途：追踪UI屏幕AI解析的异步任务状态
    与Model映射：对应 UIPrototypeScreen.parse_status 字段
    """
    PENDING = "pending"  # 待解析
    RUNNING = "running"  # 解析中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 解析失败


class ReviewStatusEnum(str, Enum):
    """
    审核状态枚举

    业务用途：标识UI屏幕解析结果的人工审核状态
    与Model映射：对应 UIPrototypeScreen.review_status 字段
    """
    PENDING = "pending"  # 待审核
    APPROVED = "approved"  # 已通过
    REJECTED = "rejected"  # 已拒绝


class UIPrototypeProjectBase(BaseModel):
    """
    UI原型项目基础模型

    业务用途：定义原型项目的核心字段，作为Create/Response的公共父类
    验证规则：名称1-200字符必填
    与Model映射：对应 UIPrototypeProject Model 的 name/description/source 字段
    """
    name: str = Field(..., min_length=1, max_length=200, description="原型项目名称")  # 必填，如"答题模块UI_v1.2"
    description: Optional[str] = Field(None, description="原型描述")  # 可选，原型功能说明
    source: UISourceEnum = Field(default=UISourceEnum.MANUAL, description="UI工具来源")  # 默认手工上传


class UIPrototypeProjectCreate(UIPrototypeProjectBase):
    """
    创建UI原型项目请求模型

    业务用途：在项目下创建新的UI原型项目
    验证规则：继承Base，project_id必填
    对应API：POST /api/v1/ui-prototype/projects/
    """
    project_id: int = Field(..., description="关联项目ID")  # 必填，原型所属项目


class UIPrototypeProjectResponse(UIPrototypeProjectBase):
    """
    UI原型项目响应模型

    业务用途：API返回原型项目信息时使用
    对应API：GET /api/v1/ui-prototype/projects/{project_id}
    与Model映射：映射 UIPrototypeProject Model 的所有业务字段
    """
    id: int  # 原型项目主键ID
    project_id: int  # 关联项目ID
    screen_count: int  # 屏幕总数
    parsed_count: int  # 已解析屏幕数量
    parse_status: str  # 整体解析状态
    create_time: datetime  # 创建时间
    update_time: datetime  # 更新时间

    class Config:
        # 启用ORM模式，支持从UIPrototypeProject Model直接读取属性
        from_attributes = True


class UIScreenBase(BaseModel):
    """
    UI屏幕基础模型

    业务用途：定义单个UI屏幕的核心字段，作为Create/Response的公共父类
    与Model映射：对应 UIPrototypeScreen Model 的 prototype_name/screen_name/screen_order 字段
    """
    prototype_name: str = Field(..., description="原型名称")  # 必填，所属原型名称
    screen_name: str = Field(..., description="屏幕名称")  # 必填，如"登录页"/"首页"
    screen_order: int = Field(default=0, description="屏幕顺序")  # 默认0，屏幕排列顺序


class UIScreenCreate(UIScreenBase):
    """
    创建UI屏幕请求模型

    业务用途：在项目下创建新的UI屏幕记录
    验证规则：继承Base，project_id必填
    对应API：POST /api/v1/ui-prototype/screens/
    """
    project_id: int = Field(..., description="关联项目ID")  # 必填，屏幕所属项目
    source: UISourceEnum = Field(default=UISourceEnum.MANUAL, description="UI工具来源")  # 默认手工上传
    prototype_project_id: Optional[int] = Field(None, description="所属原型项目ID")  # 可选，归属到原型项目


class UIScreenResponse(UIScreenBase):
    """
    UI屏幕响应模型

    业务用途：API返回屏幕基本信息时使用
    对应API：GET /api/v1/ui-prototype/screens/{screen_id}
    与Model映射：映射 UIPrototypeScreen Model 的所有业务字段（不含ui_spec大字段）
    """
    id: int  # 屏幕主键ID
    project_id: int  # 关联项目ID
    prototype_project_id: Optional[int]  # 所属原型项目ID，可能为空
    original_file_path: Optional[str]  # 原始UI图文件路径
    original_file_name: Optional[str]  # 原始文件名
    file_type: str  # 文件类型：png/jpg/webp
    file_size: Optional[int]  # 文件大小（KB）
    parse_status: str  # 解析状态：pending/running/completed/failed
    parse_status_text: str = ""  # 解析状态文本描述，默认空
    parse_model: Optional[str]  # 解析使用的视觉模型，可能为空
    parse_error: Optional[str]  # 解析错误信息
    summary: Optional[str]  # AI解析摘要，可能为空
    element_count: int  # 识别出的元素数量
    button_count: int  # 按钮数量
    input_count: int  # 输入框数量
    is_entry_point: bool  # 是否为入口页面
    is_end_point: bool  # 是否为结束页面
    review_status: str  # 审核状态：pending/approved/rejected
    create_time: datetime  # 创建时间
    update_time: datetime  # 更新时间

    class Config:
        # 启用ORM模式，支持从UIPrototypeScreen Model直接读取属性
        from_attributes = True


class UIScreenDetailResponse(UIScreenResponse):
    """
    UI屏幕详情响应模型（包含完整ui_spec）

    业务用途：获取屏幕完整解析结果，包含UI规格、布局校验和导航流程
    对应API：GET /api/v1/ui-prototype/screens/{screen_id}/detail
    嵌套关系：继承UIScreenResponse，额外包含ui_spec/layout_checks/navigation_flow
    """
    ui_spec: Optional[Dict[str, Any]]  # 完整UI规格JSON，结构化解析结果
    layout_checks: Optional[List[Dict[str, Any]]]  # 布局校验点列表
    navigation_flow: Optional[Dict[str, Any]]  # 导航流向JSON

    class Config:
        # 启用ORM模式，支持从UIPrototypeScreen Model直接读取属性
        from_attributes = True


class UIScreenParseRequest(BaseModel):
    """
    解析UI屏幕请求模型

    业务用途：触发AI解析指定屏幕的UI结构
    对应API：POST /api/v1/ui-prototype/screens/parse
    """
    screen_ids: List[int] = Field(..., description="屏幕ID列表")  # 必填，批量解析的屏幕ID
    prototype_project_id: Optional[int] = Field(None, description="原型项目ID（可选）")  # 可选，指定原型项目上下文
    parse_mode: Optional[str] = Field("text", description="解析模式：text或vision")  # 默认text模式，vision模式使用视觉模型


class UIScreenParseResponse(BaseModel):
    """
    解析UI屏幕响应模型

    业务用途：返回批量解析的结果统计
    对应API：POST /api/v1/ui-prototype/screens/parse 的响应
    """
    total: int  # 总解析屏幕数
    success: int  # 成功解析数
    failed: int  # 失败解析数
    results: List[Dict[str, Any]]  # 各屏幕的解析结果详情


class UIFlowGenerateRequest(BaseModel):
    """
    生成页面流转请求模型

    业务用途：基于原型项目中的多张UI图，AI生成页面流转关系图
    对应API：POST /api/v1/ui-prototype/flow/generate
    """
    prototype_project_id: int = Field(..., description="原型项目ID")  # 必填，指定生成流转的原型项目


class UIFlowGenerateResponse(BaseModel):
    """
    生成页面流转响应模型

    业务用途：返回页面流转图的生成结果
    对应API：POST /api/v1/ui-prototype/flow/generate 的响应
    """
    success: bool  # 是否生成成功
    message: str  # 结果消息
    flow: Optional[Dict[str, Any]]  # 页面流转图数据，可能为空


class UISpecForCaseGeneration(BaseModel):
    """
    用于生成测试用例的UI规格模型

    业务用途：将UI屏幕的解析结果整理为AI生成测试用例所需的上下文格式
    嵌套关系：被测试用例生成服务引用，整合UI信息到生成Prompt中
    """
    screen_id: int  # 屏幕ID
    screen_name: str  # 屏幕名称
    prototype_name: str  # 原型名称
    screen_order: int  # 屏幕顺序
    ui_spec: Dict[str, Any]  # UI规格JSON
    summary: Optional[str]  # 解析摘要
    layout_checks: List[Dict[str, Any]]  # 布局校验点
    navigation_flow: Optional[Dict[str, Any]]  # 导航流向
    element_count: int  # 元素数量
    button_count: int  # 按钮数量
    is_entry_point: bool  # 是否入口页面
    is_end_point: bool  # 是否结束页面
    review_status: str  # 审核状态


class UIScreenListResponse(BaseModel):
    """
    UI屏幕列表分页响应模型

    业务用途：返回屏幕分页查询结果
    对应API：GET /api/v1/ui-prototype/screens/ 的响应
    """
    total: int  # 符合条件的屏幕总数
    items: List[UIScreenResponse]  # 当前页的屏幕列表
    page: int  # 当前页码
    page_size: int  # 每页数量


class UIScreenReviewRequest(BaseModel):
    """
    审核UI屏幕请求模型

    业务用途：人工审核AI解析的UI屏幕结果，确保质量
    对应API：POST /api/v1/ui-prototype/screens/{screen_id}/review
    """
    review_status: ReviewStatusEnum  # 必填，审核结果：approved/rejected
    review_comment: Optional[str] = Field(None, description="审核意见")  # 可选，拒绝时需说明原因


class UIPrototypeUploadRequest(BaseModel):
    """
    UI原型上传请求模型

    业务用途：上传UI原型图文件（支持单文件和ZIP包）
    对应API：POST /api/v1/ui-prototype/upload
    """
    project_id: int = Field(..., description="项目ID")  # 必填，所属项目
    prototype_name: str = Field(..., description="原型名称")  # 必填，如"答题模块UI"
    source: UISourceEnum = Field(default=UISourceEnum.MANUAL, description="UI工具来源")  # 默认手工上传
    prototype_project_id: Optional[int] = Field(None, description="关联的原型项目ID")  # 可选，归属到已有原型项目
    is_zip: bool = Field(default=False, description="是否为ZIP包")  # 默认False，True时解压后批量创建屏幕


# ============== UI工具链接 Schema ==============

class UILinkAuthType(str, Enum):
    """
    认证类型枚举

    业务用途：标识访问UI工具链接时所需的认证方式
    """
    NONE = "none"  # 无认证，公开链接
    COOKIE = "cookie"  # Cookie认证，需提供Cookie字符串
    BEARER = "bearer"  # Bearer Token认证
    BASIC = "basic"  # Basic Auth认证（用户名+密码）


class UILinkBase(BaseModel):
    """
    UI工具链接基础模型

    业务用途：定义UI工具链接的核心字段，作为Create/Response的公共父类
    与Model映射：对应链接的基本信息字段
    """
    project_id: int = Field(..., description="关联项目ID")  # 必填，链接所属项目
    name: str = Field(..., min_length=1, max_length=200, description="链接名称，如：答题模块UI_v1.2")  # 必填，便于识别的链接名称
    source: UISourceEnum = Field(..., description="UI工具来源")  # 必填，标识来源工具


class UILinkCreate(UILinkBase):
    """
    创建UI工具链接请求模型

    业务用途：添加UI工具的分享链接，支持带认证的私有链接
    验证规则：继承Base，link_url必填
    对应API：POST /api/v1/ui-prototype/links/
    """
    link_url: str = Field(..., description="UI工具分享链接")  # 必填，UI工具的分享URL
    auth_type: UILinkAuthType = Field(default=UILinkAuthType.NONE, description="认证类型")  # 默认无认证
    auth_config: Optional[Dict[str, Any]] = Field(None, description="认证配置，如cookie/token等")  # 可选，根据auth_type提供
    description: Optional[str] = Field(None, description="链接描述")  # 可选，链接说明
    page_urls: Optional[List[str]] = Field(None, description="多页面URL列表")  # 可选，单链接多页面场景


class UILinkUpdate(BaseModel):
    """
    更新UI工具链接请求模型

    业务用途：修改链接信息，支持部分更新
    验证规则：所有字段可选
    对应API：PUT/PATCH /api/v1/ui-prototype/links/{link_id}
    """
    name: Optional[str] = Field(None, description="链接名称")  # 可选
    link_url: Optional[str] = Field(None, description="UI工具分享链接")  # 可选
    auth_type: Optional[UILinkAuthType] = Field(None, description="认证类型")  # 可选
    auth_config: Optional[Dict[str, Any]] = Field(None, description="认证配置")  # 可选
    description: Optional[str] = Field(None, description="链接描述")  # 可选
    is_active: Optional[bool] = Field(None, description="是否启用")  # 可选，软删除/恢复
    page_urls: Optional[List[str]] = Field(None, description="多页面URL列表")  # 可选


class UILinkResponse(UILinkBase):
    """
    UI工具链接响应模型

    业务用途：API返回链接信息时使用
    对应API：GET /api/v1/ui-prototype/links/{link_id}
    与Model映射：映射链接的所有业务字段
    """
    id: int  # 链接主键ID
    link_url: str  # 链接地址
    auth_type: str  # 认证类型
    description: Optional[str]  # 链接描述
    is_active: bool  # 是否启用
    last_fetch_time: Optional[datetime]  # 最后抓取时间
    last_fetch_status: Optional[str]  # 最后抓取状态
    create_time: datetime  # 创建时间
    update_time: datetime  # 更新时间

    class Config:
        # 启用ORM模式，支持从Model直接读取属性
        from_attributes = True


class UIFetchRequest(BaseModel):
    """
    抓取UI链接请求模型

    业务用途：触发抓取UI工具链接的内容（截图/页面结构等）
    对应API：POST /api/v1/ui-prototype/links/fetch
    """
    link_id: Optional[int] = Field(None, description="UI链接ID")  # 可选，已保存的链接ID
    link_url: Optional[str] = Field(None, description="直接传入URL")  # 可选，临时URL，与link_id二选一
    auth_config: Optional[Dict[str, Any]] = Field(None, description="认证配置")  # 可选，临时认证信息
    page_urls: Optional[List[str]] = Field(None, description="多页面URL列表")  # 可选，多页面抓取
    auto_parse: bool = Field(default=True, description="是否自动解析")  # 默认True，抓取后自动触发AI解析


class UIFetchResponse(BaseModel):
    """
    抓取UI链接响应模型

    业务用途：返回抓取结果，包含截图和解析数据
    对应API：POST /api/v1/ui-prototype/links/fetch 的响应
    """
    success: bool  # 是否抓取成功
    message: str  # 结果消息
    screenshots: Optional[List[Dict[str, Any]]] = None  # 可选，抓取的截图列表
    parsed_specs: Optional[List[Dict[str, Any]]] = None  # 可选，解析的UI规格列表


# UI工具来源映射（用于前端展示）
# 提供各UI工具的显示名称和URL匹配模式，前端根据链接URL自动识别来源工具
UI_LINK_SOURCE_OPTIONS = [
    {"value": "mockingbot", "label": "摹客", "url_patterns": ["kmock.com", "mockingsoft.com"]},
    {"value": "lannhu", "label": "蓝湖", "url_patterns": ["lanhuapp.com", "lanhu.net"]},
    {"value": "figma", "label": "Figma", "url_patterns": ["figma.com"]},
    {"value": "axure", "label": "Axure", "url_patterns": ["axure", "share.axure"]},
    {"value": "sketch", "label": "Sketch", "url_patterns": ["sketch.com"]},
    {"value": "adobe_xd", "label": "Adobe XD", "url_patterns": ["adobe.com"]},
    {"value": "manual", "label": "手工上传", "url_patterns": []},
    {"value": "other", "label": "其他", "url_patterns": []},
]
