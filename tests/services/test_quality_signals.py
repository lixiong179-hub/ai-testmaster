"""Task 16 质量信号构建与格式化测试。

断言 build_quality_signals 正确构建 issues/dim_scores/low_dimensions，
format_quality_signals 正确格式化为 Prompt 文本段（含具体问题与低分维度标记）。

历史避坑要点 4：禁止盲重试，quality_signals 必须携带具体失败原因与低分维度，
让 AI 在下一轮针对具体问题修复而非无信息地重复生成。
"""
from typing import Any, Dict, List

from app.services.case_quality.quality_signals import (
    LOW_DIMENSION_THRESHOLD,
    build_quality_signals,
    format_quality_signals,
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


# ── build_quality_signals ──


class TestBuildQualitySignals:
    """build_quality_signals 构建 issues/dim_scores/low_dimensions。"""

    def test_with_issues_and_dim_scores(self) -> None:
        issues: List[str] = ["标题为空", "步骤不足"]
        dim_scores: Dict[str, float] = {"title": 0.0, "steps": 7.0, "expected_result": 10.0}
        signals = build_quality_signals(issues, dim_scores)
        assert signals["issues"] == ["标题为空", "步骤不足"]
        assert signals["dim_scores"] == dim_scores
        # 严格小于阈值才视为低分：title=0.0 低于 7.0，steps=7.0 不低于
        assert signals["low_dimensions"] == ["title"]

    def test_filters_empty_issues(self) -> None:
        signals = build_quality_signals(["有效问题", "", "  "], {})
        assert signals["issues"] == ["有效问题"]

    def test_none_issues_returns_empty_list(self) -> None:
        signals = build_quality_signals(None, {})
        assert signals["issues"] == []

    def test_none_dim_scores_with_case_computes_dimensions(self) -> None:
        """dim_scores 为 None 时通过 QualityScoringService 现算维度评分。"""
        case = _make_valid_case()
        signals = build_quality_signals(["问题"], None, case)
        assert "dim_scores" in signals
        assert "title" in signals["dim_scores"]
        # 基准用例全维度通过，title 维度得满分
        assert signals["dim_scores"]["title"] == 10.0

    def test_none_dim_scores_and_none_case_returns_empty_scores(self) -> None:
        signals = build_quality_signals(["问题"], None, None)
        assert signals["dim_scores"] == {}

    def test_low_dimensions_below_threshold(self) -> None:
        dim_scores: Dict[str, float] = {
            "title": 10.0, "precondition": 4.0, "steps": 6.9, "expected_result": 7.0,
        }
        signals = build_quality_signals([], dim_scores)
        # precondition(4.0) 与 steps(6.9) 低于阈值，expected_result(7.0) 不低于
        assert set(signals["low_dimensions"]) == {"precondition", "steps"}

    def test_dim_scores_passed_by_value(self) -> None:
        """返回的 dim_scores 是副本，修改原 dict 不影响信号。"""
        dim_scores: Dict[str, float] = {"title": 5.0}
        signals = build_quality_signals([], dim_scores)
        dim_scores["title"] = 10.0
        assert signals["dim_scores"]["title"] == 5.0

    def test_empty_dim_scores_dict_returns_empty(self) -> None:
        signals = build_quality_signals(["问题"], {})
        assert signals["dim_scores"] == {}
        assert signals["low_dimensions"] == []

    def test_returned_structure_has_all_keys(self) -> None:
        signals = build_quality_signals(["问题"], {"title": 5.0})
        assert set(signals.keys()) == {"issues", "dim_scores", "low_dimensions"}


# ── format_quality_signals ──


class TestFormatQualitySignals:
    """format_quality_signals 格式化为 Prompt 文本段。"""

    def test_none_returns_empty(self) -> None:
        assert format_quality_signals(None) == ""

    def test_empty_dict_returns_empty(self) -> None:
        assert format_quality_signals({}) == ""

    def test_no_issues_no_dim_scores_returns_empty(self) -> None:
        assert format_quality_signals({"issues": [], "dim_scores": {}}) == ""

    def test_non_dict_returns_empty(self) -> None:
        assert format_quality_signals("not a dict") == ""  # type: ignore[arg-type]

    def test_with_issues_contains_header_and_items(self) -> None:
        signals = build_quality_signals(["标题为空", "步骤不足"], {})
        text = format_quality_signals(signals)
        assert "## 质量信号" in text
        assert "### 具体问题" in text
        assert "- 标题为空" in text
        assert "- 步骤不足" in text

    def test_with_dim_scores_contains_dimension_section(self) -> None:
        signals = build_quality_signals([], {"title": 5.0, "steps": 10.0})
        text = format_quality_signals(signals)
        assert "### 维度评分" in text
        assert "title: 5.0" in text
        assert "steps: 10.0" in text

    def test_low_dimension_marker(self) -> None:
        """低分维度行含 [低于阈值，需修复] 标记，高分维度不含。"""
        signals = build_quality_signals([], {"title": 4.0, "steps": 10.0})
        text = format_quality_signals(signals)
        assert "[低于阈值，需修复]" in text
        title_line = [ln for ln in text.split("\n") if "title: 4.0" in ln][0]
        steps_line = [ln for ln in text.split("\n") if "steps: 10.0" in ln][0]
        assert "[低于阈值，需修复]" in title_line
        assert "[低于阈值，需修复]" not in steps_line

    def test_full_format_contains_blind_retry_warning(self) -> None:
        """格式化文本含禁止盲重试提示（历史避坑要点 4）。"""
        signals = build_quality_signals(["标题为空"], {"title": 0.0})
        text = format_quality_signals(signals)
        assert "禁止忽略或无信息盲重试" in text

    def test_threshold_value_in_text(self) -> None:
        signals = build_quality_signals([], {"title": 5.0})
        text = format_quality_signals(signals)
        assert f"{LOW_DIMENSION_THRESHOLD:.1f}" in text

    def test_full_format_structure(self) -> None:
        """完整信号格式化后包含所有段落且顺序正确。"""
        signals = build_quality_signals(
            ["标题为空"], {"title": 0.0, "steps": 10.0},
        )
        text = format_quality_signals(signals)
        header_pos = text.index("## 质量信号")
        issues_pos = text.index("### 具体问题")
        dim_pos = text.index("### 维度评分")
        # 段落顺序：标题 → 具体问题 → 维度评分 → 禁止盲重试
        assert header_pos < issues_pos < dim_pos
        assert text.endswith("请针对以上具体问题逐条修复，禁止忽略或无信息盲重试。")
