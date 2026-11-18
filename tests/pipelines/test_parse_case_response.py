"""`_parse_case_response` 四级回退的行为锁（G-8 B1 拆分时补齐的直测）。

覆盖「原文 → fix_common_json_issues → clean_json_string → 正则截取」四条路径，
包括 G-8 拆分前后的差分验证用例。已知怪异行为以 `QUIRK` 标注：`{"title": ...}`
不含 `cases`/`test_cases` 键时返回 `[]`（历史实现中 `or []` 使 title 分支不可达），
本批为纯重构、不改变行为，故按现状锁定。
"""

from __future__ import annotations

import pytest

from app.pipelines.steps._parsing import _parse_case_response


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        # ① 原文直解析
        ("[]", []),
        ('[{"title": "a"}]', [{"title": "a"}]),
        ('{"cases": [{"title": "a"}]}', [{"title": "a"}]),
        ('{"test_cases": [{"title": "b"}, {"title": "c"}]}', [{"title": "b"}, {"title": "c"}]),
        # ② 代码围栏（含闭合/未闭合两种）
        ('```json\n[{"title": "fenced"}]\n```', [{"title": "fenced"}]),
        ('```json\n[{"title": "no-close"}]', [{"title": "no-close"}]),
        # ③ 前后缀噪声 → 正则截取兜底
        ('前缀噪声 [{"title": "with-prefix"}] 后缀', [{"title": "with-prefix"}]),
        # ④ 解析失败
        ("", None),
        ("   ", None),
        ("not json at all", None),
        ('"just a string"', None),
        ("123", None),
        # QUIRK：顶层 dict 无 cases/test_cases 键 → 空列表（非 [dict]）
        ('{"title": "solo"}', []),
        ('{"other": 1}', []),
    ],
)
def test_parse_case_response(content: str, expected: object) -> None:
    assert _parse_case_response(content) == expected


def test_parse_case_response_drops_code_fence_without_closing() -> None:
    """未闭合围栏只剥首行，剩余内容仍可解析。"""
    assert _parse_case_response('```\n[{"title": "x"}]') == [{"title": "x"}]


def test_parse_case_response_returns_none_for_unrecoverable_noise() -> None:
    assert _parse_case_response("抱歉，我无法生成用例。") is None
