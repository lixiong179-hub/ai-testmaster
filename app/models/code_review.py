"""
代码审查模型模块

本模块定义了代码审查流程的完整数据模型，包括审查任务、问题项、
评论和指标统计，支持团队代码质量管控。

核心类概览：
    - CodeReview   : 代码审查主表，管理审查任务的状态和基本信息
    - ReviewItem   : 审查问题项，记录代码中发现的每个问题
    - ReviewComment: 审查评论，支持对审查和问题项的讨论
    - ReviewMetric : 审查指标统计，记录代码质量指标

表关系：
    User → CodeReview（一对多，审查人）
    User → CodeReview（一对多，作者）
    CodeReview → ReviewItem（一对多，级联删除）
    CodeReview → ReviewComment（一对多，级联删除）
    CodeReview → ReviewMetric（一对多，级联删除）
    ReviewItem → ReviewComment（一对多，级联删除）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.database import Base


class CodeReview(Base):
    """
    代码审查主表

    管理代码审查任务，包括审查的仓库信息、人员分配和状态流转。
    支持全量审查（full）、快速审查（quick）和安全审查（security）三种类型。

    表关系：
        - 多对一 → User（审查人）
        - 多对一 → User（作者）
        - 一对多 → ReviewItem（问题项，级联删除）
        - 一对多 → ReviewComment（评论，级联删除）
        - 一对多 → ReviewMetric（指标，级联删除）

    使用场景：
        - 创建代码审查任务
        - AI辅助代码审查
        - 审查结果跟踪和统计
    """
    __tablename__ = "code_reviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 审查主键ID

    # 基本信息
    title = Column(String(255), nullable=False, comment="审查标题")                                     # 审查标题
    description = Column(Text, nullable=True, comment="审查描述")                                      # 审查描述

    # 仓库信息
    repository = Column(String(255), nullable=False, comment="代码仓库地址")                            # Git仓库URL
    branch = Column(String(100), nullable=False, comment="分支名称")                                   # 审查的Git分支
    commit_id = Column(String(100), nullable=True, comment="提交ID（commit hash）")                    # 具体审查的commit

    # 人员
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="审查人ID")          # 审查人
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="作者ID")              # 代码作者

    # 状态和类型
    status = Column(SQLEnum('pending', 'in_progress', 'completed', 'cancelled', name='review_status'), nullable=True, default='pending', comment="审查状态")  # pending=待审查，in_progress=审查中，completed=已完成，cancelled=已取消
    review_type = Column(SQLEnum('full', 'quick', 'security', name='review_type'), nullable=True, comment="审查类型: full/quick/security")  # full=全量审查，quick=快速审查，security=安全审查

    # 时间信息
    created_at = Column(DateTime, nullable=True, default=utcnow)                                      # 创建时间
    updated_at = Column(DateTime, nullable=True, onupdate=utcnow)                                     # 更新时间
    completed_at = Column(DateTime, nullable=True, comment="完成时间")                                 # 审查完成时间

    # 关联关系
    reviewer = relationship("User", foreign_keys=[reviewer_id])                                       # 审查人
    author = relationship("User", foreign_keys=[author_id])                                           # 代码作者
    review_items = relationship("ReviewItem", back_populates="review", cascade="all, delete-orphan")  # 问题项，级联删除
    comments = relationship("ReviewComment", back_populates="review", cascade="all, delete-orphan")   # 评论，级联删除
    metrics = relationship("ReviewMetric", back_populates="review", cascade="all, delete-orphan")     # 指标，级联删除

    def __repr__(self) -> str:
        """返回代码审查的字符串表示，便于调试和日志输出。"""
        return f"<CodeReview(id={self.id}, title='{self.title}')>"


class ReviewItem(Base):
    """
    审查问题项

    记录代码审查中发现的每个问题，包括文件位置、严重程度和修复建议。
    每个问题项有独立的状态流转（open -> acknowledged -> fixed/wontfix）。

    表关系：
        - 多对一 → CodeReview（所属审查，级联删除）
        - 一对多 → ReviewComment（评论，级联删除）

    使用场景：
        - 记录代码审查发现的问题
        - 问题状态跟踪和修复确认
    """
    __tablename__ = "review_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 问题项主键ID

    # 关联
    review_id = Column(Integer, ForeignKey("code_reviews.id", ondelete="CASCADE"), nullable=False, index=True)  # 审查ID，级联删除

    # 文件位置
    file_path = Column(String(500), nullable=False, comment="文件路径")                                # 问题所在文件路径
    line_start = Column(Integer, nullable=False, comment="起始行号")                                   # 问题起始行号
    line_end = Column(Integer, nullable=False, comment="结束行号")                                     # 问题结束行号

    # 问题详情
    severity = Column(SQLEnum('critical', 'major', 'minor', 'suggestion', name='issue_severity'), nullable=True, comment="严重程度")  # critical=致命，major=严重，minor=一般，suggestion=建议
    issue_type = Column(String(100), nullable=False, comment="问题类型: bug/style/performance/security/documentation")  # bug=缺陷，style=风格，performance=性能，security=安全，documentation=文档
    description = Column(Text, nullable=False, comment="问题描述")                                     # 问题描述
    recommendation = Column(Text, nullable=True, comment="修复建议")                                  # 修复建议

    # 状态
    status = Column(SQLEnum('open', 'acknowledged', 'fixed', 'wontfix', name='item_status'), nullable=True, default='open', comment="处理状态")  # open=待处理，acknowledged=已确认，fixed=已修复，wontfix=不修复

    # 时间信息
    created_at = Column(DateTime, default=utcnow)                                                     # 创建时间
    updated_at = Column(DateTime, onupdate=utcnow, default=utcnow)                                    # 更新时间

    # 关联关系
    review = relationship("CodeReview", back_populates="review_items")                                # 所属审查
    comments = relationship("ReviewComment", back_populates="review_item", cascade="all, delete-orphan")  # 评论，级联删除

    def __repr__(self) -> str:
        """返回问题项的字符串表示，便于调试和日志输出。"""
        return f"<ReviewItem(id={self.id}, file='{self.file_path}', lines={self.line_start}-{self.line_end})>"


class ReviewComment(Base):
    """
    审查评论

    支持对代码审查整体或具体问题项的讨论评论。

    表关系：
        - 多对一 → CodeReview（所属审查，级联删除）
        - 多对一 → ReviewItem（关联问题项，SET NULL）
        - 多对一 → User（评论者）

    使用场景：
        - 审查人对代码的讨论和反馈
        - 问题项的修复讨论
    """
    __tablename__ = "review_comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 评论主键ID

    # 关联
    review_id = Column(Integer, ForeignKey("code_reviews.id", ondelete="CASCADE"), nullable=False, index=True)  # 审查ID，级联删除
    review_item_id = Column(Integer, ForeignKey("review_items.id", ondelete="SET NULL"), nullable=True, comment="关联的问题项ID")  # 问题项ID，SET NULL保留评论
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="评论者ID")              # 评论者

    # 评论内容
    content = Column(Text, nullable=False, comment="评论内容")                                         # 评论正文

    # 时间信息
    created_at = Column(DateTime, default=utcnow)                                                     # 创建时间

    # 关联关系
    review = relationship("CodeReview", back_populates="comments")                                    # 所属审查
    review_item = relationship("ReviewItem", back_populates="comments")                               # 关联问题项
    user = relationship("User")                                                                       # 评论者

    def __repr__(self) -> str:
        """返回评论的字符串表示，便于调试和日志输出。"""
        return f"<ReviewComment(id={self.id}, user_id={self.user_id})>"


class ReviewMetric(Base):
    """
    审查指标统计

    记录代码审查的质量指标数据，如问题总数、覆盖率评分、平均复杂度等。
    每个指标以键值对形式存储，支持灵活的指标扩展。

    表关系：
        - 多对一 → CodeReview（所属审查，级联删除）

    使用场景：
        - 代码质量指标统计和趋势分析
        - 审查报告中的指标展示
    """
    __tablename__ = "review_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 指标主键ID

    # 关联
    review_id = Column(Integer, ForeignKey("code_reviews.id", ondelete="CASCADE"), nullable=False, index=True)  # 审查ID，级联删除

    # 指标数据
    metric_name = Column(String(100), nullable=False, comment="指标名称: total_issues/coverage_score/complexity_avg")  # 指标名称
    metric_value = Column(String(255), nullable=False, comment="指标值")                               # 指标值，字符串格式存储

    # 时间
    created_at = Column(DateTime, default=utcnow)                                                     # 创建时间

    # 关联关系
    review = relationship("CodeReview", back_populates="metrics")                                     # 所属审查

    def __repr__(self) -> str:
        """返回指标的字符串表示，便于调试和日志输出。"""
        return f"<ReviewMetric(id={self.id}, name='{self.metric_name}', value='{self.metric_value}')>"
