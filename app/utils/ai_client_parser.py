"""
AI响应解析器模块

本模块负责将AI模型返回的原始文本解析为结构化数据，是AI客户端分层架构中的"解析层"。
核心解决的问题是：AI返回的JSON经常格式不规范（注释、尾逗号、单引号等），需要多层修复和兜底。

解析策略（按优先级从高到低）：
1. 直接JSON解析 — 最理想情况，AI返回了标准JSON
2. fix_common_json_issues — 修复注释和尾逗号等常见问题
3. clean_json_string — 逐步尝试7种正则修复策略（单引号→双引号、缺失逗号等）
4. extract_json_objects_fallback — 最终兜底，逐对象提取+逐行解析

核心函数：
    - fix_common_json_issues: 修复JSON注释和尾逗号
    - clean_json_string: 多策略JSON修复引擎
    - extract_json_objects_fallback: 兜底提取测试点对象
    - parse_test_point_object: 从文本中提取单个测试点
    - extract_value: 从JSON值文本中推断类型并提取
    - infer_test_category: 根据步骤关键词推断测试类型
    - infer_action_type: 根据操作描述推断action_type枚举值
    - extract_input_value_from_expected: 从预期结果中提取输入值

依赖：
    - loguru.logger: 日志记录
"""
import json
import re
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger


def fix_common_json_issues(json_str: str) -> Optional[str]:
    """修复JSON中的常见格式问题

    处理两类最常见的问题：
    1. JavaScript风格注释（// 和 /* */）— JSON标准不支持注释
    2. 尾逗号（]}前的多余逗号）— 严格JSON不允许尾逗号

    Args:
        json_str: 原始JSON字符串

    Returns:
        Optional[str]: 修复后可解析的JSON字符串，无法修复返回None
    """
    if not json_str:
        return None
    # 先尝试直接解析，如果本身合法则无需修复
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass
    # 移除单行注释 //...
    json_str = re.sub(r'//[^\n]*', '', json_str)
    # 移除多行注释 /*...*/
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    # 移除 } ] 前的尾逗号
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError as e:
        # 记录解析失败位置，便于调试
        error_pos = e.pos
        context = max(0, error_pos - 50)
        logger.debug(f"JSON解析失败位置 {error_pos}: ...{json_str[context:error_pos+50]}...")
        return None


def clean_json_string(json_str: str) -> Optional[str]:
    """多策略JSON修复引擎

    依次尝试7种正则修复策略，每种策略修复后立即验证是否可解析。
    一旦某种策略成功即返回，避免过度修复引入新问题。

    修复策略（按尝试顺序）：
    1. 移除控制字符（0x00-0x1F中非空白字符）
    2. 单引号 → 双引号
    3. 冒号后缺少空格/引号
    4. 相邻字符串间缺少逗号
    5. 相邻对象间缺少逗号（}{ → },{）
    6. 未加引号的字符串值
    7. 键名缺少引号

    Args:
        json_str: 待修复的JSON字符串

    Returns:
        Optional[str]: 修复后可解析的JSON字符串，所有策略均失败返回None
    """
    if not json_str:
        return None
    # 策略1：移除控制字符（保留\n\r\t等空白字符）
    json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_str)
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass
    # 策略2：单引号替换为双引号
    fixed = re.sub(r"'([^']*)'", r'"\1"', json_str)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    # 策略3：冒号后缺少空格或引号
    fixed = re.sub(r':("?[^",\s][^}]*?)([,{])', r': \1\2', fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    # 策略4：相邻字符串值之间缺少逗号
    fixed = re.sub(r'(")\s+("\w+"\s*:)', r'\1,\2', fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    # 策略5：相邻对象之间缺少逗号
    fixed = re.sub(r'}(\s*{)', r'},\1', fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    # 策略6：未加引号的字符串值加引号
    fixed = re.sub(r'"(\w+)"\s*:\s*(?:"|)([^",}\]]+?)(\s*[},\]])', r'"\1": "\2"\3', fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    # 策略7：键名缺少引号
    fixed = re.sub(r'(\w+)":\s*', r'"\1": ', fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def extract_json_objects_fallback(content: str) -> List[Dict[str, Any]]:
    """兜底提取测试点对象

    当所有JSON修复策略均失败时，使用文本模式匹配逐个提取测试点。
    采用四级降级策略，确保即使AI返回严重格式错误的内容也能尽可能提取有效数据。

    提取策略（按优先级）：
    1. 整体数组清理：匹配最外层[...]，用clean_json_string修复后批量解析
    2. 逐个对象清理：在数组内逐个匹配{...}，单独清理并解析
    3. 关键字段定位：通过"point"字段定位，向前搜索对象起始，向后搜索结束
    4. 逐行解析：按行解析键值对，手动构建对象

    Args:
        content: AI返回的原始文本内容

    Returns:
        List[Dict[str, Any]]: 提取到的测试点列表，每个测试点至少包含point字段
    """
    # 防止超长内容导致正则回溯爆炸
    MAX_CONTENT_LENGTH = 50000
    if len(content) > MAX_CONTENT_LENGTH:
        logger.warning(f"JSON fallback内容过大({len(content)}字符)，截断至{MAX_CONTENT_LENGTH}字符")
        content = content[:MAX_CONTENT_LENGTH]
    test_points = []
    # ===== 策略1：整体数组匹配 =====
    array_match = re.search(r'\[[\s\S]*\]', content)
    if array_match:
        array_content = array_match.group(0)
        # 尝试整体清理后解析
        cleaned_array = clean_json_string(array_content)
        if cleaned_array:
            try:
                data = json.loads(cleaned_array)
                if isinstance(data, list):
                    for item in data:
                        # 只保留有效测试点：必须是字典且包含非空point字段
                        if isinstance(item, dict) and 'point' in item and item['point'].strip():
                            test_points.append(item)
                    if test_points:
                        logger.info(f"方法1(整体清理)成功提取 {len(test_points)} 个测试点")
                        return test_points
            except Exception:
                pass
        # 整体清理失败，尝试逐个对象清理
        object_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        objects = re.findall(object_pattern, array_content, re.DOTALL)
        for obj_str in objects:
            try:
                cleaned = clean_json_string(obj_str)
                if cleaned:
                    obj = json.loads(cleaned)
                    if isinstance(obj, dict) and 'point' in obj and obj['point'].strip():
                        test_points.append(obj)
            except json.JSONDecodeError:
                continue
        if test_points:
            logger.info(f"方法1(逐个清理)成功提取 {len(test_points)} 个测试点")
            return test_points
    # ===== 策略2：通过"point"关键字定位 =====
    point_pattern = r'"point"\s*:\s*"([^"]*(?:[^"]|"{2}){0,5}?)"'
    matches = re.findall(point_pattern, content, re.DOTALL)
    if matches:
        for point_text in matches:
            if point_text.strip() and len(point_text) > 5:
                # 从point文本位置向前搜索对象起始{
                context_start = content.find(point_text)
                if context_start > 0:
                    obj_start = content.rfind('{', max(0, context_start - 500))
                    obj_end = content.find('}', context_start + len(point_text))
                    if obj_start >= 0 and obj_end > obj_start:
                        obj_str = content[obj_start:obj_end + 1]
                        test_point = parse_test_point_object(obj_str)
                        if test_point:
                            test_points.append(test_point)
    # ===== 策略3：逐行键值对解析 =====
    # 检测内容中是否包含测试点相关字段
    object_pattern_loose = r'"(?:module|function|point|priority)"\s*:\s*'
    if re.search(object_pattern_loose, content):
        lines = content.split('\n')
        current_obj = {}
        in_object = False
        buffer = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 遇到{开始一个新对象
            if line.startswith('{'):
                in_object = True
                current_obj = {}
                buffer = ""
                continue
            # 遇到}结束当前对象
            if line.startswith('}') and in_object:
                if current_obj.get('point') and current_obj['point'].strip():
                    test_points.append(current_obj.copy())
                in_object = False
                current_obj = {}
                buffer = ""
                continue
            # 在对象内部，解析键值对
            if in_object:
                key_match = re.match(r'^\s*"(\w+)"\s*:\s*(.+)$', line)
                if key_match:
                    key = key_match.group(1).strip()
                    value_part = key_match.group(2).strip()
                    value = extract_value(value_part)
                    if key and value is not None:
                        current_obj[key] = value
                        buffer = ""
                    elif key:
                        # 值可能跨行，暂存到buffer
                        buffer = value_part
                elif buffer and line.startswith('"'):
                    # 续行：将当前行拼接到buffer后重新尝试提取
                    buffer += " " + line.strip()
                    value = extract_value(buffer)
                    if value is not None:
                        last_key = list(current_obj.keys())[-1] if current_obj else None
                        if last_key:
                            current_obj[last_key] = value
                            buffer = ""
    if test_points:
        logger.info(f"Fallback方法共提取 {len(test_points)} 个测试点")
        return test_points
    return []


def parse_test_point_object(text: str) -> Optional[Dict]:
    """从文本片段中提取单个测试点对象

    使用正则匹配提取module、function、point、priority四个字段。
    仅当point字段非空时才返回有效结果。

    Args:
        text: 包含测试点字段的文本片段

    Returns:
        Optional[Dict]: 提取到的测试点字典，point为空时返回None
    """
    result = {}
    module_match = re.search(r'"module"\s*:\s*"([^"]*)"', text)
    if module_match:
        result['module'] = module_match.group(1)
    func_match = re.search(r'"function"\s*:\s*"([^"]*)"', text)
    if func_match:
        result['function'] = func_match.group(1)
    # point字段可能包含转义字符，使用更宽松的匹配
    point_match = re.search(r'"point"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if point_match:
        result['point'] = point_match.group(1)
    priority_match = re.search(r'"priority"\s*:\s*(\d+)', text)
    if priority_match:
        result['priority'] = int(priority_match.group(1))
    # point是必填字段，为空则整个对象无效
    if result.get('point') and result['point'].strip():
        return result
    return None


def extract_value(value_part: str) -> Optional[Any]:
    """从JSON值文本中推断类型并提取值

    支持的类型推断：
    - 双引号字符串 → str
    - 整数 → int
    - 浮点数 → float
    - true/false → bool
    - 其他 → 原样返回字符串

    Args:
        value_part: JSON值部分的文本（如 '"hello"'、'42'、'true'）

    Returns:
        Optional[Any]: 提取并类型转换后的值，空值返回None
    """
    if not value_part or value_part == ',':
        return None
    value_part = value_part.rstrip(',')
    # 字符串值：提取双引号之间的内容
    if value_part.startswith('"'):
        end_quote = value_part.rfind('"')
        if end_quote > 0:
            return value_part[1:end_quote]
        return value_part[1:]
    # 整数值
    if re.match(r'^-?\d+$', value_part):
        return int(value_part)
    # 浮点数值
    if re.match(r'^-?\d+\.\d+$', value_part):
        return float(value_part)
    # 布尔值
    if value_part.lower() == 'true':
        return True
    if value_part.lower() == 'false':
        return False
    # 其他情况原样返回
    return value_part if value_part else None


# ==================== test_category 关键词映射常量 ====================
# 各测试类别的中英文+同义词关键词库，用于 infer_test_category 匹配

TEST_CATEGORY_API_KEYWORDS: Tuple[str, ...] = (
    '调用接口', 'API', '接口', 'HTTP', 'JSON', '请求', '响应', '状态码', '断言',
    'request', 'response', 'endpoint', 'rest', 'restful', 'status code',
)
"""api_automation类别关键词：API接口调用与验证"""

TEST_CATEGORY_MANUAL_KEYWORDS: Tuple[str, ...] = (
    '手工', '人工', '审核', '主观', '体验', '感受', '满意度', '美观',
    'manual', 'human', 'review', 'subjective',
)
"""manual类别关键词：人工判断与审核"""

TEST_CATEGORY_PERFORMANCE_KEYWORDS: Tuple[str, ...] = (
    '响应时间', '并发', '吞吐量', '性能', '负载', '压力', '延迟', 'QPS', 'TPS', '资源占用',
    'performance', 'throughput', 'latency', 'load', 'stress', 'concurrent',
)
"""performance类别关键词：性能与压力测试"""

TEST_CATEGORY_SECURITY_KEYWORDS: Tuple[str, ...] = (
    'XSS', 'SQL注入', 'CSRF', '权限绕过', '越权', '加密', '解密', '漏洞', '注入攻击', '安全', '认证绕过',
    'injection', 'vulnerability', 'exploit', 'security', 'authentication bypass',
)
"""security类别关键词：安全漏洞与渗透测试"""

TEST_CATEGORY_UI_KEYWORDS: Tuple[str, ...] = (
    '点击', '输入', '导航', '滚动', '悬停', '选择', '截图', '页面', '按钮', '输入框',
    'click', 'input', 'navigate', 'scroll', 'hover', 'select', 'screenshot', 'page', 'button',
)
"""ui_automation类别关键词：UI交互操作"""

TEST_CATEGORY_CHECK_KEYWORDS: Tuple[str, ...] = (
    '查看', '检查', '确认', '验证',
    'check', 'inspect', 'examine',
)
"""检查类关键词：用于区分手工测试与UI自动化"""


def infer_test_category(steps: List[Dict]) -> Tuple[str, str]:
    """根据测试步骤关键词推断测试类型

    通过分析步骤中的action、action_type和expected_result字段，
    匹配预定义的中英文+同义词关键词库来推断最合适的测试类别。

    推断优先级（安全 > 性能 > API > 手工 > UI自动化）：
    - security: 包含XSS、SQL注入、CSRF等安全关键词
    - performance: 包含并发、吞吐量、QPS等性能关键词
    - api_automation: 包含接口、HTTP、JSON等API关键词
    - manual: 包含手工、审核等人工关键词，或仅有检查操作无UI操作
    - ui_automation: 默认类别，包含点击、输入等UI操作关键词

    Args:
        steps: 测试步骤列表，每个步骤包含action、action_type、expected_result等字段

    Returns:
        Tuple[str, str]: (test_category, case_type) 测试类别和用例类型
    """
    has_api = has_manual = has_performance = has_security = has_ui = has_check = False
    # 遍历所有步骤，合并action和expected_result进行关键词匹配
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
        # UI判断：action中包含UI关键词，或action_type属于UI操作枚举
        if any(kw in action for kw in TEST_CATEGORY_UI_KEYWORDS) or action_type in [
            'click', 'input', 'navigate', 'scroll', 'hover', 'select',
            'captcha', 'refresh', 'keypress',
        ]:
            has_ui = True
        if any(kw in action for kw in TEST_CATEGORY_CHECK_KEYWORDS):
            has_check = True
    # 按优先级返回测试类别
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


# ==================== action_type 关键词映射常量 ====================
# 每个操作类型对应一组中英文+同义词关键词，用于 infer_action_type 匹配
# 命名规则: ACTION_TYPE_KEYWORDS_{枚举值大写}

ACTION_TYPE_KEYWORDS_INPUT: Tuple[str, ...] = (
    '输入', '填写', '录入', '键入', 'input', 'type', 'enter', 'fill', 'write', 'set',
)
"""input操作关键词：向输入框填入文本内容"""

ACTION_TYPE_KEYWORDS_CLICK: Tuple[str, ...] = (
    '点击', '按下', '单击', 'click', 'press', 'tap',
)
"""click操作关键词：单击页面元素"""

ACTION_TYPE_KEYWORDS_NAVIGATE: Tuple[str, ...] = (
    '导航', '访问', '打开', '跳转', 'navigate', 'open', 'goto', 'go to', 'visit',
)
"""navigate操作关键词：跳转到指定URL"""

ACTION_TYPE_KEYWORDS_VERIFY: Tuple[str, ...] = (
    '验证', '检查', '确认', 'verify', 'check', 'assert', 'validate', 'confirm',
)
"""verify操作关键词：断言页面元素状态或文本内容"""

ACTION_TYPE_KEYWORDS_WAIT: Tuple[str, ...] = (
    '等待', 'wait', 'sleep', 'pause',
)
"""wait操作关键词：等待元素出现或消失"""

ACTION_TYPE_KEYWORDS_SCROLL: Tuple[str, ...] = (
    '滚动', 'scroll', 'swipe',
)
"""scroll操作关键词：滚动页面到指定位置"""

ACTION_TYPE_KEYWORDS_HOVER: Tuple[str, ...] = (
    '悬停', 'hover', 'mouseover',
)
"""hover操作关键词：鼠标悬停在元素上"""

ACTION_TYPE_KEYWORDS_SELECT: Tuple[str, ...] = (
    '选择', 'select', 'choose', 'pick',
)
"""select操作关键词：从下拉列表中选择选项"""

ACTION_TYPE_KEYWORDS_REFRESH: Tuple[str, ...] = (
    '刷新', 'refresh', 'reload',
)
"""refresh操作关键词：刷新当前页面"""

ACTION_TYPE_KEYWORDS_KEYPRESS: Tuple[str, ...] = (
    '按键', 'keypress', 'keydown', 'press key',
)
"""keypress操作关键词：模拟键盘按键"""

ACTION_TYPE_KEYWORDS_CAPTCHA: Tuple[str, ...] = (
    '验证码', 'captcha', '滑块',
)
"""captcha操作关键词：处理图形验证码或滑块验证"""


def infer_action_type(action: str) -> str:
    """根据操作描述推断action_type枚举值

    通过中英文+同义词关键词匹配，将自然语言的操作描述映射为标准化的action_type。
    未匹配到任何关键词时默认返回'click'。

    Args:
        action: 操作描述文本（如"输入用户名"、"click submit button"、"打开页面"）

    Returns:
        str: 标准化的action_type枚举值（input/click/navigate/verify/wait/scroll/hover/select/refresh/keypress/captcha）
    """
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
    # 默认为点击操作
    return 'click'


def extract_input_value_from_expected(expected: str) -> tuple:
    """从预期结果中提取输入值

    当预期结果格式为"标签：值"或"标签为：值"时，识别为输入操作，
    提取值部分作为input_value，并将预期结果改写为"标签显示对应值"。
    仅当标签包含输入相关关键词时才进行提取。

    Args:
        expected: 预期结果文本（如"用户名：admin"、"密码为：123456"）

    Returns:
        tuple: (input_value, modified_expected)
            - input_value: 提取到的输入值，无匹配时为空字符串
            - modified_expected: 修改后的预期结果，无匹配时原样返回
    """
    # 支持两种格式：冒号分隔和"为"字分隔
    patterns = [
        r'^(.{1,20})[：:]\s*(.+)$',       # 格式：标签：值
        r'^(.{1,20})为[：:]\s*(.+)$',      # 格式：标签为：值
    ]
    for pat in patterns:
        m = re.match(pat, expected.strip())
        if m:
            label = m.group(1).strip()
            value = m.group(2).strip()
            # 仅当标签包含输入相关关键词时才提取
            if any(kw in label for kw in ('用户名', '密码', '邮箱', '手机', '账号', '输入', '填写', '文本', '内容', '地址', '名称', '编号', '验证码')):
                return value, f'{label}显示对应值'
    return '', expected
