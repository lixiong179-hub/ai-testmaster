from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from app.utils.db_time import utcnow
from app.db.database import Base


class HistoryAsset(Base):
    __tablename__ = "history_assets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type = Column(String(30), nullable=False, comment="资产类型: excel/xmind/system_cases")
    file_path = Column(String(500), nullable=True, comment="上传文件路径")
    original_filename = Column(String(255), nullable=True, comment="原始文件名")
    parse_status = Column(String(30), nullable=False, default="pending", comment="解析状态: pending/parsing/completed/failed")
    parse_error = Column(String(500), nullable=True, comment="解析失败原因")
    parsed_cases_json = Column(JSON, nullable=True, comment="解析后的结构化历史用例数据")
    case_count = Column(Integer, nullable=False, default=0, comment="解析出的用例数量")
    batch_id = Column(Integer, ForeignKey("generation_batches.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联的生成批次ID")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=utcnow, default=utcnow)

    project = relationship("Project", backref="history_assets")
    user = relationship("User", backref="history_assets")

    __table_args__ = (
        Index("ix_history_asset_project_created", "project_id", "created_at"),
        Index("ix_history_asset_project_type", "project_id", "asset_type"),
    )
