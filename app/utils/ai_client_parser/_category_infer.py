import re
from typing import Dict, List, Tuple


TEST_CATEGORY_API_KEYWORDS: Tuple[str, ...] = (
    '调用接口', 'API', '接口', 'HTTP', 'JSON', '请求', '响应', '状态码', '断言',
    'request', 'response', 'endpoint', 'rest', 'restful', 'status code',
)

TEST_CATEGORY_MANUAL_KEYWORDS: Tuple[str, ...] = (
    '手工', '人工', '审核', '主观', '体验', '感受', '满意度', '美观',
    'manual', 'human', 'review', 'subjective',
)

TEST_CATEGORY_PERFORMANCE_KEYWORDS: Tuple[str, ...] = (
    '响应时间', '并发', '吞吐量', '性能', '负载', '压力', '延迟', 'QPS', 'TPS', '资源占用',
    'performance', 'throughput', 'latency', 'load', 'stress', 'concurrent',
)

TEST_CATEGORY_SECURITY_KEYWORDS: Tuple[str, ...] = (
    'XSS', 'SQL注入', 'CSRF', '权限绕过', '越权', '加密', '解密', '漏洞', '注入攻击', '安全', '认证绕过',
    'injection', 'vulnerability', 'exploit', 'security', 'authentication bypass',
)

TEST_CATEGORY_UI_KEYWORDS: Tuple[str, ...] = (
    '点击', '输入', '导航', '滚动', '悬停', '选择', '截图', '页面', '按钮', '输入框',
    'click', 'input', 'navigate', 'scroll', 'hover', 'select', 'screenshot', 'page', 'button',
)

TEST_CATEGORY_CHECK_KEYWORDS: Tuple[str, ...] = (
    '查看', '检查', '确认', '验证',
    'check', 'inspect', 'examine',
)


def infer_test_category(steps: List[Dict]) -> Tuple[str, str]:
    has_api = has_manual = has_performance = has_security = has_ui = has_check = False
    for step in steps:
        action = step.get('action', '')
        action_type = step.get('action_type', '')
        expected = step.get('expected_result', '')
        combined = f"{action} {expected}"
        if any(kw in combined for kw in TEST_CATEGORY_API_KEYWORDS):
            has_api = True
        if any(kw in combined for kw in TEST_CATEGORY_MANUAL_KEYWORDS):
            has_manual = True
        if any(kw in combined for kw in TEST_CATEGORY_PERFORMANCE_KEYWORDS):
            has_performance = True
        if any(kw in combined for kw in TEST_CATEGORY_SECURITY_KEYWORDS):
            has_security = True
        if any(kw in action for kw in TEST_CATEGORY_UI_KEYWORDS) or action_type in [
            'click', 'input', 'navigate', 'scroll', 'hover', 'select',
            'captcha', 'refresh', 'keypress',
        ]:
            has_ui = True
        if any(kw in action for kw in TEST_CATEGORY_CHECK_KEYWORDS):
            has_check = True
    if has_security:
        return ('security', 'security')
    elif has_performance:
        return ('performance', 'performance')
    elif has_api:
        return ('api_automation', 'api_automation')
    elif has_manual or (has_check and not has_ui):
        return ('manual', 'manual')
    else:
        return ('ui_automation', 'ui_automation')


ACTION_TYPE_KEYWORDS_INPUT: Tuple[str, ...] = (
    '输入', '填写', '录入', '键入', 'input', 'type', 'enter', 'fill', 'write', 'set',
)

ACTION_TYPE_KEYWORDS_CLICK: Tuple[str, ...] = (
    '点击', '按下', '单击', 'click', 'press', 'tap',
)

ACTION_TYPE_KEYWORDS_NAVIGATE: Tuple[str, ...] = (
    '导航', '访问', '打开', '跳转', 'navigate', 'open', 'goto', 'go to', 'visit',
)

ACTION_TYPE_KEYWORDS_VERIFY: Tuple[str, ...] = (
    '验证', '检查', '确认', 'verify', 'check', 'assert', 'validate', 'confirm',
)

ACTION_TYPE_KEYWORDS_WAIT: Tuple[str, ...] = (
    '等待', 'wait', 'sleep', 'pause',
)

ACTION_TYPE_KEYWORDS_SCROLL: Tuple[str, ...] = (
    '滚动', 'scroll', 'swipe',
)

ACTION_TYPE_KEYWORDS_HOVER: Tuple[str, ...] = (
    '悬停', 'hover', 'mouseover',
)

ACTION_TYPE_KEYWORDS_SELECT: Tuple[str, ...] = (
    '选择', 'select', 'choose', 'pick',
)

ACTION_TYPE_KEYWORDS_REFRESH: Tuple[str, ...] = (
    '刷新', 'refresh', 'reload',
)

ACTION_TYPE_KEYWORDS_KEYPRESS: Tuple[str, ...] = (
    '按键', 'keypress', 'keydown', 'press key',
)

ACTION_TYPE_KEYWORDS_CAPTCHA: Tuple[str, ...] = (
    '验证码', 'captcha', '滑块',
)


def infer_action_type(action: str) -> str:
    if any(kw in action for kw in ACTION_TYPE_KEYWORDS_INPUT):
        return 'input'
    if any(kw in action for kw in ACTION_TYPE_KEYWORDS_CLICK):
        return 'click'
    if any(kw in action for kw in ACTION_TYPE_KEYWORDS_NAVIGATE):
        return 'navigate'
    if any(kw in action for kw in ACTION_TYPE_KEYWORDS_VERIFY):
        return 'verify'
    if any(kw in action for kw in ACTION_TYPE_KEYWORDS_WAIT):
        return 'wait'
    if any(kw in action for kw in ACTION_TYPE_KEYWORDS_SCROLL):
        return 'scroll'
    if any(kw in action for kw in ACTION_TYPE_KEYWORDS_HOVER):
        return 'hover'
    if any(kw in action for kw in ACTION_TYPE_KEYWORDS_SELECT):
        return 'select'
    if any(kw in action for kw in ACTION_TYPE_KEYWORDS_REFRESH):
        return 'refresh'
    if any(kw in action for kw in ACTION_TYPE_KEYWORDS_KEYPRESS):
        return 'keypress'
    if any(kw in action for kw in ACTION_TYPE_KEYWORDS_CAPTCHA):
        return 'captcha'
    return 'click'


def extract_input_value_from_expected(expected: str) -> tuple:
    patterns = [
        r'^(.{1,20})[：:]\s*(.+)$',
        r'^(.{1,20})为[：:]\s*(.+)$',
    ]
    for pat in patterns:
        m = re.match(pat, expected.strip())
        if m:
            label = m.group(1).strip()
            value = m.group(2).strip()
            if any(kw in label for kw in ('用户名', '密码', '邮箱', '手机', '账号', '输入', '填写', '文本', '内容', '地址', '名称', '编号', '验证码')):
                return value, f'{label}显示对应值'
    return '', expected
