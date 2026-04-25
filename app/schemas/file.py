"""
文件模块 Schema - 项目文件上传/管理/内容提取的请求与响应模型

本模块定义了项目文件管理的数据契约，包括：

枚举类型：
- ResourceType: 资源类型枚举（需求文档/UI原型图/接口文档/测试数据/其他）
- ExtractStatus: 内容提取状态枚举（待处理/处理中/已完成/失败）

文件Schema分层：
- FileBase: 文件基础字段（仅project_id）
- FileUploadRequest: 文件上传请求（文件通过Form表单上传）
- UrlSubmitRequest: URL提交请求（支持多种文件类型）
- FileUpdateRequest: 文件更新请求（资源类型/描述/激活状态/迭代归属）
- FileResponse: 文件响应模型（完整信息）
- FileListResponse: 文件列表响应

文件操作Schema：
- FileExtractRequest: 文件内容提取请求（批量提取+强制刷新）

与Model的对应关系：
- File系列 -> app.models.project.ProjectFile
- ResourceType -> ProjectFile.resource_type 字段的枚举值
- ExtractStatus -> ProjectFile.extract_status 字段的枚举值
"""
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import Optional, List
from enum import Enum


class ResourceType(str, Enum):
    """
    资源类型枚举

    业务用途：标识上传文件的资源分类，影响AI解析策略和测试用例生成
    与Model映射：对应 ProjectFile.resource_type 字段
    """
    REQUIREMENT = "requirement"  # 需求文档，如PRD/SRS
    UI_MOCKUP = "ui_mockup"  # UI原型图，如Axure/Figma导出
    API_DOC = "api_doc"  # 接口文档，如Swagger/Postman
    TEST_DATA = "test_data"  # 测试数据，如CSV/Excel
    OTHER = "other"  # 其他，默认分类


class ExtractStatus(str, Enum):
    """
    内容提取状态枚举

    业务用途：追踪文件内容提取的异步任务状态
    与Model映射：对应 ProjectFile.extract_status 字段
    """
    PENDING = "pending"  # 待处理，文件刚上传
    PROCESSING = "processing"  # 处理中，AI正在提取内容
    COMPLETED = "completed"  # 已完成，内容已提取
    FAILED = "failed"  # 失败，提取过程出错


class FileBase(BaseModel):
    """
    文件基础模型

    业务用途：定义文件的核心字段，作为FileUploadRequest/UrlSubmitRequest的公共父类
    与Model映射：project_id对应 ProjectFile.project_id 外键
    """
    project_id: int = Field(..., description="项目ID")  # 必填，文件所属项目，实现多项目隔离


class FileUploadRequest(FileBase):
    """
    文件上传请求模型

    业务用途：上传本地文件到项目，文件通过multipart/form-data传输
    注意：文件本身通过Form表单的file字段上传，此Schema仅定义project_id
    对应API：POST /api/v1/files/upload
    """
    # 文件通过Form表单上传，这里只定义project_id
    pass


class UrlSubmitRequest(FileBase):
    """
    URL提交请求模型

    业务用途：通过URL提交在线资源（如在线文档/原型链接）
    验证规则：URL格式校验（HttpUrl），文件类型正则校验
    对应API：POST /api/v1/files/url
    """
    url: HttpUrl = Field(..., description="URL链接")  # 必填，Pydantic HttpUrl自动校验URL格式
    file_type: str = Field(
        ...,
        pattern=(
            "^(docx|doc|pdf|xlsx|xls|csv|txt|md|png|jpg|jpeg|"
            "gif|webp|figma|url|yaml|yml|json|zip|rar)$"
        ),
        description="文件类型",  # 必填，正则限制支持的文件格式，确保系统能正确解析
    )


class FileUpdateRequest(BaseModel):
    """
    文件更新请求模型

    业务用途：修改文件的元信息，支持部分更新
    验证规则：所有字段可选
    对应API：PUT/PATCH /api/v1/files/{file_id}
    """
    resource_type: Optional[ResourceType] = Field(None, description="资源类型")  # 可选，更新资源分类
    description: Optional[str] = Field(None, description="文件描述")  # 可选，更新文件描述
    is_active: Optional[bool] = Field(None, description="是否激活")  # 可选，软删除/恢复
    # 支持修改迭代归属，null或省略表示未分类
    iteration_id: Optional[int] = Field(
        None, description="迭代ID（null或省略表示未分类）"
    )  # 可选，将文件归属到指定迭代


class FileResponse(BaseModel):
    """
    文件响应模型

    业务用途：API返回文件信息时使用
    对应API：GET /api/v1/files/{file_id}
    与Model映射：映射 ProjectFile Model 的所有业务字段
    """
    id: int  # 文件主键ID
    project_id: int  # 所属项目ID
    file_name: str  # 文件名，与ProjectFile.file_name对应
    file_type: str  # 文件格式，如docx/pdf/png
    file_url: str  # 文件存储路径，与ProjectFile.file_url对应
    file_source: str  # 文件来源：file=本地上传/url=URL提交
    size: Optional[int] = None  # 可选，文件大小（KB）
    upload_time: datetime  # 上传时间
    resource_type: Optional[str] = "other"  # 资源类型，默认other
    content: Optional[str] = None  # 可选，从文件提取的文本内容
    extract_status: Optional[str] = "pending"  # 提取状态，默认pending
    extract_error: Optional[str] = None  # 可选，提取失败原因
    extracted_at: Optional[datetime] = None  # 可选，内容提取完成时间
    description: Optional[str] = None  # 可选，文件描述
    is_active: Optional[bool] = True  # 是否激活，默认True
    linked_case_count: Optional[int] = 0  # 关联的测试用例数量，默认0

    class Config:
        # 启用ORM模式，支持从ProjectFile Model直接读取属性
        from_attributes = True


class FileListResponse(BaseModel):
    """
    文件列表响应模型

    业务用途：返回文件列表查询结果，包装在code/message/data结构中
    对应API：GET /api/v1/files/ 的响应
    """
    code: int = Field(200, description="状态码")  # HTTP状态码，默认200
    message: str = Field("获取成功", description="消息")  # 操作结果消息
    data: dict = Field(..., description="数据")  # 文件列表数据，含items和total


class FileExtractRequest(BaseModel):
    """
    文件内容提取请求模型

    业务用途：批量触发文件内容提取，AI解析文件内容用于测试用例生成
    对应API：POST /api/v1/files/extract
    """
    file_ids: List[int] = Field(..., description="文件ID列表")  # 必填，批量提取的文件ID
    project_id: int = Field(..., description="项目ID")  # 必填，项目隔离
    force_refresh: bool = Field(False, description="是否强制刷新")  # 默认False，已提取的文件不重复提取；True则强制重新提取
