"""
元素定位器模型模块

本模块定义了UI自动化测试中的元素定位器（ElementLocator）模型，
支持多重定位策略（CSS/XPath/ID/Name/AI坐标），并记录定位成功率
和乐观锁版本号，确保并发安全。

核心类概览：
    - ElementLocator : 元素定位器模型，支持多重定位策略和成功率统计

表关系：
    TestStep → ElementLocator（一对一，级联删除）
    TestCasePreconditionStep → ElementLocator（一对一，级联删除）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类

定位策略优先级：
    CSS选择器 > XPath > 元素ID > 元素Name > AI坐标识别
"""
from app.utils.db_time import utcnow
from typing import Optional, Dict, Any, List

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, text
from sqlalchemy.orm import relationship

from app.db.database import Base


class ElementLocator(Base):
    """
    元素定位器模型

    存储UI自动化测试步骤的元素定位信息，支持多重定位策略。
    每个定位器可同时存储CSS选择器、XPath、元素ID、Name属性和AI坐标，
    执行时按优先级选择最佳可用策略。

    表关系：
        - 一对一 → TestStep（测试步骤，级联删除）
        - 一对一 → TestCasePreconditionStep（前置条件步骤，级联删除）

    并发安全：
        使用乐观锁（version字段）确保并发更新时数据一致性，
        atomic_record_success/atomic_record_failure 方法通过
        WHERE version = :version 条件实现原子更新。

    使用场景：
        - UI自动化录制时记录元素定位信息
        - 执行时按优先级选择最佳定位策略
        - 统计定位成功率，辅助定位策略优化
    """
    __tablename__ = "element_locators"

    id = Column(Integer, primary_key=True, index=True)                                                # 定位器主键ID
    step_id = Column(Integer, ForeignKey("test_steps.id", ondelete="CASCADE"), nullable=True, index=True, unique=True, comment="关联的测试步骤ID（前置条件步骤时为NULL")  # 测试步骤ID，唯一约束，级联删除
    precondition_step_id = Column(Integer, ForeignKey("test_case_precondition_steps.id", ondelete="CASCADE"), nullable=True, index=True, comment="关联前置条件步骤ID")  # 前置条件步骤ID，级联删除

    test_step = relationship("TestStep", back_populates="element_locator")                            # 关联的测试步骤
    precondition_step = relationship("TestCasePreconditionStep", back_populates="element_locator")    # 关联的前置条件步骤

    element_description = Column(String(255), nullable=True, comment="元素描述（如'登录按钮'）")        # 元素的自然语言描述
    element_type = Column(String(50), nullable=True, comment="元素类型（button/input/link等）")        # HTML元素类型

    # 定位策略字段（按优先级排列）
    css_selector = Column(String(500), nullable=True, comment="CSS选择器（优先级最高）")                # CSS选择器，优先级1
    xpath = Column(String(500), nullable=True, comment="XPath（次优先级）")                            # XPath表达式，优先级2
    element_id = Column(String(100), nullable=True, comment="元素ID")                                 # HTML id属性，优先级3
    element_name = Column(String(100), nullable=True, comment="元素name属性")                         # HTML name属性，优先级4
    element_class = Column(String(255), nullable=True, comment="元素class")                           # HTML class属性
    element_text = Column(String(500), nullable=True, comment="元素文本内容")                          # 元素的可见文本

    # AI识别相关
    ai_coordinate = Column(JSON, nullable=True, comment="AI识别坐标{x,y,width,height}")                # AI视觉识别的坐标区域，优先级5
    ai_confidence = Column(Float, default=0.0, comment="AI识别置信度")                                 # AI识别的置信度，0.0-1.0

    # 统计信息
    success_count = Column(Integer, default=0, comment="成功次数")                                     # 定位成功次数
    fail_count = Column(Integer, default=0, comment="失败次数")                                        # 定位失败次数
    last_used_at = Column(DateTime, nullable=True, comment="最后使用时间")                             # 最近一次使用该定位器的时间

    # 来源和版本
    source = Column(String(20), default="ai", comment="定位来源：ai(AI识别)/manual(人工录入)/auto(自动生成)")  # 定位信息的来源方式
    version = Column(Integer, default=0, comment="乐观锁版本号")                                       # 乐观锁版本号，用于并发控制

    created_at = Column(DateTime, default=utcnow, comment="创建时间")                                  # 创建时间，UTC时区
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, comment="更新时间")                  # 更新时间

    def __repr__(self) -> str:
        """返回定位器的字符串表示，便于调试和日志输出。"""
        return f"<ElementLocator(id={self.id}, step_id={self.step_id}, css={self.css_selector})>"

    @property
    def priority_order(self) -> List[str]:
        """
        获取可用的定位策略优先级列表。

        Returns:
            List[str]: 按优先级排列的可用策略名称列表，
                       如 ["css", "xpath", "id"]。
        """
        strategies = []
        if self.css_selector:
            strategies.append("css")
        if self.xpath:
            strategies.append("xpath")
        if self.element_id:
            strategies.append("id")
        if self.element_name:
            strategies.append("name")
        if self.ai_coordinate:
            strategies.append("ai")
        return strategies

    def to_dict(self) -> Dict[str, Any]:
        """
        将定位器信息转换为字典格式。

        Returns:
            Dict[str, Any]: 包含定位器核心字段的字典，
                            包括优先级策略列表。
        """
        return {
            "id": self.id,
            "step_id": self.step_id,
            "css_selector": self.css_selector,
            "xpath": self.xpath,
            "element_id": self.element_id,
            "element_name": self.element_name,
            "element_class": self.element_class,
            "element_text": self.element_text,
            "ai_coordinate": self.ai_coordinate,
            "ai_confidence": self.ai_confidence,
            "priority_order": self.priority_order,
        }

    def record_success(self) -> None:
        """记录一次定位成功，更新成功计数、使用时间和版本号。"""
        self.success_count = (self.success_count or 0) + 1
        self.last_used_at = utcnow()
        self.version = (self.version or 0) + 1

    def record_failure(self) -> None:
        """记录一次定位失败，更新失败计数、使用时间和版本号。"""
        self.fail_count = (self.fail_count or 0) + 1
        self.last_used_at = utcnow()
        self.version = (self.version or 0) + 1

    @staticmethod
    def atomic_record_success(db, locator_id: int, current_version: int) -> bool:
        """
        原子化记录定位成功（乐观锁）。

        通过 WHERE id = :id AND version = :version 条件确保并发安全，
        只有版本号匹配时才更新，避免覆盖其他并发修改。

        注意：本方法仅执行 flush，不 commit。由调用方管理事务边界。

        Args:
            db: 数据库会话
            locator_id: 定位器ID
            current_version: 当前版本号

        Returns:
            bool: 更新是否成功，True表示版本号匹配且已更新
        """
        result = db.execute(text(
            "UPDATE element_locators SET success_count = success_count + 1, "
            "last_used_at = UTC_TIMESTAMP(), version = version + 1 "
            "WHERE id = :id AND version = :version"
        ), {"id": locator_id, "version": current_version})
        db.flush()
        return result.rowcount > 0

    @staticmethod
    def atomic_record_failure(db, locator_id: int, current_version: int) -> bool:
        """
        原子化记录定位失败（乐观锁）。

        通过 WHERE id = :id AND version = :version 条件确保并发安全，
        只有版本号匹配时才更新，避免覆盖其他并发修改。

        注意：本方法仅执行 flush，不 commit。由调用方管理事务边界。

        Args:
            db: 数据库会话
            locator_id: 定位器ID
            current_version: 当前版本号

        Returns:
            bool: 更新是否成功，True表示版本号匹配且已更新
        """
        result = db.execute(text(
            "UPDATE element_locators SET fail_count = fail_count + 1, "
            "last_used_at = UTC_TIMESTAMP(), version = version + 1 "
            "WHERE id = :id AND version = :version"
        ), {"id": locator_id, "version": current_version})
        db.flush()
        return result.rowcount > 0

    @staticmethod
    def validate_coordinate(coordinate: dict) -> bool:
        """
        校验AI坐标数据格式是否合法。

        合法坐标需包含 x/y/width/height 中的至少一个，
        且所有数值必须为非负数。

        Args:
            coordinate: 坐标字典，如 {"x": 100, "y": 200, "width": 50, "height": 30}

        Returns:
            bool: 坐标数据是否合法
        """
        if not isinstance(coordinate, dict):
            return False
        for key in ["x", "y", "width", "height"]:
            if key in coordinate:
                val = coordinate[key]
                if val is not None:
                    try:
                        num = float(val)
                        if num < 0:
                            return False
                    except (ValueError, TypeError):
                        return False
        return True

    @property
    def success_rate(self) -> float:
        """
        计算定位成功率。

        Returns:
            float: 成功率，0.0-1.0；无使用记录时返回0.0
        """
        total = (self.success_count or 0) + (self.fail_count or 0)
        if total == 0:
            return 0.0
        return (self.success_count or 0) / total

    def get_best_locator(self) -> Optional[Dict[str, Any]]:
        """
        获取最佳可用定位策略。

        按优先级 CSS > XPath > ID > Name > AI 依次检查，
        返回第一个非空的定位策略。

        Returns:
            Optional[Dict[str, Any]]: 最佳定位策略字典，
                格式为 {"type": "css", "value": "..."}，
                无可用策略时返回 None。
        """
        if self.css_selector:
            return {"type": "css", "value": self.css_selector}
        if self.xpath:
            return {"type": "xpath", "value": self.xpath}
        if self.element_id:
            return {"type": "id", "value": self.element_id}
        if self.element_name:
            return {"type": "name", "value": self.element_name}
        if self.ai_coordinate:
            coordinate = self.ai_coordinate if isinstance(self.ai_coordinate, dict) else {}
            if coordinate:
                coordinate = coordinate.copy()
                for key in ["x", "y", "width", "height"]:
                    if key in coordinate and isinstance(coordinate[key], list):
                        coordinate[key] = coordinate[key][0] if coordinate[key] else 0
                return {"type": "ai", "value": coordinate}
        return None
