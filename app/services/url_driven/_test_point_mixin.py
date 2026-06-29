"""网址驱动快速测试 - 测试点推导 Mixin。

从 PageSnapshot 元素识别核心入口测试点（登录/搜索/表单/导航），为 AI 用例
生成提供聚焦的测试点上下文。识别规则对齐 spec ADDED Requirements：
- 登录入口：is_login_page=True 的页面；
- 搜索入口：含 searchbox 角色或 name 含"搜索/search"等关键词的元素；
- 表单入口：forms 非空的页面；
- 导航入口：navigation 链接非空的页面。

设计要点：单文件聚焦测试点推导与元素归类，与 Prompt 构建/锚定校验/生成主
流程解耦，便于随识别规则演进独立调整与单测。
"""
from typing import Any, Dict, List, Optional

from app.services.url_driven.site_explorer import PageSnapshot, SiteMap

# 测试点类型枚举值，与 AutoCaseGenerator 主流程及 module 字段保持一致
_TEST_POINT_LOGIN = "login"
_TEST_POINT_SEARCH = "search"
_TEST_POINT_FORM = "form"
_TEST_POINT_NAVIGATION = "navigation"
# 搜索元素识别关键词（中英文），用于 name 含搜索语义的可交互元素
_SEARCH_KEYWORDS = ("搜索", "search", "查询", "find")


class TestPointMixin:
    """测试点推导 Mixin。

    提供 _derive_test_points 从 SiteMap 识别核心入口，自身不持有状态，
    依赖宿主传入 SiteMap。识别常量集中在本模块，便于统一调优。
    """

    def _derive_test_points(self, site_map: SiteMap) -> List[Dict[str, Any]]:
        """从 PageSnapshot 元素识别核心入口测试点。

        每页至多产生一个测试点（按 登录→搜索→表单→导航 优先级取首个命中类型），
        避免单页重复生成；无任何命中的页面跳过。

        Returns:
            测试点字典列表，每项含 test_point_type/target_page_url/
            related_elements/page_snapshot（page_snapshot 供主流程回查元素）。
        """
        points: List[Dict[str, Any]] = []
        for page in site_map.pages:
            point = self._derive_page_test_point(page)
            if point is not None:
                points.append(point)
        return points

    def _derive_page_test_point(self, page: PageSnapshot) -> Optional[Dict[str, Any]]:
        """识别单页首个核心入口类型，返回测试点字典或 None。"""
        if page.is_login_page:
            return self._make_test_point(_TEST_POINT_LOGIN, page, self._login_related_elements(page))
        search_elements = self._search_elements(page)
        if search_elements:
            return self._make_test_point(_TEST_POINT_SEARCH, page, search_elements)
        if page.forms:
            return self._make_test_point(_TEST_POINT_FORM, page, self._form_related_elements(page))
        if page.navigation:
            return self._make_test_point(
                _TEST_POINT_NAVIGATION, page, self._navigation_related_elements(page)
            )
        return None

    def _fallback_login_test_points(self, site_map: SiteMap) -> List[Dict[str, Any]]:
        """无核心入口时构造登录测试点（若有登录页），保证至少一条降级路径。

        用于 generate 主流程在 _derive_test_points 返回空但站点含登录页时，
        仍能进入 AI 生成流程；登录页缺元素时由 _fallback_login_cases 兜底。
        """
        login_page = next((p for p in site_map.pages if p.is_login_page), None)
        if login_page is None:
            return []
        return [
            self._make_test_point(_TEST_POINT_LOGIN, login_page, self._login_related_elements(login_page))
        ]

    @staticmethod
    def _make_test_point(
        point_type: str, page: PageSnapshot, related_elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """构造测试点字典，page_snapshot 字段供主流程回查页面元素做锚定校验。"""
        return {
            "test_point_type": point_type,
            "target_page_url": page.url,
            "related_elements": related_elements,
            "page_snapshot": page,
        }

    @staticmethod
    def _login_related_elements(page: PageSnapshot) -> List[Dict[str, Any]]:
        """登录页相关元素：textbox + button（用户名/密码/登录按钮）。"""
        return [
            element for element in page.elements
            if element.get("role") in ("textbox", "button")
        ]

    @staticmethod
    def _search_elements(page: PageSnapshot) -> List[Dict[str, Any]]:
        """识别搜索元素：searchbox 角色或 name 含搜索关键词的可交互元素。"""
        matched: List[Dict[str, Any]] = []
        for element in page.elements:
            role = str(element.get("role", "")).lower()
            name = str(element.get("name", "")).lower()
            if role == "searchbox" or any(kw in name for kw in _SEARCH_KEYWORDS):
                matched.append(element)
        return matched

    @staticmethod
    def _form_related_elements(page: PageSnapshot) -> List[Dict[str, Any]]:
        """表单相关元素：取首个 form 的可交互字段（前 5 个）作为相关元素提示。"""
        if not page.forms or not isinstance(page.forms[0], dict):
            return []
        fields = page.forms[0].get("fields") or []
        return [
            {
                "role": "textbox",
                "name": field.get("name") or field.get("placeholder") or field.get("text", ""),
            }
            for field in fields[:5]
            if isinstance(field, dict)
        ]

    @staticmethod
    def _navigation_related_elements(page: PageSnapshot) -> List[Dict[str, Any]]:
        """导航相关元素：取前 5 个导航链接作为相关元素提示。"""
        return [
            {"role": "link", "name": nav.get("text", ""), "locator": ""}
            for nav in page.navigation[:5] if isinstance(nav, dict)
        ]
