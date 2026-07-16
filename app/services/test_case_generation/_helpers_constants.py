"""test_case_generation 辅助常量。

分页与上下文预算、用例类型（执行方式）、需求/UI 元素关键词等模块级常量集中定义，
供 helpers 各拆分模块及 context_builder / mixin 复用。
"""
# ── 分页与上下文预算常量 ──
DEFAULT_CONTEXT_TOKEN_BUDGET = 5000
DEFAULT_TEST_POINT_PAGE_SIZE = 100
MAX_TEST_POINT_PAGE_SIZE = 500
DEFAULT_MATCHED_REQUIREMENT_LIMIT = 3
DEFAULT_MATCHED_UI_SCREEN_LIMIT = 3
DEFAULT_ADJACENT_UI_SCREEN_LIMIT = 2

# ── 用例类型常量（执行方式） ──
TEST_CATEGORY_UI_AUTO = "ui_automation"
TEST_CATEGORY_MANUAL = "manual"
TEST_CATEGORY_API_AUTO = "api_automation"

# UI 元素关键词提示：检测需求描述中提到的关键 UI 元素
REQUIRED_UI_ELEMENT_HINTS = (
    "忘记密码", "验证码", "提交", "下一步", "上一步", "登录", "注册",
    "搜索", "支付", "结算", "加入购物车", "保存", "取消", "确认",
)

# 需求文档操作动词集合，用于判定需求描述是否具备可执行的操作意图
REQUIREMENT_ACTION_VERBS = (
    "点击", "输入", "提交", "选择", "查看", "验证", "确认", "核对",
    "观察", "获取", "填写", "勾选", "切换", "按下", "长按", "等待",
    "打开", "进入", "返回",
)
REQUIREMENT_MIN_CHAR_COUNT = 50
