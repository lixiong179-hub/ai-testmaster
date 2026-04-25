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
