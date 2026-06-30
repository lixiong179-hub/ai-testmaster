"""
测试报告模块 Schema - 测试报告生成/查询/导出的请求与响应模型

本模块定义了测试报告相关的数据契约，包括：

报告Schema分层：
- TestReportBase: 报告基础字段（名称/描述/项目ID/任务ID）
- TestReportCreate: 创建报告请求，直接继承Base
- TestReportUpdate: 更新报告请求，所有字段可选
- TestReportResponse: 报告响应模型（含统计数据）

报告内容Schema：
- TestCaseResult: 单条用例执行结果
- TestReportDetail: 报告详细内容（用例列表+统计+环境信息）

报告操作Schema：
- TestReportList: 报告列表响应
- ReportExportRequest: 导出报告请求（支持PDF/HTML）
- ReportGenerateRequest: 生成报告请求

与Model的对应关系：
- TestReport系列 -> app.models.report.TestReport
- TestCaseResult -> TestResult Model 的单条结果映射
- TestReportDetail -> TestReport.content (JSON字段)的结构化表示
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any, List


class TestReportBase(BaseModel):
    """
    测试报告基础模型

    业务用途：定义测试报告的核心字段，作为TestReportCreate/TestReportResponse的公共父类
    验证规则：名称必填，项目ID必填
    与Model映射：对应 TestReport Model 的 name/description/project_id/test_task_id 字段
    """
    __test__ = False
    name: str = Field(..., description="报告名称")  # 必填，如"登录模块测试报告_v1.0"
    description: Optional[str] = Field(None, description="报告描述")  # 可选，报告内容概述
    project_id: int = Field(..., description="项目ID")  # 必填，报告所属项目
    test_task_id: Optional[int] = Field(None, description="测试任务ID")  # 可选，关联的测试任务，为空则汇总项目所有结果


class TestReportCreate(TestReportBase):
    """
    创建测试报告请求模型

    业务用途：基于测试任务结果生成测试报告
    验证规则：直接继承TestReportBase
    对应API：POST /api/v1/reports/
    """
    __test__ = False


class TestReportUpdate(BaseModel):
    """
    更新测试报告请求模型

    业务用途：修改报告信息，支持部分更新
    验证规则：所有字段可选
    对应API：PUT/PATCH /api/v1/reports/{report_id}
    """
    __test__ = False
    name: Optional[str] = Field(None, description="报告名称")  # 可选，更新报告名称
    description: Optional[str] = Field(None, description="报告描述")  # 可选，更新报告描述
    status: Optional[str] = Field(None, description="报告状态")  # 可选，如pending/running/completed/failed
    summary: Optional[str] = Field(None, description="报告摘要")  # 可选，AI生成的报告摘要


class TestCaseResult(BaseModel):
    """
    测试用例执行结果模型

    业务用途：报告中单条用例的执行结果，用于展示详细测试情况
    嵌套关系：被TestReportDetail引用，作为用例结果列表的单项
    与Model映射：部分字段映射 TestResult Model
    """
    __test__ = False
    case_id: int  # 用例ID
    case_name: str  # 用例名称/标题
    status: str  # 执行状态：passed/failed/blocked
    execution_time: Optional[float] = None  # 可选，执行耗时（秒）
    error_message: Optional[str] = None  # 可选，失败时的错误信息
    steps: Optional[List[Dict[str, Any]]] = None  # 可选，步骤级别的执行详情


class TestReportDetail(BaseModel):
    """
    测试报告详细内容模型

    业务用途：报告的完整内容，包含所有用例结果和统计信息
    嵌套关系：被报告详情API使用，包含TestCaseResult列表
    与Model映射：对应 TestReport.content JSON字段的结构化表示
    """
    __test__ = False
    test_cases: List[TestCaseResult]  # 所有用例的执行结果列表
    statistics: Dict[str, Any]  # 统计数据，如通过率、失败率、按模块统计等
    environment: Optional[Dict[str, Any]] = None  # 可选，测试环境信息，如浏览器版本/操作系统等


class TestReportResponse(TestReportBase):
    """
    测试报告响应模型

    业务用途：API返回报告信息时使用，包含统计数据
    对应API：GET /api/v1/reports/{report_id}
    与Model映射：映射 TestReport Model 的所有业务字段
    """
    __test__ = False
    id: int  # 报告主键ID
    status: str  # 报告状态：pending/running/completed/failed
    total_cases: int  # 总用例数
    passed_cases: int  # 通过用例数
    failed_cases: int  # 失败用例数
    blocked_cases: int  # 阻塞用例数
    pass_rate: float = 0.0  # 通过率（百分比）
    start_time: Optional[datetime] = None  # 测试开始时间，可能为空
    end_time: Optional[datetime] = None  # 测试结束时间，可能为空
    execution_time: Optional[int] = None  # 总执行时间（秒），可能为空
    summary: Optional[str] = None  # 报告摘要，AI生成的总结
    content: Optional[Dict[str, Any]] = None  # 详细报告内容(JSON)
    create_time: datetime  # 创建时间
    update_time: datetime  # 更新时间

    class Config:
        # 启用ORM模式，支持从TestReport Model直接读取属性
        from_attributes = True


class TestReportList(BaseModel):
    """
    测试报告列表响应模型

    业务用途：返回报告列表查询结果
    对应API：GET /api/v1/reports/ 的响应
    """
    __test__ = False
    reports: List[TestReportResponse]  # 报告列表
    total: int  # 报告总数


class ReportExportRequest(BaseModel):
    """
    导出报告请求模型

    业务用途：将测试报告导出为PDF或HTML格式
    验证规则：report_id必填，format必须为pdf或html
    对应API：POST /api/v1/reports/export
    """
    report_id: int  # 必填，要导出的报告ID
    format: str = Field(..., pattern="^(pdf|html)$", description="导出格式")  # 必填，仅支持pdf和html两种格式


class ReportGenerateRequest(BaseModel):
    """
    生成报告请求模型

    业务用途：基于测试任务结果生成新的测试报告
    对应API：POST /api/v1/reports/generate
    """
    project_id: int  # 必填，项目ID
    test_task_id: Optional[int] = None  # 可选，指定任务则只汇总该任务结果
    name: str  # 必填，报告名称
    description: Optional[str] = None  # 可选，报告描述
