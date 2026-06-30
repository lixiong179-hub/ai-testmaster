"""质量评分统一常量与正则模式（Task 14 三合一）。

所有正则与规则常量仅在此模块定义，quality_scoring_service /
quality_validator / continuous_scorer / pipelines._scoring 共同导入复用，
消除同一字段在不同评分函数中给出冲突分数的问题
（spec Phase 2 Scenario: 同一用例三处评分一致）。
"""
import re
from typing import Literal

# ── 合法值集合 ──
VALID_CASE_CATEGORIES: frozenset[str] = frozenset(
    {"positive", "boundary", "exception", "inapplicable"}
)
VALID_ACTION_TYPES: frozenset[str] = frozenset(
    {"click", "input", "navigate", "scroll", "verify", "select"}
)
CLICK_ACTION_KEYWORDS: frozenset[str] = frozenset(
    {"点击", "选择", "勾选", "切换", "按下", "长按"}
)
INPUT_ACTION_KEYWORDS: frozenset[str] = frozenset(
    {"输入", "填写", "键入", "录入"}
)

# 登录状态标记：已登录 / 未登录两组，互斥校验。
# 同时命中两组说明前置条件语义矛盾（如"账号已登录状态为未登录"）。
LOGGED_IN_MARKERS: tuple[str, ...] = ("账号已登录", "已登录")
LOGGED_OUT_MARKERS: tuple[str, ...] = ("用户未登录", "未登录")

TITLE_VAGUE_WORDS: frozenset[str] = frozenset({
    "功能验证", "界面测试", "XX测试", "功能测试", "页面测试",
    "模块测试", "系统测试", "单元测试", "集成测试", "回归测试",
})

EXPECTED_VAGUE_WORDS: frozenset[str] = frozenset({
    "正常显示", "提交成功", "功能正常", "页面正常", "操作成功",
    "显示正常", "运行正常", "没问题", "交互跳转正确", "无崩溃白屏",
    "UI元素完整", "无崩溃", "无白屏", "流程正常",
})

# input/select 步骤禁止的占位符，需填写具体输入值
INPUT_VALUE_PLACEHOLDERS: frozenset[str] = frozenset({
    "待输入", "测试数据", "xxx", "XXX", "test", "Test",
    "示例", "占位", "placeholder",
    "任意值", "合理值", "合适的数据", "适当的数据", "随机值", "任意数据",
})

# UI 操作动作集合：不应出现在 api_automation 用例中
UI_ACTION_TYPES: frozenset[str] = frozenset({
    "click", "hover", "select", "double_click", "right_click",
    "drag_and_drop", "scroll", "upload", "switch_frame", "switch_window",
    "close_window", "refresh", "captcha", "verify_captcha",
})

# ── 步骤内容正则（grade_status / score_dimensions / prior 共用）──
STEP_UNCERTAINTY_PATTERN = re.compile(
    r'(或者|或点击|或选择|或输入|或按|或触发|或通过|或弹窗|或在|或长按|或滑动|或拖拽|'
    r'也可以|任选|二选一|任选其一)'
)
MANUAL_JUDGMENT_PATTERN = re.compile(
    r'(手动判断|人工确认|目测|肉眼|人工检查|手动检查|手动验证|人工判断|目视确认|手动标记|'
    r'主观判断|凭感觉|大致判断|自行判断)'
)
STEP_REFERENCE_PATTERN = re.compile(
    r'(参见|参考|同上|重复.*步骤|重复.*用例|如上|按照.*步骤)'
)
STEP_INFERENCE_ACTION_PATTERN = re.compile(
    r'(应该\w{0,4}|可能\w{0,4}|预计\w{0,4}|大概是|也许是|或许是|'
    r'根据常规|根据经验|通常应该|一般来说|按理说|'
    r'任意值|任意数据|合理值|合适的数据|适当的数据|随机值|'
    r'可能是.*按钮|可能是.*元素|大概是.*位置)'
)
STEP_INFERENCE_EXPECTED_PATTERN = re.compile(
    r'(大概是|也许是|或许是|'
    r'根据常规|根据经验|一般来说|按理说|'
    r'任意值|任意数据|合理值|合适的数据|适当的数据|随机值|'
    r'可能是.*按钮|可能是.*元素|大概是.*位置)'
)
TITLE_ATOMICITY_VIOLATION_PATTERN = re.compile(
    r'(触发.*旁路.*验证|'
    r'触发.*话术.*验证|'
    r'正确率100%.*错词|'
    r'全对.*错词学习|'
    r'旁路.*错词.*学习|'
    r'完成听写.*触发.*旁路|'
    r'主流程.*分支.*验证|'
    r'正向.*触发.*旁路.*验证)',
    re.IGNORECASE,
)

# ── prior 评分特有正则（原 _scoring.py 定义，统一迁移至此）──
# 标题模糊模式：补足 TITLE_VAGUE_WORDS 未覆盖的"接口测试""UI测试""X验证"等
TITLE_VAGUE_PATTERNS = re.compile(
    r'^(功能验证|界面测试|UI测试|接口测试|性能测试|安全测试|'
    r'异常测试|边界测试|兼容性测试|回归测试|'
    r'.{1,6}测试$|.{1,6}验证$|.{1,6}功能$)',
    re.IGNORECASE,
)
EXPECTED_VAGUE_PATTERNS = re.compile(
    r'(正常显示|提交成功|功能正常|页面正常|操作成功|'
    r'显示正常|运行正常|没问题|交互跳转正确|无崩溃白屏|'
    r'UI元素完整|无崩溃|无白屏|流程正常|'
    r'无异常|无报错|正常工作)',
    re.IGNORECASE,
)
QUANTIFIABLE_PATTERNS = re.compile(
    r'(为["\u201c]|等于|显示.*[：:]|文案.*[：:]|'
    r'不可|无法|禁止|锁定|超时|状态码|错误码|'
    r'\d+次|\d+秒|\d+条|\d+个|\d+%|'
    r'\d+页|\d+张|\d+行|\d+字段|\d+记录|'
    r'置灰|隐藏|消失|变红|变灰|高亮|'
    r'跳转|弹出|返回|关闭|刷新|重定向|'
    r'提示|弹窗|Toast|对话框|Snackbar|'
    r'\d+[~\-～至到]\d+|'
    r'(最多|不超过|不大于|上限为|≤|<=)\s*\d+\s*(个|条|次|秒|字|页|张|行|字段|记录|字符|位|MB|KB|GB|%)|'
    r'(最少|不少于|不小于|至少|下限为|≥|>=)\s*\d+\s*(个|条|次|秒|字|页|张|行|字段|记录|字符|位|MB|KB|GB|%))',
    re.IGNORECASE,
)
VERB_STACKING_PATTERN = re.compile(
    r'(点击|验证|检查|查看|测试|校验|弹出|关闭|跳转|返回)'
    r'.*?(点击|验证|检查|查看|测试|校验|弹出|关闭|跳转|返回)'
    r'.*?(点击|验证|检查|查看|测试|校验|弹出|关闭|跳转|返回)',
    re.IGNORECASE,
)

# ── 7 维度权重（原 continuous_scorer）──
WEIGHT_TITLE: float = 0.15
WEIGHT_PRECONDITION: float = 0.15
WEIGHT_STEPS: float = 0.20
WEIGHT_EXPECTED_RESULT: float = 0.15
WEIGHT_CASE_CATEGORY: float = 0.10
WEIGHT_ACTION_TYPE: float = 0.10
WEIGHT_ATOMICITY: float = 0.15

# ── 标题长度阈值（grade_status / score_dimensions 共用）──
TITLE_MIN_LENGTH: int = 8
TITLE_MAX_LENGTH: int = 50

# verdict 字面量
TitleVerdict = Literal["empty", "vague", "length", "ok"]
