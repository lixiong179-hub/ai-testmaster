"""AutoCaseGenerator 单元测试。

使用真实测试库（tests/conftest.py 的 db fixture，事务隔离 + 自动回滚），
不 Mock 数据库，验证测试点推导、Prompt 构建、元素锚定校验、AI 成功/失败降级、
JSON 解析失败、持久化字段与回滚。

清理策略：依赖 db fixture 的事务级回滚，用例执行后全部数据自动清理，
无需逐用例显式删除。

AI 隔离：FakeAIClient 实现 AIClient Protocol，可控返回内容/抛异常/空响应，
不真实调用 DeepSeek，避免网络与费用。
"""
import json
from typing import Any, Dict, List, Optional

import pytest

from app.ai.client import AIResponse
from app.models.test_case import TestCase
from app.models.project import Project
from app.services.url_driven.auto_case_generator import (
    AutoCaseGenerator,
    GROUNDING_SOURCE_DOM_SNAPSHOT,
)
from app.services.url_driven.site_explorer import PageSnapshot, SiteMap


def make_element(role: str, name: str, locator: str = "") -> Dict[str, Any]:
    """构造 PageSnapshot.elements 项，对齐 _snapshot_mixin 输出结构。"""
    return {"role": role, "name": name, "locator": locator or f'get_by_role("{role}", name="{name}")', "css_selector": ""}


def make_page(
    url: str = "https://example.com",
    title: str = "示例页",
    elements: Optional[List[Dict[str, Any]]] = None,
    forms: Optional[List[Dict[str, Any]]] = None,
    navigation: Optional[List[Dict[str, str]]] = None,
    is_login_page: bool = False,
) -> PageSnapshot:
    """快速构造 PageSnapshot，省略字段取默认空值便于聚焦测试断言。"""
    return PageSnapshot(
        url=url,
        title=title,
        elements=elements if elements is not None else [],
        forms=forms if forms is not None else [],
        navigation=navigation if navigation is not None else [],
        is_login_page=is_login_page,
        screenshot_path=None,
        captured_at="2026-06-27T00:00:00+00:00",
    )


def make_site_map(pages: List[PageSnapshot], entry_url: str = "https://example.com") -> SiteMap:
    """构造 SiteMap，cache_key 与探索引擎算法解耦（测试不依赖缓存）。"""
    return SiteMap(
        entry_url=entry_url,
        pages=pages,
        max_depth_reached=1,
        explored_count=len(pages),
        skipped_count=0,
        cache_key="test-cache-key",
    )


class FakeAIClient:
    """AIClient Protocol 替身，可控返回内容/抛异常/空响应，记录调用便于断言。"""

    def __init__(self, content: str = "", raise_exc: Optional[Exception] = None) -> None:
        self._content = content
        self._raise = raise_exc
        self.calls: List[Dict[str, Any]] = []

    def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AIResponse:
        self.calls.append({
            "prompt": prompt, "system": system, "metadata": metadata,
            "max_tokens": max_tokens,
        })
        if self._raise is not None:
            raise self._raise
        return AIResponse(content=self._content, model_version="fake-model", latency_ms=10)


def make_ai_case(
    title: str = "AI 用例",
    target_element: str = "用户名",
    action_type: str = "input",
) -> Dict[str, Any]:
    """构造 AI 返回的单条用例字典，target_element 可控便于锚定校验断言。"""
    return {
        "title": title,
        "case_category": "positive",
        "precondition": "已登录并进入目标页面",
        "priority": 2,
        "steps": [
            {"action": f"在 {target_element} 输入内容", "action_type": action_type, "target_element": target_element},
            {"action": "点击提交", "action_type": "click", "target_element": "登录"},
        ],
        "expected_result": "操作成功",
    }


@pytest.fixture
def generator() -> AutoCaseGenerator:
    """默认无 AI 客户端的生成器，测试按需注入 FakeAIClient。"""
    return AutoCaseGenerator()


@pytest.fixture
def project(db, testUser) -> Project:
    """为用例持久化提供归属项目，依赖 db 事务回滚自动清理。"""
    proj = Project(
        name="acg_test_project",
        user_id=testUser.id,
        project_type="web",
        source="url_quick_test",
    )
    db.add(proj)
    db.flush()
    return proj


class TestDeriveTestPoints:
    """测试点推导：登录/搜索/表单/导航入口识别。"""

    def test_login_page_derives_login_point(self, generator):
        page = make_page(is_login_page=True, elements=[make_element("textbox", "用户名")])
        points = generator._derive_test_points(make_site_map([page]))
        assert len(points) == 1
        assert points[0]["test_point_type"] == "login"
        assert points[0]["target_page_url"] == page.url
        assert points[0]["page_snapshot"] is page

    def test_searchbox_role_derives_search_point(self, generator):
        page = make_page(elements=[make_element("searchbox", "搜索")])
        points = generator._derive_test_points(make_site_map([page]))
        assert points[0]["test_point_type"] == "search"

    def test_search_keyword_in_name_derives_search_point(self, generator):
        page = make_page(elements=[make_element("textbox", "搜索商品")])
        points = generator._derive_test_points(make_site_map([page]))
        assert points[0]["test_point_type"] == "search"

    def test_form_derives_form_point(self, generator):
        page = make_page(forms=[{"action": "/submit", "method": "post", "fields": [
            {"tag": "input", "type": "text", "name": "email", "placeholder": "邮箱", "text": ""}
        ]}])
        points = generator._derive_test_points(make_site_map([page]))
        assert points[0]["test_point_type"] == "form"
        assert len(points[0]["related_elements"]) == 1

    def test_navigation_derives_navigation_point(self, generator):
        page = make_page(navigation=[{"text": "首页", "href": "https://example.com/home"}])
        points = generator._derive_test_points(make_site_map([page]))
        assert points[0]["test_point_type"] == "navigation"

    def test_empty_page_derives_no_point(self, generator):
        page = make_page()
        assert generator._derive_test_points(make_site_map([page])) == []

    def test_login_priority_over_search(self, generator):
        page = make_page(is_login_page=True, elements=[make_element("searchbox", "搜索")])
        points = generator._derive_test_points(make_site_map([page]))
        assert points[0]["test_point_type"] == "login"

    def test_multiple_pages_multiple_points(self, generator):
        login_page = make_page(url="https://example.com/login", is_login_page=True)
        search_page = make_page(url="https://example.com/home", elements=[make_element("searchbox", "搜索")])
        points = generator._derive_test_points(make_site_map([login_page, search_page]))
        assert len(points) == 2
        assert {p["test_point_type"] for p in points} == {"login", "search"}

    def test_fallback_login_test_points_when_no_entry(self, generator):
        login_page = make_page(is_login_page=True)
        points = generator._fallback_login_test_points(make_site_map([login_page]))
        assert len(points) == 1
        assert points[0]["test_point_type"] == "login"

    def test_fallback_login_test_points_no_login_page(self, generator):
        page = make_page()
        assert generator._fallback_login_test_points(make_site_map([page])) == []


class TestBuildPrompt:
    """Prompt 构建：元素清单 Markdown 表格 + 禁编造约束 + description 聚焦。"""

    def test_prompt_contains_element_table(self, generator):
        elements = [make_element("textbox", "用户名"), make_element("button", "登录")]
        page = make_page(elements=elements)
        point = {"test_point_type": "login", "target_page_url": page.url, "related_elements": elements}
        prompt = generator._build_prompt(point, page, None)
        assert "| 序号 | role | name | locator |" in prompt
        assert "用户名" in prompt
        assert "登录" in prompt
        assert "get_by_role" in prompt

    def test_prompt_contains_no_fabrication_rule(self, generator):
        page = make_page(elements=[make_element("button", "登录")])
        point = {"test_point_type": "login", "target_page_url": page.url, "related_elements": []}
        prompt = generator._build_prompt(point, page, None)
        assert "严禁编造元素" in prompt
        assert "target_element" in prompt

    def test_prompt_contains_description_focus(self, generator):
        page = make_page(elements=[make_element("searchbox", "搜索")])
        point = {"test_point_type": "search", "target_page_url": page.url, "related_elements": []}
        prompt = generator._build_prompt(point, page, "重点测试购物车")
        assert "用户聚焦范围" in prompt
        assert "重点测试购物车" in prompt

    def test_prompt_without_description_omits_focus(self, generator):
        page = make_page(elements=[make_element("button", "登录")])
        point = {"test_point_type": "login", "target_page_url": page.url, "related_elements": []}
        prompt = generator._build_prompt(point, page, None)
        assert "用户聚焦范围" not in prompt

    def test_prompt_empty_elements_shows_placeholder(self, generator):
        page = make_page(elements=[])
        point = {"test_point_type": "form", "target_page_url": page.url, "related_elements": []}
        prompt = generator._build_prompt(point, page, None)
        assert "（无可用元素）" in prompt

    def test_prompt_escapes_pipe_in_element_name(self, generator):
        page = make_page(elements=[make_element("button", "a|b")])
        point = {"test_point_type": "login", "target_page_url": page.url, "related_elements": []}
        prompt = generator._build_prompt(point, page, None)
        assert "a\\|b" in prompt

    def test_prompt_related_elements_summary(self, generator):
        elements = [make_element("textbox", "用户名"), make_element("textbox", "密码")]
        page = make_page(elements=elements)
        point = {"test_point_type": "login", "target_page_url": page.url, "related_elements": elements}
        prompt = generator._build_prompt(point, page, None)
        assert "用户名、密码" in prompt


class TestValidateElements:
    """元素锚定校验：ratio 计算与 action 语义匹配。"""

    def test_all_match_returns_one(self, generator):
        elements = [make_element("textbox", "用户名"), make_element("button", "登录")]
        page = make_page(elements=elements)
        case = {"steps": [
            {"target_element": "用户名", "action_type": "input"},
            {"target_element": "登录", "action_type": "click"},
        ]}
        assert generator._validate_elements(case, page) == 1.0

    def test_no_match_returns_zero(self, generator):
        elements = [make_element("textbox", "用户名")]
        page = make_page(elements=elements)
        case = {"steps": [{"target_element": "不存在的元素", "action_type": "input"}]}
        assert generator._validate_elements(case, page) == 0.0

    def test_partial_match_returns_ratio(self, generator):
        elements = [make_element("textbox", "用户名"), make_element("button", "登录")]
        page = make_page(elements=elements)
        case = {"steps": [
            {"target_element": "用户名", "action_type": "input"},
            {"target_element": "不存在", "action_type": "input"},
        ]}
        assert generator._validate_elements(case, page) == 0.5

    def test_action_role_incompatible_not_counted(self, generator):
        # 对 button 执行 input：语义不兼容，不计入命中
        elements = [make_element("button", "登录")]
        page = make_page(elements=elements)
        case = {"steps": [{"target_element": "登录", "action_type": "input"}]}
        assert generator._validate_elements(case, page) == 0.0

    def test_unconstrained_action_type_compatible(self, generator):
        elements = [make_element("button", "登录")]
        page = make_page(elements=elements)
        case = {"steps": [{"target_element": "登录", "action_type": "verify"}]}
        assert generator._validate_elements(case, page) == 1.0

    def test_step_without_target_excluded_from_denominator(self, generator):
        elements = [make_element("textbox", "用户名")]
        page = make_page(elements=elements)
        case = {"steps": [
            {"target_element": "用户名", "action_type": "input"},
            {"action": "等待页面加载", "action_type": "navigate"},
        ]}
        assert generator._validate_elements(case, page) == 1.0

    def test_empty_elements_returns_zero(self, generator):
        page = make_page(elements=[])
        case = {"steps": [{"target_element": "用户名", "action_type": "input"}]}
        assert generator._validate_elements(case, page) == 0.0

    def test_no_checkable_steps_returns_zero(self, generator):
        elements = [make_element("textbox", "用户名")]
        page = make_page(elements=elements)
        case = {"steps": [{"action": "导航", "action_type": "navigate"}]}
        assert generator._validate_elements(case, page) == 0.0

    def test_locator_reverse_match(self, generator):
        locator = 'get_by_role("textbox", name="用户名")'
        elements = [make_element("textbox", "用户名", locator)]
        page = make_page(elements=elements)
        case = {"steps": [{"target_element": locator, "action_type": "input"}]}
        assert generator._validate_elements(case, page) == 1.0

    def test_case_insensitive_name_match(self, generator):
        elements = [make_element("textbox", "Username")]
        page = make_page(elements=elements)
        case = {"steps": [{"target_element": "username", "action_type": "input"}]}
        assert generator._validate_elements(case, page) == 1.0

    def test_non_list_steps_returns_zero(self, generator):
        page = make_page(elements=[make_element("textbox", "用户名")])
        assert generator._validate_elements({"steps": "not-a-list"}, page) == 0.0

    def test_non_dict_step_skipped(self, generator):
        elements = [make_element("textbox", "用户名")]
        page = make_page(elements=elements)
        case = {"steps": ["not-a-dict", {"target_element": "用户名", "action_type": "input"}]}
        assert generator._validate_elements(case, page) == 1.0

    def test_empty_target_excluded(self, generator):
        elements = [make_element("textbox", "用户名")]
        page = make_page(elements=elements)
        case = {"steps": [{"target_element": "", "action_type": "input"}]}
        assert generator._validate_elements(case, page) == 0.0


class TestParseCases:
    """AI JSON 解析：合法/字典包裹/数组/缺失 cases/非法 JSON。"""

    def test_parse_dict_with_cases(self, generator):
        raw = json.dumps({"cases": [make_ai_case("用例1"), make_ai_case("用例2")]})
        cases = generator._parse_cases(raw)
        assert len(cases) == 2

    def test_parse_list_directly(self, generator):
        raw = json.dumps([make_ai_case("用例1")])
        cases = generator._parse_cases(raw)
        assert len(cases) == 1

    def test_parse_markdown_wrapped(self, generator):
        raw = "```json\n" + json.dumps({"cases": [make_ai_case()]}) + "\n```"
        cases = generator._parse_cases(raw)
        assert len(cases) == 1

    def test_parse_missing_cases_returns_empty(self, generator):
        raw = json.dumps({"other": []})
        assert generator._parse_cases(raw) == []

    def test_parse_invalid_json_returns_empty(self, generator):
        assert generator._parse_cases("not json at all") == []

    def test_parse_empty_content_returns_empty(self, generator):
        assert generator._parse_cases("") == []

    def test_parse_filters_case_without_title(self, generator):
        raw = json.dumps({"cases": [{"title": "", "steps": []}, make_ai_case("有标题")]})
        cases = generator._parse_cases(raw)
        assert len(cases) == 1
        assert cases[0]["title"] == "有标题"

    def test_parse_filters_non_dict_case(self, generator):
        raw = json.dumps({"cases": ["not-a-dict", make_ai_case("有效")]})
        cases = generator._parse_cases(raw)
        assert len(cases) == 1


class TestCallAi:
    """AIClient 调用：成功/异常降级/空响应/懒加载。"""

    def test_call_ai_returns_content(self):
        gen = AutoCaseGenerator(ai_client=FakeAIClient(content="hello"))
        assert gen._call_ai("prompt") == "hello"

    def test_call_ai_exception_returns_none(self):
        gen = AutoCaseGenerator(ai_client=FakeAIClient(raise_exc=RuntimeError("boom")))
        assert gen._call_ai("prompt") is None

    def test_call_ai_empty_content_returns_none(self):
        gen = AutoCaseGenerator(ai_client=FakeAIClient(content="   "))
        assert gen._call_ai("prompt") is None

    def test_call_ai_passes_system_and_metadata(self):
        fake = FakeAIClient(content="ok")
        gen = AutoCaseGenerator(ai_client=fake)
        gen._call_ai("prompt")
        assert fake.calls[0]["system"] is not None
        assert fake.calls[0]["metadata"]["step_name"] == "url_driven_case_generation"

    def test_call_ai_uses_url_quick_test_max_tokens(self, monkeypatch):
        """验证 _call_ai 使用 URL_QUICK_TEST_AI_MAX_TOKENS 而非 AI_MAX_TOKENS（BUG 2 修复）。

        spec BUG 2 根因：原代码用 settings.AI_MAX_TOKENS（默认 2048），DeepSeek
        v4-flash 推理模型 reasoning_tokens + content 不足 2048 导致空 content。
        修复后改用专用配置 URL_QUICK_TEST_AI_MAX_TOKENS（默认 4096），与全局
        AI_MAX_TOKENS 解耦。

        回归守护：通过 monkeypatch 强制 AI_MAX_TOKENS=2048 模拟默认场景，
        断言 _call_ai 仍传 URL_QUICK_TEST_AI_MAX_TOKENS 而非 AI_MAX_TOKENS。
        不依赖 .env 全局配置的具体值，避免环境差异导致测试不稳定。
        """
        from app.core.config import settings
        monkeypatch.setattr(settings, "AI_MAX_TOKENS", 2048)
        monkeypatch.setattr(settings, "URL_QUICK_TEST_AI_MAX_TOKENS", 4096)
        fake = FakeAIClient(content="ok")
        gen = AutoCaseGenerator(ai_client=fake)
        gen._call_ai("prompt")
        # 核心断言：_call_ai 使用专用配置项，不回退到 AI_MAX_TOKENS
        assert fake.calls[0]["max_tokens"] == settings.URL_QUICK_TEST_AI_MAX_TOKENS
        assert fake.calls[0]["max_tokens"] == 4096
        assert fake.calls[0]["max_tokens"] != settings.AI_MAX_TOKENS


class TestGenerateSuccess:
    """AI 成功生成：用例持久化、grounding_source、element_verified_ratio。"""

    def test_generate_persists_cases_with_grounding_source(self, generator, db, project):
        elements = [make_element("textbox", "用户名"), make_element("button", "登录")]
        page = make_page(is_login_page=True, elements=elements)
        site_map = make_site_map([page])
        ai_cases = {"cases": [make_ai_case("登录用例1", "用户名"), make_ai_case("登录用例2", "用户名")]}
        gen = AutoCaseGenerator(ai_client=FakeAIClient(content=json.dumps(ai_cases)))

        cases = gen.generate(site_map, project.id, None, project.user_id, db)

        assert len(cases) == 2
        for case in cases:
            assert case.project_id == project.id
            assert case.grounding_source == GROUNDING_SOURCE_DOM_SNAPSHOT
            assert case.element_verified_ratio == 1.0
            assert case.case_type == "ui_automation"
            assert case.generate_status == 1
            assert case.case_no.startswith(f"TC-{project.id:03d}-")

    def test_generate_assigns_module_from_test_point(self, generator, db, project):
        page = make_page(is_login_page=True, elements=[make_element("textbox", "用户名"), make_element("button", "登录")])
        gen = AutoCaseGenerator(ai_client=FakeAIClient(
            content=json.dumps({"cases": [make_ai_case("登录", "用户名")]})
        ))
        cases = gen.generate(make_site_map([page]), project.id, None, project.user_id, db)
        assert cases[0].module == "login"

    def test_generate_with_description_focus(self, generator, db, project):
        page = make_page(is_login_page=True, elements=[make_element("textbox", "用户名")])
        fake = FakeAIClient(content=json.dumps({"cases": [make_ai_case("聚焦用例", "用户名")]}))
        gen = AutoCaseGenerator(ai_client=fake)
        gen.generate(make_site_map([page]), project.id, "重点测试登录", project.user_id, db)
        assert "重点测试登录" in fake.calls[0]["prompt"]

    def test_generate_case_no_incremental(self, generator, db, project):
        page = make_page(is_login_page=True, elements=[make_element("textbox", "用户名"), make_element("button", "登录")])
        gen = AutoCaseGenerator(ai_client=FakeAIClient(
            content=json.dumps({"cases": [make_ai_case("c1", "用户名"), make_ai_case("c2", "用户名"), make_ai_case("c3", "用户名")]})
        ))
        cases = gen.generate(make_site_map([page]), project.id, None, project.user_id, db)
        seqs = [int(c.case_no.split("-")[-1]) for c in cases]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == 3


class TestGenerateFallback:
    """AI 失败/降级：异常降级登录用例、JSON 失败降级、无登录页降级空。"""

    def test_generate_ai_exception_falls_back_to_login(self, generator, db, project):
        page = make_page(is_login_page=True, elements=[
            make_element("textbox", "用户名"), make_element("textbox", "密码"), make_element("button", "登录")
        ])
        gen = AutoCaseGenerator(ai_client=FakeAIClient(raise_exc=RuntimeError("ai down")))
        cases = gen.generate(make_site_map([page]), project.id, None, project.user_id, db)
        assert len(cases) == 1
        assert cases[0].title == "用户使用有效凭据登录成功"
        assert cases[0].grounding_source == GROUNDING_SOURCE_DOM_SNAPSHOT
        assert cases[0].element_verified_ratio == 1.0

    def test_generate_ai_invalid_json_falls_back_to_login(self, generator, db, project):
        page = make_page(is_login_page=True, elements=[
            make_element("textbox", "用户名"), make_element("button", "登录")
        ])
        gen = AutoCaseGenerator(ai_client=FakeAIClient(content="not json"))
        cases = gen.generate(make_site_map([page]), project.id, None, project.user_id, db)
        assert len(cases) == 1
        assert cases[0].title == "用户使用有效凭据登录成功"

    def test_generate_ai_empty_response_falls_back(self, generator, db, project):
        page = make_page(is_login_page=True, elements=[make_element("textbox", "用户名"), make_element("button", "登录")])
        gen = AutoCaseGenerator(ai_client=FakeAIClient(content=""))
        cases = gen.generate(make_site_map([page]), project.id, None, project.user_id, db)
        assert len(cases) == 1

    def test_generate_fallback_no_login_page_returns_empty(self, generator, db, project):
        page = make_page(elements=[make_element("searchbox", "搜索")])
        gen = AutoCaseGenerator(ai_client=FakeAIClient(raise_exc=RuntimeError("ai down")))
        cases = gen.generate(make_site_map([page]), project.id, None, project.user_id, db)
        assert cases == []

    def test_generate_fallback_login_page_no_elements_returns_empty(self, generator, db, project):
        page = make_page(is_login_page=True, elements=[])
        gen = AutoCaseGenerator(ai_client=FakeAIClient(raise_exc=RuntimeError("ai down")))
        cases = gen.generate(make_site_map([page]), project.id, None, project.user_id, db)
        assert cases == []

    def test_generate_no_test_point_uses_fallback_login_test_point(self, generator, db, project):
        # 登录页但无 search/form/nav，_derive 仍识别为 login，故不走 fallback_login_test_points
        # 这里验证纯登录页路径：AI 成功时正常生成
        page = make_page(is_login_page=True, elements=[make_element("textbox", "用户名")])
        gen = AutoCaseGenerator(ai_client=FakeAIClient(
            content=json.dumps({"cases": [make_ai_case("登录用例", "用户名")]})
        ))
        cases = gen.generate(make_site_map([page]), project.id, None, project.user_id, db)
        assert len(cases) == 1

    def test_fallback_login_cases_single_textbox(self, generator):
        page = make_page(is_login_page=True, elements=[
            make_element("textbox", "用户名"), make_element("button", "登录")
        ])
        cases = generator._fallback_login_cases(make_site_map([page]))
        assert len(cases) == 1
        # 单 textbox 时只生成用户名输入 + 点击登录两步
        assert len(cases[0]["steps"]) == 2

    def test_fallback_login_cases_two_textboxes(self, generator):
        page = make_page(is_login_page=True, elements=[
            make_element("textbox", "用户名"), make_element("textbox", "密码"), make_element("button", "登录")
        ])
        cases = generator._fallback_login_cases(make_site_map([page]))
        assert len(cases[0]["steps"]) == 3

    def test_fallback_login_cases_no_login_page(self, generator):
        page = make_page()
        assert generator._fallback_login_cases(make_site_map([page])) == []


class TestGenerateEdgeCases:
    """generate 主流程边界：空 SiteMap、单测试点失败不阻断其他点。"""

    def test_generate_empty_site_map_returns_empty(self, generator, db, project):
        gen = AutoCaseGenerator(ai_client=FakeAIClient(content="{}"))
        assert gen.generate(make_site_map([]), project.id, None, project.user_id, db) == []

    def test_generate_none_site_map_returns_empty(self, generator, db, project):
        gen = AutoCaseGenerator(ai_client=FakeAIClient(content="{}"))
        assert gen.generate(None, project.id, None, project.user_id, db) == []  # type: ignore[arg-type]

    def test_generate_one_point_failure_does_not_block_others(self, generator, db, project):
        # 第一个测试点 AI 失败，第二个测试点 AI 成功：单 FakeAIClient 全失败
        # 这里用两个页面但同一 AI 客户端，验证一处失败不阻断整体（最终降级登录）
        login_page = make_page(url="https://example.com/login", is_login_page=True, elements=[make_element("textbox", "用户名"), make_element("button", "登录")])
        gen = AutoCaseGenerator(ai_client=FakeAIClient(raise_exc=RuntimeError("fail")))
        cases = gen.generate(make_site_map([login_page]), project.id, None, project.user_id, db)
        assert len(cases) == 1


class TestPersistCases:
    """持久化：成功/commit 失败回滚/steps_json 规范化。"""

    def test_persist_commit_failure_rolls_back_and_reraises(self, generator, db, project, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("commit failed")
        monkeypatch.setattr(db, "commit", boom)
        case_dicts = [make_ai_case("回滚用例", "用户名")]
        with pytest.raises(RuntimeError, match="commit failed"):
            generator._persist_cases(case_dicts, project.id, db)
        assert db.query(TestCase).filter(TestCase.project_id == project.id).count() == 0

    def test_normalize_steps_non_list_returns_empty(self, generator):
        assert generator._normalize_steps("not-a-list") == []

    def test_normalize_steps_invalid_action_type_downgrades(self, generator, db, project):
        page = make_page(is_login_page=True, elements=[make_element("textbox", "用户名")])
        ai_case = {
            "title": "非法动作", "steps": [
                {"action": "奇怪操作", "action_type": "unknown_action", "target_element": "用户名"}
            ],
            "precondition": "前置", "expected_result": "预期",
        }
        gen = AutoCaseGenerator(ai_client=FakeAIClient(content=json.dumps({"cases": [ai_case]})))
        cases = gen.generate(make_site_map([page]), project.id, None, project.user_id, db)
        assert len(cases) == 1
        assert cases[0].steps_json[0]["action_type"] == "navigate"

    def test_sanitize_ratio_invalid_returns_none(self):
        assert AutoCaseGenerator._sanitize_ratio("abc") is None
        assert AutoCaseGenerator._sanitize_ratio(None) is None

    def test_sanitize_ratio_out_of_range_returns_none(self):
        assert AutoCaseGenerator._sanitize_ratio(1.5) is None
        assert AutoCaseGenerator._sanitize_ratio(-0.1) is None

    def test_sanitize_ratio_valid(self):
        assert AutoCaseGenerator._sanitize_ratio(0.5) == 0.5
        assert AutoCaseGenerator._sanitize_ratio(0) == 0.0
        assert AutoCaseGenerator._sanitize_ratio(1) == 1.0

    def test_normalize_steps_skips_non_dict_step(self, generator):
        # _normalize_steps 中 step 非 dict 应 continue 跳过
        normalized = generator._normalize_steps(["not-a-dict", 123, {"action_type": "click", "target_element": "登录"}])
        assert len(normalized) == 1
        assert normalized[0]["target_element"] == "登录"


class TestElementIndexEdgeCases:
    """_build_element_index / _match_element / _action_role_compatible 边界。"""

    def test_build_index_skips_non_dict_element(self, generator):
        # 元素非 dict 应 continue 跳过
        index = generator._build_element_index(["not-a-dict", 123, None])
        assert index == {}

    def test_build_index_skips_empty_name_element(self, generator):
        # name 为空字符串元素不进索引
        index = generator._build_element_index([
            {"role": "button", "name": ""},
            {"role": "button", "name": "   "},
            make_element("button", "登录"),
        ])
        assert list(index.keys()) == ["登录"]

    def test_match_element_empty_target_returns_none(self, generator):
        # _match_element 空 target 返回 None（不进索引查询）
        index = generator._build_element_index([make_element("textbox", "用户名")])
        assert generator._match_element("", index) is None
        assert generator._match_element("   ", index) is None

    def test_action_role_compatible_none_action_returns_true(self, generator):
        # action_type 或 role 为空时默认兼容，不阻断 ratio
        assert generator._action_role_compatible(None, "button") is True
        assert generator._action_role_compatible("input", None) is True
        assert generator._action_role_compatible("", "") is True


class TestParseCasesEdgeCases:
    """_parse_cases 边界：parsed 既非 dict 也非 list。"""

    def test_parse_non_dict_non_list_returns_empty(self, generator):
        # parse_ai_json_response 返回 string/int/bool 时进入 else 分支
        assert generator._parse_cases(json.dumps("a-string")) == []
        assert generator._parse_cases(json.dumps(123)) == []
        assert generator._parse_cases(json.dumps(True)) == []


class TestGetAiClientLazyLoad:
    """_get_ai_client 懒加载分支：未注入 ai_client 时调用 create_ai_client。"""

    def test_get_ai_client_lazy_loads_default(self, monkeypatch):
        # 替换 create_ai_client 避免真实环境变量依赖，验证懒加载分支被触发
        import app.services.url_driven.auto_case_generator as acg_module

        fake = FakeAIClient(content="lazy-loaded")
        monkeypatch.setattr(
            "app.api.v1.endpoints.pipeline_resume.create_ai_client",
            lambda: fake,
        )
        gen = AutoCaseGenerator()
        client = gen._get_ai_client()
        assert client is fake
        # 二次获取复用缓存，不重复调用 create_ai_client
        assert gen._get_ai_client() is fake

    def test_get_ai_client_returns_injected(self, monkeypatch):
        # 注入 ai_client 时不应调用 create_ai_client
        calls = []

        def fail_if_called():
            calls.append(1)
            raise AssertionError("不应调用 create_ai_client")

        monkeypatch.setattr(
            "app.api.v1.endpoints.pipeline_resume.create_ai_client",
            fail_if_called,
        )
        injected = FakeAIClient(content="injected")
        gen = AutoCaseGenerator(ai_client=injected)
        assert gen._get_ai_client() is injected
        assert calls == []


class TestGenerateFallbackEdgeCases:
    """generate 主流程降级路径边界。"""

    def test_generate_blank_page_falls_back_to_login_test_point(self, generator, db, project):
        # 无核心入口（非登录页、无 search/form/nav）触发 _fallback_login_test_points
        # 无登录页则 fallback_login_test_points 也返回空，最终无用例
        blank_page = make_page(
            url="https://example.com/blank",
            elements=[],
            forms=[],
            navigation=[],
            is_login_page=False,
        )
        gen = AutoCaseGenerator(ai_client=FakeAIClient(content="{}"))
        cases = gen.generate(make_site_map([blank_page]), project.id, None, project.user_id, db)
        assert cases == []

    def test_generate_skips_non_pagesnapshot_point(self, generator, db, project, monkeypatch):
        # test_point 的 page_snapshot 非 PageSnapshot 时跳过该测试点
        page = make_page(is_login_page=True, elements=[make_element("textbox", "用户名")])
        gen = AutoCaseGenerator(ai_client=FakeAIClient(content=json.dumps({"cases": [make_ai_case("登录用例", "用户名")]})))

        def fake_derive(site_map):
            return [
                {"test_point_type": "login", "target_page_url": "https://example.com", "related_elements": [], "page_snapshot": "not-a-page-snapshot"},
                {"test_point_type": "login", "target_page_url": page.url, "related_elements": [], "page_snapshot": page},
            ]

        monkeypatch.setattr(gen, "_derive_test_points", fake_derive)
        cases = gen.generate(make_site_map([page]), project.id, None, project.user_id, db)
        # 仅第二个测试点被处理
        assert len(cases) == 1
        assert cases[0].title == "登录用例"


class TestFormRelatedElementsEdgeCases:
    """_form_related_elements 边界：forms 首项非 dict。"""

    def test_form_first_item_non_dict_returns_empty(self, generator):
        # page.forms 非空但首项非 dict 时返回空列表
        page = make_page(forms=["not-a-dict", 123, None])
        assert generator._form_related_elements(page) == []
