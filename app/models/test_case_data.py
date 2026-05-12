"""
测试用例-数据关联模型模块

本模块定义了测试用例与测试数据之间的多对多关联关系，
支持同一组测试数据被多个用例复用，实现数据驱动测试的灵活配置。

核心类概览：
    - TestCaseData : 测试用例-数据关联模型，支持参数映射

表关系：
    TestCase ←→ TestData（多对多，通过 TestCaseData 关联）
    TestCaseData.case_id 级联删除
    TestCaseData.test_data_id 级联删除

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db.database import Base


class TestCaseData(Base):
    """
    测试用例-数据关联模型

    建立测试用例与测试数据之间的多对多关联关系，
    支持同一组测试数据被多个用例复用。
    通过 parameter_mapping 字段支持字段名映射，
    解决不同用例对同一数据字段使用不同参数名的问题。

    表关系：
        - 多对一 → TestCase（所属用例，级联删除）
        - 多对一 → TestData（所属数据，级联删除）

    使用场景：
        - 数据驱动测试：一个用例绑定多组测试数据
        - 数据复用：同一组数据被多个用例引用
        - 参数映射：不同用例对同一数据的字段名映射
    """
    __tablename__ = "test_case_data"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 关联主键ID

    # 关联ID
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True, comment="测试用例ID")  # 用例ID，级联删除
    test_data_id = Column(Integer, ForeignKey("test_data.id", ondelete="CASCADE"), nullable=False, index=True, comment="测试数据ID")    # 数据ID，级联删除

    # 参数映射配置（支持字段名映射）
    # 格式示例：{"用例参数名": "数据字段名"}，如 {"username": "account", "pwd": "password"}
    parameter_mapping = Column(JSON, nullable=True, comment="参数映射配置（JSON格式）")                  # 字段名映射，解决用例与数据字段名不一致问题

    # 时间信息
    create_time = Column(DateTime, nullable=False, default=utcnow, comment="创建时间")                  # 创建时间，UTC时区

    # 关联关系
    test_case = relationship("TestCase", backref="case_data_links")                                   # 关联的测试用例
    test_data = relationship("TestData", backref="case_data_links")                                   # 关联的测试数据

    def __repr__(self):
        """返回关联记录的字符串表示，便于调试和日志输出。"""
        return f"<TestCaseData(id={self.id}, case_id={self.test_case_id}, data_id={self.test_data_id})>"
