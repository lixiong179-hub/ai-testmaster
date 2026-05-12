"""
API调用成本日志模型模块

本模块定义了AI API调用成本日志（ApiCostLog）模型，用于记录和统计
AI API（如DeepSeek、通义千问、Kimi等）的调用成本，支持成本追踪和预算控制。

核心类概览：
    - ApiCostLog : API成本日志模型，记录每次AI调用的Token用量和费用

表关系：
    TestTask → ApiCostLog（一对多，可选关联）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, text
from app.db.database import Base


class ApiCostLog(Base):
    """
    API成本日志模型

    记录每次AI API调用的详细信息，包括使用的模型、Token用量和费用。
    支持按任务、模型、API类型等维度统计成本。

    表关系：
        - 多对一 → TestTask（关联任务，可选）

    使用场景：
        - AI API调用成本追踪和统计
        - 按模型/类型维度分析成本分布
        - 成本预算控制和超支预警
    """
    __tablename__ = "api_cost_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 日志主键ID

    # 关联信息
    task_id = Column(Integer, ForeignKey("test_tasks.id"), nullable=True, index=True, comment="关联任务ID")  # 任务ID，可选关联

    # API调用信息
    model = Column(String(30), nullable=False, comment="使用的AI模型，如deepseek-v4-flash/qwen/kimi")
    api_type = Column(String(50), nullable=False, comment="API类型: test_generation/analysis/vision")

    # Token使用量
    input_tokens = Column(Integer, nullable=True, comment="输入Token数")                               # 输入Token消耗量
    output_tokens = Column(Integer, nullable=True, comment="输出Token数")                              # 输出Token消耗量

    # 成本信息（精确到6位小数）
    cost = Column(Numeric(10, 6), nullable=True, comment="本次调用成本（元）")                          # 调用费用，单位人民币元

    # 时间和状态
    call_time = Column(
        DateTime, nullable=False,
        default=utcnow,
        server_default=text('CURRENT_TIMESTAMP'),
        comment="调用时间"
    )
    status = Column(String(20), nullable=True, comment="状态: success/failed/timeout")
    error_message = Column(String(500), nullable=True, comment="错误信息")                              # 调用失败时的错误信息

    def __repr__(self) -> str:
        """返回API成本日志的字符串表示，便于调试和日志输出。"""
        return f"<ApiCostLog(id={self.id}, model='{self.model}', cost={self.cost})>"
