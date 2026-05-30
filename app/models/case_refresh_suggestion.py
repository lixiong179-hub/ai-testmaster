from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.utils.db_time import utcnow
from app.db.database import Base


class CaseRefreshSuggestion(Base):
    __tablename__ = "case_refresh_suggestions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True, index=True)
    trigger_reason = Column(String(100), nullable=False, comment="触发原因: stale/requirement_changed/ui_changed/manual")
    triggered_at = Column(DateTime, default=utcnow, nullable=False, comment="触发时间")

    suggestion_status = Column(String(30), nullable=False, default="pending", comment="建议状态: pending/accepted/rejected/applied/expired")
    suggested_title = Column(String(255), nullable=True, comment="AI建议的用例标题")
    suggested_steps = Column(JSON, nullable=True, comment="AI建议的步骤JSON")
    suggested_expected_result = Column(Text, nullable=True, comment="AI建议的预期结果")
    diff_description = Column(Text, nullable=True, comment="差异说明")
    deprecation_reason = Column(Text, nullable=True, comment="建议废弃原因（仅当建议废弃时填写）")

    review_status = Column(String(30), nullable=False, default="pending", comment="人工确认状态: pending/approved/rejected")
    reviewer_id = Column(Integer, nullable=True, comment="确认人ID")
    reviewer_name = Column(String(100), nullable=True, comment="确认人姓名")
    reviewed_at = Column(DateTime, nullable=True, comment="确认时间")
    reject_reason = Column(Text, nullable=True, comment="驳回原因")

    failure_reason = Column(Text, nullable=True, comment="AI生成失败原因")
    retry_count = Column(Integer, nullable=False, default=0, comment="重试次数")
    model_version = Column(String(64), nullable=True, comment="生成建议的AI模型版本")
    snapshot_version_id = Column(Integer, ForeignKey("test_case_versions.id", ondelete="SET NULL"), nullable=True, index=True, comment="应用时创建的快照版本ID(TestCaseVersion.id)，用于回滚")

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=utcnow, default=utcnow)

    test_case = relationship("TestCase", backref="refresh_suggestions")
    requirement = relationship("Requirement", backref="refresh_suggestions")
