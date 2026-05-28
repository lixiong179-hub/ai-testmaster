"""
测试结果模型模块

本模块定义了测试结果（TestResult）模型，记录每条测试用例在任务执行中的
详细结果，包括执行状态、日志、截图、AI分析等。

核心类概览：
    - TestResult : 测试结果模型，记录单条用例的执行详情

表关系：
    TestTask → TestResult（一对多，级联删除）
    Project → TestResult（一对多，级联删除）
    TestCase → TestResult（一对多，级联删除）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, and_
from sqlalchemy.orm import relationship
from app.utils.db_time import utcnow
from app.db.database import Base


class TestResult(Base):
    """
    执行结果表

    记录每条测试用例在特定任务中的执行结果，包括执行状态、日志、
    错误信息、截图路径以及AI智能分析结果。

    表关系：
        - 多对一 → TestTask（所属任务，级联删除）
        - 多对一 → Project（所属项目，级联删除）
        - 多对一 → TestCase（所属用例，级联删除）

    使用场景：
        - 测试任务执行后查看每条用例的执行结果
        - 失败用例的错误信息查看和截图展示
        - AI分析失败原因并给出改进建议
        - 按项目/用例/状态筛选执行结果
    """
    __tablename__ = "test_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)                                        # 结果主键ID
    task_id = Column(Integer, ForeignKey("test_tasks.id", ondelete="SET NULL"), nullable=True, comment="任务ID")  # 所属任务ID，任务删除时保留结果
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="项目ID")  # 所属项目ID，级联删除
    case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, comment="用例ID")  # 所属用例ID，级联删除
    case_no = Column(String(50), nullable=False, comment="用例编号")                                   # 冗余存储用例编号，避免关联查询
    exec_status = Column(Integer, nullable=False, default=0, comment="执行状态：0未执行/1执行成功/2执行失败/3阻塞")  # 0=未执行，1=成功，2=失败，3=阻塞
    exec_time = Column(DateTime, nullable=False, default=utcnow, comment="执行时间")              # 用例执行时间
    exec_log = Column(Text, nullable=True, comment="单条用例执行日志")                                 # 执行过程的详细日志
    error_msg = Column(Text, nullable=True, comment="失败错误信息")                                    # 失败时的错误信息
    screenshot_url = Column(String(500), nullable=True, comment="失败截图存储路径")                     # 失败时的截图文件路径
    create_time = Column(DateTime, default=utcnow, comment="创建时间")                           # 记录创建时间
    update_time = Column(DateTime, default=utcnow, onupdate=utcnow, comment="更新时间")     # 记录更新时间

    # AI分析结果
    ai_analysis = Column(Text, nullable=True, comment="AI智能分析结果（失败原因、改进建议）")            # AI对失败用例的智能分析
    location_method = Column(String(50), nullable=True, comment="元素定位方式：css/xpath/ai/image")     # UI自动化使用的元素定位方式
    video_path = Column(String(500), nullable=True, comment="执行视频录制文件路径")                      # 执行过程的视频录制路径

    # 关系
    project = relationship("Project", backref="test_results")                                         # 所属项目
    test_case = relationship("TestCase", backref="test_results",
                             primaryjoin="and_(TestResult.case_id == TestCase.id, TestCase.is_deleted == False)")                                      # 所属用例，排除软删除
    test_task = relationship("TestTask", back_populates="test_results")                               # 所属任务
