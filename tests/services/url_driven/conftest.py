"""url_driven 站点探索单元测试共享替身与 fixture。

测试替身设计原则：
- FakeController 替换 BrowserControllerV2，避免真实浏览器启动；
- FakePage 模拟 Playwright page API（多页模拟器，goto 切换 PageData）；
- FakeLocator 模拟 page.locator(selector).aria_snapshot() / fill / click 行为；
- FakeRedis 模拟同步 redis 客户端 get/set/ping；
- 测试不联网、不连真实 Redis、不启动浏览器，保证单测稳定与确定性。

Playwright 1.58 兼容性：
- page.accessibility.snapshot 已被移除，SnapshotMixin 改用
  page.locator("body").aria_snapshot() 获取无障碍树快照（YAML 字符串）；
- FakePage.locator("body") 返回的 FakeLocator 实现 aria_snapshot() 方法，
  将 PageData.a11y dict 树经 dict_to_aria_yaml 序列化为 YAML 字符串返回，
  与生产端 _parse_aria_yaml 解析路径闭环。
"""
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, List, Optional, Set

import pytest
from sqlalchemy import inspect, text

from app.core.config import settings
from app.services.url_driven import site_explorer as site_explorer_module
from app.services.url_driven._login_mixin import _SUBMIT_SELECTORS
from app.services.url_driven.site_explorer import PageSnapshot, SiteExplorer, SiteMap


@dataclass
class PageData:
    """单页预设数据，供 FakePage.goto 切换。

    a11y 字段为 dict 树格式（与原 page.accessibility.snapshot 一致），
    FakeLocator.aria_snapshot() 会序列化为 YAML 字符串供生产端 _parse_aria_yaml 解析。
    """
    url: str
    title: str
    a11y: Dict[str, Any] = field(default_factory=dict)
    forms: List[Dict[str, Any]] = field(default_factory=list)
    nav_raw: List[Dict[str, str]] = field(default_factory=list)
    login_state: bool = False  # _detect_login_page 的 hasPassword&hasLoginButton


def dict_to_aria_yaml(tree: Optional[Dict[str, Any]], indent: int = 0) -> str:
    """将 a11y dict 树序列化为 Playwright aria_snapshot YAML 格式字符串。

    与生产端 _parse_aria_yaml 互为逆运算，供 FakeLocator.aria_snapshot() 使用。

    规则：
    - 每节点一行 `- role "name" [attrs]` 或 `- role:` (有 children)；
    - role=text 时输出 `- text: "name"`；
    - children 缩进 2 空格递归；
    - attrs 取 dict 中除 role/name/children 外的字段渲染为 [k=v k2=v2]。
    """
    if not tree:
        return ""
    lines: List[str] = []
    children = tree.get("children") or []
    for child in children:
        if not isinstance(child, dict):
            continue
        role = child.get("role") or ""
        name = child.get("name") or ""
        prefix = "  " * indent + "- "
        if role == "text":
            lines.append(f'{prefix}text: "{name}"')
            continue
        line = f"{prefix}{role}"
        if name:
            line += f' "{name}"'
        # 提取 attrs（除 role/name/children）
        attrs = {k: str(v) for k, v in child.items() if k not in ("role", "name", "children")}
        if attrs:
            attr_str = " ".join(f"{k}={v}" for k, v in attrs.items())
            line += f" [{attr_str}]"
        sub_children = child.get("children") or []
        if sub_children:
            line += ":"
            lines.append(line)
            sub_yaml = dict_to_aria_yaml(child, indent + 1)
            if sub_yaml:
                lines.append(sub_yaml)
        else:
            lines.append(line)
    return "\n".join(lines)


class FakeLocator:
    """Playwright locator 替身。

    覆盖三种使用场景：
    - LoginMixin 的 fill/click/is_visible（依 visible_selectors 判定可见性）；
    - SnapshotMixin 的 aria_snapshot（仅 selector=="body" 时返回当前页 a11y YAML）；
    - 其他 selector 的 aria_snapshot 返回空串，避免误用。
    """

    def __init__(self, page: "FakePage", selector: str, visible: bool) -> None:
        self._page = page
        self._selector = selector
        self._visible = visible
        self.filled_value: Optional[str] = None
        self.clicked = False

    @property
    def first(self) -> "FakeLocator":
        return self

    async def is_visible(self) -> bool:
        return self._visible

    async def fill(self, value: str) -> None:
        self.filled_value = value
        self._page.fill_log.append((self._selector, value))

    async def click(self) -> None:
        self.clicked = True
        self._page.click_log.append(self._selector)
        # 提交按钮点击后切换登录态（登录成功路径）；失败场景由 login_succeeds 控制
        cur = self._page._current
        if (
            self._selector in _SUBMIT_SELECTORS
            and cur is not None
            and self._page.login_succeeds
        ):
            cur.login_state = False

    async def aria_snapshot(self) -> str:
        """返回当前页 a11y dict 树序列化的 YAML 字符串。

        与生产端 page.locator("body").aria_snapshot() 等价：仅 body locator
        返回完整无障碍树；其他 selector 返回空串（FakeLocator 不模拟范围缩减）。
        """
        if self._selector != "body":
            return ""
        cur = self._page._current
        if cur is None:
            return ""
        return dict_to_aria_yaml(cur.a11y)


class FakePage:
    """Playwright page 替身，goto 切换 PageData 模拟多页探索。"""

    def __init__(
        self,
        pages_data: Dict[str, PageData],
        visible_selectors: Optional[Set[str]] = None,
        goto_errors: Optional[Set[str]] = None,
        login_succeeds: bool = True,
    ) -> None:
        self._pages_data = pages_data
        self._current: Optional[PageData] = None
        self.visible_selectors = visible_selectors or set()
        self._goto_errors = goto_errors or set()
        self.login_succeeds = login_succeeds
        self.fill_log: List[Any] = []
        self.click_log: List[str] = []
        self.goto_log: List[str] = []

    async def goto(self, url: str, **kwargs: Any) -> None:
        self.goto_log.append(url)
        if url in self._goto_errors:
            raise TimeoutError(f"goto timeout: {url}")
        page = self._pages_data.get(url)
        if page is None:
            raise RuntimeError(f"unknown url: {url}")
        self._current = page

    async def title(self) -> str:
        return self._current.title if self._current else ""

    @property
    def url(self) -> str:
        return self._current.url if self._current else ""

    async def eval_on_selector_all(self, selector: str, js: str) -> Any:
        cur = self._current
        if cur is None:
            return []
        if selector == "form":
            return cur.forms
        if selector == "a[href]":
            return cur.nav_raw
        return []

    async def evaluate(self, js: str) -> Dict[str, bool]:
        cur = self._current
        state = cur.login_state if cur is not None else False
        return {"hasPassword": state, "hasLoginButton": state}

    async def screenshot(self, type: str = "png") -> bytes:
        return b"\x89PNG\r\n\x1a\nfake-screenshot-bytes"

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector, selector in self.visible_selectors)

    async def wait_for_load_state(self, state: str = "load", timeout: int = 0) -> None:
        return None

    async def wait_for_url(self, predicate: Any, timeout: int = 0) -> None:
        return None


class FakeController:
    """BrowserControllerV2 替身，initialize/close 为 async noop。"""

    def __init__(self, config: Any = None) -> None:
        self.config = config
        self._active_page: Optional[FakePage] = None
        self.initialized = False
        self.closed = False

    @property
    def active_page(self) -> Optional[FakePage]:
        return self._active_page

    async def initialize(self) -> None:
        self.initialized = True

    async def close(self) -> None:
        self.closed = True


class FakeRedis:
    """同步 redis 客户端替身，记录 get/set/ping 调用。"""

    def __init__(self) -> None:
        self.store: Dict[str, str] = {}
        self.set_calls: List[Any] = []
        self.get_calls: List[str] = []

    def get(self, key: str) -> Optional[str]:
        self.get_calls.append(key)
        return self.store.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self.set_calls.append((key, value, ex))
        self.store[key] = value
        return True

    def ping(self) -> bool:
        return True


def make_a11y_node(
    role: str, name: str = "", children: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """构造无障碍树节点，供 _extract_interactive_elements 测试。"""
    return {"role": role, "name": name, "children": children or []}


def build_page_snapshot(url: str, navigation: List[Dict[str, str]], **kw: Any) -> PageSnapshot:
    """快速构造 PageSnapshot，用于 _discover_links 等纯函数测试。"""
    return PageSnapshot(
        url=url,
        title=kw.get("title", ""),
        elements=kw.get("elements", []),
        forms=kw.get("forms", []),
        navigation=navigation,
        is_login_page=kw.get("is_login_page", False),
        screenshot_path=kw.get("screenshot_path"),
        captured_at=kw.get("captured_at", ""),
    )


def cache_key_for(url: str) -> str:
    """复刻 site_explorer.explore 的缓存键算法，供断言。"""
    return f"sitemap:{sha256(url.encode('utf-8')).hexdigest()}"


@pytest.fixture
def patch_browser(monkeypatch):
    """替换 site_explorer.BrowserControllerV2 为 FakeController。

    返回 state dict：测试设 state["page"] = FakePage(...) 注入活动页；
    explore 后读 state["instances"] 校验是否启动浏览器（缓存命中时应为空）。
    """
    state: Dict[str, Any] = {"page": None, "instances": []}

    class _FakeController(FakeController):
        async def initialize(self) -> None:
            self._active_page = state["page"]
            self.initialized = True
            state["instances"].append(self)

    monkeypatch.setattr(site_explorer_module, "BrowserControllerV2", _FakeController)
    return state


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def explorer(monkeypatch, tmp_path) -> SiteExplorer:
    """构造 SiteExplorer 实例，UPLOAD_DIR 重定向到 tmp_path 避免污染仓库。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    return SiteExplorer()


@pytest.fixture(scope="session", autouse=True)
def ensureProjectsSourceColumn(testEngine) -> None:
    """幂等补齐 projects.source 列，保障 url_driven 测试可读写 source 字段。

    业务背景：
    - Task 4 迁移脚本 20260627_add_source_to_project 已建但用户禁止 alembic upgrade；
    - Base.metadata.create_all 不会为已存在表 ALTER 补列；
    - DatabaseSyncTool 对字符串 server_default 渲染未加引号，生成
      `DEFAULT manual` 被 MySQL 拒绝，sync_all_tables 无法自动补 source 列。
    - 此 fixture 在 url_driven 子包会话启动时直接执行迁移脚本等价的
      ALTER TABLE / CREATE INDEX，先 inspect 判断列与索引是否存在以保幂等，
      确保后续 AutoProjectBuilder 与 Phase 4 QuickLauncher 测试可用。

    边界场景：
    - 列已存在（二次运行 / 已手动 upgrade）→ 跳过 ALTER，不抛错；
    - 索引已存在 → 跳过 CREATE INDEX；
    - 其他异常向上抛出，避免静默失败。
    """
    inspector = inspect(testEngine)
    existing_columns = {col["name"] for col in inspector.get_columns("projects")}
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("projects")}
    with testEngine.connect() as conn:
        if "source" not in existing_columns:
            conn.execute(text(
                "ALTER TABLE projects ADD COLUMN source VARCHAR(64) NOT NULL "
                "DEFAULT 'manual' COMMENT '来源:manual/url_quick_test'"
            ))
        if "ix_projects_source" not in existing_indexes:
            conn.execute(text("CREATE INDEX ix_projects_source ON projects (source)"))
        conn.commit()
    yield


@pytest.fixture(scope="session", autouse=True)
def ensureTestCaseGroundingSourceColumn(testEngine) -> None:
    """幂等补齐 test_cases.grounding_source 列，保障 Task 6 用例可读写锚定来源。

    业务背景：
    - Task 6 迁移脚本 20260627_add_grounding_source_to_test_case 已建但用户禁止
      alembic upgrade，且 Base.metadata.create_all 不会为已存在表 ALTER 补列；
    - DatabaseSyncTool 仅按 model 增量同步缺失列，但环境内已禁用自动升级，
      故在此 fixture 内执行等价 ALTER TABLE / CREATE INDEX 保证幂等。
    - AutoCaseGenerator 持久化用例时写入 grounding_source="dom_snapshot"，
      缺列会致 ORM flush 报错，故必须在子包会话启动前补齐。

    边界场景：
    - 列已存在（二次运行 / 已手动 upgrade）→ 跳过 ALTER，不抛错；
    - 索引已存在 → 跳过 CREATE INDEX；
    - 其他异常向上抛出，避免静默失败。
    """
    inspector = inspect(testEngine)
    existing_columns = {col["name"] for col in inspector.get_columns("test_cases")}
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("test_cases")}
    with testEngine.connect() as conn:
        if "grounding_source" not in existing_columns:
            conn.execute(text(
                "ALTER TABLE test_cases ADD COLUMN grounding_source VARCHAR(32) "
                "NULL COMMENT '元素锚定来源: dom_snapshot/manual'"
            ))
        if "ix_test_cases_grounding_source" not in existing_indexes:
            conn.execute(text(
                "CREATE INDEX ix_test_cases_grounding_source ON test_cases (grounding_source)"
            ))
        conn.commit()
    yield


__all__ = [
    "PageData",
    "FakeLocator",
    "FakePage",
    "FakeController",
    "FakeRedis",
    "dict_to_aria_yaml",
    "make_a11y_node",
    "build_page_snapshot",
    "cache_key_for",
    "PageSnapshot",
    "SiteMap",
]
