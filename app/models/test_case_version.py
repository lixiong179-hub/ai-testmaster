"""
测试用例版本历史模型模块

本模块定义了测试用例版本历史（TestCaseVersion）模型，记录测试用例的
每次变更，支持版本对比和回滚。

核心类概览：
    - TestCaseVersion : 测试用例版本历史模型

表关系：
    TestCase → TestCaseVersion（一对多，级联删除）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.utils.db_time import utcnow
from app.db.database import Base


class TestCaseVersion(Base):
    """
    测试用例版本历史模型

    记录测试用例的每次变更，包括变更类型、变更说明、变更字段和完整数据快照。
    支持版本对比、回滚和审计追溯。

    表关系：
        - 多对一 → TestCase（所属用例，级联删除）

    使用场景：
        - 用例修改历史追溯
        - 版本对比和差异查看
        - 用例回滚到历史版本
        - AI纠正操作的版本记录
    """
    __test__ = False
    __tablename__ = "test_case_versions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 版本主键ID
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联用例ID")  # 用例ID，级联删除
    version_number = Column(Integer, nullable=False, comment="版本号，从1开始递增")                     # 版本号，每次变更递增
    change_type = Column(String(30), nullable=True, comment="修改类型：create/update/delete/restore/correction/human_edit")  # create=创建，update=更新，delete=删除，restore=恢复，correction=AI纠正，human_edit=人工修改
    change_description = Column(String(500), nullable=True, comment="修改说明")                         # 变更描述
    changed_fields = Column(JSON, nullable=True, comment="变更的字段及前后值")                          # 变更字段对比，格式：{"field": {"old": ..., "new": ...}}
    snapshot_data = Column(JSON, nullable=True, comment="用例完整数据快照（JSON格式，归档后置空）")                  # 用例变更后的完整数据快照
    operator_id = Column(Integer, nullable=True, comment="操作人ID")                                   # 变更操作人ID
    operator_name = Column(String(100), nullable=True, comment="操作人姓名")                            # 变更操作人姓名
    created_at = Column(DateTime, default=utcnow, nullable=False, comment="创建时间")                   # 版本创建时间，UTC时区

    test_case = relationship("TestCase", backref="version_records")                                   # 所属用例
