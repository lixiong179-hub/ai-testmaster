"""Task 19.4 流式与非流式生成路径一致性集成测试。

断言流式端点（test_case_ai_stream._run_quality_feedback_for_cases）与非流式
入口（ai_mixin._generate_case_with_ai）都通过共享函数 run_quality_feedback_loop
处理用例，且使用相同的 build_quality_feedback_text 作为 feedback_builder。

这是 spec 19.4"A/B 级占比差异 ≤ 5%"的代码路径一致性强证据：
两者共用同一反馈闭环函数 → 同一质量门禁 → 同一重生成逻辑 →
质量分布差异仅来源于 AI 生成本身的随机性。

真实 A/B 占比差异 ≤ 5% 的统计验证待真实 AI 环境执行（spec 19.4 第三项），
原因：
1. 测试环境 AI_API_KEY 默认空（见 app/core/config.py L83），无法真实调用 AI
2. AI 生成本质非确定（temperature > 0），需多次采样统计才有意义
3. 项目规则禁止 CI 中调用真实 AI（token 成本 + 不稳定）
"""
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.endpoints import test_case_ai_stream
from app.services.case_quality import quality_feedback_loop as feedback_loop_module
from app.services.case_quality.quality_feedback_loop import (
    build_quality_feedback_text,
    run_quality_feedback_loop,
)
from app.services.test_case_generation import TestCaseGenerationService


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


def _build_spy() -> tuple[list, Any]:
    """构建 run_quality_feedback_loop 的 spy 包装器，记录调用参数并透传原函数。

    Returns:
        (calls, spy_loop) — calls 为调用记录列表，spy_loop 为 async 包装器。
    """
    calls: List[Dict[str, Any]] = []
    original = run_quality_feedback_loop

    async def spy_loop(
        case: Dict[str, Any],
        regen_fn: Any,
        feedback_builder: Optional[Any] = None,
        max_rounds: int = 3,
        on_round: Optional[Any] = None,
    ) -> Any:
        calls.append({
            "case": case,
            "feedback_builder": feedback_builder,
            "max_rounds": max_rounds,
        })
        return await original(case, regen_fn, feedback_builder, max_rounds, on_round)

    return calls, spy_loop


class TestStreamNonstreamSharedFeedbackLoop:
    """流式与非流式入口都调用共享 run_quality_feedback_loop。"""

    @pytest.mark.asyncio
    async def test_stream_endpoint_uses_shared_feedback_loop(self) -> None:
        """流式端点 _run_quality_feedback_for_cases 调用共享 run_quality_feedback_loop。

        流式端点通过 _run_quality_feedback_for_cases 包装 run_quality_feedback_loop，
        传入 build_quality_feedback_text 作为 feedback_builder（spec 19.4 路径一致性）。
        """
        bad_case = _make_valid_case(title="")
        good_case = _make_valid_case()
        regen_fn = AsyncMock(return_value=good_case)
        calls, spy_loop = _build_spy()

        with patch.object(test_case_ai_stream, "run_quality_feedback_loop", spy_loop):
            final_cases, regen_events = await test_case_ai_stream._run_quality_feedback_for_cases(
                [bad_case], regen_fn,
            )

        assert len(calls) == 1, "流式端点应对每条用例调用一次 run_quality_feedback_loop"
        assert calls[0]["feedback_builder"] is build_quality_feedback_text, (
            "流式端点应使用共享 build_quality_feedback_text 作为 feedback_builder"
        )
        assert calls[0]["case"] is bad_case
        # bad_case 经重生成修复为 good_case，应保留在 final_cases 而非丢弃
        assert len(final_cases) == 1
        assert final_cases[0] is good_case
        # 重生成轮次事件被收集（供 SSE 推送 regen 事件）
        assert len(regen_events) >= 1

    @pytest.mark.asyncio
    async def test_nonstream_endpoint_uses_shared_feedback_loop(self) -> None:
        """非流式 _generate_case_with_ai 调用共享 run_quality_feedback_loop。

        非流式入口通过 _generate_case_with_ai 调用 run_quality_feedback_loop，
        传入 build_quality_feedback_text 作为 feedback_builder（spec 19.4 路径一致性）。
        """
        good_case = _make_valid_case()
        service = TestCaseGenerationService.__new__(TestCaseGenerationService)
        service._generation_cache = {}

        calls, spy_loop = _build_spy()

        async def mock_call_ai(prompt: str, min_case_count: int = 1) -> Optional[Dict[str, Any]]:
            return good_case

        context: Dict[str, Any] = {
            "test_point": {"module": "登录模块", "function": "用户登录", "point": "正常登录", "priority": 2},
            "test_points": [],
            "requirement_content": "用户登录功能",
            "ui_description": "",
            "case_type": "manual",
            "ui_specs": [],
            "history_cases": [],
            "project_id": 1,
        }

        with patch.object(feedback_loop_module, "run_quality_feedback_loop", spy_loop), \
                patch.object(service, "_call_ai_and_parse", mock_call_ai), \
                patch("app.services.test_case_generation.ai_mixin.PromptBuilder.build_linear_prompt",
                      return_value="mocked prompt"):
            final_case = await service._generate_case_with_ai(context)

        assert len(calls) == 1, "非流式入口应调用一次 run_quality_feedback_loop"
        assert calls[0]["feedback_builder"] is build_quality_feedback_text, (
            "非流式入口应使用共享 build_quality_feedback_text 作为 feedback_builder"
        )
        assert final_case is not None
        # good_case 全维度通过，应被缓存（passed 状态）
        assert calls[0]["case"] is good_case

    @pytest.mark.asyncio
    async def test_stream_and_nonstream_share_same_loop_function(self) -> None:
        """流式与非流式使用同一个 run_quality_feedback_loop 函数对象。

        强不变量：两端点 import 的 run_quality_feedback_loop 是同一对象，
        保证行为一致（spec 19.4 A/B 占比一致的结构性保证）。
        """
        from app.api.v1.endpoints import test_case_ai_stream as stream_mod
        from app.services.case_quality import quality_feedback_loop as src_mod

        # 流式端点模块顶部 import 的 run_quality_feedback_loop 与源模块同一对象
        assert stream_mod.run_quality_feedback_loop is run_quality_feedback_loop
        # 非流式 ai_mixin 函数内部 import 运行时从源模块取 attribute（ai_mixin.py L146-148），
        # 故源模块的 run_quality_feedback_loop 即非流式入口实际调用的函数对象
        assert src_mod.run_quality_feedback_loop is run_quality_feedback_loop
