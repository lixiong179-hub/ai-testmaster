"""
项目模型模块

本模块定义了多项目隔离体系的核心表，所有业务数据（测试用例、测试点、
测试任务、迭代等）均通过 project_id 实现租户级数据隔离。

核心类概览：
    - Project     : 项目主表，存储项目基本信息、测试对象配置和多环境配置
    - ProjectFile : 项目文件表，管理需求文档、UI原型图等资源文件

表关系：
    User → Project（一对多，用户拥有多个项目）
    Project → ProjectFile（一对多，级联删除）
    Project → TestCase（一对多，级联删除）
    Project → TestPoint（一对多，级联删除）
    Project → TestTask（一对多，级联删除）
    Project → TestReport（一对多，级联删除）
    Project → Iteration（一对多，级联删除）
    Iteration → ProjectFile（一对多，SET NULL删除）

依赖关系：
    - app.utils.crypto.encrypt_password / decrypt_password : 测试账号密码加解密
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类

安全说明：
    测试对象密码通过 test_object_password 属性自动加解密，
    数据库中仅存储加密后的密文（test_object_password_encrypted 列）。
"""
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean, Index, and_, text as sa_text
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.utils.crypto import encrypt_password, decrypt_password


class Project(Base):
    """
    项目主表 - 多项目隔离核心

    每个项目独立管理测试用例、测试点、测试任务等数据，
    通过 project_id 外键实现租户级数据隔离。

    表关系：
        - 多对一 → User（项目所有者）
        - 一对多 → ProjectFile（项目文件，级联删除）
        - 一对多 → TestCase（测试用例，级联删除）
        - 一对多 → TestPoint（测试点，级联删除）
        - 一对多 → TestTask（测试任务，级联删除）
        - 一对多 → TestReport（测试报告，级联删除）
        - 一对多 → Iteration（迭代，级联删除）

    使用场景：
        - 项目创建、编辑、归档
        - 配置测试对象（Web/客户端）及多环境信息
        - 作为所有业务数据的隔离边界
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)                          # 项目主键ID
    name = Column(String(255), nullable=False, comment="项目名称")                                    # 项目名称，必填
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属用户ID")  # 项目所有者，级联删除
    description = Column(Text, nullable=True, comment="项目描述")                                     # 项目描述，可选
    status = Column(Integer, nullable=False, default=1, comment="状态: 0未激活/1正常/2归档")            # 项目状态，默认1正常
    config = Column(JSON, nullable=True, comment="项目个性化配置")                                    # 项目级个性化配置，JSON格式
    is_self_test = Column(Boolean, nullable=False, default=False, server_default=sa_text("0"), comment="是否为平台自测项目")
    self_test_schedule = Column(String(100), nullable=True, comment="自测项目定时执行 cron 表达式")

    # 项目类型: web=Web端, app=客户端(Android/iOS)
    project_type = Column(String(50), nullable=False, default="web", comment="项目类型: web=Web端, app=客户端")  # 默认Web端

    # Web端配置（简化版，兼容旧数据）
    web_config = Column(JSON, nullable=True, comment="Web端配置")                                    # Web端项目配置，如浏览器类型、窗口大小等
    client_config = Column(JSON, nullable=True, comment="客户端配置")                                 # 客户端项目配置，如设备平台、App路径等

    # 测试对象信息
    test_object_type = Column(String(20), nullable=True, comment="测试对象类型: web/app/api")          # 测试对象类型
    test_object_url = Column(String(1000), nullable=True, comment="测试对象URL地址")                   # 被测系统URL
    test_object_username = Column(String(255), nullable=True, comment="测试账号用户名")                # 被测系统登录账号
    test_object_password_encrypted = Column("test_object_password", String(255), nullable=True, comment="测试账号密码(加密)")  # 数据库列名为test_object_password，存储加密密文
    test_object_device_info = Column(Text, nullable=True, comment="设备连接信息（JSON格式）")           # 客户端测试的设备连接参数
    test_object_app_package = Column(String(255), nullable=True, comment="App包名（Android/iOS）")     # Android包名或iOS Bundle ID
    test_object_app_activity = Column(String(255), nullable=True, comment="App启动Activity")           # Android启动Activity

    # Web端多环境配置 (测试/灰度/正式) - 保留兼容性
    # 存储格式: {"test": {"url": "", "username": "", "password": ""}, "staging": {...}, "prod": {...}}
    web_env_configs = Column(JSON, nullable=True, comment="Web端多环境配置")                           # 多环境URL和账号配置

    # C端设备连接信息(预留)
    device_config = Column(JSON, nullable=True, comment="C端设备连接信息")                             # 预留字段，客户端设备配置

    create_time = Column(DateTime, nullable=False, default=utcnow, comment="创建时间")                 # 创建时间，UTC时区
    update_time = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, comment="更新时间") # 更新时间，自动更新

    @property
    def test_object_password(self) -> str:
        """
        获取测试对象密码的明文值。

        Returns:
            str: 解密后的密码明文；若未设置则返回 None。

        注意：仅在业务层使用，不持久化明文密码。
        """
        if self.test_object_password_encrypted is None:
            return None
        return decrypt_password(self.test_object_password_encrypted)

    @test_object_password.setter
    def test_object_password(self, value: str) -> None:
        """
        设置测试对象密码，自动加密后存储。

        Args:
            value: 密码明文。若为 None 或空字符串，则清除加密字段。

        安全说明：密码通过 app.utils.crypto 加密后存储到数据库，
        数据库中仅保留密文，防止明文泄露。
        """
        if value is None or value == "":
            self.test_object_password_encrypted = None
        else:
            self.test_object_password_encrypted = encrypt_password(value)

    # 关联关系 - 所有子表通过project_id隔离
    owner = relationship("User", back_populates="projects", foreign_keys=[user_id])                   # 项目所有者
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")       # 项目文件，级联删除
    test_cases = relationship("TestCase", back_populates="project", cascade="all, delete-orphan",
                              primaryjoin="and_(Project.id == TestCase.project_id, TestCase.is_deleted == False)")     # 测试用例，级联删除，排除软删除
    test_points = relationship("TestPoint", back_populates="project", cascade="all, delete-orphan")   # 测试点，级联删除
    test_tasks = relationship("TestTask", back_populates="project", cascade="all, delete-orphan")     # 测试任务，级联删除
    test_reports = relationship("TestReport", back_populates="project", cascade="all, delete-orphan") # 测试报告，级联删除
    iterations = relationship("Iteration", back_populates="project", cascade="all, delete-orphan")    # 迭代，级联删除
    test_capabilities = relationship("TestCapability", back_populates="project", cascade="all, delete-orphan")  # 业务能力，级联删除


class ProjectFile(Base):
    """
    项目文件表 - 文件隔离存储

    管理项目中的资源文件，包括需求文档、UI原型图、接口文档等。
    支持文件内容提取（用于AI生成测试用例），并按资源类型和排序序号组织。

    表关系：
        - 多对一 → Project（项目文件，级联删除）
        - 多对一 → Iteration（迭代文件，SET NULL删除）

    索引设计：
        - ix_project_file_sort(project_id, resource_type, sort_order) :
          支持按项目+资源类型查询并按排序序号排列，是文件列表页的核心查询

    使用场景：
        - 上传需求文档、UI原型图等资源文件
        - AI从文件内容自动生成测试用例
        - 按迭代组织文件
    """
    __tablename__ = "project_files"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)                           # 文件主键ID
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联项目ID，多项目隔离核心")  # 项目ID，级联删除
    file_name = Column(String(500), nullable=False, comment="文件名")                                 # 原始文件名
    file_type = Column(String(50), nullable=False, comment="文件格式: docx/pdf/xlsx/png/jpg/figma")   # 文件扩展名
    file_url = Column(String(1000), nullable=False, comment="文件存储路径")                           # 文件在存储服务中的路径
    file_source = Column(String(20), nullable=False, default="file", comment="file=本地上传")          # 文件来源，预留扩展
    size = Column(Integer, nullable=True, comment="文件大小，单位KB")                                 # 文件大小，单位KB
    upload_time = Column(DateTime, nullable=False, default=utcnow, comment="上传时间")                 # 上传时间

    # 资源类型：需求文档、UI原型图、接口文档、测试数据、其他
    resource_type = Column(String(50), nullable=True, default="other", comment="资源类型: requirement/ui_mockup/api_doc/test_data/other")  # 文件分类
    # 从文件中提取的文本内容（用于AI生成测试用例）
    content = Column(Text, nullable=True, comment="从文件提取的文本内容")                              # AI用例生成的输入源
    # 内容提取状态：pending/processing/completed/failed
    extract_status = Column(String(20), nullable=False, default="pending", comment="内容提取状态")      # pending=待提取，processing=提取中，completed=已完成，failed=失败
    extract_error = Column(Text, nullable=True, comment="提取失败原因")                                # 提取失败时的错误信息
    extracted_at = Column(DateTime, nullable=True, comment="内容提取时间")                             # 内容提取完成时间
    # 文件描述
    description = Column(Text, nullable=True, comment="文件描述")                                     # 用户填写的文件说明
    # 是否启用（软删除）
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")                      # 软删除标记，False表示已停用
    # 排序序号（用于控制显示顺序，同类型内按此字段升序排列）
    sort_order = Column(Integer, nullable=True, default=0, comment="排序序号")                        # 同类型文件内的显示顺序

    __table_args__ = (
        Index('ix_project_file_sort', 'project_id', 'resource_type', 'sort_order'),                  # 复合索引：按项目+类型查询并排序
    )
    # 关联的测试用例数量
    linked_case_count = Column(Integer, nullable=False, default=0, comment="关联测试用例数量")          # 冗余计数，避免频繁关联查询

    iteration_id = Column(Integer, ForeignKey("iterations.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联迭代ID")  # 迭代ID，SET NULL保留文件
    iteration = relationship("Iteration", backref="files")                                           # 所属迭代

    project = relationship("Project", back_populates="files")                                        # 所属项目
