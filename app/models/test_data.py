"""
测试数据模型模块

本模块定义了测试步骤的数据驱动模型，支持多种数据类型和生成规则，
用于UI自动化测试中的参数化数据管理。

核心类概览：
    - DataType        : 测试数据类型枚举（文本、数字、日期、邮箱等）
    - GenerationRule  : 数据生成规则枚举（随机、边界值、特殊字符等）
    - TestData        : 测试数据模型，绑定到测试步骤的具体字段

表关系：
    TestStep → TestData（一对多，级联删除）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
import json
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.utils.db_time import utcnow
from enum import Enum

from app.db.database import Base


class DataType(str, Enum):
    """
    测试数据类型枚举

    定义测试数据支持的字段类型，用于数据校验和生成策略选择。

    Attributes:
        TEXT      : 文本类型，默认类型
        NUMBER    : 数字类型，支持整数和浮点数
        DATE      : 日期类型，格式 YYYY-MM-DD
        DATETIME  : 日期时间类型，格式 YYYY-MM-DD HH:MM:SS
        EMAIL     : 邮箱类型，符合邮箱格式校验
        PHONE     : 手机号类型，符合手机号格式校验
        ENUM      : 枚举类型，从预定义值列表中选择
        BOOLEAN   : 布尔值类型，True/False
        URL       : URL类型，符合URL格式校验
        ID_CARD   : 身份证号类型，符合18位身份证格式
        BANK_CARD : 银行卡号类型，符合银行卡号格式
    """
    TEXT = "text"           # 文本
    NUMBER = "number"       # 数字
    DATE = "date"           # 日期
    DATETIME = "datetime"   # 日期时间
    EMAIL = "email"         # 邮箱
    PHONE = "phone"         # 手机号
    ENUM = "enum"           # 枚举
    BOOLEAN = "boolean"     # 布尔值
    URL = "url"             # URL
    ID_CARD = "id_card"     # 身份证号
    BANK_CARD = "bank_card" # 银行卡号


class GenerationRule(str, Enum):
    """
    数据生成规则枚举

    定义测试数据的生成策略，用于自动化测试中的数据驱动。

    Attributes:
        RANDOM        : 随机生成，根据字段类型生成随机合法值
        BOUNDARY_MIN  : 边界值-最小，生成字段允许的最小值
        BOUNDARY_MAX  : 边界值-最大，生成字段允许的最大值
        BOUNDARY_OVER : 边界值-超长，生成超出字段限制的值
        SPECIAL_CHARS : 特殊字符，注入特殊字符测试系统鲁棒性
        EMPTY         : 空值，测试空值处理逻辑
        CUSTOM        : 自定义，用户手动指定数据值
    """
    RANDOM = "random"           # 随机生成
    BOUNDARY_MIN = "boundary_min"   # 边界值-最小
    BOUNDARY_MAX = "boundary_max"   # 边界值-最大
    BOUNDARY_OVER = "boundary_over" # 边界值-超长
    SPECIAL_CHARS = "special_chars" # 特殊字符
    EMPTY = "empty"             # 空值
    CUSTOM = "custom"           # 自定义

class TestData(Base):
    """
    测试数据模型

    存储测试步骤的具体测试数据，支持多种数据类型和生成规则。
    每条测试数据绑定到特定的测试步骤和字段名称，实现数据驱动测试。

    表关系：
        - 多对一 → TestStep（所属步骤，级联删除）

    使用场景：
        - UI自动化测试的参数化数据管理
        - 按生成规则自动生成测试数据
        - 边界值和特殊字符测试数据准备
    """
    __tablename__ = "test_data"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 数据主键ID
    step_id = Column(Integer, ForeignKey("test_steps.id", ondelete="CASCADE"), nullable=False, comment="关联的测试步骤ID")  # 步骤ID，级联删除

    # 数据基本信息
    field_name = Column(String(100), nullable=False, comment="字段名称")                               # 对应页面表单字段的名称
    field_type = Column(SQLEnum(DataType, length=20), nullable=False, default=DataType.TEXT, comment="字段类型")  # type: ignore  # 字段数据类型，默认文本
    data_value = Column(Text, nullable=True, comment="数据值")                                         # 实际数据值

    # 生成规则
    generation_rule = Column(SQLEnum(GenerationRule, length=20), nullable=False, default=GenerationRule.RANDOM, comment="生成规则")  # type: ignore  # 数据生成策略，默认随机
    rule_config = Column(Text, nullable=True, comment="生成规则配置(JSON格式)")                         # 生成规则的额外配置，如正则表达式、格式模板等

    # 约束条件
    min_length = Column(Integer, nullable=True, comment="最小长度")                                    # 文本类型的最小长度约束
    max_length = Column(Integer, nullable=True, comment="最大长度")                                    # 文本类型的最大长度约束
    min_value = Column(Integer, nullable=True, comment="最小值(数字类型)")                              # 数字类型的最小值约束
    max_value = Column(Integer, nullable=True, comment="最大值(数字类型)")                              # 数字类型的最大值约束
    enum_values = Column(Text, nullable=True, comment="枚举值列表(JSON数组)")                           # ENUM类型的可选值列表

    # 元数据
    description = Column(String(500), nullable=True, comment="数据描述")                               # 字段用途说明
    is_required = Column(Boolean, default=True, comment="是否必填")                                    # 字段是否必填，默认True
    sort_order = Column(Integer, default=0, comment="排序顺序")                                        # 同一步骤内字段的显示顺序

    # 时间信息
    created_at = Column(DateTime, default=utcnow, comment="创建时间")                                  # 创建时间，UTC时区
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, comment="更新时间")                  # 更新时间

    # 关联关系
    step = relationship("TestStep", back_populates="test_data")                                       # 所属测试步骤

    def __repr__(self) -> str:
        """返回测试数据的字符串表示，便于调试和日志输出。"""
        return f"<TestData(id={self.id}, step_id={self.step_id}, field_name='{self.field_name}')>"

    def to_dict(self) -> dict:
        """
        将测试数据转换为字典格式。

        Returns:
            dict: 包含所有字段的字典，枚举值转换为字符串，
                  JSON字符串字段解析为Python对象，
                  时间字段转换为ISO格式字符串。
        """
        return {
            "id": self.id,
            "step_id": self.step_id,
            "field_name": self.field_name,
            "field_type": self.field_type.value if self.field_type else None,
            "data_value": self.data_value,
            "generation_rule": self.generation_rule.value if self.generation_rule else None,
            "rule_config": json.loads(str(self.rule_config)) if self.rule_config else None,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "enum_values": json.loads(str(self.enum_values)) if self.enum_values else None,
            "description": self.description,
            "is_required": bool(self.is_required),
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
