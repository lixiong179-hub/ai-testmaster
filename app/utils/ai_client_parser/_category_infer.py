import re


TEST_CATEGORY_API_KEYWORDS: tuple[str, ...] = (
    "调用接口",
    "API",
    "接口",
    "HTTP",
    "JSON",
    "请求",
    "响应",
    "状态码",
    "断言",
    "request",
    "response",
    "endpoint",
    "rest",
    "restful",
    "status code",
)

TEST_CATEGORY_MANUAL_KEYWORDS: tuple[str, ...] = (
    "手工",
    "人工",
    "审核",
    "主观",
    "体验",
    "感受",
    "满意度",
    "美观",
    "manual",
    "human",
    "review",
    "subjective",
)

TEST_CATEGORY_PERFORMANCE_KEYWORDS: tuple[str, ...] = (
    "响应时间",
    "并发",
    "吞吐量",
    "性能",
    "负载",
    "压力",
    "延迟",
    "QPS",
    "TPS",
    "资源占用",
    "performance",
    "throughput",
    "latency",
    "load",
    "stress",
    "concurrent",
)

TEST_CATEGORY_SECURITY_KEYWORDS: tuple[str, ...] = (
    "XSS",
    "SQL注入",
    "CSRF",
    "权限绕过",
    "越权",
    "加密",
    "解密",
    "漏洞",
    "注入攻击",
    "安全",
    "认证绕过",
    "injection",
    "vulnerability",
    "exploit",
    "security",
    "authentication bypass",
)

TEST_CATEGORY_UI_KEYWORDS: tuple[str, ...] = (
    "点击",
    "输入",
    "导航",
    "滚动",
    "悬停",
    "选择",
    "截图",
    "页面",
    "按钮",
    "输入框",
    "click",
    "input",
    "navigate",
    "scroll",
    "hover",
    "select",
    "screenshot",
    "page",
    "button",
)

TEST_CATEGORY_CHECK_KEYWORDS: tuple[str, ...] = (
    "查看",
    "检查",
    "确认",
    "验证",
    "check",
    "inspect",
    "examine",
)


UI_ACTION_TYPES: tuple[str, ...] = (
    "click",
    "input",
    "navigate",
    "scroll",
    "hover",
    "select",
    "captcha",
    "refresh",
    "keypress",
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in text for kw in keywords)


def _step_flags(step: dict) -> dict[str, bool]:
    """单步骤的类别信号：动作/预期拼接后按关键词族判定，UI 另看 action_type。"""
    action = step.get("action", "")
    action_type = step.get("action_type", "")
    combined = f"{action} {step.get('expected_result', '')}"
    return {
        "api": _contains_any(combined, TEST_CATEGORY_API_KEYWORDS),
        "manual": _contains_any(combined, TEST_CATEGORY_MANUAL_KEYWORDS),
        "performance": _contains_any(combined, TEST_CATEGORY_PERFORMANCE_KEYWORDS),
        "security": _contains_any(combined, TEST_CATEGORY_SECURITY_KEYWORDS),
        "ui": _contains_any(action, TEST_CATEGORY_UI_KEYWORDS) or action_type in UI_ACTION_TYPES,
        "check": _contains_any(action, TEST_CATEGORY_CHECK_KEYWORDS),
    }


def _merge_flags(steps: list[dict]) -> dict[str, bool]:
    """多步骤信号取并集（空列表 → 全 False）。"""
    merged: dict[str, bool] = {
        "api": False,
        "manual": False,
        "performance": False,
        "security": False,
        "ui": False,
        "check": False,
    }
    for step in steps:
        for key, value in _step_flags(step).items():
            merged[key] = merged[key] or value
    return merged


def _resolve_category(flags: dict[str, bool]) -> str:
    """优先级：安全 > 性能 > 接口 > 手工（含「只检查不操作」）> UI。"""
    if flags["security"]:
        return "security"
    if flags["performance"]:
        return "performance"
    if flags["api"]:
        return "api_automation"
    if flags["manual"] or (flags["check"] and not flags["ui"]):
        return "manual"
    return "ui_automation"


def infer_test_category(steps: list[dict]) -> tuple[str, str]:
    category = _resolve_category(_merge_flags(steps))
    return category, category


ACTION_TYPE_KEYWORDS_INPUT: tuple[str, ...] = (
    "输入",
    "填写",
    "录入",
    "键入",
    "input",
    "type",
    "enter",
    "fill",
    "write",
    "set",
)

ACTION_TYPE_KEYWORDS_CLICK: tuple[str, ...] = (
    "点击",
    "按下",
    "单击",
    "click",
    "press",
    "tap",
)

ACTION_TYPE_KEYWORDS_NAVIGATE: tuple[str, ...] = (
    "导航",
    "访问",
    "打开",
    "跳转",
    "navigate",
    "open",
    "goto",
    "go to",
    "visit",
)

ACTION_TYPE_KEYWORDS_VERIFY: tuple[str, ...] = (
    "验证",
    "检查",
    "确认",
    "verify",
    "check",
    "assert",
    "validate",
    "confirm",
)

ACTION_TYPE_KEYWORDS_WAIT: tuple[str, ...] = (
    "等待",
    "wait",
    "sleep",
    "pause",
)

ACTION_TYPE_KEYWORDS_SCROLL: tuple[str, ...] = (
    "滚动",
    "scroll",
    "swipe",
)

ACTION_TYPE_KEYWORDS_HOVER: tuple[str, ...] = (
    "悬停",
    "hover",
    "mouseover",
)

ACTION_TYPE_KEYWORDS_SELECT: tuple[str, ...] = (
    "选择",
    "select",
    "choose",
    "pick",
)

ACTION_TYPE_KEYWORDS_REFRESH: tuple[str, ...] = (
    "刷新",
    "refresh",
    "reload",
)

ACTION_TYPE_KEYWORDS_KEYPRESS: tuple[str, ...] = (
    "按键",
    "keypress",
    "keydown",
    "press key",
)

ACTION_TYPE_KEYWORDS_CAPTCHA: tuple[str, ...] = (
    "验证码",
    "captcha",
    "滑块",
)


# 有序匹配表：先命中先用（顺序即优先级，勿按字母序重排）
ACTION_TYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("input", ACTION_TYPE_KEYWORDS_INPUT),
    ("click", ACTION_TYPE_KEYWORDS_CLICK),
    ("navigate", ACTION_TYPE_KEYWORDS_NAVIGATE),
    ("verify", ACTION_TYPE_KEYWORDS_VERIFY),
    ("wait", ACTION_TYPE_KEYWORDS_WAIT),
    ("scroll", ACTION_TYPE_KEYWORDS_SCROLL),
    ("hover", ACTION_TYPE_KEYWORDS_HOVER),
    ("select", ACTION_TYPE_KEYWORDS_SELECT),
    ("refresh", ACTION_TYPE_KEYWORDS_REFRESH),
    ("keypress", ACTION_TYPE_KEYWORDS_KEYPRESS),
    ("captcha", ACTION_TYPE_KEYWORDS_CAPTCHA),
)

DEFAULT_ACTION_TYPE = "click"


def infer_action_type(action: str) -> str:
    for action_type, keywords in ACTION_TYPE_RULES:
        if _contains_any(action, keywords):
            return action_type
    return DEFAULT_ACTION_TYPE


def extract_input_value_from_expected(expected: str) -> tuple:
    patterns = [
        r"^(.{1,20})[：:]\s*(.+)$",
        r"^(.{1,20})为[：:]\s*(.+)$",
    ]
    for pat in patterns:
        m = re.match(pat, expected.strip())
        if m:
            label = m.group(1).strip()
            value = m.group(2).strip()
            if any(
                kw in label
                for kw in (
                    "用户名",
                    "密码",
                    "邮箱",
                    "手机",
                    "账号",
                    "输入",
                    "填写",
                    "文本",
                    "内容",
                    "地址",
                    "名称",
                    "编号",
                    "验证码",
                )
            ):
                return value, f"{label}显示对应值"
    return "", expected
