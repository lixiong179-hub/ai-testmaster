"""
迭代模块 Schema - 迭代管理的请求与响应模型

本模块定义了项目迭代和迭代输入的数据契约，包括：

枚举类型：
- IterationPipelineStatus: 迭代流水线状态枚举（draft/in_pipeline/in_review/finalized/archived）
- IterationInputKind: 迭代输入类型枚举（prd/prototype/xmind/testpoint/supplement_form）

迭代Schema分层：
- IterationCreate: 创建迭代请求
- IterationUpdate: 更新迭代请求，所有字段可选
- IterationResponse: 迭代响应模型

迭代输入Schema分层：
- IterationInputCreate: 添加迭代输入请求
- IterationInputResponse: 迭代输入响应模型

与Model的对应关系：
- Iteration系列 -> app.models.iteration.Iteration
- IterationInput系列 -> app.models.iteration.IterationInput
- IterationPipelineStatus -> Iteration.status 字段的枚举值
- IterationInputKind -> IterationInput.kind 字段的枚举值
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class IterationPipelineStatus(str, Enum):
    """
    迭代流水线状态枚举

    状态由系统自动驱动，不由用户手动设置：
    draft → in_pipeline → in_review → finalized
    """
    DRAFT = "draft"                     # 草稿
    IN_PIPELINE = "in_pipeline"         # 流水线运行中
    IN_REVIEW = "in_review"             # 评审中
    FINALIZED = "finalized"             # 已定稿
    ARCHIVED = "archived"               # 已归档


class IterationInputKind(str, Enum):
    """
    迭代输入类型枚举
    """
    PRD = "prd"                         # 需求文档
    PROTOTYPE = "prototype"             # UI原型
    XMIND = "xmind"                     # XMind思维导图
    TESTPOINT = "testpoint"             # 测试点
    SUPPLEMENT_FORM = "supplement_form" # 补充表单
    CHANGE_NOTES = "change_notes"       # 变更说明


class IterationCreate(BaseModel):
    """
    创建迭代请求模型

    验证规则：project_id和name必填，版本号默认v1.0，状态默认draft
    """
    project_id: int = Field(..., description="项目ID")
    name: str = Field(..., min_length=1, max_length=200, description="迭代名称")
    version: str = Field(default="v1.0", max_length=50, description="版本号")
    description: Optional[str] = Field(None, description="迭代描述")
    base_iteration_id: Optional[int] = Field(None, description="基线迭代ID，必须属于同project且status=finalized")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    target_device: Optional[str] = Field(None, max_length=20, description="迭代目标设备：tablet/phone/desktop/web")


class IterationUpdate(BaseModel):
    """
    更新迭代请求模型

    验证规则：所有字段可选；status 由系统自动驱动，不允许用户手动修改
    """
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="迭代名称")
    version: Optional[str] = Field(None, max_length=50, description="版本号")
    description: Optional[str] = Field(None, description="迭代描述")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    target_device: Optional[str] = Field(None, max_length=20, description="迭代目标设备")


class IterationInputCreate(BaseModel):
    """
    添加迭代输入请求模型

    验证规则：kind必填；file_id和payload至少提供一个；hash必填用于幂等校验
    """
    kind: IterationInputKind = Field(..., description="输入类型")
    file_id: Optional[int] = Field(None, description="关联项目文件ID")
    payload: Optional[dict] = Field(None, description="非文件型输入的JSON载荷")
    hash: str = Field(..., min_length=1, max_length=64, description="输入内容哈希，用于幂等校验（映射到 content_hash 列）")


class IterationInputResponse(BaseModel):
    """
    迭代输入响应模型
    """
    id: int
    iteration_id: int
    kind: str
    file_id: Optional[int]
    payload: Optional[dict]
    content_hash: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class IterationResponse(BaseModel):
    """
    迭代响应模型
    """
    id: int
    project_id: int
    name: str
    version: str
    description: Optional[str]
    status: str
    start_date: Optional[date]
    end_date: Optional[date]
    base_iteration_id: Optional[int]
    target_device: Optional[str] = None
    created_by: Optional[int]
    finalized_at: Optional[datetime]
    create_time: datetime
    update_time: datetime
    inputs: Optional[List[IterationInputResponse]] = None

    class Config:
        from_attributes = True
