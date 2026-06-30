"""Task 15 质量反馈闭环共享函数测试。

断言 run_quality_feedback_loop 正确执行 3 轮反馈闭环：
- 首轮校验通过时不重生成
- 不通过时通过 regen_fn 重生成，每轮注入 quality_feedback + quality_signals
- 只 rejected 不阻断返回（阻断由调用方决定，历史避坑：分级阻断）
- on_round 回调正确收集每轮状态（供流式端点 SSE 事件）
- 禁止盲重试：extra_context 必须含具体 quality_signals（历史避坑要点 4）

同时覆盖 build_quality_feedback_text 的严重问题排序与修复示例匹配。
"""
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock

import pytest

from app.services.case_quality.quality_feedback_loop import (
    _match_quality_fix_example,
    build_quality_feedback_text,
    run_quality_feedback_loop,
)


def _make_valid_case(**overrides: Any) -> Dict[str, Any]:
    """构造一条全维度通过的基准用例，通过 overrides 覆盖特定字段。"""
    base: Dict[str, Any] = {
        "title": "验证用户登录功能正常工作流程",
        "precondition": "账号已登录，网络环境正常，测试数据已准备",
        "steps": [
            {"action": "点击登录按钮", "expected_result": "跳转到首页", "action_type": "click"},
            {"action": "查看欢迎信息", "expected_result": "显示欢迎文字", "action_type": "verify"},
        ],
        "expected_result": "登录成功并显示欢迎页面，用户名正确显示",
        "case_category": "positive",
        "case_type": "ui_automation",
    }
    base.update(overrides)
    return base


# ── run_quality_feedback_loop ──


class TestRunQualityFeedbackLoop:
    """run_quality_feedback_loop 3 轮反馈闭环。"""

    @pytest.mark.asyncio
    async def test_first_round_passed_no_regen(self) -> None:
        """首轮校验通过时不调用 regen_fn，直接返回。"""
        case = _make_valid_case()
        regen_fn = AsyncMock()
        final_case, status, _ = await run_quality_feedback_loop(case, regen_fn)
        assert status == "passed"
        assert final_case is case
        regen_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_regen_passed_second_round(self) -> None:
        """首轮不通过，第二轮重生成通过。"""
        bad_case = _make_valid_case(title="")
        good_case = _make_valid_case()
        regen_fn = AsyncMock(return_value=good_case)
        final_case, status, _ = await run_quality_feedback_loop(bad_case, regen_fn)
        assert status == "passed"
        assert final_case is good_case
        regen_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_rounds_fail_returns_last(self) -> None:
        """所有轮次都不通过，返回最终 case 与 rejected 状态。"""
        bad_case = _make_valid_case(title="")
        regen_fn = AsyncMock(return_value=_make_valid_case(title=""))
        final_case, status, _ = await run_quality_feedback_loop(
            bad_case, regen_fn, max_rounds=3,
        )
        # max_rounds=3：首轮校验 + range(1,3)=2 轮重生成
        assert regen_fn.call_count == 2
        assert status == "rejected"

    @pytest.mark.asyncio
    async def test_rejected_not_blocking_return(self) -> None:
        """rejected 状态仍返回（不阻断返回，阻断由调用方决定）。"""
        bad_case = _make_valid_case(title="")
        regen_fn = AsyncMock(return_value=_make_valid_case(title=""))
        final_case, status, issues = await run_quality_feedback_loop(
            bad_case, regen_fn, max_rounds=2,
        )
        assert status == "rejected"
        assert final_case is not None
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_on_round_callback_first_round(self) -> None:
        """首轮校验通过时 on_round 以 round=0 调用。"""
        case = _make_valid_case()
        rounds: List[Tuple[int, str]] = []

        def on_round(round_idx: int, rst_status: str, issues: List[str]) -> None:
            rounds.append((round_idx, rst_status))

        await run_quality_feedback_loop(case, AsyncMock(), on_round=on_round)
        assert len(rounds) == 1
        assert rounds[0] == (0, "passed")

    @pytest.mark.asyncio
    async def test_on_round_callback_multiple_rounds(self) -> None:
        """多轮重生成时 on_round 每轮都被调用。"""
        bad_case = _make_valid_case(title="")
        good_case = _make_valid_case()
        regen_fn = AsyncMock(side_effect=[bad_case, good_case])
        rounds: List[Tuple[int, str]] = []

        def on_round(round_idx: int, rst_status: str, issues: List[str]) -> None:
            rounds.append((round_idx, rst_status))

        await run_quality_feedback_loop(
            bad_case, regen_fn, on_round=on_round, max_rounds=3,
        )
        # round 0 首轮 rejected → round 1 regen 仍 rejected → round 2 regen passed
        assert len(rounds) == 3
        assert rounds[0] == (0, "rejected")
        assert rounds[1] == (1, "rejected")
        assert rounds[2] == (2, "passed")

    @pytest.mark.asyncio
    async def test_regen_fn_returns_none_continues(self) -> None:
        """regen_fn 返回 None 时保留上轮用例继续下一轮。"""
        bad_case = _make_valid_case(title="")
        good_case = _make_valid_case()
        regen_fn = AsyncMock(side_effect=[None, good_case])
        final_case, status, _ = await run_quality_feedback_loop(
            bad_case, regen_fn, max_rounds=3,
        )
        assert regen_fn.call_count == 2
        assert status == "passed"
        assert final_case is good_case

    @pytest.mark.asyncio
    async def test_max_rounds_one_only_first_check(self) -> None:
        """max_rounds=1 只做首轮校验，不重生成。"""
        bad_case = _make_valid_case(title="")
        regen_fn = AsyncMock()
        final_case, status, _ = await run_quality_feedback_loop(
            bad_case, regen_fn, max_rounds=1,
        )
        assert status == "rejected"
        regen_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_extra_context_contains_feedback_and_signals(self) -> None:
        """regen_fn 收到含 quality_feedback 与 quality_signals 的 extra_context。

        历史避坑要点 4：禁止盲重试，quality_signals 必须含具体问题与低分维度。
        """
        bad_case = _make_valid_case(title="")
        good_case = _make_valid_case()
        captured: List[Dict[str, Any]] = []

        async def capture_regen(extra_ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            captured.append(extra_ctx)
            return good_case

        await run_quality_feedback_loop(bad_case, capture_regen)
        assert len(captured) == 1
        ctx = captured[0]
        assert "quality_feedback" in ctx
        assert "quality_signals" in ctx
        assert isinstance(ctx["quality_feedback"], str)
        assert len(ctx["quality_feedback"]) > 0
        signals = ctx["quality_signals"]
        assert "issues" in signals
        assert "dim_scores" in signals
        assert "low_dimensions" in signals
        # 禁止盲重试：quality_signals 必须含具体问题
        assert len(signals["issues"]) > 0

    @pytest.mark.asyncio
    async def test_warning_status_triggers_regen(self) -> None:
        """warning 状态（非 passed）触发重生成尝试改进。

        run_quality_feedback_loop 中只有 passed 直接返回，warning/pending_review/
        rejected 都进入重生成循环。只 rejected 阻断入库由调用方决定（分级阻断）。
        """
        warning_case = _make_valid_case(title="短标题")
        good_case = _make_valid_case()
        regen_fn = AsyncMock(return_value=good_case)
        final_case, status, _ = await run_quality_feedback_loop(warning_case, regen_fn)
        assert status == "passed"
        assert final_case is good_case
        regen_fn.assert_called_once()


# ── build_quality_feedback_text ──


class TestBuildQualityFeedbackText:
    """build_quality_feedback_text 反馈文本构建。"""

    def test_rejected_all_severe(self) -> None:
        """rejected 状态所有问题视为严重。"""
        text = build_quality_feedback_text(
            ["标题为空", "步骤过多"], _make_valid_case(), "rejected",
        )
        assert "请优先修复以下严重问题" in text
        assert "标题为空" in text
        assert "步骤过多" in text

    def test_pending_review_severe_keywords_sorted_first(self) -> None:
        """pending_review 含'为空''不足''非法'的视为严重，排在前面。"""
        text = build_quality_feedback_text(
            ["步骤过多", "标题为空"], _make_valid_case(), "pending_review",
        )
        # "标题为空"含"为空"是严重，"步骤过多"不含是普通，严重排前
        empty_pos = text.index("标题为空")
        many_pos = text.index("步骤过多")
        assert empty_pos < many_pos

    def test_fix_example_matched(self) -> None:
        """问题匹配修复示例时附带修复示例。"""
        text = build_quality_feedback_text(
            ["标题为空"], _make_valid_case(), "rejected",
        )
        assert "修复示例" in text
        assert "示例标题" in text

    def test_no_fix_example_for_unknown_issue(self) -> None:
        """无匹配修复示例时该问题行不含修复示例。"""
        text = build_quality_feedback_text(
            ["未知问题类型"], _make_valid_case(), "rejected",
        )
        unknown_line = [ln for ln in text.split("\n") if "未知问题类型" in ln][0]
        assert "修复示例" not in unknown_line

    def test_output_contains_modify_instruction(self) -> None:
        """反馈文本含修改指令（只输出修改后的完整JSON）。"""
        text = build_quality_feedback_text(["问题"], {}, "rejected")
        assert "只输出修改后的完整JSON" in text

    def test_empty_issues_returns_header_only(self) -> None:
        """issues 为空时仍返回含头部的文本（边界场景）。"""
        text = build_quality_feedback_text([], {}, "rejected")
        assert "请优先修复以下严重问题" in text


# ── _match_quality_fix_example ──


class TestMatchQualityFixExample:
    """_match_quality_fix_example 关键词匹配修复示例。"""

    def test_match_found(self) -> None:
        result = _match_quality_fix_example("标题为空")
        assert result is not None
        assert "示例标题" in result

    def test_no_match_returns_none(self) -> None:
        assert _match_quality_fix_example("完全无法匹配的问题") is None

    def test_match_action_type(self) -> None:
        result = _match_quality_fix_example("action_type非法")
        assert result is not None
        assert "click" in result
