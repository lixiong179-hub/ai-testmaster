"""测试用例质量校验器。

对 AI 生成的测试用例进行语义质量校验，确保入库前满足质量标准。
校验不通过时返回具体问题描述，供重试反馈使用。

校验维度:
    - 标题质量：禁止模糊词、长度限制
    - 前置条件完整性：须含登录状态和网络环境
    - 步骤完整性：非空、原子性、确定性、自动化可执行性
    - 预期结果质量：禁止模糊描述
    - case_category 合法性
    - 用例数量达标
    - 原子性：标题不应同时包含主流程+分支/旁路逻辑
"""
import re
from typing import List, Dict, Any, Tuple

VALID_CASE_CATEGORIES = frozenset({"positive", "boundary", "exception"})

TITLE_VAGUE_WORDS = frozenset({
    "功能验证", "界面测试", "XX测试", "功能测试", "页面测试",
    "模块测试", "系统测试", "单元测试", "集成测试", "回归测试",
})

EXPECTED_VAGUE_WORDS = frozenset({
    "正常显示", "提交成功", "功能正常", "页面正常", "操作成功",
    "显示正常", "运行正常", "没问题", "交互跳转正确", "无崩溃白屏",
    "UI元素完整", "无崩溃", "无白屏", "流程正常",
})

_STEP_UNCERTAINTY_PATTERN = re.compile(
    r'(或者|或点击|或选择|或输入|或按|或触发|或通过|或弹窗|或在|或长按|或滑动|或拖拽|'
    r'也可以|任选|二选一|任选其一)'
)

_MANUAL_JUDGMENT_PATTERN = re.compile(
    r'(手动判断|人工确认|目测|肉眼|人工检查|手动检查|手动验证|人工判断|目视确认|手动标记|'
    r'主观判断|凭感觉|大致判断|自行判断)'
)

_TITLE_ATOMICITY_VIOLATION = re.compile(
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


def validate_title(title: str) -> Tuple[bool, str]:
    """校验标题质量。

    Args:
        title: 用例标题

    Returns:
        (是否通过, 问题描述)
    """
    if not title or not title.strip():
        return False, "标题为空"
    title = title.strip()
    if len(title) < 8:
        return False, f"标题过短（{len(title)}字），需≥8字: {title}"
    if len(title) > 50:
        return False, f"标题过长（{len(title)}字），需≤50字: {title}"
    for word in TITLE_VAGUE_WORDS:
        if word in title:
            return False, f"标题包含模糊词「{word}」: {title}"
    if _TITLE_ATOMICITY_VIOLATION.search(title):
        return False, f"标题违反原子性原则（混合主流程与分支/旁路逻辑），应拆分为独立用例: {title}"
    return True, ""


def validate_precondition(precondition: str) -> Tuple[bool, str]:
    """校验前置条件完整性。

    Args:
        precondition: 前置条件文本

    Returns:
        (是否通过, 问题描述)
    """
    if not precondition or not precondition.strip():
        return False, "前置条件为空"
    precondition = precondition.strip()
    if "账号已登录" not in precondition and "已登录" not in precondition:
        return False, "前置条件缺少「账号已登录」"
    if len(precondition) < 15:
        return False, f"前置条件过于简单（{len(precondition)}字）: {precondition}"
    return True, ""


def validate_steps(steps: List[Dict[str, Any]], case_type: str = "") -> Tuple[bool, str]:
    """校验步骤完整性、确定性和自动化可执行性。

    Args:
        steps: 步骤列表
        case_type: 用例类型，用于判断是否需要自动化可执行性校验

    Returns:
        (是否通过, 问题描述)
    """
    if not steps or len(steps) == 0:
        return False, "步骤列表为空"
    for i, step in enumerate(steps):
        action = step.get("action", "") or step.get("description", "")
        if not action or not action.strip():
            return False, f"第{i + 1}步的 action 为空"
        expected = step.get("expected_result", "")
        if not expected or not expected.strip():
            return False, f"第{i + 1}步的 expected_result 为空"
        if _STEP_UNCERTAINTY_PATTERN.search(action):
            return False, f"第{i + 1}步操作不确定（含\"或\"字措辞），应拆分为独立用例: {action[:50]}"
        if case_type == "ui_automation" and _MANUAL_JUDGMENT_PATTERN.search(action):
            return False, f"第{i + 1}步含人工判断描述，与ui_automation类型矛盾: {action[:50]}"
    return True, ""


def validate_expected_result(expected_result: str) -> Tuple[bool, str]:
    """校验总体预期结果质量。

    检查策略：
        1. 非空且 ≥10 字
        2. 精确匹配模糊短语（如'正常显示''提交成功'）

    Args:
        expected_result: 总体预期结果文本

    Returns:
        (是否通过, 问题描述)
    """
    if not expected_result or not expected_result.strip():
        return False, "总体预期结果为空"
    expected_result = expected_result.strip()
    if len(expected_result) < 10:
        return False, f"预期结果过短（{len(expected_result)}字）: {expected_result}"
    for word in EXPECTED_VAGUE_WORDS:
        if word in expected_result:
            return False, f"预期结果包含模糊短语「{word}」: {expected_result}"
    return True, ""


def validate_case_category(case_category: str) -> Tuple[bool, str]:
    """校验 case_category 合法性。

    Args:
        case_category: 用例分类

    Returns:
        (是否通过, 问题描述)
    """
    if not case_category:
        return False, "case_category 为空"
    if case_category not in VALID_CASE_CATEGORIES:
        return False, f"case_category 非法值「{case_category}」，合法值: {sorted(VALID_CASE_CATEGORIES)}"
    return True, ""


def validate_single_case(case: Dict[str, Any]) -> List[str]:
    """对单条用例执行全量质量校验。

    Args:
        case: 单条测试用例字典

    Returns:
        问题描述列表，空列表表示全部通过
    """
    case_type = case.get("case_type", "")
    issues: List[str] = []
    checks: List[Tuple[str, Tuple[bool, str]]] = [
        ("标题", validate_title(case.get("title", ""))),
        ("前置条件", validate_precondition(case.get("precondition", ""))),
        ("步骤", validate_steps(case.get("steps", []), case_type=case_type)),
        ("预期结果", validate_expected_result(case.get("expected_result", ""))),
        ("case_category", validate_case_category(case.get("case_category", ""))),
    ]
    for check_name, (passed, msg) in checks:
        if not passed:
            issues.append(f"[{check_name}] {msg}")
    return issues


def validate_cases_quality(cases: List[Dict[str, Any]], min_count: int = 0) -> Tuple[bool, List[str]]:
    """对用例列表执行全量质量校验。

    Args:
        cases: 用例字典列表
        min_count: 最少用例数要求，0 表示不校验数量

    Returns:
        (是否全部通过, 所有问题描述列表)
    """
    all_issues: List[str] = []
    if min_count > 0 and len(cases) < min_count:
        all_issues.append(f"[数量] 生成{len(cases)}条用例，要求至少{min_count}条")
    for i, case in enumerate(cases):
        case_issues = validate_single_case(case)
        for issue in case_issues:
            all_issues.append(f"用例{i + 1} {issue}")
    return len(all_issues) == 0, all_issues


def compute_quality_score(cases: List[Dict[str, Any]]) -> float:
    """计算用例列表的质量分（0~100）。

    每维度 20 分，5 维度总分 100。

    Args:
        cases: 用例字典列表

    Returns:
        质量分 0~100
    """
    if not cases:
        return 0.0
    dim_scores: List[float] = []
    for case in cases:
        passed = 0
        total = 5
        case_type = case.get("case_type", "")
        if validate_title(case.get("title", ""))[0]:
            passed += 1
        if validate_precondition(case.get("precondition", ""))[0]:
            passed += 1
        if validate_steps(case.get("steps", []), case_type=case_type)[0]:
            passed += 1
        if validate_expected_result(case.get("expected_result", ""))[0]:
            passed += 1
        if validate_case_category(case.get("case_category", ""))[0]:
            passed += 1
        dim_scores.append(passed / total * 100)
    return sum(dim_scores) / len(dim_scores)


QUALITY_MIN_SCORE = 50.0
"""质量分阈值：低于此分数触发质量反馈重试"""