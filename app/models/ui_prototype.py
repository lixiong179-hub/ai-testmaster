"""
UI原型模型模块

本模块定义了UI原型相关的数据模型，支持多种UI工具（摹客、蓝湖、Figma、Axure等）
的原型图存储、AI解析和与测试用例的关联。

核心类概览：
    - UIPrototypeSource   : UI原型来源类型常量类
    - UIPrototypeScreen   : UI原型屏幕模型，存储单页UI图及AI解析结果
    - UIScreenTestCaseLink: UI屏幕与测试用例的关联表
    - UIPrototypeProject  : UI原型项目模型，整组UI原型作为项目管理

表关系：
    Project → UIPrototypeScreen（一对多，级联删除）
    Project → UIPrototypeProject（一对多，级联删除）
    UIPrototypeScreen ←→ TestCase（多对多，通过 ui_screen_test_case_links 关联表）
    UIPrototypeScreen → UIPrototypeScreen（自引用，parent_screen_id 构成页面层级）
    UIPrototypeProject → UIPrototypeScreen（一对多，级联删除）
    Iteration → UIPrototypeProject（一对多，SET NULL）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类

重要说明：
    本模块必须在 test_case.py 之前导入，因为 TestCase 模型通过
    secondary="ui_screen_test_case_links" 引用本模块定义的关联表。
"""
from datetime import datetime
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base


class UIPrototypeSource(str):
    """
    UI原型来源类型常量类

    定义支持的UI设计工具来源，用于标识原型图的来源平台。

    Attributes:
        MOCKINGBOT : 摹客（国产UI设计协作平台）
        LANNHU     : 蓝湖（国产UI设计协作平台）
        FIGMA      : Figma（国际UI设计工具）
        AXURE      : Axure RP（原型设计工具）
        SKETCH     : Sketch（macOS UI设计工具）
        ADOBE_XD   : Adobe XD（Adobe UI设计工具）
        MANUAL     : 手工上传（用户直接上传图片）
        OTHER      : 其他来源
    """
    MOCKINGBOT = "mockingbot"  # 摹客
    LANNHU = "lannhu"  # 蓝湖
    FIGMA = "figma"
    AXURE = "axure"
    SKETCH = "sketch"
    ADOBE_XD = "adobe_xd"
    MANUAL = "manual"  # 手工上传
    OTHER = "other"


class UIPrototypeScreen(Base):
    """
    UI原型屏幕模型

    存储各种UI工具导出的每页UI图及其AI解析后的结构化规格（ui_spec），
    包括：页面元素、导航关系、布局约束、跳转流程等。
    支持页面层级结构（通过 parent_screen_id 自引用）。

    表关系：
        - 多对一 → Project（所属项目，级联删除）
        - 多对一 → User（创建者，SET NULL）
        - 自引用 → UIPrototypeScreen（父屏幕，SET NULL，构成页面层级）
        - 多对多 → TestCase（关联测试用例，通过 ui_screen_test_case_links）
        - 多对一 → UIPrototypeProject（所属原型项目，级联删除）

    使用场景：
        - 上传和管理UI原型截图
        - AI解析UI规格，提取页面元素和导航关系
        - 基于UI原型自动生成UI自动化测试用例
        - UI适配校验（布局校验点）
    """
    __tablename__ = "ui_prototype_screens"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)                            # 屏幕主键ID
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联项目ID")  # 项目ID，级联删除

    # 原型基本信息
    prototype_name = Column(String(200), nullable=False, comment="原型名称，如：答题模块v1.2")          # 原型名称，标识整组原型
    source = Column(String(50), nullable=False, default="manual", comment="UI工具来源：mockingbot/lannhu/figma/axure/manual/other")  # 原型来源工具
    screen_name = Column(String(200), nullable=False, comment="屏幕名称，如：答题页、结果页")           # 单页屏幕名称
    screen_order = Column(Integer, default=0, comment="屏幕顺序/页码")                                 # 屏幕在原型中的排列顺序

    # 文件存储
    original_file_path = Column(String(500), nullable=True, comment="原始UI图文件路径")                # 原型图文件存储路径
    original_file_name = Column(String(255), nullable=True, comment="原始文件名")                      # 上传时的原始文件名
    file_type = Column(String(20), nullable=False, default="png", comment="文件类型：png/jpg/webp")    # 图片格式
    file_size = Column(Integer, nullable=True, comment="文件大小（KB）")                               # 文件大小，单位KB

    # AI解析结果（核心字段）
    ui_spec = Column(JSON, nullable=True, comment="UI规格JSON，结构化解析结果")                        # AI解析出的UI规格，包含元素、布局、交互等
    ui_spec_version = Column(String(20), nullable=False, default="1.0", comment="解析规格版本")         # ui_spec的版本号，兼容格式升级
    parse_status = Column(String(20), nullable=False, default="pending", comment="解析状态：pending/running/completed/failed")  # pending=待解析，running=解析中，completed=已完成，failed=解析失败
    parse_error = Column(Text, nullable=True, comment="解析错误信息")                                  # 解析失败时的错误信息
    parse_model = Column(String(50), nullable=True, comment="解析使用的视觉模型")                      # AI视觉模型标识，如 gpt-4o、claude-3.5

    # 页面关系
    parent_screen_id = Column(Integer, ForeignKey("ui_prototype_screens.id", ondelete="SET NULL"), nullable=True, comment="父屏幕ID（用于页面层级）")  # 父屏幕ID，构成页面层级树
    related_screens = Column(JSON, nullable=True, comment="关联屏幕ID列表")                            # 关联的其他屏幕ID列表

    # 导航与流程
    navigation_flow = Column(JSON, nullable=True, comment="导航流向JSON，从本屏出发的可能跳转")         # 页面跳转关系，JSON格式
    is_entry_point = Column(Boolean, default=False, comment="是否为入口页面")                          # 标记是否为应用入口页面
    is_end_point = Column(Boolean, default=False, comment="是否为结束页面")                            # 标记是否为流程结束页面

    # 布局校验点（专门针对UI适配问题）
    layout_checks = Column(JSON, nullable=True, comment="布局校验点列表，如：底栏固定、弹窗遮罩等")      # UI适配校验规则列表

    # 解析摘要（用于前端快速展示）
    summary = Column(Text, nullable=True, comment="AI解析摘要，前端快速展示用")                        # AI生成的页面摘要
    element_count = Column(Integer, default=0, comment="识别出的元素数量")                             # AI识别出的UI元素总数
    button_count = Column(Integer, default=0, comment="按钮数量")                                      # AI识别出的按钮数量
    input_count = Column(Integer, default=0, comment="输入框数量")                                     # AI识别出的输入框数量

    # 审核状态
    review_status = Column(String(20), default="pending", comment="审核状态：pending/approved/rejected")  # pending=待审核，approved=已通过，rejected=已拒绝
    reviewed_by = Column(String(100), nullable=True, comment="审核人")                                 # 审核人用户名
    reviewed_at = Column(DateTime, nullable=True, comment="审核时间")                                  # 审核操作时间
    review_comment = Column(Text, nullable=True, comment="审核意见")                                   # 审核人填写的意见

    # 元数据
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)          # 创建者ID，SET NULL保留屏幕
    create_time = Column(DateTime, nullable=False, default=utcnow, comment="创建时间")                 # 创建时间，UTC时区
    update_time = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, comment="更新时间") # 更新时间

    # 关联关系
    project = relationship("Project", back_populates="ui_prototype_screens")                          # 所属项目
    creator = relationship("User", foreign_keys=[created_by])                                         # 创建者
    parent = relationship("UIPrototypeScreen", remote_side=[id], backref="children")                  # 父屏幕，自引用构成层级

    # 多对多关联（通过关联表）
    linked_test_cases = relationship(
        "TestCase",
        secondary="ui_screen_test_case_links",
        back_populates="linked_ui_screens"
    )                                                                                                # 关联的测试用例列表


class UIScreenTestCaseLink(Base):
    """
    UI屏幕与测试用例关联表

    建立UI原型屏幕与测试用例之间的多对多关联关系，
    支持从UI原型自动生成测试用例并保持追溯关系。

    关联类型：
        - source : 来源关联，用例是基于该UI屏幕生成的
        - documented : 已文档化，用例已覆盖该UI屏幕的测试
    """
    __tablename__ = "ui_screen_test_case_links"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)                            # 关联主键ID
    screen_id = Column(Integer, ForeignKey("ui_prototype_screens.id", ondelete="CASCADE"), nullable=False, comment="UI屏幕ID")  # 屏幕ID，级联删除
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, comment="测试用例ID")  # 用例ID，级联删除
    link_type = Column(String(20), default="source", comment="关联类型：source=来源/documented=已文档化")  # 关联类型
    create_time = Column(DateTime, nullable=False, default=utcnow)                                    # 创建时间


# 扩展Project模型添加关联关系
from app.models.project import Project
Project.ui_prototype_screens = relationship(
    "UIPrototypeScreen",
    back_populates="project",
    cascade="all, delete-orphan"
)                                                                                                    # 动态扩展Project模型，添加UI原型屏幕关联


class UIPrototypeProject(Base):
    """
    UI原型项目模型 - 整组UI原型作为一个项目管理

    将一组相关的UI原型屏幕组织为一个原型项目，支持多来源
    （摹客、蓝湖、Figma等）的原型项目管理。

    表关系：
        - 多对一 → Project（所属项目，级联删除）
        - 多对一 → User（创建者，SET NULL）
        - 多对一 → Iteration（关联迭代，SET NULL）
        - 一对多 → UIPrototypeScreen（屏幕列表，级联删除）

    使用场景：
        - 从摹客/蓝湖/Figma导入整组原型
        - 按迭代组织UI原型项目
        - 合并多页面的页面流转图
    """
    __tablename__ = "ui_prototype_projects"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)                            # 原型项目主键ID
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联项目ID")  # 项目ID，级联删除
    name = Column(String(200), nullable=False, comment="原型项目名称")                                 # 原型项目名称
    description = Column(Text, nullable=True, comment="原型描述")                                      # 原型项目描述
    source = Column(String(50), nullable=False, default="manual", comment="来源：mockingbot/lannhu/figma/axure/manual/other")  # 原型来源工具
    screen_count = Column(Integer, default=0, comment="屏幕总数")                                     # 原型项目包含的屏幕总数
    parsed_count = Column(Integer, default=0, comment="已解析数量")                                   # 已完成AI解析的屏幕数量
    parse_status = Column(String(20), default="pending", comment="整体解析状态")                      # 整体解析进度状态

    # 合并的页面流程
    merged_flow = Column(JSON, nullable=True, comment="多图合并后的页面流转图")                        # 多屏幕合并后的完整页面流转图

    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)          # 创建者ID，SET NULL保留项目
    create_time = Column(DateTime, nullable=False, default=utcnow)                                    # 创建时间，UTC时区
    update_time = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)                   # 更新时间

    iteration_id = Column(Integer, ForeignKey("iterations.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联迭代ID")  # 迭代ID，SET NULL保留项目
    iteration = relationship("Iteration", backref="ui_prototype_projects")                            # 所属迭代

    # 关联关系
    screens = relationship("UIPrototypeScreen", back_populates="prototype_project", cascade="all, delete-orphan")  # 屏幕列表，级联删除


# 扩展UIPrototypeScreen添加prototype_project关系
UIPrototypeScreen.prototype_project_id = Column(
    Integer,
    ForeignKey("ui_prototype_projects.id", ondelete="CASCADE"),
    nullable=True,
    comment="所属原型项目ID"
)                                                                                                    # 动态添加原型项目ID字段
UIPrototypeScreen.prototype_project = relationship(
    "UIPrototypeProject",
    back_populates="screens"
)                                                                                                    # 动态添加原型项目关联关系
