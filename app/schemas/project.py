"""
项目模块 Schema - 项目管理及被测对象配置的请求与响应模型

本模块定义了项目管理相关的所有数据契约，包括：

项目Schema分层：
- ProjectBase: 项目基础字段（名称、描述、项目类型）
- ProjectCreate: 创建项目请求，继承Base并添加环境配置
- ProjectUpdate: 更新项目请求，所有字段可选
- ProjectResponse: 项目响应模型，包含ID和状态信息
- ProjectDetailResponse: 项目详情响应，额外包含文件列表和环境配置
- ProjectListResponse: 项目列表响应，带状态码和消息

环境配置Schema（嵌套结构）：
- WebEnvConfig: Web端单环境配置（URL/账号/密码）
- WebEnvConfigs: Web端多环境配置（测试/灰度/正式）
- DeviceInfo: C端设备连接信息
- DeviceConfig: C端设备配置（默认设备+设备列表）

兼容旧接口Schema：
- TestObjectInfo: 被测对象信息（兼容旧版API）
- TestObjectInfoUpdate: 更新被测对象信息（兼容旧版API）
- TestObjectInfoResponse: 被测对象信息响应（兼容旧版API）

与Model的对应关系：
- Project系列 -> app.models.project.Project
- Web端环境配置 -> Project.web_env_configs (JSON字段)
- C端设备配置 -> Project.device_config (JSON字段)
- TestObjectInfo系列 -> Project的test_object_*字段（兼容旧版）
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict


# ============== Web端环境配置 ==============
class WebEnvConfig(BaseModel):
    """
    Web端单环境配置模型

    业务用途：定义Web端单个环境（如测试/灰度/正式）的访问信息
    嵌套关系：被WebEnvConfigs引用，作为多环境配置的单项
    与Model映射：存储在Project.web_env_configs JSON字段中
    """
    url: Optional[str] = Field(None, description="环境访问地址")  # 可选，Web应用URL，如https://test.example.com
    username: Optional[str] = Field(None, description="登录账号")  # 可选，环境登录用户名
    password: Optional[str] = Field(None, description="登录密码")  # 可选，环境登录密码（存储时加密）


class WebEnvConfigs(BaseModel):
    """
    Web端多环境配置模型

    业务用途：定义Web端测试/灰度/正式三套环境的配置
    嵌套关系：被ProjectCreate和ProjectDetailResponse引用
    与Model映射：整体序列化为JSON存储在Project.web_env_configs字段
    """
    test: Optional[WebEnvConfig] = Field(None, description="测试环境")  # 测试环境配置，通常最先配置
    staging: Optional[WebEnvConfig] = Field(None, description="灰度环境")  # 灰度/预发布环境配置
    prod: Optional[WebEnvConfig] = Field(None, description="正式环境")  # 生产环境配置，需谨慎使用


# ============== C端设备配置 ==============
class DeviceInfo(BaseModel):
    """
    C端设备连接信息模型

    业务用途：定义Android/iOS设备的连接参数，用于App自动化测试
    嵌套关系：被DeviceConfig引用，作为设备列表的单项
    与Model映射：存储在Project.device_config JSON字段中
    """
    device_id: Optional[str] = Field(None, description="设备ID/序列号")  # 可选，adb devices获取的设备序列号
    device_name: Optional[str] = Field(None, description="设备名称")  # 可选，便于识别的设备别名
    app_package: Optional[str] = Field(None, description="App包名")  # 可选，如com.example.app
    app_activity: Optional[str] = Field(None, description="启动Activity")  # 可选，如.MainActivity


class DeviceConfig(BaseModel):
    """
    C端设备配置模型

    业务用途：定义C端测试的设备列表和默认设备
    嵌套关系：被ProjectCreate和ProjectDetailResponse引用
    与Model映射：整体序列化为JSON存储在Project.device_config字段
    """
    default_device: Optional[DeviceInfo] = Field(None, description="默认设备")  # 默认执行的设备
    devices: Optional[List[DeviceInfo]] = Field(default_factory=list, description="设备列表")  # 所有可用设备，default_factory避免可变默认值陷阱


# ============== 项目配置 ==============
class ProjectBase(BaseModel):
    """
    项目基础模型

    业务用途：定义项目的核心字段，作为ProjectCreate/ProjectResponse的公共父类
    验证规则：名称1-255字符，项目类型默认web
    与Model映射：对应 Project Model 的 name/description/project_type 字段
    """
    name: str = Field(..., min_length=1, max_length=255, description="项目名称")  # 必填，项目唯一标识名称
    description: Optional[str] = Field(None, description="项目描述")  # 可选，项目功能说明
    project_type: str = Field("web", description="项目类型: web=Web端, app=C端")  # 默认web，区分Web应用和App应用


class ProjectCreate(ProjectBase):
    """
    创建项目请求模型

    业务用途：用户新建测试项目，可同时配置环境信息
    验证规则：继承ProjectBase，环境配置可选
    对应API：POST /api/v1/projects/
    与Model映射：web_env_configs/device_config分别映射Project的JSON字段
    """
    web_env_configs: Optional[WebEnvConfigs] = Field(None, description="Web端多环境配置")  # 可选，Web项目必填
    device_config: Optional[DeviceConfig] = Field(None, description="C端设备配置")  # 可选，App项目必填


class ProjectUpdate(BaseModel):
    """
    更新项目请求模型

    业务用途：修改项目基本信息和状态，支持部分更新
    验证规则：所有字段可选，状态值0-2
    对应API：PUT/PATCH /api/v1/projects/{project_id}
    与Model映射：字段对应 Project Model 的 name/description/status
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="项目名称")  # 可选，更新项目名称
    description: Optional[str] = Field(None, description="项目描述")  # 可选，更新项目描述
    status: Optional[int] = Field(None, ge=0, le=2, description="状态: 0未激活/1正常/2归档")  # 可选，0=未激活/1=正常/2=归档


class ProjectResponse(ProjectBase):
    """
    项目响应模型

    业务用途：API返回项目基本信息时使用
    对应API：GET /api/v1/projects/{project_id}
    与Model映射：映射 Project Model 的 id/name/description/project_type/user_id/status/create_time/update_time
    """
    id: int  # 项目主键ID，与Project.id对应
    user_id: int  # 项目所有者ID，与Project.user_id对应
    status: int  # 项目状态：0未激活/1正常/2归档，与Project.status对应
    create_time: datetime  # 创建时间，与Project.create_time对应
    update_time: datetime  # 更新时间，与Project.update_time对应

    class Config:
        # 启用ORM模式，支持从Project Model直接读取属性
        from_attributes = True


class ProjectDetailResponse(ProjectResponse):
    """
    项目详情响应模型

    业务用途：获取项目完整信息，包含关联文件和环境配置
    对应API：GET /api/v1/projects/{project_id}/detail
    嵌套关系：继承ProjectResponse，额外包含files列表和配置信息
    """
    files: List[dict] = Field(default_factory=list, description="关联文件列表")  # 项目关联的文件列表，默认空列表
    web_env_configs: Optional[Dict] = Field(None, description="Web端多环境配置")  # Web环境配置，从JSON字段反序列化
    device_config: Optional[Dict] = Field(None, description="C端设备配置")  # 设备配置，从JSON字段反序列化


class ProjectListResponse(BaseModel):
    """
    项目列表响应模型

    业务用途：返回项目列表查询结果，包含状态码和消息
    对应API：GET /api/v1/projects/
    """
    code: int = Field(200, description="状态码")  # HTTP状态码，默认200
    message: str = Field("获取成功", description="消息")  # 操作结果消息
    data: dict = Field(..., description="数据")  # 项目列表数据，含items和total


# ============== 兼容旧接口 ==============
class TestObjectInfo(BaseModel):
    """
    被测对象信息模型（兼容旧接口）

    业务用途：旧版API中使用，统一管理Web/App被测对象信息
    与Model映射：对应 Project Model 的 test_object_* 系列字段
    注意：新接口建议使用WebEnvConfigs/DeviceConfig替代
    """
    type: Optional[str] = Field(None, description="被测对象类型: web/app")  # 可选，区分Web和App测试对象
    url: Optional[str] = Field(None, description="Web访问地址")  # 可选，与Project.test_object_url对应
    username: Optional[str] = Field(None, description="登录账号")  # 可选，与Project.test_object_username对应
    password: Optional[str] = Field(None, description="登录密码")  # 可选，与Project.test_object_password对应
    device_info: Optional[dict] = Field(None, description="设备连接信息")  # 可选，与Project.test_object_device_info对应
    app_package: Optional[str] = Field(None, description="App包名")  # 可选，与Project.test_object_app_package对应
    app_activity: Optional[str] = Field(None, description="App启动Activity")  # 可选，与Project.test_object_app_activity对应


class TestObjectInfoUpdate(BaseModel):
    """
    更新被测对象信息请求模型（兼容旧接口）

    业务用途：旧版API中更新被测对象信息，所有字段可选
    对应API：PUT /api/v1/projects/{project_id}/test-object
    注意：新接口建议使用ProjectUpdate配合环境配置替代
    """
    type: Optional[str] = Field(None, description="被测对象类型: web/app")  # 可选
    url: Optional[str] = Field(None, description="Web访问地址")  # 可选
    username: Optional[str] = Field(None, description="登录账号")  # 可选
    password: Optional[str] = Field(None, description="登录密码")  # 可选
    device_info: Optional[dict] = Field(None, description="设备连接信息")  # 可选
    app_package: Optional[str] = Field(None, description="App包名")  # 可选
    app_activity: Optional[str] = Field(None, description="App启动Activity")  # 可选


class TestObjectInfoResponse(BaseModel):
    """
    被测对象信息响应模型（兼容旧接口）

    业务用途：旧版API返回被测对象信息，包装在code/message/data结构中
    对应API：GET /api/v1/projects/{project_id}/test-object
    """
    code: int = Field(200, description="状态码")  # HTTP状态码，默认200
    message: str = Field("获取成功", description="消息")  # 操作结果消息
    data: Optional[TestObjectInfo] = Field(None, description="被测对象信息")  # 被测对象详情，可能为空
