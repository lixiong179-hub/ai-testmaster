"""质量反馈闭环共享函数（Task 15）。

提取 ai_mixin._generate_case_with_ai 中的 3 轮反馈闭环逻辑为共享 async
函数，供流式端点（test_case_ai_stream）与非流式端点（ai_mixin）共用。

设计要点：
- regen_fn 由调用方提供 async 可调用对象，封装具体 AI 调用方式
  （流式端点用 asyncio.to_thread 包装 sync generate_test_case_enhanced；
   ai_mixin 直接 await _call_ai_and_parse），接收 extra_context dict。
- feedback_builder 由调用方提供，封装反馈文本构建逻辑（默认使用本模块的
  build_quality_feedback_text）。
- 只 rejected 阻断入库，pending_review/warning 不阻断（历史避坑：质量门禁
  分级阻断）。
- 第 N+1 轮注入 quality_signals（禁止盲重试，历史避坑要点 4）。
- on_round 回调供流式端点收集 SSE regen 事件。
"""
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from loguru import logger

from app.services.case_quality.quality_signals import build_quality_signals
from app.services.test_case_generation.quality_validator import validate_single_case_status

# 重生成函数：接收 extra_context dict（含 quality_feedback 与 quality_signals），
# 返回新用例 dict 或 None（本轮生成失败）
AsyncRegenFn = Callable[[Dict[str, Any]], Awaitable[Optional[Dict[str, Any]]]]
# 反馈文本构建器：(issues, case, status) -> 反馈文本
FeedbackBuilder = Callable[[List[str], Dict[str, Any], str], str]
# 轮次回调：(round_idx, status, issues) -> None，供流式端点收集 SSE 事件
RoundCallback = Callable[[int, str, List[str]], None]


# 质量反馈修复示例库（Task 9 spec L140/L202）。
# key 为问题关键词，value 为对应修复示例文本。build_quality_feedback_text
# 对每个 issue 按关键词匹配，将示例注入反馈供 AI 修复参考。
_QUALITY_FIX_EXAMPLES: Dict[str, str] = {
    "标题为空": "示例标题：'正常登录_正确账号密码_跳转首页'（场景+条件+验证重点，15-40字）",
    "标题过短": "示例标题：'异常登录_密码错误三次锁定账号显示等待时间'（需含场景+操作+验证重点，≥8字）",
    "标题过长": "示例标题：'正常登录_正确账号密码跳转首页'（控制在50字以内，删除冗余修饰词）",
    "模糊词": "避免使用'功能验证''界面测试''模块测试'等模糊词，改为具体场景+操作+验证重点",
    "原子性": "拆分为多条独立用例，每条只验证一个测试场景，禁止混合主流程与分支逻辑",
    "前置条件为空": "示例前置条件：'账号已登录，浏览器网络正常，已配置可用教材和单词数据'",
    "前置条件过短": "前置条件需包含：登录状态 + 网络环境 + 必要数据状态（如'账号已登录，设备网络正常'）",
    "缺少登录状态": "前置条件需明确登录状态：'账号已登录'或'用户未登录'",
    "步骤为空": "至少2步：1.导航到目标页面 2.核心操作/验证。前置条件中的状态必须通过步骤到达",
    "步骤不足": "至少2步（导航+核心操作），禁止生成仅1步的用例",
    "步骤过多": "最多8步，超过8步说明混合多个测试场景，必须拆分为多条独立用例",
    "预期结果为空": "示例预期结果：'登录成功，页面跳转至首页，顶部显示用户昵称'",
    "预期结果过短": "预期结果需包含交互校验点：弹窗文案、按钮跳转、元素状态变化等可量化判定标准",
    "预期结果包含模糊词": "避免'正常显示''功能正常''提交成功'等模糊描述，改为可量化判定标准",
    "action_type非法": "合法值：click/input/navigate/scroll/verify/select。判定口诀：含'点击'→click，含'输入'→input，含'查看/检查'→verify",
    "case_category": "合法值：positive(正向)/boundary(边界)/exception(异常)/inapplicable(不适用)",
    "边界用例": "边界用例应使用实际边界值（最大值/最小值/空值/特殊字符），而非占位符",
    "不应包含": "检查 case_type 与 action_type 组合一致性：api_automation 不应含 UI 动作，manual 不应含 api_call",
    "引用式步骤": "禁止'参见正向用例步骤''重复上一步''同上'等引用式步骤，每步必须写出完整可执行动作",
    "不确定措辞": "禁止'或''或者'等不确定措辞，每个步骤操作必须唯一确定",
}


def _match_quality_fix_example(issue: str) -> Optional[str]:
    """从 _QUALITY_FIX_EXAMPLES 按关键词匹配修复示例。

    Args:
        issue: validate_single_case_status 返回的单条问题描述。

    Returns:
        匹配到的修复示例文本；无匹配时返回 None。
    """
    for keyword, example in _QUALITY_FIX_EXAMPLES.items():
        if keyword in issue:
            return example
    return None


def build_quality_feedback_text(
    issues: List[str], case: Dict[str, Any], status: str = "pending_review"
) -> str:
    """将校验问题转为 AI 可理解的修复指引，按严重程度排序并匹配修复示例。

    从 ai_mixin._build_quality_feedback 提取的独立函数（不依赖 self），
    供 run_quality_feedback_loop 与 ai_mixin 共用。

    Args:
        issues: validate_single_case_status 返回的问题列表。
        case: 当前用例字典（供 AI 参考原有结构）。
        status: 上轮校验状态（passed/warning/pending_review/rejected），
            rejected 时所有问题视为严重；pending_review 时含"为空""不足""非法"
            关键词的视为严重；warning/passed 时均视为一般。

    Returns:
        结构化反馈文本，严重问题排在前列，每个问题附带修复示例（从
        _QUALITY_FIX_EXAMPLES 匹配），开头标注"请优先修复以下严重问题"。
    """
    severe_keywords = ("为空", "不足", "非法")
    if status == "rejected":
        severe_issues = list(issues)
        normal_issues: List[str] = []
    else:
        severe_issues = [i for i in issues if any(k in str(i) for k in severe_keywords)]
        normal_issues = [i for i in issues if not any(k in str(i) for k in severe_keywords)]
    sorted_issues = severe_issues + normal_issues

    feedback_lines: List[str] = []
    for issue in sorted_issues:
        fix_example = _match_quality_fix_example(str(issue))
        if fix_example:
            feedback_lines.append(f"- {issue}\n  修复示例: {fix_example}")
        else:
            feedback_lines.append(f"- {issue}")
    issue_lines = "\n".join(feedback_lines)
    return (
        f"请优先修复以下严重问题（按严重程度排序，严重问题排在前面）：\n{issue_lines}\n"
        "请基于原有用例修改上述问题，保持未变更部分不变。只输出修改后的完整JSON。"
    )


async def run_quality_feedback_loop(
    case: Dict[str, Any],
    regen_fn: AsyncRegenFn,
    feedback_builder: Optional[FeedbackBuilder] = None,
    max_rounds: Optional[int] = None,
    on_round: Optional[RoundCallback] = None,
) -> Tuple[Dict[str, Any], str, List[str]]:
    """执行质量反馈闭环（最多 max_rounds 轮，含首轮校验）。

    首轮直接校验输入 case；不通过则通过 regen_fn 重生成，每轮注入
    quality_feedback + quality_signals。只 rejected 阻塞，其他状态返回。
    流式端点通过 on_round 回调收集 SSE regen 事件。

    性能优化：max_rounds 默认从 3 收敛到 settings.AI_QUALITY_FEEDBACK_MAX_ROUNDS
    （默认 1）。推理模型下每轮 25-55s，3 轮可能 200s+；1 轮重生成已能修复
    大部分质量问题，仍 rejected 由上层 batch_orchestrator 跳过该用例。

    Args:
        case: 首轮生成的用例 dict。
        regen_fn: 重生成 async 函数，接收 extra_context dict（含
            quality_feedback 与 quality_signals），返回新用例 dict 或 None。
        feedback_builder: 反馈文本构建器，默认使用 build_quality_feedback_text。
        max_rounds: 最大轮次（含首轮校验），None 时取 settings.AI_QUALITY_FEEDBACK_MAX_ROUNDS + 1。
        on_round: 可选轮次回调，每轮校验后调用，供流式端点收集 SSE 事件。

    Returns:
        (最终用例, 最终状态, 最终问题列表)。
    """
    from app.core.config import settings
    from app.services.case_quality.quality_scoring_service import QualityScoringService

    # 性能优化：默认轮数从配置读取，避免硬编码 3 导致 200s+ 长尾
    if max_rounds is None:
        max_rounds = settings.AI_QUALITY_FEEDBACK_MAX_ROUNDS + 1  # 含首轮校验

    builder = feedback_builder or build_quality_feedback_text

    current_case = case
    status, issues = validate_single_case_status(current_case)
    if on_round:
        on_round(0, status, issues)

    if status == "passed":
        return current_case, status, issues

    for round_idx in range(1, max_rounds):
        # 构建反馈文本与质量信号（禁止盲重试，必须传具体问题与低分维度）
        feedback_text = builder(issues, current_case, status)
        dim_scores = QualityScoringService.score_dimensions(current_case)
        signals = build_quality_signals(issues, dim_scores, current_case)
        extra_context: Dict[str, Any] = {
            "quality_feedback": feedback_text,
            "quality_signals": signals,
        }

        logger.info(
            f"质量反馈闭环第{round_idx}轮: status={status}, "
            f"issues={len(issues)}, low_dims={signals.get('low_dimensions')}"
        )

        new_case = await regen_fn(extra_context)
        if new_case is None:
            logger.warning(f"质量反馈闭环第{round_idx}轮重生成失败，保留上轮用例")
            continue

        current_case = new_case
        status, issues = validate_single_case_status(current_case)
        if on_round:
            on_round(round_idx, status, issues)

        if status == "passed":
            return current_case, status, issues

    return current_case, status, issues
