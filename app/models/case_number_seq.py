"""用例编号序列模型 — 按项目隔离的自增序号。

本模块提供按 project_id 隔离的用例编号序列表，配合 CaseNumberService
实现统一编号生成，使用 SELECT ... FOR UPDATE 行级锁保证并发安全。

核心类:
    CaseNumberSeq: 编号序列模型，project_id 为主键，current_seq 记录当前序号
"""
from sqlalchemy import Column, Integer, String
from app.db.database import Base


class CaseNumberSeq(Base):
    """用例编号序列模型 — 按 project_id 隔离的自增序号。

    每个项目维护一条记录，current_seq 记录已分配的最大序号。
    生成新编号时通过 SELECT ... FOR UPDATE 加行级锁，
    确保并发场景下编号不重复、不跳号。

    表关系:
        - project_id 与 projects.id 逻辑关联（不建外键，避免级联删除影响序列）
    """
    __tablename__ = "case_number_seqs"

    project_id = Column(Integer, primary_key=True, comment="项目ID，同时为主键")
    current_seq = Column(Integer, nullable=False, default=0, comment="当前已分配的最大序号")
