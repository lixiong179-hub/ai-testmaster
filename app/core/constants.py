"""
项目常量和枚举定义模块

本模块统一管理AI测试平台中的所有枚举类型、状态码和默认值常量，
消除代码中的魔法数字和魔法字符串，提高可读性与可维护性。

核心枚举概览：
    - TestCasePriority: 测试用例优先级（高/中/低），用于用例排序与资源分配
    - TestCaseType: 测试用例类型（UI自动化/手工/API自动化/性能/安全），决定执行策略
    - TestCaseGenerateStatus: AI用例生成状态（生成中/成功/失败），追踪异步生成流程
    - TestCaseReviewStatus: 用例审核状态（待审核/已通过/已拒绝/需优化），人工审核流程
    - TestCaseCorrectionStatus: 用例纠正状态（纠正失败/纠正中/验证中/已验证），AI纠正流程
    - TestCategory: 测试分类（已废弃，统一使用TestCaseType）
    - ActionType: 测试步骤操作类型（点击/输入/导航等），定义可执行的操作集合
    - LocatorStatus: 元素定位状态（待定位/已录制/定位失败），UI元素追踪
    - ExecutionStatus: 测试执行状态（待执行/执行中/通过/失败/跳过），执行结果追踪
    - ResponseCode: API响应状态码，统一前后端错误码约定
    - Environment: 环境类型（dev/test/prod），与config模块配合使用

配置常量类概览：
    - TimeoutConfig: 各场景超时时间配置（API/AI/上传/导出）
    - PaginationConfig: 分页参数配置（默认/最大/最小页大小）
    - SecurityConfig: 安全策略配置（JWT过期/密码长度/登录锁定）
    - FileExtension: 允许上传的文件扩展名枚举（动态生成自file_utils）

依赖关系：
    - app.utils.file_utils.SUPPORTED_FILE_TYPES: 文件类型白名单，用于动态生成FileExtension枚举

枚举设计原则：
    - 状态类枚举使用str, Enum基类，值可直接序列化为JSON字符串
    - 数值类枚举使用IntEnum基类，值可用于数据库存储和比较运算
    - 每个枚举值都有明确的业务语义，禁止使用无意义数字
"""
from enum import Enum, IntEnum
from typing import List


# ==================== 测试用例相关枚举 ====================

class TestCasePriority(IntEnum):
    """测试用例优先级枚举。

    用于标识测试用例的重要程度，影响执行顺序和资源分配策略。
    数值越小优先级越高，在批量执行时高优先级用例优先运行。

    使用场景：
        - 用例创建时指定优先级（默认MEDIUM）
        - 执行计划中按优先级排序用例
        - 统计报表中按优先级分组展示

    关联关系：
        - DEFAULT_PRIORITY常量引用MEDIUM作为默认值
        - 数据库test_case表的priority字段存储此枚举的整数值
    """
    HIGH = 1      # 高优先级：核心业务流程、P0级功能，必须通过
    MEDIUM = 2    # 中优先级：常规功能验证，默认优先级
    LOW = 3       # 低优先级：边界场景、非核心功能，可延后执行


class TestCaseType(str, Enum):
    """测试用例类型枚举。

    定义测试用例的执行方式和技术类型，不同类型对应不同的执行引擎和策略。
    继承str和Enum，枚举值可直接作为字符串使用，便于JSON序列化和数据库存储。

    使用场景：
        - 用例创建时选择类型（默认UI_AUTOMATION）
        - 根据类型路由到不同的执行引擎（Playwright/HTTP客户端等）
        - 按类型统计用例分布

    关联关系：
        - DEFAULT_CASE_TYPE常量引用UI_AUTOMATION作为默认值
        - 数据库test_case表的case_type字段存储此枚举的字符串值
        - TestCategory（已废弃）的值与本枚举完全相同，迁移时直接替换即可
    """
    UI_AUTOMATION = "ui_automation"    # UI自动化测试：通过Playwright驱动浏览器执行
    MANUAL = "manual"                  # 手工测试：人工执行，系统仅记录结果
    API_AUTOMATION = "api_automation"  # API自动化测试：通过HTTP客户端调用接口验证
    PERFORMANCE = "performance"        # 性能测试：压力测试、负载测试、基准测试
    SECURITY = "security"              # 安全测试：漏洞扫描、渗透测试、合规检查

    @classmethod
    def get_label(cls, value: str) -> str:
        """获取用例类型的中文显示标签。

        用于前端界面展示，将枚举值映射为用户友好的中文名称。

        Args:
            value: 枚举值字符串，如 "ui_automation"。

        Returns:
            str: 对应的中文标签，如 "UI自动化"。
                 若枚举值不存在则原样返回value本身。

        Examples:
            >>> TestCaseType.get_label("ui_automation")
            'UI自动化'
            >>> TestCaseType.get_label("unknown_type")
            'unknown_type'
        """
        labels = {
            cls.UI_AUTOMATION.value: "UI自动化",
            cls.MANUAL.value: "手工测试",
            cls.API_AUTOMATION.value: "API自动化",
            cls.PERFORMANCE.value: "性能测试",
            cls.SECURITY.value: "安全测试",
        }
        return labels.get(value, value)

    @classmethod
    def from_legacy(cls, value: str) -> "TestCaseType":
        """从旧版用例类型值转换为新版枚举。

        兼容历史数据中的旧类型标识，将其映射到当前枚举值。
        主要用于数据迁移和外部系统对接场景。

        Args:
            value: 旧版类型标识字符串，支持以下格式：
                - 旧版中文标识：如 "UI"、"API"、"接口"、"功能"、"功能测试"
                - 旧版英文标识：如 "functional"、"api_auto"、"compatibility"
                - 当前枚举值：如 "ui_automation"、"manual"（直接映射）

        Returns:
            TestCaseType: 对应的新版枚举成员，无法识别时默认返回MANUAL。

        Examples:
            >>> TestCaseType.from_legacy("UI")
            <TestCaseType.UI_AUTOMATION: 'ui_automation'>
            >>> TestCaseType.from_legacy("接口")
            <TestCaseType.API_AUTOMATION: 'api_automation'>
            >>> TestCaseType.from_legacy("compatibility")
            <TestCaseType.MANUAL: 'manual'>
        """
        legacy_map = {
            # 旧版缩写映射
            "UI": cls.UI_AUTOMATION,
            "API": cls.API_AUTOMATION,
            # 旧版中文标识映射
            "接口": cls.API_AUTOMATION,
            "功能": cls.MANUAL,
            "功能测试": cls.MANUAL,
            # 旧版英文标识映射
            "functional": cls.MANUAL,
            "ui_automation": cls.UI_AUTOMATION,
            "manual": cls.MANUAL,
            "api_automation": cls.API_AUTOMATION,
            "api_auto": cls.API_AUTOMATION,  # 旧版缩写
            "performance": cls.PERFORMANCE,
            "security": cls.SECURITY,
            "compatibility": cls.MANUAL,  # 兼容性测试归入手工测试
        }
        return legacy_map.get(value, cls.MANUAL)


class TestCaseGenerateStatus(IntEnum):
    """测试用例AI生成状态枚举。

    追踪AI异步生成测试用例的生命周期状态。
    数值类型便于数据库存储和状态比较（如 status > 0 表示终态）。

    使用场景：
        - AI用例生成任务的状态追踪
        - 前端轮询生成进度时判断是否完成
        - 生成失败时触发重试或告警

    关联关系：
        - DEFAULT_GENERATE_STATUS常量引用GENERATING作为初始状态
        - 与Celery异步任务状态对应：PENDING->GENERATING, SUCCESS->SUCCESS, FAILURE->FAILED
        - 数据库test_case表的generate_status字段存储此枚举的整数值

    状态流转：
        GENERATING(0) -> SUCCESS(1)  生成成功
        GENERATING(0) -> FAILED(2)   生成失败
    """
    GENERATING = 0  # 生成中：AI正在分析需求并生成用例（初始状态）
    SUCCESS = 1     # 生成成功：用例已成功生成并入库
    FAILED = 2      # 生成失败：AI生成过程出错，需排查或重试


class TestCaseReviewStatus(str, Enum):
    """测试用例人工审核状态枚举。

    定义AI生成用例的人工审核流程状态，确保用例质量符合要求后才可执行。
    继承str和Enum，值可直接序列化为JSON字符串。

    使用场景：
        - AI生成用例后的审核流程管理
        - 前端审核看板的状态筛选
        - 审核通过后用例才可纳入执行计划

    关联关系：
        - DEFAULT_REVIEW_STATUS常量引用PENDING作为初始状态
        - 数据库test_case表的review_status字段存储此枚举的字符串值

    状态流转：
        PENDING -> APPROVED           审核通过，用例可执行
        PENDING -> REJECTED           审核拒绝，需重新生成
        PENDING -> NEEDS_OPTIMIZATION 需优化，AI自动纠正后重新审核
        NEEDS_OPTIMIZATION -> PENDING 优化完成后回到待审核
    """
    PENDING = "pending"              # 待审核：AI生成后等待人工审核（初始状态）
    APPROVED = "approved"            # 已通过：审核通过，用例可纳入执行计划
    REJECTED = "rejected"            # 已拒绝：审核不通过，需重新生成或大幅修改
    NEEDS_OPTIMIZATION = "needs_optimization"  # 需优化：小问题需AI自动纠正，纠正后重新审核


class TestCaseCorrectionStatus(str, Enum):
    """测试用例AI纠正状态枚举。

    追踪AI自动纠正用例问题的生命周期，当审核状态为NEEDS_OPTIMIZATION时触发。
    纠正流程：AI根据审核意见修改用例 -> 自动验证修改结果 -> 人工确认。

    使用场景：
        - 审核反馈"需优化"后的自动纠正流程
        - 前端展示纠正进度
        - 纠正验证通过后自动将审核状态重置为PENDING

    关联关系：
        - 与TestCaseReviewStatus.NEEDS_OPTIMIZATION联动触发
        - 数据库test_case表的correction_status字段存储此枚举的字符串值

    状态流转：
        CORRECTING -> VERIFYING -> VERIFIED           纠正成功，验证通过
        CORRECTING -> VERIFYING -> FAILED_CORRECTION  纠正后验证失败
        FAILED_CORRECTION -> CORRECTING               重试纠正
    """
    FAILED_CORRECTION = "failed_correction"  # 纠正失败：AI纠正后验证未通过或纠正过程出错
    CORRECTING = "correcting"                # 纠正中：AI正在根据审核意见修改用例
    VERIFYING = "verifying"                  # 验证中：纠正完成，正在自动验证修改结果
    VERIFIED = "verified"                    # 已验证：纠正结果验证通过，等待人工确认


class TestCategory(str, Enum):
    """测试用例分类枚举（已废弃）。

    本枚举已被TestCaseType替代，保留仅为兼容历史数据和旧版API。
    枚举值与TestCaseType完全相同，迁移时直接替换类名即可。

    废弃原因：
        - "分类"(Category)与"类型"(Type)语义重叠，统一使用TestCaseType更清晰
        - TestCaseType额外提供了get_label()和from_legacy()方法

    迁移说明：
        - 代码中所有TestCategory引用替换为TestCaseType
        - 数据库中category字段已迁移至case_type字段
        - API接口中category参数已废弃，使用case_type替代
        - 枚举值无需转换，两者值完全一致

    注意：本枚举将在下个大版本中移除，请尽快完成迁移。
    """
    UI_AUTOMATION = "ui_automation"
    MANUAL = "manual"
    API_AUTOMATION = "api_automation"
    PERFORMANCE = "performance"
    SECURITY = "security"


# ==================== 测试步骤相关枚举 ====================

class ActionType(str, Enum):
    """测试步骤操作类型枚举。

    定义UI自动化测试中可执行的操作集合，每个操作类型对应Playwright的一个或一组API调用。
    继承str和Enum，值可直接序列化为JSON，存储在测试步骤的action_type字段中。

    使用场景：
        - 测试步骤定义时选择操作类型
        - 执行引擎根据操作类型路由到对应的Playwright方法
        - AI生成用例时输出标准化的操作类型
        - MCP直执配置中限定允许自动执行的操作类型白名单

    关联关系：
        - 数据库test_step表的action_type字段存储此枚举的字符串值
        - MCP_EXECUTION_OPERATION_TYPES配置项引用其中的click/type/hover/select
        - 每种操作类型对应不同的参数结构（如INPUT需要text参数，CLICK无需额外参数）
    """
    CLICK = "click"        # 点击操作：单击页面元素（按钮、链接等）
    INPUT = "input"        # 输入操作：向输入框填入文本内容
    NAVIGATE = "navigate"  # 导航操作：跳转到指定URL
    VERIFY = "verify"      # 验证操作：断言页面元素状态或文本内容
    WAIT = "wait"          # 等待操作：等待元素出现、消失或达到指定时间
    SCROLL = "scroll"      # 滚动操作：滚动页面到指定位置或元素
    HOVER = "hover"        # 悬停操作：鼠标悬停在元素上触发下拉菜单等
    SELECT = "select"      # 选择操作：从下拉列表中选择指定选项
    CAPTCHA = "captcha"    # 验证码操作：处理图形验证码或滑块验证
    REFRESH = "refresh"    # 刷新操作：刷新当前页面
    KEYPRESS = "keypress"  # 按键操作：模拟键盘按键（Enter、Tab、Escape等）


class LocatorStatus(str, Enum):
    """元素定位状态枚举。

    追踪UI元素定位器（CSS选择器/XPath等）的录制和验证状态。
    定位器是UI自动化测试的核心，其可靠性直接影响测试稳定性。

    使用场景：
        - 录制测试步骤时标记定位器状态
        - 执行前校验定位器是否可用
        - AI自愈功能根据定位状态决定是否需要修复

    关联关系：
        - 数据库test_step表的locator_status字段存储此枚举的字符串值
        - 与LocatorStatusFlag配合使用：LocatorStatusFlag.YES/NO用于布尔判断

    状态流转：
        PENDING -> RECORDED  录制成功，定位器已确认
        PENDING -> FAILED    录制失败，需人工修复或AI自愈
    """
    PENDING = "pending"    # 待定位：尚未录制或验证定位器（初始状态）
    RECORDED = "recorded"  # 已录制：定位器已通过录制或验证确认可用
    FAILED = "failed"      # 定位失败：定位器无法找到对应元素


class ViewVisibility(IntEnum):
    """视图可见性枚举。

    标识UI元素在页面上的可见状态，用于判断元素是否可交互。
    隐藏元素无法被点击或输入，执行引擎需根据可见性决定操作策略。

    使用场景：
        - 执行前检查元素是否可见，不可见时等待或跳过
        - 验证操作中判断元素显示/隐藏状态
        - UI原型解析时标记元素的可见性

    关联关系：
        - 数据库中相关表的visibility字段存储此枚举的整数值
    """
    HIDDEN = 0   # 隐藏：元素不可见（display:none、visibility:hidden等）
    VISIBLE = 1  # 可见：元素在页面上可见且可交互


class LocatorStatusFlag(IntEnum):
    """元素定位状态标志枚举。

    提供布尔级别的定位状态标识，用于快速判断定位器是否已确认。
    与LocatorStatus互补：LocatorStatus提供详细状态，LocatorStatusFlag提供简单的是/否判断。

    使用场景：
        - 数据库查询中快速筛选已定位/未定位的步骤
        - 统计报表中计算定位完成率
        - 前端列表展示中的状态标记

    关联关系：
        - LocatorStatus.RECORDED 对应 LocatorStatusFlag.YES
        - LocatorStatus.PENDING/FAILED 对应 LocatorStatusFlag.NO
    """
    NO = 0   # 未定位：定位器尚未确认或定位失败
    YES = 1  # 已定位：定位器已确认可用


# ==================== 测试执行相关枚举 ====================

class ExecutionStatus(str, Enum):
    """测试执行状态枚举。

    追踪测试用例或测试步骤的执行生命周期，从创建到完成的全过程。
    继承str和Enum，值可直接序列化为JSON字符串。

    使用场景：
        - 测试执行记录的状态追踪
        - 前端执行看板的状态展示和筛选
        - 执行完成后生成测试报告

    关联关系：
        - DEFAULT_EXECUTION_STATUS常量引用PENDING作为初始状态
        - 数据库execution_record表的status字段存储此枚举的字符串值
        - 测试用例和测试步骤共享此状态枚举

    状态流转：
        PENDING -> RUNNING -> PASSED   执行通过
        PENDING -> RUNNING -> FAILED   执行失败
        PENDING -> SKIPPED             跳过执行（前置条件不满足等）
    """
    PENDING = "pending"    # 待执行：用例已加入执行队列，等待调度（初始状态）
    RUNNING = "running"    # 执行中：用例正在被测试引擎执行
    PASSED = "passed"      # 已通过：所有步骤执行成功，断言全部通过
    FAILED = "failed"      # 已失败：存在步骤执行失败或断言不通过
    SKIPPED = "skipped"    # 已跳过：因前置条件不满足等原因跳过执行


# ==================== 通用常量 ====================

class ResponseCode(IntEnum):
    """API响应状态码枚举。

    统一定义前后端交互的HTTP状态码和业务错误码，确保错误处理的一致性。
    使用IntEnum便于与HTTP标准状态码对齐，同时支持自定义业务码。

    使用场景：
        - 后端API返回统一格式的响应体 { code: ResponseCode.SUCCESS, ... }
        - 前端根据状态码展示不同的提示信息和处理逻辑
        - 全局异常处理器将异常映射为对应的ResponseCode

    注意：
        - 部分业务错误码复用HTTP状态码（如VALIDATION_ERROR=400）
        - 同一HTTP状态码可能有多个业务含义（如400同时表示参数错误和校验错误）
        - 前端应优先根据业务错误码（如code字段）而非HTTP状态码判断结果
    """
    SUCCESS = 200              # 请求成功
    VALIDATION_ERROR = 400     # 数据校验失败（请求体不符合模型约束）
    PARAMETER_ERROR = 400      # 参数错误（缺少必填参数、参数格式错误）
    NOT_FOUND = 404            # 资源不存在（请求的URL或ID对应的记录不存在）
    PERMISSION_DENIED = 403    # 权限不足（无权访问该资源或执行该操作）
    UNAUTHORIZED = 401         # 未认证（未登录或Token无效）
    TOKEN_EXPIRED = 401        # Token已过期（需刷新Token或重新登录）
    FILE_ERROR = 400           # 文件操作错误（上传失败、格式不支持等）
    DUPLICATE_ERROR = 409      # 数据冲突（唯一约束违反，如重复创建）
    DATABASE_ERROR = 500       # 数据库错误（SQL执行失败、连接异常等）
    API_ERROR = 500            # 外部API调用错误（AI服务不可用等）
    SERVER_ERROR = 500         # 服务器内部错误（未预期的运行时异常）


# ==================== 常用默认值 ====================
# 以下常量为各枚举的默认值，用于创建新记录时设置初始状态
# 集中定义避免在业务代码中硬编码枚举值

DEFAULT_PRIORITY = TestCasePriority.MEDIUM          # 默认用例优先级：中
DEFAULT_CASE_TYPE = TestCaseType.UI_AUTOMATION      # 默认用例类型：UI自动化
DEFAULT_GENERATE_STATUS = TestCaseGenerateStatus.GENERATING  # 默认生成状态：生成中
DEFAULT_REVIEW_STATUS = TestCaseReviewStatus.PENDING         # 默认审核状态：待审核
DEFAULT_EXECUTION_STATUS = ExecutionStatus.PENDING           # 默认执行状态：待执行


# ==================== 文件相关常量 ====================

from app.utils.file_utils import SUPPORTED_FILE_TYPES


# 动态生成文件扩展名枚举，键名为大写扩展名，键值为小写扩展名
# 例如：SUPPORTED_FILE_TYPES = {"png": "image/png", ...} -> FileExtension.PNG = "png"
# 这样可以在代码中通过 FileExtension.PNG 引用，比硬编码字符串更安全
FileExtension = Enum(
    'FileExtension',
    {ext.upper(): ext for ext in SUPPORTED_FILE_TYPES},
    type=str
)

# 允许上传的文件扩展名列表，从file_utils动态获取
# 用于文件上传校验：上传文件的扩展名必须在此列表中
ALLOWED_EXTENSIONS: List[str] = list(SUPPORTED_FILE_TYPES.keys())


# ==================== 时间相关常量 ====================

class TimeoutConfig(IntEnum):
    """超时配置枚举（单位：秒）。

    集中管理各场景的HTTP请求和任务超时时间，避免在代码中硬编码魔法数字。
    超时值需根据实际网络环境和AI服务响应时间调整。

    使用场景：
        - HTTP请求的timeout参数
        - Celery任务的time_limit参数
        - AI服务调用的超时控制

    注意：
        - AI_API超时设为120秒，因为大模型推理可能较慢
        - 上传和导出超时设为60秒，考虑大文件传输耗时
    """
    DEFAULT_API = 30   # 默认API请求超时：30秒，适用于常规CRUD操作
    AI_API = 120       # AI服务请求超时：120秒，大模型推理需要较长等待时间
    UPLOAD = 60        # 文件上传超时：60秒，考虑大文件和网络波动
    EXPORT = 60        # 数据导出超时：60秒，批量数据生成可能耗时


# ==================== 分页相关常量 ====================

class PaginationConfig(IntEnum):
    """分页配置枚举。

    统一管理API分页查询的参数约束，确保分页行为一致且安全。
    防止客户端请求过大的页面导致数据库查询超时或内存溢出。

    使用场景：
        - API分页参数校验：page_size必须在MIN_PAGE_SIZE和MAX_PAGE_SIZE之间
        - 未指定page_size时使用DEFAULT_PAGE_SIZE
        - 前端分页组件的配置

    关联关系：
        - 各列表查询API的page_size参数校验引用MAX_PAGE_SIZE和MIN_PAGE_SIZE
    """
    DEFAULT_PAGE_SIZE = 20  # 默认每页条数：20条，平衡查询性能和数据展示量
    MAX_PAGE_SIZE = 100     # 最大每页条数：100条，防止一次查询过多数据
    MIN_PAGE_SIZE = 1       # 最小每页条数：1条，确保分页参数有效


# ==================== 安全相关常量 ====================

class SecurityConfig(IntEnum):
    """安全策略配置枚举。

    集中管理认证、授权和账户安全相关的参数阈值。
    这些值直接影响系统的安全等级，修改时需评估安全影响。

    使用场景：
        - JWT令牌过期时间设置（与config.py中的JWT配置对应）
        - 密码强度校验（最小长度）
        - 登录安全策略（最大尝试次数、锁定时间）

    关联关系：
        - JWT_ACCESS_TOKEN_EXPIRE_MINUTES 与 config.Settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES 对应
        - JWT_REFRESH_TOKEN_EXPIRE_DAYS 与 config.Settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS 对应
        - MAX_LOGIN_ATTEMPTS 和 ACCOUNT_LOCKOUT_MINUTES 用于登录失败锁定逻辑

    注意：
        - 修改JWT过期时间需同步更新config.py中的对应配置
        - ACCOUNT_LOCKOUT_MINUTES=30表示锁定30分钟，防止暴力破解
    """
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30   # 访问令牌有效期：30分钟
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7      # 刷新令牌有效期：7天
    MIN_PASSWORD_LENGTH = 6                # 密码最小长度：6字符
    MAX_LOGIN_ATTEMPTS = 5                 # 最大登录尝试次数：5次，超出后锁定账户
    ACCOUNT_LOCKOUT_MINUTES = 30           # 账户锁定时长：30分钟，防止暴力破解


# ==================== 环境相关常量 ====================

class Environment(str, Enum):
    """环境类型枚举。

    定义应用运行的环境类型，与config模块中的环境配置类对应。
    继承str和Enum，值可直接用于环境变量比较和日志标记。

    使用场景：
        - 环境判断逻辑：if env == Environment.PROD
        - 日志和监控中标记运行环境
        - 功能开关按环境差异化配置

    关联关系：
        - Environment.DEV 对应 config.DevSettings
        - Environment.TEST 对应 config.TestSettings
        - Environment.PROD 对应 config.ProdSettings
        - config.get_settings()根据ENVIRONMENT环境变量选择对应的配置类
    """
    DEV = "dev"    # 开发环境：本地开发调试，宽松安全策略
    TEST = "test"  # 测试环境：CI/CD和自动化测试，适度安全策略
    PROD = "prod"  # 生产环境：线上服务，严格安全策略
