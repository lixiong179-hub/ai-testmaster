"""XMind AI 增强解析器单元测试。

测试策略：
    - 工具函数（_build_user_prompt、_parse_ai_response、_normalize_case）使用真实输入输出验证
    - XmindAIParser 集成测试通过注入无效 base_url 触发真实网络错误，不使用 Mock
"""
import json

import pytest

from app.services.xmind_ai_parser import (
    XmindAIParser,
    _build_user_prompt,
    _normalize_case,
    _parse_ai_response,
)


# ── _build_user_prompt ──────────────────────────────────────────


def test_build_user_prompt_single_path():
    paths = [["字词听写", "有教材内容", "点击听写记录", "界面显示最近的听写记录"]]
    result = _build_user_prompt(paths)
    assert "1. 字词听写 → 有教材内容 → 点击听写记录 → 界面显示最近的听写记录" in result


def test_build_user_prompt_multiple_paths():
    paths = [
        ["模块A", "功能1", "结果1"],
        ["模块B", "功能2", "结果2"],
    ]
    result = _build_user_prompt(paths)
    assert result.startswith("1.")
    assert "2." in result


# ── _parse_ai_response ──────────────────────────────────────────


def test_parse_ai_response_direct_object_with_cases():
    text = json.dumps({"cases": [{"module": "A", "title": "T1"}]})
    result = _parse_ai_response(text, 1)
    assert result is not None
    assert len(result) == 1
    assert result[0]["module"] == "A"


def test_parse_ai_response_direct_array():
    text = json.dumps([{"module": "A", "title": "T1"}])
    result = _parse_ai_response(text, 1)
    assert result is not None
    assert len(result) == 1


def test_parse_ai_response_with_markdown_wrapper():
    text = '```json\n{"cases": [{"module": "A"}]}\n```'
    result = _parse_ai_response(text, 1)
    assert result is not None
    assert len(result) == 1


def test_parse_ai_response_invalid_json():
    result = _parse_ai_response("not json at all", 1)
    assert result is None


def test_parse_ai_response_empty_text():
    result = _parse_ai_response("", 1)
    assert result is None


def test_parse_ai_response_count_mismatch():
    text = json.dumps({"cases": [{"module": "A"}, {"module": "B"}]})
    result = _parse_ai_response(text, 3)
    assert result is not None
    assert len(result) == 2


def test_parse_ai_response_repairs_missing_comma_between_fields():
    text = '{"cases": [{"module": "A"\n"title": "T1"}]}'
    result = _parse_ai_response(text, 1)
    assert result is not None
    assert len(result) == 1
    assert result[0]["module"] == "A"
    assert result[0]["title"] == "T1"


def test_parse_ai_response_extracts_partial_objects_when_wrapper_is_broken():
    text = '{"cases": [{"module": "A", "title": "T1"}, {"module": "B", "title": "T2"}'
    result = _parse_ai_response(text, 2)
    assert result is not None
    assert len(result) == 2
    assert result[0]["module"] == "A"
    assert result[1]["module"] == "B"


# ── _normalize_case ──────────────────────────────────────────────


def test_normalize_case_full():
    raw = {
        "module": "字词听写",
        "precondition": "有教材内容\n有记录",
        "title": "点击听写记录显示最近记录",
        "steps": [
            {"action": "点击听写记录", "expected_result": "显示最近的听写记录"}
        ],
        "expected_result": "显示最近的听写记录",
        "priority": 2,
    }
    result = _normalize_case(raw, "fallback")
    assert result["module"] == "字词听写"
    assert result["precondition"] == "有教材内容\n有记录"
    assert result["title"] == "点击听写记录显示最近记录"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["step"] == 1
    assert result["steps"][0]["action"] == "点击听写记录"
    assert result["expected_result"] == "显示最近的听写记录"
    assert result["priority"] == 2
    assert result["case_type"] == "manual"
    assert result["action_count"] == 1


def test_normalize_case_no_steps_creates_verify():
    raw = {
        "module": "M",
        "title": "T",
        "expected_result": "界面正常",
        "steps": [],
    }
    result = _normalize_case(raw, "M")
    assert len(result["steps"]) == 1
    assert "验证场景" in result["steps"][0]["action"]


def test_normalize_case_invalid_priority():
    raw = {"priority": 99, "expected_result": "R", "steps": []}
    result = _normalize_case(raw, "M")
    assert result["priority"] == 2


def test_normalize_case_fallback_module():
    raw = {"steps": [], "expected_result": "R"}
    result = _normalize_case(raw, "默认模块")
    assert result["module"] == "默认模块"


# ── XmindAIParser 集成测试（不使用 Mock）─────────────────────────


def test_parse_paths_with_invalid_api_key_returns_empty():
    """使用无效配置触发真实网络错误，验证返回空列表而非抛异常。

    使用 127.0.0.1 的无效端口避免 DNS 解析等待，加速测试执行。
    """
    parser = XmindAIParser(
        api_key="invalid-key-for-testing",
        base_url="http://127.0.0.1:59999",
        model="deepseek-chat",
        timeout=2,
    )
    paths = [["字词听写", "有教材内容", "点击听写记录", "显示记录"]]
    results = parser.parse_paths(paths)
    assert results == []


def test_parse_paths_empty():
    parser = XmindAIParser()
    assert parser.parse_paths([]) == []


def test_parser_timeout_config_is_set():
    """验证 timeout 参数正确传递到客户端配置。"""
    parser = XmindAIParser(timeout=30)
    assert parser._timeout == 30
    assert parser.client.timeout == 30


def test_parser_settings_defaults_applied(monkeypatch):
    """未传入构造参数时应回退到 settings 配置值。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "XMIND_AI_TIMEOUT", 77, raising=False)
    monkeypatch.setattr(settings, "XMIND_AI_MAX_WORKERS", 7, raising=False)
    monkeypatch.setattr(settings, "XMIND_AI_BATCH_SIZE", 17, raising=False)
    monkeypatch.setattr(settings, "XMIND_AI_MAX_TOKENS", 1234, raising=False)

    parser = XmindAIParser()
    assert parser._timeout == 77
    assert parser._max_workers == 7
    assert parser._batch_size == 17
    assert parser._max_tokens == 1234


# ── 并行调度 ────────────────────────────────────────────────────


def test_parse_paths_parallel_preserves_input_order(monkeypatch):
    """即使后批次先返回，最终结果仍按输入顺序排列。"""
    import threading
    import time as _time

    parser = XmindAIParser(batch_size=2, max_workers=3, timeout=5)

    call_order: list = []
    lock = threading.Lock()

    def fake_call_ai(self, batch):
        # 让第一个批次响应最慢，验证 as_completed 不会破坏最终顺序
        delay = {"A0": 0.20, "B0": 0.05, "C0": 0.05}.get(batch[0][0], 0.0)
        _time.sleep(delay)
        with lock:
            call_order.append(batch[0][0])
        return [
            {
                "module": path[0],
                "title": f"T-{path[0]}-{i}",
                "expected_result": "ok",
                "steps": [{"action": f"act-{i}", "expected_result": "ok"}],
                "priority": 2,
            }
            for i, path in enumerate(batch)
        ]

    monkeypatch.setattr(XmindAIParser, "_call_ai", fake_call_ai)

    paths = [
        ["A0", "leaf"], ["A1", "leaf"],     # 批次 0（最慢）
        ["B0", "leaf"], ["B1", "leaf"],     # 批次 1
        ["C0", "leaf"], ["C1", "leaf"],     # 批次 2
    ]
    result = parser.parse_paths(paths)

    assert [item["module"] for item in result] == ["A0", "A1", "B0", "B1", "C0", "C1"]
    # 至少 B 或 C 中的一个先于 A 完成，证明确实并行
    assert call_order[0] in ("B0", "C0")


def test_parse_paths_skips_failed_batch_keeps_others(monkeypatch):
    """单个批次失败时其余批次结果应正常返回。"""
    parser = XmindAIParser(batch_size=2, max_workers=2, timeout=5)

    def fake_call_ai(self, batch):
        if batch[0][0] == "BAD":
            return None
        return [
            {
                "module": path[0],
                "title": f"T-{path[0]}",
                "expected_result": "ok",
                "steps": [{"action": "x", "expected_result": "ok"}],
                "priority": 2,
            }
            for path in batch
        ]

    monkeypatch.setattr(XmindAIParser, "_call_ai", fake_call_ai)

    paths = [
        ["GOOD0", "leaf"], ["GOOD1", "leaf"],
        ["BAD", "leaf"], ["BAD", "leaf"],
        ["GOOD2", "leaf"], ["GOOD3", "leaf"],
    ]
    result = parser.parse_paths(paths)

    modules = [item["module"] for item in result]
    assert modules == ["GOOD0", "GOOD1", "GOOD2", "GOOD3"]


# ── finish_reason / 参数校验 ─────────────────────────────────────


def test_call_ai_warns_on_finish_reason_length():
    """当 AI 返回 finish_reason='length' 时应记录截断警告日志。"""
    from unittest.mock import MagicMock
    from loguru import logger

    parser = XmindAIParser(timeout=5)

    # 构造一个模拟的 OpenAI response
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "cases": [
            {
                "module": "M",
                "title": "T",
                "expected_result": "ok",
                "steps": [{"action": "a", "expected_result": "e"}],
                "priority": 2,
            }
        ]
    })
    mock_choice.finish_reason = "length"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    parser._client = mock_client

    captured: list = []
    sink_id = logger.add(lambda msg: captured.append(str(msg)), level="WARNING")
    try:
        result = parser._call_ai([["M", "leaf"]])
    finally:
        logger.remove(sink_id)

    assert result is not None
    assert any("截断" in m or "max_tokens" in m for m in captured)


def test_parser_rejects_non_positive_params():
    """传入 0 或负值参数应抛出 ValueError。"""
    with pytest.raises(ValueError, match="batch_size"):
        XmindAIParser(batch_size=0)
    with pytest.raises(ValueError, match="timeout"):
        XmindAIParser(timeout=-1)
    with pytest.raises(ValueError, match="max_workers"):
        XmindAIParser(max_workers=0)
    with pytest.raises(ValueError, match="max_tokens"):
        XmindAIParser(max_tokens=-10)
