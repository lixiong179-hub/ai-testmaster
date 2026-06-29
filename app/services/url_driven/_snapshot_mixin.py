"""站点探索 - 页面快照采集 Mixin。

负责调用 Playwright Accessibility Tree 采集页面 DOM 快照，提取可交互元素、
表单结构与同源导航链接，生成 Playwright locator 字符串供后续用例生成锚定，
并截图落盘作为探索证据。

Accessibility Tree 相比 DOM 解析更稳定，不依赖易变的 CSS 选择器，
是后续 AI 用例生成确定性输入的来源，禁编造不存在的元素。

Playwright 1.58 兼容性：page.accessibility 已被移除（3 年弃用期结束），
本模块改用 page.locator("body").aria_snapshot() 获取无障碍树快照，
返回值为 YAML 字符串（格式见 https://playwright.dev/python/docs/aria-snapshots），
通过自研 _parse_aria_yaml 解析为 dict 树保持下游接口稳定。
"""
import json
import re
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.url_driven.site_explorer import PageSnapshot


# 可交互角色集合：仅采集这些角色的节点作为可操作元素清单
INTERACTIVE_ROLES = {
    "button", "link", "textbox", "searchbox", "combobox",
    "checkbox", "radio", "menuitem", "tab", "treeitem",
}

# 登录按钮文本关键词：覆盖中英文常见登录按钮文案
_LOGIN_BUTTON_KEYWORDS = ("登录", "login", "sign in", "signin", "log in")

# aria_snapshot YAML 行解析正则：
#   - role "name" [key=value key2=value2]:  → 节点带 children
#   - role "name" [key=value]              → 叶子节点
#   - text: "..."                          → 文本内容叶子
# 顺序：可选 name（双引号包裹）→ 可选 [attrs] → 可选结尾冒号
_ARIA_NODE_PATTERN = re.compile(
    r'^-\s+(?P<role>[a-zA-Z][a-zA-Z0-9_-]*)'
    r'(?:\s+"(?P<name>[^"]*)")?'
    r'(?P<attrs>\s+\[[^\]]*\])?'
    r'(?P<colon>:?)\s*$'
)
_ARIA_TEXT_PATTERN = re.compile(r'^-\s+text:\s+"(?P<text>[^"]*)"\s*$')
_ARIA_ATTR_PATTERN = re.compile(r'(\w+)=([^\s\]]+)')


def _parse_aria_attrs(attr_text: Optional[str]) -> Dict[str, str]:
    """解析 aria_snapshot 行的 [key=value key2=value2] 属性段为 dict。

    输入示例：' [level=1 ref=e5]'  →  {'level': '1', 'ref': 'e5'}
    空串或 None 返回空 dict，避免 None.get 误用。
    """
    if not attr_text:
        return {}
    return {m.group(1): m.group(2) for m in _ARIA_ATTR_PATTERN.finditer(attr_text)}


def _parse_aria_yaml(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """解析 Playwright aria_snapshot() 返回的 YAML 字符串为 dict 树。

    输入格式（每行缩进 2 空格表示层级）：
        - heading "todos" [level=1]
        - textbox "What needs to be done?" [ref=e5]
        - listitem:
          - checkbox "Toggle Todo" [ref=e10]
          - text: "Buy groceries"

    输出格式（与原 page.accessibility.snapshot 兼容）：
        {"role": "root", "name": "", "children": [
            {"role": "heading", "name": "todos", "level": "1", "children": []},
            {"role": "textbox", "name": "...", "ref": "e5", "children": []},
            {"role": "listitem", "name": "", "children": [
                {"role": "checkbox", "name": "Toggle Todo", "ref": "e10", "children": []},
                {"role": "text", "name": "Buy groceries", "children": []},
            ]},
        ]}

    根节点固定为 {"role": "root", "name": "", "children": [...]}，
    保证 _extract_interactive_elements 的栈迭代起点稳定。

    边界场景：
    - 空串/None → 返回 None（上游降级为空 elements）；
    - 行无法匹配 → 跳过该行不抛错，保证部分页面可降级采集；
    - 缩进异常（跳级）→ 找不到父节点时挂回 root，不抛错。
    """
    if not text or not text.strip():
        return None
    root: Dict[str, Any] = {"role": "root", "name": "", "children": []}
    # 栈元素：(indent_level, node)，根节点 indent_level=-1 保证永远不被弹出
    stack: List[tuple] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        stripped = raw_line.lstrip()
        if stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(stripped)
        indent_level = indent // 2
        # 弹栈直到找到比当前行缩进更小的父节点
        while len(stack) > 1 and stack[-1][0] >= indent_level:
            stack.pop()
        parent = stack[-1][1]
        parent_children = parent.setdefault("children", [])

        text_match = _ARIA_TEXT_PATTERN.match(stripped)
        if text_match:
            parent_children.append({
                "role": "text",
                "name": text_match.group("text"),
                "children": [],
            })
            continue

        node_match = _ARIA_NODE_PATTERN.match(stripped)
        if not node_match:
            continue
        attrs = _parse_aria_attrs(node_match.group("attrs"))
        node: Dict[str, Any] = {
            "role": node_match.group("role"),
            "name": node_match.group("name") or "",
            "children": [],
        }
        node.update(attrs)
        parent_children.append(node)
        if node_match.group("colon") == ":":
            stack.append((indent_level, node))
    return root


class SnapshotMixin:
    """页面快照采集 Mixin。

    提供 _capture_page_snapshot 与登录页检测能力，自身不持有浏览器资源，
    page 对象由 SiteExplorer.explore 从 BrowserControllerV2 注入。
    """

    async def _capture_page_snapshot(self, page: Any) -> "PageSnapshot":
        """采集单页 DOM 快照，产出结构化 PageSnapshot。

        采集项：可交互元素（Accessibility Tree）、表单结构、同源导航链接、
        登录页判定、截图。任一采集子步骤失败仅降级为空值，不阻断整页快照。

        Playwright 1.58 兼容性：page.accessibility 已移除，改用
        page.locator("body").aria_snapshot() 获取无障碍树快照（YAML 字符串），
        经 _parse_aria_yaml 解析为 dict 树后供 _extract_interactive_elements 消费。
        """
        title = ""
        url = ""
        try:
            title = await page.title()
            url = page.url
        except Exception as e:
            logger.warning(f"采集页面基础信息失败: {e}")

        elements = await self._safe_collect_async(
            page, "无障碍树", self._collect_interactive_elements
        )
        forms = await self._safe_collect_async(page, "表单结构", self._collect_forms)
        navigation = await self._safe_collect_async(page, "导航链接", self._collect_navigation)
        is_login_page = await self._safe_collect_async(page, "登录页判定", self._detect_login_page, default=False)
        screenshot_path = await self._save_screenshot(page, url)

        from app.services.url_driven.site_explorer import PageSnapshot
        return PageSnapshot(
            url=url,
            title=title,
            elements=elements,
            forms=forms,
            navigation=navigation,
            is_login_page=is_login_page,
            screenshot_path=screenshot_path,
            captured_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _collect_interactive_elements(self, page: Any) -> List[Dict[str, Any]]:
        """采集 aria_snapshot YAML 并提取可交互元素。

        Playwright 1.58 起 page.accessibility.snapshot 被移除，本方法封装
        page.locator("body").aria_snapshot() 调用与 YAML 解析，对外提供与
        原 _extract_interactive_elements(tree) 等价的可交互元素清单。

        locator 调用或 aria_snapshot 抛错时由上游 _safe_collect_async 兜底为空列表。
        """
        body_locator = page.locator("body")
        yaml_text = await body_locator.aria_snapshot()
        tree = _parse_aria_yaml(yaml_text)
        return self._extract_interactive_elements(tree)

    async def _safe_collect_async(self, page: Any, label: str, collector: Any, default: Any = None) -> Any:
        """统一包装异步采集步骤的异常降级，失败返回 default 并记录警告。"""
        try:
            return await collector(page)
        except Exception as e:
            logger.warning(f"采集{label}失败: {e}")
            return default if default is not None else []

    def _extract_interactive_elements(self, tree: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """递归遍历无障碍树，提取 INTERACTIVE_ROLES 内的可交互元素。

        为每个元素生成 Playwright locator 字符串（优先 get_by_role），
        css_selector 留空（a11y tree 不含 DOM 选择器），元素锚定主依赖 locator。
        """
        elements: List[Dict[str, Any]] = []
        if not tree or not isinstance(tree, dict):
            return elements
        # 用栈迭代避免递归栈溢出，逆序入栈保证文档顺序稳定
        stack: List[Dict[str, Any]] = [tree]
        while stack:
            node = stack.pop()
            role = node.get("role") or ""
            name = node.get("name") or ""
            if role in INTERACTIVE_ROLES:
                elements.append({
                    "role": role,
                    "name": name,
                    "locator": self._build_locator(role, name),
                    "css_selector": "",
                })
            children = node.get("children") or []
            for child in reversed(children):
                if isinstance(child, dict):
                    stack.append(child)
        return elements

    def _build_locator(self, role: str, name: str) -> str:
        """生成 Playwright locator 字符串，优先 get_by_role(role, name=name)。

        name 为空时退化为 get_by_role(role)，避免匹配空名称导致定位漂移；
        name 内双引号转义防止字符串注入破坏 locator 语义。
        """
        safe_name = name.replace('"', '\\"')
        if safe_name:
            return f'get_by_role("{role}", name="{safe_name}")'
        return f'get_by_role("{role}")'

    async def _collect_forms(self, page: Any) -> List[Dict[str, Any]]:
        """采集页面表单结构，含表单内可交互控件清单。

        用 JS 遍历 form 元素，提取 action/method 及其内 input/button 的
        type/name/placeholder，供用例生成识别表单提交测试点。
        """
        return await page.eval_on_selector_all("form", """forms => forms.map(form => {
            const fields = Array.from(form.querySelectorAll('input, select, textarea, button')).map(el => ({
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type') || el.tagName.toLowerCase(),
                name: el.getAttribute('name') || '',
                placeholder: el.getAttribute('placeholder') || '',
                text: (el.textContent || '').trim().substring(0, 80),
            }));
            return {
                action: form.getAttribute('action') || '',
                method: (form.getAttribute('method') || 'get').toLowerCase(),
                fields: fields,
            };
        })""")

    async def _collect_navigation(self, page: Any) -> List[Dict[str, str]]:
        """采集所有带 href 的导航链接 {text, href}，供 _discover_links BFS 使用。"""
        links = await page.eval_on_selector_all("a[href]", """els => els.map(e => ({
            text: (e.textContent || '').trim().substring(0, 80),
            href: e.href || '',
        }))""")
        return [link for link in links if link.get("href")]

    async def _detect_login_page(self, page: Any) -> bool:
        """检测当前页是否为登录页：存在可见 password 输入框 + 登录按钮。

        登录按钮识别覆盖 button/input[type=submit]/a，文本含登录关键词；
        Accessibility Tree 的 textbox 角色无法区分 password 类型，改用 page JS
        检测更可靠，故本方法接收 page 而非 snapshot。
        """
        keywords_json = json.dumps(_LOGIN_BUTTON_KEYWORDS)
        result = await page.evaluate(f"""() => {{
            const passwordInputs = document.querySelectorAll('input[type="password"]');
            const hasPassword = Array.from(passwordInputs).some(el => el.offsetParent !== null);
            const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], a'));
            const keywords = {keywords_json};
            const hasLoginButton = buttons.some(el => {{
                const text = ((el.textContent || '') + ' ' + (el.value || '')).toLowerCase().trim();
                return keywords.some(kw => text.includes(kw));
            }});
            return {{ hasPassword, hasLoginButton }};
        }}""")
        return bool(result and result.get("hasPassword") and result.get("hasLoginButton"))

    async def _save_screenshot(self, page: Any, url: str) -> Optional[str]:
        """截图并保存到 site_explorer 目录，返回文件绝对路径。

        路径按 URL 哈希分桶避免单目录文件过多；截图失败仅记录警告返回 None，
        不阻断快照采集。
        """
        try:
            screenshot_bytes = await page.screenshot(type="png")
        except Exception as e:
            logger.warning(f"截图失败: {e}")
            return None
        url_hash = sha256(url.encode("utf-8")).hexdigest()[:12]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        screenshot_dir = Path(settings.UPLOAD_DIR) / "site_explorer" / url_hash
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshot_dir / f"{timestamp}.png"
        try:
            with open(screenshot_path, "wb") as f:
                f.write(screenshot_bytes)
            return str(screenshot_path)
        except OSError as e:
            logger.warning(f"保存截图失败: {e}")
            return None
