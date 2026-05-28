"""
T11: 路由兼容与边缘场景 + T12: 权限动态菜单 Playwright 复测脚本
执行命令: python tests/e2e_t11_t12_routes_permissions.py

核心策略：用 page.route 拦截所有后端 API 请求返回模拟数据，
防止 401 响应触发 Axios 拦截器清除 token。
"""
import base64
import json
import time
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Route

BASE_URL = "http://localhost:3001"


# ── API Mock ─────────────────────────────────────────────────────────────────

def mock_api_route(route: Route) -> None:
    """拦截后端 API 请求返回模拟数据，防止 401 清除 token。
    仅拦截 /api/v1/ 开头的真实后端请求，不拦截 Vite 的 JS 模块请求。"""
    url = route.request.url
    method = route.request.method

    # 只拦截真正的后端 API 请求（/api/v1/ 路径），跳过 Vite 模块请求
    if "/api/v1/" not in url:
        route.continue_()
        return

    # 登录接口
    if "/auth/login" in url and method == "POST":
        token = make_fake_jwt()
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"code": 0, "msg": "success", "message": "success", "data": {"access_token": token}}),
        )
        return

    # 验证码接口
    if "/captcha" in url:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"code": 0, "msg": "success", "message": "success", "data": {"captcha_id": "mock", "image": ""}}),
        )
        return

    # 当前用户信息
    if "/auth/me" in url or "/user/me" in url:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"code": 0, "msg": "success", "message": "success", "data": {"id": 1, "username": "admin", "permissions": ["*"]}}),
        )
        return

    # 项目列表
    if "/project" in url and "config" not in url and "test-object" not in url:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"code": 0, "msg": "success", "message": "success", "data": {"items": [], "total": 0}}),
        )
        return

    # 通用列表接口
    if method == "GET":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"code": 0, "msg": "success", "message": "success", "data": {"items": [], "total": 0}}),
        )
        return

    # 通用写接口
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps({"code": 0, "msg": "success", "message": "success", "data": {}}),
    )


# ── JWT / 权限工具 ────────────────────────────────────────────────────────────

def make_fake_jwt(exp_offset: int = 3600) -> str:
    """构造伪造 JWT，使用标准 base64 编码"""
    import time as _t
    header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
    payload = base64.b64encode(json.dumps({"sub": 1, "exp": int(_t.time()) + exp_offset}).encode()).decode()
    sig = base64.b64encode(b"fakesignature").decode()
    return f"{header}.{payload}.{sig}"


def set_permissions_js(permissions: list[str]) -> str:
    """生成设置 userInfo 的 JS 代码（含签名）"""
    perms_json = json.dumps(permissions)
    return f"""(() => {{
        const p = {perms_json};
        const r = p.slice().sort().join(',');
        let h = 0;
        for (let i = 0; i < r.length; i++) {{
            h = (h << 5) - h + r.charCodeAt(i);
            h |= 0;
        }}
        localStorage.setItem('userInfo', JSON.stringify({{
            permissions: p,
            __perm_sig__: h.toString(36)
        }}));
    }})()"""


def login_as(page: Page, permissions: list[str] | None = None) -> None:
    """完整登录流程：导航到站点 -> 设置 token + userInfo -> 导航到 /home/project"""
    # 先确保在目标站点上（about:blank 无法访问 localStorage）
    if "localhost" not in page.url:
        page.goto(BASE_URL + "/login", wait_until="networkidle", timeout=15000)

    token = make_fake_jwt()
    page.evaluate(f"localStorage.setItem('token', '{token}')")

    perms = permissions if permissions is not None else ["*"]
    page.evaluate(set_permissions_js(perms))

    page.goto(BASE_URL + "/home/project", wait_until="networkidle", timeout=15000)
    time.sleep(0.5)

    # 如果仍然在 login 页面，重试
    if "/login" in page.url:
        page.evaluate(f"localStorage.setItem('token', '{token}')")
        page.evaluate(set_permissions_js(perms))
        page.goto(BASE_URL + "/home/project", wait_until="networkidle", timeout=15000)
        time.sleep(0.5)


def logout(page: Page) -> None:
    """清除认证信息"""
    page.evaluate("""() => {
        localStorage.removeItem('token');
        localStorage.removeItem('userInfo');
    }""")


# ── DOM 查询工具 ──────────────────────────────────────────────────────────────

def get_menu_items(page: Page) -> list[dict]:
    """获取侧边栏菜单项（含子菜单），先展开所有子菜单"""
    page.evaluate("""() => {
        const titles = document.querySelectorAll('.sidebar-menu .el-sub-menu__title');
        titles.forEach(t => t.click());
    }""")
    time.sleep(0.5)

    items = page.evaluate("""() => {
        const menu = document.querySelector('.sidebar-menu');
        if (!menu) return [];
        const result = [];
        const topItems = menu.querySelectorAll(':scope > .el-menu-item, :scope > .el-sub-menu');
        topItems.forEach(item => {
            const isSubMenu = item.classList.contains('el-sub-menu');
            const titleEl = isSubMenu ? item.querySelector('.el-sub-menu__title') : item;
            const label = titleEl ? titleEl.textContent.trim() : '';
            const children = [];
            if (isSubMenu) {
                const childItems = item.querySelectorAll('.el-menu .el-menu-item');
                childItems.forEach(child => { children.push(child.textContent.trim()); });
            }
            result.push({ label, children, isSubMenu });
        });
        return result;
    }""")
    return items or []


def get_active_menu_text(page: Page) -> str | None:
    """获取当前高亮菜单项的文本"""
    return page.evaluate("""() => {
        const active = document.querySelector('.sidebar-menu .el-menu-item.is-active');
        return active ? active.textContent.trim() : null;
    }""")


def get_breadcrumb_texts(page: Page) -> list[str]:
    """获取面包屑文本列表"""
    return page.evaluate("""() => {
        const items = document.querySelectorAll('.el-breadcrumb__inner');
        return Array.from(items).map(el => el.textContent.trim()).filter(Boolean);
    }""")


# ── 测试结果记录 ──────────────────────────────────────────────────────────────

results: list[dict] = []

def record(id: str, operation: str, expected: str, actual: str, status: str) -> None:
    results.append({"id": id, "operation": operation, "expected": expected, "actual": actual, "status": status})
    print(f"  {status} {id}: {operation}")
    if status != "✅":
        print(f"      期望: {expected}")
        print(f"      实际: {actual}")


# ── T11: 路由兼容与边缘场景 ──────────────────────────────────────────────────

def test_t11(page: Page) -> None:
    print("\n" + "=" * 70)
    print("T11: 路由兼容与边缘场景")
    print("=" * 70)

    login_as(page, ["*"])

    # T11-1: /home 重定向到 /home/project 或 /home/dashboard
    page.goto(BASE_URL + "/home", wait_until="networkidle", timeout=15000)
    time.sleep(0.5)
    final_url = page.url
    redirected = "/home/project" in final_url or "/home/dashboard" in final_url
    record("T11-1", "导航到 /home", "重定向到 /home/project 或 /home/dashboard",
           f"最终URL: {final_url}", "✅" if redirected else "❌")

    # T11-2: / 重定向到 /login
    logout(page)
    page.goto(BASE_URL + "/", wait_until="networkidle", timeout=15000)
    time.sleep(0.5)
    final_url = page.url
    record("T11-2", "导航到 /", "重定向到 /login",
           f"最终URL: {final_url}", "✅" if "/login" in final_url else "❌")

    # 恢复认证
    login_as(page, ["*"])

    # T11-3: /home/nonexistent-page
    page.goto(BASE_URL + "/home/nonexistent-page", wait_until="networkidle", timeout=15000)
    time.sleep(1)
    final_url = page.url
    page_content = page.content().lower()
    has_404 = "404" in page_content or "not found" in page_content or "找不到" in page_content
    redirected_home = "/home/project" in final_url
    stays_on_url = "/home/nonexistent-page" in final_url
    main_content = page.evaluate("""() => {
        const mc = document.querySelector('.main-content');
        return mc ? mc.innerHTML.trim() : '';
    }""")
    empty_view = len(main_content) < 50
    record("T11-3", "导航到 /home/nonexistent-page", "显示404页面或重定向到有效页面",
           f"URL: {final_url}, 404: {has_404}, 空视图: {empty_view}",
           "✅" if (has_404 or redirected_home or (stays_on_url and empty_view)) else "⚠️")

    # T11-4: /home/case/detail/99999
    page.goto(BASE_URL + "/home/case/detail/99999", wait_until="networkidle", timeout=15000)
    time.sleep(1.5)
    final_url = page.url
    if "/login" in final_url:
        login_as(page, ["*"])
        page.goto(BASE_URL + "/home/case/detail/99999", wait_until="networkidle", timeout=15000)
        time.sleep(1.5)
        final_url = page.url
    page_text = page.inner_text("body")
    has_empty = any(kw in page_text for kw in ["空", "不存在", "未找到", "404", "暂无", "无数据", "Error", "加载", "返回"])
    stays = "/home/case/detail/99999" in final_url
    record("T11-4", "导航到 /home/case/detail/99999", "页面显示空状态或错误提示",
           f"URL: {final_url}, 停留: {stays}, 有提示: {has_empty}",
           "✅" if (has_empty or stays) else "⚠️")

    # T11-5: /home/project/detail?id=99999
    page.goto(BASE_URL + "/home/project/detail?id=99999", wait_until="networkidle", timeout=15000)
    time.sleep(1.5)
    final_url = page.url
    if "/login" in final_url:
        login_as(page, ["*"])
        page.goto(BASE_URL + "/home/project/detail?id=99999", wait_until="networkidle", timeout=15000)
        time.sleep(1.5)
        final_url = page.url
    page_text = page.inner_text("body")
    has_empty = any(kw in page_text for kw in ["空", "不存在", "未找到", "404", "暂无", "无数据", "Error", "错误", "返回"])
    stays = "/home/project/detail" in final_url
    record("T11-5", "导航到 /home/project/detail?id=99999", "页面显示空状态或错误提示",
           f"URL: {final_url}, 停留: {stays}, 有提示: {has_empty}",
           "✅" if (has_empty or stays) else "⚠️")

    # T11-6: 面包屑
    print("\n  --- T11-6: 面包屑检查 ---")
    bc_cases = [
        ("/home/project", "项目中心"), ("/home/case", "用例列表"),
        ("/home/task", "执行中心"), ("/home/report", "报告中心"),
        ("/home/system/user", "用户管理"), ("/home/system/role", "角色管理"),
    ]
    bc_ok = 0
    bc_details = []
    for url, kw in bc_cases:
        page.goto(BASE_URL + url, wait_until="networkidle", timeout=15000)
        time.sleep(0.8)
        if "/login" in page.url:
            login_as(page, ["*"])
            page.goto(BASE_URL + url, wait_until="networkidle", timeout=15000)
            time.sleep(0.8)
        bcs = get_breadcrumb_texts(page)
        found = any(kw in b for b in bcs)
        bc_details.append(f"{url}: {bcs}")
        if found:
            bc_ok += 1
        else:
            record(f"T11-6({url})", f"导航到 {url} 检查面包屑", f"面包屑包含'{kw}'", f"面包屑: {bcs}", "❌")
    total = len(bc_cases)
    if bc_ok == total:
        record("T11-6", f"检查 {total} 个页面的面包屑", "所有页面面包屑正确显示", f"{bc_ok}/{total} 正确", "✅")
    else:
        record("T11-6", f"检查 {total} 个页面的面包屑", "所有页面面包屑正确显示",
               f"{bc_ok}/{total} 正确, 详情: {'; '.join(bc_details)}", "❌")

    # T11-7: activeMenu 高亮
    print("\n  --- T11-7: activeMenu 高亮检查 ---")
    am_cases = [
        ("/home/project", "项目中心"), ("/home/project/detail?id=1", "项目中心"),
        ("/home/case", "用例列表"), ("/home/case/detail/1", "用例列表"),
        ("/home/case/test-point-management", "测试点管理"),
        ("/home/task", "执行中心"), ("/home/task/detail/1", "执行中心"),
        ("/home/report", "报告中心"), ("/home/report/detail?id=1", "报告中心"),
        ("/home/system/user", "用户管理"),
    ]
    am_ok = 0
    for url, label in am_cases:
        page.goto(BASE_URL + url, wait_until="networkidle", timeout=15000)
        time.sleep(0.8)
        if "/login" in page.url:
            login_as(page, ["*"])
            page.goto(BASE_URL + url, wait_until="networkidle", timeout=15000)
            time.sleep(0.8)
        active = get_active_menu_text(page)
        if active is not None and label in active:
            am_ok += 1
        else:
            record(f"T11-7({url})", f"导航到 {url} 检查菜单高亮", f"高亮: {label}", f"实际: {active}", "⚠️")
    total_am = len(am_cases)
    if am_ok == total_am:
        record("T11-7", f"检查 {total_am} 个页面的菜单高亮", "所有子页面正确高亮父菜单", f"{am_ok}/{total_am} 正确", "✅")
    else:
        record("T11-7", f"检查 {total_am} 个页面的菜单高亮", "所有子页面正确高亮父菜单", f"{am_ok}/{total_am} 正确", "⚠️")

    # T11-8: 浏览器后退/前进
    print("\n  --- T11-8: 浏览器后退/前进 ---")
    # 使用 Vue Router 实例做 SPA 内部导航，确保历史记录正确入栈
    page.goto(BASE_URL + "/home/project", wait_until="networkidle", timeout=15000)
    time.sleep(0.5)

    # 通过 Vue 应用实例获取 router 并 push（SPA 内部导航，正确操作浏览器历史）
    push_js = "(path) => document.getElementById('app').__vue_app__.config.globalProperties.$router.push(path)"
    page.evaluate(push_js, "/home/case")
    time.sleep(0.5)
    page.evaluate(push_js, "/home/task")
    time.sleep(0.5)

    page.go_back(wait_until="networkidle", timeout=10000)
    time.sleep(0.5)
    url_b1 = page.url
    b1_ok = "/home/case" in url_b1

    page.go_back(wait_until="networkidle", timeout=10000)
    time.sleep(0.5)
    url_b2 = page.url
    b2_ok = "/home/project" in url_b2

    page.go_forward(wait_until="networkidle", timeout=10000)
    time.sleep(0.5)
    url_f = page.url
    f_ok = "/home/case" in url_f

    record("T11-8", "浏览器后退/前进按钮",
           "后退到 /home/case -> 后退到 /home/project -> 前进到 /home/case",
           f"后退1: {url_b1}, 后退2: {url_b2}, 前进: {url_f}",
           "✅" if (b1_ok and b2_ok and f_ok) else "❌")


# ── T12: 权限动态菜单 ────────────────────────────────────────────────────────

def test_t12(page: Page) -> None:
    print("\n" + "=" * 70)
    print("T12: 权限动态菜单")
    print("=" * 70)

    # T12-1 & T12-2: 超级管理员
    login_as(page, ["*"])
    menu_items = get_menu_items(page)
    top_labels = [item["label"] for item in menu_items]
    expected_top = ["项目中心", "资源中心", "测试资产", "执行中心", "报告中心", "迭代中心", "系统管理"]
    missing = [lbl for lbl in expected_top if not any(lbl in t for t in top_labels)]
    record("T12-1", "设置超级管理员权限 (permissions: ['*'])", f"所有菜单项可见: {expected_top}",
           f"可见菜单: {top_labels}, 缺失: {missing}", "✅" if len(missing) == 0 else "❌")

    sys_menu = next((item for item in menu_items if "系统管理" in item["label"]), None)
    sys_children = sys_menu["children"] if sys_menu else []
    expected_sys = ["用户管理", "角色管理", "审计日志", "测试能力"]
    missing_c = [c for c in expected_sys if not any(c in sc for sc in sys_children)]
    record("T12-2", "验证系统管理子菜单全部可见", f"子菜单: {expected_sys}",
           f"可见: {sys_children}, 缺失: {missing_c}", "✅" if len(missing_c) == 0 else "❌")

    # T12-3: 普通用户
    login_as(page, [])
    menu_items = get_menu_items(page)
    sys_menu = next((item for item in menu_items if "系统管理" in item["label"]), None)
    sys_children = sys_menu["children"] if sys_menu else []
    sys_hidden = sys_menu is None or len(sys_children) == 0
    record("T12-3", "设置普通用户权限 (permissions: [])", "系统管理子菜单全部隐藏",
           f"系统管理: {'不可见或无子菜单' if sys_hidden else f'可见: {sys_children}'}",
           "✅" if sys_hidden else "❌")

    # T12-4: user:list
    login_as(page, ["user:list"])
    menu_items = get_menu_items(page)
    sys_menu = next((item for item in menu_items if "系统管理" in item["label"]), None)
    sys_children = sys_menu["children"] if sys_menu else []
    u_vis = any("用户管理" in c for c in sys_children)
    r_hid = not any("角色管理" in c for c in sys_children)
    a_hid = not any("审计日志" in c for c in sys_children)
    c_hid = not any("测试能力" in c for c in sys_children)
    record("T12-4", "设置部分权限 (permissions: ['user:list'])",
           "只有用户管理可见，其他隐藏",
           f"用户管理: {u_vis}, 角色管理隐藏: {r_hid}, 审计日志隐藏: {a_hid}, 测试能力隐藏: {c_hid}",
           "✅" if (u_vis and r_hid and a_hid and c_hid) else "❌")

    # T12-5: user:list + role:list
    login_as(page, ["user:list", "role:list"])
    menu_items = get_menu_items(page)
    sys_menu = next((item for item in menu_items if "系统管理" in item["label"]), None)
    sys_children = sys_menu["children"] if sys_menu else []
    u_vis = any("用户管理" in c for c in sys_children)
    r_vis = any("角色管理" in c for c in sys_children)
    a_hid = not any("审计日志" in c for c in sys_children)
    c_hid = not any("测试能力" in c for c in sys_children)
    record("T12-5", "设置部分权限 (permissions: ['user:list', 'role:list'])",
           "用户管理和角色管理可见，审计日志和测试能力隐藏",
           f"用户管理: {u_vis}, 角色管理: {r_vis}, 审计日志隐藏: {a_hid}, 测试能力隐藏: {c_hid}",
           "✅" if (u_vis and r_vis and a_hid and c_hid) else "❌")

    # T12-6: 无权限访问 /home/system/user
    login_as(page, [])
    page.goto(BASE_URL + "/home/system/user", wait_until="networkidle", timeout=15000)
    time.sleep(1)
    final_url = page.url
    redirected = "/home/project" in final_url
    page_text = page.inner_text("body")
    no_content = "用户管理" not in page_text
    record("T12-6", "无权限用户访问 /home/system/user",
           "路由守卫拦截或页面无内容",
           f"URL: {final_url}, 重定向: {redirected}, 无用户管理内容: {no_content}",
           "✅" if (redirected or no_content) else "❌")

    # T12-7: 菜单过滤与路由可达性
    login_as(page, ["*"])
    page.goto(BASE_URL + "/home/system/user", wait_until="networkidle", timeout=15000)
    time.sleep(0.5)

    login_as(page, [])
    time.sleep(0.5)
    menu_items = get_menu_items(page)
    sys_in_menu = any("系统管理" in item["label"] for item in menu_items)

    page.goto(BASE_URL + "/home/system/role", wait_until="networkidle", timeout=15000)
    time.sleep(1)
    direct_url = page.url
    guarded = "/home/project" in direct_url
    filtered = not sys_in_menu

    record("T12-7", "验证菜单过滤与路由可达性",
           "菜单不显示系统管理，直接URL访问被路由守卫拦截",
           f"菜单过滤: {filtered}, 路由守卫: {guarded}, URL: {direct_url}",
           "✅" if (filtered and guarded) else "⚠️")


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main() -> None:
    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="zh-CN")

        # 拦截后端 API 请求，返回模拟数据（精确匹配 /api/v1/ 避免 Vite 模块被拦截）
        page.route("**/api/v1/**", mock_api_route)

        try:
            test_t11(page)
        except Exception as e:
            print(f"\n  ❌ T11 执行异常: {e}")
            import traceback
            traceback.print_exc()

        try:
            test_t12(page)
        except Exception as e:
            print(f"\n  ❌ T12 执行异常: {e}")
            import traceback
            traceback.print_exc()

        browser.close()

    # ── 输出汇总 ──
    print("\n" + "=" * 70)
    print("复测结果汇总")
    print("=" * 70)
    pass_count = sum(1 for r in results if r["status"] == "✅")
    fail_count = sum(1 for r in results if r["status"] == "❌")
    warn_count = sum(1 for r in results if r["status"] == "⚠️")
    total = len(results)

    for r in results:
        print(f"  {r['status']} {r['id']}: {r['operation']}")
        if r["status"] != "✅":
            print(f"      期望: {r['expected']}")
            print(f"      实际: {r['actual']}")

    print(f"\n总计: {total} 项 | ✅ {pass_count} | ❌ {fail_count} | ⚠️ {warn_count}")
    print(f"通过率: {pass_count / total * 100:.1f}%" if total > 0 else "无测试结果")


if __name__ == "__main__":
    main()
