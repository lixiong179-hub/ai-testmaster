"""XMind AI 增强解析器单元测试（模拟 LLM 响应）。"""
import json
from unittest.mock import MagicMock, patch

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


def test_parse_ai_response_count_mismatch():
    text = json.dumps({"cases": [{"module": "A"}, {"module": "B"}]})
    result = _parse_ai_response(text, 3)
    assert result is not None
    assert len(result) == 2


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


# ── XmindAIParser.parse_paths (mocked) ──────────────────────────


@patch("app.services.xmind_ai_parser.XmindAIParser._call_ai")
def test_parse_paths_success(mock_call_ai):
    mock_call_ai.return_value = [
        {
            "module": "字词听写",
            "precondition": "有教材内容",
            "title": "有记录时显示听写记录",
            "steps": [{"action": "点击听写记录", "expected_result": "显示记录"}],
            "expected_result": "显示记录",
            "priority": 2,
        }
    ]
    parser = XmindAIParser()
    paths = [["字词听写", "有教材内容", "点击听写记录", "显示记录"]]
    results = parser.parse_paths(paths)

    assert len(results) == 1
    assert results[0]["module"] == "字词听写"
    assert results[0]["precondition"] == "有教材内容"
    assert results[0]["steps"][0]["action"] == "点击听写记录"
    mock_call_ai.assert_called_once()


@patch("app.services.xmind_ai_parser.XmindAIParser._call_ai")
def test_parse_paths_ai_failure_returns_empty(mock_call_ai):
    mock_call_ai.return_value = None
    parser = XmindAIParser()
    paths = [["M", "F", "R"]]
    results = parser.parse_paths(paths)
    assert results == []


@patch("app.services.xmind_ai_parser.XmindAIParser._call_ai")
def test_parse_paths_batching(mock_call_ai):
    batch1_response = [{"module": f"M{i}", "title": f"T{i}", "steps": [], "expected_result": f"R{i}", "priority": 2} for i in range(3)]
    batch2_response = [{"module": "M3", "title": "T3", "steps": [], "expected_result": "R3", "priority": 2}]
    mock_call_ai.side_effect = [batch1_response, batch2_response]

    parser = XmindAIParser(batch_size=3)
    paths = [["M", "F", f"R{i}"] for i in range(4)]
    results = parser.parse_paths(paths)

    assert len(results) == 4
    assert mock_call_ai.call_count == 2


def test_parse_paths_empty():
    parser = XmindAIParser()
    assert parser.parse_paths([]) == []
