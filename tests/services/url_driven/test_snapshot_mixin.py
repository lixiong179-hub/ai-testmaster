"""SnapshotMixin 页面快照采集单元测试。

覆盖 spec 场景：
13. 登录页检测：_detect_login_page 有 password+登录按钮返回 True，无则 False
16. 元素提取：_extract_interactive_elements 只采集 INTERACTIVE_ROLES
17. locator 生成：_build_locator 含 name 用 get_by_role(role,name)，空 name 用 get_by_role(role)

Playwright 1.58 兼容性覆盖：
- _parse_aria_yaml：YAML 字符串 → dict 树解析（含嵌套、attrs、text 节点、异常降级）
- _collect_interactive_elements：page.locator("body").aria_snapshot() 闭环
"""
from typing import Any, Dict, Optional

from app.services.url_driven._snapshot_mixin import (
    INTERACTIVE_ROLES,
    SnapshotMixin,
    _parse_aria_attrs,
    _parse_aria_yaml,
)

from tests.services.url_driven.conftest import make_a11y_node


class _SnapshotTester(SnapshotMixin):
    """SnapshotMixin 独立测试宿主，仅测纯函数与 evaluate 路径。"""


class _FakeEvalPage:
    """仅实现 evaluate 的最小 page 替身，用于 _detect_login_page。"""

    def __init__(self, result: Optional[Dict[str, Any]]) -> None:
        self._result = result

    async def evaluate(self, js: str) -> Optional[Dict[str, Any]]:
        return self._result


class TestDetectLoginPage:
    """场景 13：_detect_login_page 登录页判定。"""

    def setup_method(self) -> None:
        self.m = _SnapshotTester()

    async def test_password_and_login_button_present(self) -> None:
        page = _FakeEvalPage({"hasPassword": True, "hasLoginButton": True})
        assert await self.m._detect_login_page(page) is True

    async def test_no_password_returns_false(self) -> None:
        page = _FakeEvalPage({"hasPassword": False, "hasLoginButton": True})
        assert await self.m._detect_login_page(page) is False

    async def test_no_login_button_returns_false(self) -> None:
        page = _FakeEvalPage({"hasPassword": True, "hasLoginButton": False})
        assert await self.m._detect_login_page(page) is False

    async def test_none_result_returns_false(self) -> None:
        page = _FakeEvalPage(None)
        assert await self.m._detect_login_page(page) is False


class TestExtractInteractiveElements:
    """场景 16：_extract_interactive_elements 仅采集 INTERACTIVE_ROLES。"""

    def setup_method(self) -> None:
        self.m = _SnapshotTester()

    def test_only_interactive_roles_collected(self) -> None:
        tree = make_a11y_node("root", children=[
            make_a11y_node("button", "提交"),
            make_a11y_node("link", "首页"),
            make_a11y_node("heading", "标题"),  # 非交互
            make_a11y_node("textbox", "用户名"),
        ])
        els = self.m._extract_interactive_elements(tree)
        roles = [e["role"] for e in els]
        assert roles == ["button", "link", "textbox"]
        assert all(e["css_selector"] == "" for e in els)
        assert all("locator" in e for e in els)

    def test_nested_children_traversed(self) -> None:
        tree = make_a11y_node("root", children=[
            make_a11y_node("button", "A", children=[make_a11y_node("link", "B")]),
        ])
        els = self.m._extract_interactive_elements(tree)
        assert [e["name"] for e in els] == ["A", "B"]

    def test_interactive_roles_constant(self) -> None:
        assert "button" in INTERACTIVE_ROLES
        assert "heading" not in INTERACTIVE_ROLES

    def test_empty_tree_returns_empty(self) -> None:
        assert self.m._extract_interactive_elements({}) == []

    def test_none_tree_returns_empty(self) -> None:
        assert self.m._extract_interactive_elements(None) == []

    def test_node_without_role_skipped(self) -> None:
        tree = {"name": "no-role", "children": []}
        assert self.m._extract_interactive_elements(tree) == []

    def test_node_children_non_dict_ignored(self) -> None:
        tree = make_a11y_node("button", "X", children=["not-a-dict", 42])
        els = self.m._extract_interactive_elements(tree)
        assert [e["name"] for e in els] == ["X"]


class TestBuildLocator:
    """场景 17：_build_locator locator 字符串生成。"""

    def setup_method(self) -> None:
        self.m = _SnapshotTester()

    def test_with_name(self) -> None:
        assert self.m._build_locator("button", "提交") == 'get_by_role("button", name="提交")'

    def test_empty_name_degrades_to_role_only(self) -> None:
        assert self.m._build_locator("textbox", "") == 'get_by_role("textbox")'

    def test_quote_in_name_escaped(self) -> None:
        loc = self.m._build_locator("button", 'a"b')
        assert loc == 'get_by_role("button", name="a\\"b")'

    def test_whitespace_only_name_treated_as_empty(self) -> None:
        # name="" 经 _extract_interactive_elements 取 node.get("name") or ""，
        # 空白名会进入 _build_locator 的 safe_name="" 分支
        assert self.m._build_locator("link", "") == 'get_by_role("link")'


class _ErrorBodyLocator:
    """page.locator("body") 替身，aria_snapshot 抛错覆盖 a11y 采集降级路径。"""

    async def aria_snapshot(self) -> str:
        raise RuntimeError("a11y fail")


class _ErrorPage:
    """各采集子步骤抛异常的 page 替身，覆盖 _capture_page_snapshot 降级路径。

    Playwright 1.58 兼容性：page.accessibility.snapshot 已被移除，
    SnapshotMixin 改用 page.locator("body").aria_snapshot()，
    故 _ErrorPage 改为通过 locator("body") 返回 _ErrorBodyLocator 触发异常。
    """

    def __init__(self, *, title_raise: bool = False, screenshot_raise: bool = False) -> None:
        self._title_raise = title_raise
        self._screenshot_raise = screenshot_raise
        self.url = "https://x.com/"

    def locator(self, selector: str) -> Any:
        """返回 body locator 替身触发 aria_snapshot 异常；其他 selector 不应被调用。"""
        if selector == "body":
            return _ErrorBodyLocator()
        raise RuntimeError(f"unexpected selector: {selector}")

    async def title(self) -> str:
        if self._title_raise:
            raise RuntimeError("title fail")
        return "T"

    async def eval_on_selector_all(self, selector: str, js: str) -> Any:
        raise RuntimeError("eval fail")

    async def evaluate(self, js: str) -> Optional[Dict[str, Any]]:
        raise RuntimeError("evaluate fail")

    async def screenshot(self, type: str = "png") -> bytes:
        if self._screenshot_raise:
            raise RuntimeError("shot fail")
        return b"\x89PNG\r\n\x1a\nfake"


class TestCapturePageSnapshotErrorPaths:
    """_capture_page_snapshot 各子步骤异常降级覆盖（_snapshot_mixin:52-53,78-80,86-88,187-189）。"""

    def setup_method(self) -> None:
        self.m = _SnapshotTester()

    async def test_title_failure_degrades_to_empty(
        self, monkeypatch, tmp_path
    ) -> None:
        # title() 抛异常时 url=page.url 不会执行，url 同 title 一起降级为空串
        from app.core.config import settings
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
        page = _ErrorPage(title_raise=True)
        snap = await self.m._capture_page_snapshot(page)
        assert snap.title == ""
        assert snap.url == ""

    async def test_a11y_failure_returns_empty_elements(
        self, monkeypatch, tmp_path
    ) -> None:
        from app.core.config import settings
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
        snap = await self.m._capture_page_snapshot(_ErrorPage())
        assert snap.elements == []
        assert snap.forms == []
        assert snap.navigation == []
        assert snap.is_login_page is False

    async def test_screenshot_failure_returns_none(
        self, monkeypatch, tmp_path
    ) -> None:
        from app.core.config import settings
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
        snap = await self.m._capture_page_snapshot(_ErrorPage(screenshot_raise=True))
        assert snap.screenshot_path is None


class TestSaveScreenshotOSError:
    """_save_screenshot 写盘失败降级覆盖（_snapshot_mixin:199-201）。"""

    async def test_oserror_returns_none(self, monkeypatch, tmp_path) -> None:
        import builtins

        from app.core.config import settings
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

        class _Page:
            url = "https://x.com/"

            async def screenshot(self, type: str = "png") -> bytes:
                return b"\x89PNG"

        real_open = builtins.open

        def raising_open(*args: Any, **kwargs: Any) -> Any:
            raise OSError("open fail")

        monkeypatch.setattr(builtins, "open", raising_open)
        try:
            res = await _SnapshotTester()._save_screenshot(_Page(), "https://x.com/")
        finally:
            monkeypatch.setattr(builtins, "open", real_open)
        assert res is None


class TestParseAriaAttrs:
    """_parse_aria_attrs 属性段解析覆盖。"""

    def test_none_returns_empty(self) -> None:
        assert _parse_aria_attrs(None) == {}

    def test_empty_returns_empty(self) -> None:
        assert _parse_aria_attrs("") == {}

    def test_single_attr(self) -> None:
        assert _parse_aria_attrs(" [level=1]") == {"level": "1"}

    def test_multi_attrs(self) -> None:
        attrs = _parse_aria_attrs(" [level=1 ref=e5 expanded=true]")
        assert attrs == {"level": "1", "ref": "e5", "expanded": "true"}

    def test_no_brackets_ignored(self) -> None:
        # 无 [] 包裹的片段，仅按 k=v 模式扫描
        assert _parse_aria_attrs("level=1") == {"level": "1"}


class TestParseAriaYaml:
    """_parse_aria_yaml YAML → dict 树解析覆盖。"""

    def test_none_returns_none(self) -> None:
        assert _parse_aria_yaml(None) is None

    def test_empty_returns_none(self) -> None:
        assert _parse_aria_yaml("") is None
        assert _parse_aria_yaml("   \n  \n") is None

    def test_single_leaf_node(self) -> None:
        tree = _parse_aria_yaml('- button "提交"')
        assert tree is not None
        assert tree["role"] == "root"
        children = tree["children"]
        assert len(children) == 1
        assert children[0] == {"role": "button", "name": "提交", "children": []}

    def test_node_without_name(self) -> None:
        tree = _parse_aria_yaml("- listitem:")
        assert tree is not None
        node = tree["children"][0]
        assert node["role"] == "listitem"
        assert node["name"] == ""
        assert node["children"] == []

    def test_node_with_attrs(self) -> None:
        tree = _parse_aria_yaml('- heading "todos" [level=1]')
        node = tree["children"][0]
        assert node["role"] == "heading"
        assert node["name"] == "todos"
        assert node["level"] == "1"

    def test_text_node(self) -> None:
        tree = _parse_aria_yaml('- text: "Buy groceries"')
        node = tree["children"][0]
        assert node == {"role": "text", "name": "Buy groceries", "children": []}

    def test_nested_children_indent_2(self) -> None:
        yaml_text = (
            "- listitem:\n"
            '  - checkbox "Toggle Todo" [ref=e10]\n'
            '  - text: "Buy groceries"\n'
        )
        tree = _parse_aria_yaml(yaml_text)
        assert tree is not None
        listitem = tree["children"][0]
        assert listitem["role"] == "listitem"
        assert len(listitem["children"]) == 2
        assert listitem["children"][0]["role"] == "checkbox"
        assert listitem["children"][0]["ref"] == "e10"
        assert listitem["children"][1] == {"role": "text", "name": "Buy groceries", "children": []}

    def test_multi_top_level_nodes(self) -> None:
        yaml_text = (
            '- heading "todos" [level=1]\n'
            '- textbox "What needs to be done?" [ref=e5]\n'
        )
        tree = _parse_aria_yaml(yaml_text)
        assert tree is not None
        assert len(tree["children"]) == 2
        assert tree["children"][0]["role"] == "heading"
        assert tree["children"][1]["role"] == "textbox"

    def test_unknown_line_skipped(self) -> None:
        # 非法行不匹配正则，应跳过不抛错
        yaml_text = "- button \"OK\"\n!invalid line\n- link \"Next\""
        tree = _parse_aria_yaml(yaml_text)
        assert tree is not None
        assert len(tree["children"]) == 2

    def test_comment_lines_skipped(self) -> None:
        yaml_text = "# comment\n- button \"OK\"\n  # indented comment\n- link \"Next\""
        tree = _parse_aria_yaml(yaml_text)
        assert tree is not None
        assert len(tree["children"]) == 2

    def test_deep_indent_attaches_to_nearest_parent(self) -> None:
        """子节点缩进比父深（如 4 空格而非 2），仍正确挂到栈顶父节点。

        解析器用 indent_level 比较判定父子关系，栈顶 listitem indent=0 < 子节点
        indent_level=2 不弹栈，故 button 正确挂到 listitem 下而非 root。
        覆盖 Playwright aria_snapshot 不同项目缩进风格（2/4 空格）兼容性。
        """
        yaml_text = "- listitem:\n    - button \"X\""
        tree = _parse_aria_yaml(yaml_text)
        assert tree is not None
        # 根仅 1 个 top-level 节点 listitem
        assert len(tree["children"]) == 1
        listitem = tree["children"][0]
        assert listitem["role"] == "listitem"
        # button 挂到 listitem 下
        assert len(listitem["children"]) == 1
        assert listitem["children"][0] == {
            "role": "button", "name": "X", "children": []
        }

    def test_round_trip_with_dict_to_aria_yaml(self) -> None:
        """dict_to_aria_yaml 序列化后 _parse_aria_yaml 解析应保持元素清单一致。

        覆盖生产端 _parse_aria_yaml 与测试替身 dict_to_aria_yaml 的逆运算闭环，
        保证 FakePage.locator("body").aria_snapshot() 返回的 YAML 经生产端解析
        后，可交互元素清单与原始 dict 树一致。
        """
        from tests.services.url_driven.conftest import dict_to_aria_yaml

        original = make_a11y_node("root", children=[
            make_a11y_node("button", "提交"),
            make_a11y_node("link", "首页"),
            make_a11y_node("listitem", children=[
                make_a11y_node("textbox", "用户名"),
                make_a11y_node("text", "提示文本"),
            ]),
        ])
        yaml_text = dict_to_aria_yaml(original)
        parsed = _parse_aria_yaml(yaml_text)
        assert parsed is not None

        # 验证 _extract_interactive_elements 输出一致（核心闭环）
        m = _SnapshotTester()
        original_elements = m._extract_interactive_elements(original)
        parsed_elements = m._extract_interactive_elements(parsed)
        assert original_elements == parsed_elements
        # 顺序与角色应稳定
        assert [e["role"] for e in parsed_elements] == ["button", "link", "textbox"]


class _FakeBodyPage:
    """page.locator("body").aria_snapshot() 闭环测试替身。

    持有 a11y dict 树，通过 dict_to_aria_yaml 序列化为 YAML 字符串，
    与生产端 SnapshotMixin._collect_interactive_elements 完整链路对接。
    """

    def __init__(self, a11y: Dict[str, Any]) -> None:
        self._a11y = a11y
        self.url = "https://x.com/"

    async def title(self) -> str:
        return "T"

    def locator(self, selector: str) -> Any:
        if selector != "body":
            raise RuntimeError(f"unexpected selector: {selector}")
        from tests.services.url_driven.conftest import dict_to_aria_yaml

        a11y_ref = self._a11y

        class _BoundBodyLocator:
            async def aria_snapshot(self_inner: Any) -> str:
                return dict_to_aria_yaml(a11y_ref)

        return _BoundBodyLocator()

    async def eval_on_selector_all(self, selector: str, js: str) -> Any:
        return []

    async def evaluate(self, js: str) -> Dict[str, bool]:
        return {"hasPassword": False, "hasLoginButton": False}

    async def screenshot(self, type: str = "png") -> bytes:
        return b"\x89PNG\r\n\x1a\nfake"


class TestCollectInteractiveElements:
    """_collect_interactive_elements page.locator("body").aria_snapshot() 闭环覆盖。"""

    def setup_method(self) -> None:
        self.m = _SnapshotTester()

    async def test_collect_interactive_elements_from_yaml(self, monkeypatch, tmp_path) -> None:
        """完整链路：page.locator("body").aria_snapshot() → YAML → 解析 → 提取。"""
        from app.core.config import settings
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

        a11y = make_a11y_node("root", children=[
            make_a11y_node("button", "提交"),
            make_a11y_node("heading", "标题"),  # 非交互
            make_a11y_node("textbox", "用户名"),
        ])
        page = _FakeBodyPage(a11y)
        elements = await self.m._collect_interactive_elements(page)
        assert [e["role"] for e in elements] == ["button", "textbox"]
        assert all(e["css_selector"] == "" for e in elements)
        assert all("locator" in e for e in elements)

    async def test_collect_interactive_elements_empty_a11y(
        self, monkeypatch, tmp_path
    ) -> None:
        """空 a11y 树经 YAML 序列化为空串，解析返回 None，提取返回空列表。"""
        from app.core.config import settings
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

        page = _FakeBodyPage({})  # 空 dict
        elements = await self.m._collect_interactive_elements(page)
        assert elements == []
