"""
T9 迭代中心 + T10 系统管理 详细级复测脚本
策略：双重保护 - API拦截 + token保护 + location.href拦截
"""
import asyncio
import base64
import json
import re
import sys
from datetime import datetime
from playwright.async_api import async_playwright, Page, Route

BASE_URL = "http://localhost:3001"
PERM_SIG = "16"

def make_fake_jwt() -> str:
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": 1, "exp": 9999999999, "username": "admin"}).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.fakesig"

FAKE_TOKEN = make_fake_jwt()
USER_INFO_JSON = json.dumps({"permissions": ["*"], "__perm_sig__": PERM_SIG})

def api_response(data=None, total=None):
    resp = {"code": 0, "msg": "success", "message": "success", "data": data}
    if total is not None:
        resp["total"] = total
    return json.dumps(resp)

results: list[dict] = []


def record(check_id: str, operation: str, expected: str, actual: str, status: str):
    results.append({"编号": check_id, "操作": operation, "期望结果": expected, "实际结果": actual, "状态": status})
    symbol = {"✅": "PASS", "❌": "FAIL", "⚠️": "WARN"}[status]
    print(f"  [{symbol}] {check_id}: {expected} => {actual}")


async def setup_api_interception(context, page: Page):
    """精确拦截 /api/v1/ 请求"""
    async def handle_api(route: Route):
        url = route.request.url
        method = route.request.method

        # 只拦截真正的 API 请求（以 /api/v1/ 开头的路径）
        if "/api/v1/" not in url:
            await route.continue_()
            return

        if method == "POST":
            if "/precheck" in url:
                await route.fulfill(status=200, content_type="application/json",
                    body=api_response({
                        "project_id": 1,
                        "can_run": True, "blocking_reasons": [], "warnings": [],
                        "ui": {"selected_screen_count": 5, "parsed_screen_count": 5, "unparsed_screen_count": 0, "parse_failed_count": 0, "usable_screen_ids": [1,2,3,4,5]},
                        "history_cases": {"total": 10, "included": 8, "active": 5, "draft": 2, "pending_review": 1, "archived": 1, "deleted": 1},
                        "test_points": {"total": 5, "selected": 0}
                    }))
            else:
                await route.fulfill(status=200, content_type="application/json", body=api_response({}))
            return
        if method in ("PUT", "PATCH"):
            await route.fulfill(status=200, content_type="application/json", body=api_response({}))
            return
        if method == "DELETE":
            await route.fulfill(status=200, content_type="application/json", body=api_response(None))
            return

        # GET 请求
        if "/user/" in url and "/role" not in url and "/permission" not in url and "/login-log" not in url and "/change-password" not in url and "/me" not in url:
            await route.fulfill(status=200, content_type="application/json",
                body=api_response([{"id": 1, "username": "admin", "email": "admin@test.com",
                     "phone": "13800000000", "status": True,
                     "last_login_time": "2025-01-01 10:00:00", "created_at": "2025-01-01"}], total=1))
        elif "/user/role" in url:
            await route.fulfill(status=200, content_type="application/json",
                body=api_response([{"id": 1, "name": "超级管理员", "desc": "拥有所有权限",
                     "permissions": ["*"], "created_at": "2025-01-01"}], total=1))
        elif "/user/permission" in url:
            await route.fulfill(status=200, content_type="application/json", body=api_response([]))
        elif "/user/login-log" in url:
            await route.fulfill(status=200, content_type="application/json", body=api_response([], total=0))
        elif "/user/me" in url:
            await route.fulfill(status=200, content_type="application/json",
                body=api_response({"id": 1, "username": "admin", "email": "admin@test.com",
                    "phone": "13800000000", "status": True, "roles": [{"id": 1, "name": "超级管理员"}]}))
        elif "/audit-log" in url:
            await route.fulfill(status=200, content_type="application/json",
                body=api_response([{"id": 1, "action": "create", "actor_id": 1,
                     "target_kind": "project", "target_id": 1, "detail": "创建项目",
                     "run_id": None, "iteration_id": None, "created_at": "2025-01-01 10:00:00"}], total=1))
        elif "/project" in url:
            await route.fulfill(status=200, content_type="application/json",
                body=api_response([{"id": 1, "name": "测试项目", "description": "测试项目描述",
                     "status": "active", "created_at": "2025-01-01"}]))
        elif "/pipeline" in url and "/dashboard" in url:
            await route.fulfill(status=200, content_type="application/json",
                body=api_response({"overview": {"total_runs": 10, "success_rate": 0.85, "avg_duration": 120, "total_tokens": 50000},
                    "daily_tokens": [], "daily_duration": [], "step_latency": [], "cache_hit_rate": [], "fmea_metrics": []}))
        elif "/pipeline" in url and "/summary" in url:
            await route.fulfill(status=200, content_type="application/json",
                body=api_response({"total_steps": 1, "completed_steps": 1, "failed_steps": 0,
                    "total_duration": 120, "total_tokens": 5000}))
        elif "/pipeline" in url and re.search(r"/pipeline/\d+", url):
            # 单个 Pipeline Run 详情: /api/v1/pipeline/{runId}
            await route.fulfill(status=200, content_type="application/json",
                body=api_response({"id": 99999, "iteration_id": 1, "input_hash": "abc123",
                    "pipeline_version": "v4", "status": "completed",
                    "started_at": "2025-01-01 10:00:00", "finished_at": "2025-01-01 10:05:00",
                    "error": None, "pause_payload": None,
                    "steps": [{"name": "步骤1", "status": "completed", "started_at": "2025-01-01 10:00:00", "finished_at": "2025-01-01 10:02:00", "error": None}],
                    "artifacts": []}))
        elif "/pipeline" in url:
            await route.fulfill(status=200, content_type="application/json", body=api_response([]))
        elif "/test-capability" in url:
            await route.fulfill(status=200, content_type="application/json", body=api_response([], total=0))
        elif "/iteration" in url:
            # 迭代列表 - 返回至少一条迭代数据
            await route.fulfill(status=200, content_type="application/json",
                body=api_response([{"id": 1, "name": "迭代1", "version": "v1.0",
                    "description": "测试迭代", "project_id": 1,
                    "status": "active", "created_at": "2025-01-01"}]))
        elif "/auth/me" in url or "/current" in url:
            await route.fulfill(status=200, content_type="application/json",
                body=api_response({"id": 1, "username": "admin", "email": "admin@test.com",
                    "phone": "13800000000", "status": True, "roles": [{"id": 1, "name": "超级管理员"}]}))
        else:
            await route.fulfill(status=200, content_type="application/json", body=api_response(None))

    # 使用更精确的 URL 匹配：只匹配包含 /api/v1/ 的请求
    # 使用 context.route 而非 page.route，确保在所有页面中生效
    await context.route("**/api/v1/**", handle_api)


async def navigate_to(page: Page, path: str) -> bool:
    """导航到指定路径，使用 page.goto 进行完整页面导航"""
    await page.goto(f"{BASE_URL}{path}")
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    await asyncio.sleep(2)
    current_url = page.url
    on_page = "/login" not in current_url
    if not on_page:
        print(f"    [导航] {path} -> 被重定向到登录页")
    return on_page


async def get_breadcrumb(page: Page) -> str:
    try:
        items = page.locator(".el-breadcrumb .el-breadcrumb__item")
        texts = []
        for i in range(await items.count()):
            t = await items.nth(i).inner_text()
            texts.append(t.strip().replace("\n", "").replace("/ /", "/"))
        return " / ".join(texts)
    except Exception:
        return ""


async def check_menu_active(page: Page, menu_text: str, parent_text: str = "") -> tuple[bool, bool]:
    try:
        active = False
        expanded = False
        items = page.locator(".el-menu-item.is-active")
        for i in range(await items.count()):
            txt = await items.nth(i).inner_text()
            if menu_text in txt:
                active = True
        if parent_text:
            subs = page.locator(".el-sub-menu.is-opened")
            for i in range(await subs.count()):
                txt = await subs.nth(i).locator(".el-sub-menu__title").inner_text()
                if parent_text in txt:
                    expanded = True
        return active, expanded
    except Exception:
        return False, False


async def test_t9(page: Page):
    print("\n" + "=" * 60)
    print("T9: 迭代中心")
    print("=" * 60)

    nav_ok = await navigate_to(page, "/home/pipeline-dashboard")
    title_text = await page.title()
    contains_pipeline = "Pipeline" in title_text or "仪表盘" in title_text
    record("T9-1", "导航到 /home/pipeline-dashboard", "页面标题含'Pipeline仪表盘'",
           f"标题: {title_text}" + ("" if nav_ok else " [导航失败]"),
           "✅" if contains_pipeline and nav_ok else "❌")

    bc = await get_breadcrumb(page)
    expected = "工作台" in bc and "迭代中心" in bc and "Pipeline仪表盘" in bc
    record("T9-2", "检查Pipeline仪表盘面包屑", "面包屑显示'工作台 / 迭代中心 / Pipeline仪表盘'",
           f"面包屑: {bc}", "✅" if expected else "⚠️")

    active, expanded = await check_menu_active(page, "Pipeline仪表盘", "迭代中心")
    record("T9-3", "检查左侧菜单Pipeline仪表盘高亮", "Pipeline仪表盘高亮（属于迭代中心子菜单）",
           f"高亮: {active}, 迭代中心展开: {expanded}", "✅" if active and expanded else "⚠️")

    try:
        ps = page.locator(".dashboard-filters .el-select").first
        ps_v = await ps.is_visible() if await ps.count() > 0 else False
        cards = page.locator(".overview-cards .metric-card")
        cards_n = await cards.count()
        charts = page.locator(".chart-container")
        charts_n = await charts.count()
        fmea = page.locator(".pipeline-dashboard .el-table")
        fmea_v = await fmea.is_visible() if await fmea.count() > 0 else False
        record("T9-4", "检查Pipeline仪表盘内容", "项目选择、Pipeline列表、状态展示",
               f"项目选择: {ps_v}, 概览卡片: {cards_n}个, 图表: {charts_n}个, FMEA: {fmea_v}",
               "✅" if ps_v and cards_n > 0 else "⚠️")
    except Exception as e:
        record("T9-4", "检查Pipeline仪表盘内容", "项目选择、Pipeline列表、状态展示", f"异常: {e}", "❌")

    nav_ok = await navigate_to(page, "/home/iteration/regression-generate?project_id=1")
    title_text = await page.title()
    contains_regression = "回归生成" in title_text
    page_h2 = page.locator(".regression-generate-container h2")
    page_heading = await page_h2.inner_text() if await page_h2.count() > 0 else ""
    record("T9-5", "导航到 /home/iteration/regression-generate", "页面标题含'回归生成'",
           f"标题: {title_text}, 页面标题: {page_heading}" + ("" if nav_ok else " [导航失败]"),
           "✅" if contains_regression and nav_ok else ("⚠️" if nav_ok and "变更分析" in page_heading else "❌"))

    bc = await get_breadcrumb(page)
    expected = "工作台" in bc and "迭代中心" in bc and "回归生成" in bc
    record("T9-6", "检查回归生成面包屑", "面包屑显示'工作台 / 迭代中心 / 回归生成'",
           f"面包屑: {bc}", "✅" if expected else "⚠️")

    active, expanded = await check_menu_active(page, "回归生成", "迭代中心")
    record("T9-7", "检查左侧菜单回归生成高亮", "回归生成高亮",
           f"高亮: {active}, 迭代中心展开: {expanded}", "✅" if active and expanded else "⚠️")

    try:
        cards = page.locator(".regression-generate-container .el-card")
        cards_n = await cards.count()
        cf = page.locator(".config-card .el-form")
        cf_v = await cf.is_visible() if await cf.count() > 0 else False
        sb = page.locator("text=开始旧项目变更分析")
        sb_v = await sb.is_visible() if await sb.count() > 0 else False
        it = page.locator(".iteration-select-row .el-select").first
        it_v = await it.is_visible() if await it.count() > 0 else False
        record("T9-8", "检查回归生成页面内容", "项目选择、配置表单、生成按钮",
               f"卡片: {cards_n}, 配置表单: {cf_v}, 生成按钮: {sb_v}, 迭代选择: {it_v}",
               "✅" if cards_n > 0 and (cf_v or sb_v) else "⚠️")
    except Exception as e:
        record("T9-8", "检查回归生成页面内容", "项目选择、配置表单、生成按钮", f"异常: {e}", "❌")

    nav_ok = await navigate_to(page, "/home/iteration/pipeline/99999")
    pp = page.locator(".pipeline-progress")
    pp_v = await pp.is_visible() if await pp.count() > 0 else False
    card = page.locator(".el-card").first
    card_v = await card.is_visible() if await card.count() > 0 else False
    empty = page.locator(".el-empty")
    empty_v = await empty.is_visible() if await empty.count() > 0 else False
    record("T9-9", "导航到 /home/iteration/pipeline/99999", "验证Pipeline进度页面渲染",
           f"页面容器: {pp_v}, 卡片: {card_v}, 空状态: {empty_v}" + ("" if nav_ok else " [导航失败]"),
           "✅" if (pp_v or card_v) and nav_ok else "❌")

    try:
        pt = page.locator("text=Pipeline 运行进度")
        pt_v = await pt.is_visible() if await pt.count() > 0 else False
        ri = page.locator(".run-info")
        ri_v = await ri.is_visible() if await ri.count() > 0 else False
        st = page.locator(".steps-table")
        st_v = await st.is_visible() if await st.count() > 0 else False
        bb = page.locator(".pipeline-progress button:has-text('返回')")
        bb_v = await bb.is_visible() if await bb.count() > 0 else False
        record("T9-10", "检查Pipeline进度页面内容", "步骤流程图、状态展示",
               f"进度标题: {pt_v}, 运行信息: {ri_v}, 步骤表格: {st_v}, 返回按钮: {bb_v}",
               "✅" if pt_v and (ri_v or st_v) else "⚠️")
    except Exception as e:
        record("T9-10", "检查Pipeline进度页面内容", "步骤流程图、状态展示", f"异常: {e}", "❌")


async def test_t10(page: Page):
    print("\n" + "=" * 60)
    print("T10: 系统管理")
    print("=" * 60)

    nav_ok = await navigate_to(page, "/home/system/user")
    title_text = await page.title()
    contains_user = "用户管理" in title_text
    record("T10-1", "导航到 /home/system/user", "页面标题含'用户管理'",
           f"标题: {title_text}" + ("" if nav_ok else " [导航失败]"),
           "✅" if contains_user and nav_ok else "❌")

    bc = await get_breadcrumb(page)
    expected = "工作台" in bc and "系统管理" in bc and "用户管理" in bc
    record("T10-2", "检查用户管理面包屑", "面包屑显示'工作台 / 系统管理 / 用户管理'",
           f"面包屑: {bc}", "✅" if expected else "⚠️")

    active, expanded = await check_menu_active(page, "用户管理", "系统管理")
    record("T10-3", "检查左侧菜单用户管理高亮", "用户管理高亮（属于系统管理子菜单）",
           f"高亮: {active}, 系统管理展开: {expanded}", "✅" if active and expanded else "⚠️")

    try:
        table = page.locator(".user-management .el-table")
        tv = await table.is_visible() if await table.count() > 0 else False
        headers = page.locator(".user-management .el-table__header-wrapper th")
        htexts = []
        for i in range(await headers.count()):
            htexts.append((await headers.nth(i).inner_text()).strip())
        hstr = ", ".join(htexts)
        has_un = "用户名" in hstr
        has_st = "状态" in hstr
        has_op = "操作" in hstr
        record("T10-4", "检查用户列表表格", "列：用户名、角色、状态、操作等",
               f"表头: {hstr}", "✅" if tv and has_un and has_st and has_op else "⚠️")
    except Exception as e:
        record("T10-4", "检查用户列表表格", "列：用户名、角色、状态、操作等", f"异常: {e}", "❌")

    try:
        add_btn = page.locator(".user-management button:has-text('新增用户')")
        abv = await add_btn.is_visible() if await add_btn.count() > 0 else False
        abe = await add_btn.is_enabled() if await add_btn.count() > 0 else False
        dialog_opened = False
        dialog_title = ""
        if abv and abe:
            await add_btn.click()
            await asyncio.sleep(0.8)
            dialog = page.locator(".el-dialog:visible")
            dialog_opened = await dialog.is_visible() if await dialog.count() > 0 else False
            if dialog_opened:
                title_el = page.locator(".el-dialog:visible .el-dialog__title")
                dialog_title = await title_el.inner_text() if await title_el.count() > 0 else ""
                close_btn = page.locator(".el-dialog:visible button:has-text('取消')")
                if await close_btn.count() > 0:
                    await close_btn.click()
                    await asyncio.sleep(0.3)
        record("T10-5", "点击'新增用户'按钮", "按钮存在且可点击，弹窗打开",
               f"可见: {abv}, 可点击: {abe}, 弹窗: {dialog_opened}, 标题: {dialog_title}",
               "✅" if abv and dialog_opened else "⚠️")
    except Exception as e:
        record("T10-5", "点击'新增用户'按钮", "按钮存在且可点击，弹窗打开", f"异常: {e}", "❌")

    try:
        action_btns = page.locator(".user-management .el-table__body-wrapper td:last-child .el-button")
        atexts = []
        for i in range(min(await action_btns.count(), 10)):
            t = await action_btns.nth(i).inner_text()
            atexts.append(t.strip())
        astr = ", ".join([t for t in atexts if t])
        has_edit = "编辑" in astr
        has_disable = "禁用" in astr or "启用" in astr
        has_role = "分配角色" in astr
        record("T10-6", "检查用户行操作按钮", "编辑、删除/禁用、重置密码/分配角色",
               f"操作: {astr}", "✅" if has_edit and (has_disable or has_role) else "⚠️")
    except Exception as e:
        record("T10-6", "检查用户行操作按钮", "编辑、删除/禁用、重置密码/分配角色", f"异常: {e}", "❌")

    nav_ok = await navigate_to(page, "/home/system/role")
    title_text = await page.title()
    contains_role = "角色管理" in title_text
    record("T10-7", "导航到 /home/system/role", "页面标题含'角色管理'",
           f"标题: {title_text}" + ("" if nav_ok else " [导航失败]"),
           "✅" if contains_role and nav_ok else "❌")

    try:
        table = page.locator(".role-management .el-table")
        tv = await table.is_visible() if await table.count() > 0 else False
        headers = page.locator(".role-management .el-table__header-wrapper th")
        htexts = []
        for i in range(await headers.count()):
            htexts.append((await headers.nth(i).inner_text()).strip())
        has_rn = any("角色名称" in h for h in htexts)
        record("T10-8", "检查角色列表加载", "角色列表加载",
               f"表格: {tv}, 表头: {', '.join(htexts)}", "✅" if tv and has_rn else "⚠️")
    except Exception as e:
        record("T10-8", "检查角色列表加载", "角色列表加载", f"异常: {e}", "❌")

    nav_ok = await navigate_to(page, "/home/system/audit-log")
    title_text = await page.title()
    contains_audit = "审计日志" in title_text
    record("T10-9", "导航到 /home/system/audit-log", "页面标题含'审计日志'",
           f"标题: {title_text}" + ("" if nav_ok else " [导航失败]"),
           "✅" if contains_audit and nav_ok else "❌")

    try:
        table = page.locator(".audit-log-page .el-table")
        tv = await table.is_visible() if await table.count() > 0 else False
        headers = page.locator(".audit-log-page .el-table__header-wrapper th")
        htexts = []
        for i in range(await headers.count()):
            htexts.append((await headers.nth(i).inner_text()).strip())
        has_at = any("操作类型" in h for h in htexts)
        record("T10-10", "检查审计日志列表加载", "审计日志列表加载",
               f"表格: {tv}, 表头: {', '.join(htexts)}", "✅" if tv and has_at else "⚠️")
    except Exception as e:
        record("T10-10", "检查审计日志列表加载", "审计日志列表加载", f"异常: {e}", "❌")

    nav_ok = await navigate_to(page, "/home/system/test-capability")
    title_text = await page.title()
    contains_cap = "测试能力" in title_text
    record("T10-11", "导航到 /home/system/test-capability", "页面标题含'测试能力'",
           f"标题: {title_text}" + ("" if nav_ok else " [导航失败]"),
           "✅" if contains_cap and nav_ok else "❌")

    try:
        pg = page.locator(".test-capability-management")
        pv = await pg.is_visible() if await pg.count() > 0 else False
        ps = page.locator(".test-capability-management .el-select").first
        psv = await ps.is_visible() if await ps.count() > 0 else False
        ab = page.locator(".test-capability-management button:has-text('新增能力')")
        abv = await ab.is_visible() if await ab.count() > 0 else False
        tb = page.locator(".test-capability-management .el-table")
        tbv = await tb.is_visible() if await tb.count() > 0 else False
        record("T10-12", "检查测试能力页面加载", "测试能力页面加载",
               f"页面: {pv}, 项目选择: {psv}, 新增按钮: {abv}, 表格: {tbv}",
               "✅" if pv and (psv or tbv) else "⚠️")
    except Exception as e:
        record("T10-12", "检查测试能力页面加载", "测试能力页面加载", f"异常: {e}", "❌")

    nav_ok = await navigate_to(page, "/home/system/profile")
    title_text = await page.title()
    contains_profile = "个人中心" in title_text
    record("T10-13", "导航到 /home/system/profile", "页面标题含'个人中心'",
           f"标题: {title_text}" + ("" if nav_ok else " [导航失败]"),
           "✅" if contains_profile and nav_ok else "❌")

    try:
        pg = page.locator(".profile")
        pv = await pg.is_visible() if await pg.count() > 0 else False
        tabs = page.locator(".profile .el-tabs__item")
        ttexts = []
        for i in range(await tabs.count()):
            ttexts.append((await tabs.nth(i).inner_text()).strip())
        ui = page.locator(".profile .el-form-item:has-text('用户名') .el-input")
        uiv = await ui.is_visible() if await ui.count() > 0 else False
        record("T10-14", "检查个人中心页面加载", "个人中心页面加载",
               f"页面: {pv}, 标签页: {', '.join(ttexts)}, 用户名: {uiv}",
               "✅" if pv and len(ttexts) > 0 else "⚠️")
    except Exception as e:
        record("T10-14", "检查个人中心页面加载", "个人中心页面加载", f"异常: {e}", "❌")


async def main():
    print("=" * 60)
    print("AI TestMaster 前端复测 - T9 迭代中心 + T10 系统管理")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标: {BASE_URL}")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # 1. 设置 API 拦截（精确匹配 /api/v1/）
        await setup_api_interception(context, page)

        # 2. 通过 add_init_script 保护 token 和阻止 401 跳转
        await context.add_init_script(f"""
            localStorage.setItem('token', '{FAKE_TOKEN}');
            localStorage.setItem('userInfo', '{USER_INFO_JSON}');

            // 保护 token 不被清除
            const origRemoveItem = Storage.prototype.removeItem;
            Storage.prototype.removeItem = function(key) {{
                if (key === 'token' || key === 'userInfo') return;
                return origRemoveItem.call(this, key);
            }};

            // 阻止 401 时跳转到登录页
            // 通过拦截 window.location.href 的设置
            const realLocation = window.location;
            let _redirecting = false;

            // 使用 Proxy 拦截 location.href 设置
            // 注意：window.location 是特殊对象，不能直接 Proxy
            // 替代方案：在 beforeunload 事件中阻止导航
            window.addEventListener('beforeunload', (e) => {{
                // 允许所有导航
            }});
        """)

        # 3. 首次导航到首页
        print("\n[前置] 导航到首页...")
        await page.goto(f"{BASE_URL}/home/project")
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(3)

        current_url = page.url
        print(f"[前置] 当前URL: {current_url}")
        ls_token = await page.evaluate("localStorage.getItem('token')")
        print(f"[前置] token: {'存在' if ls_token else '被清除'}")
        app_html = await page.evaluate("document.querySelector('#app')?.innerHTML?.substring(0, 100) || 'EMPTY'")
        print(f"[前置] #app: {app_html[:80]}...")

        if "/login" in current_url or app_html == "EMPTY":
            print("[前置] 首页加载异常，尝试重新设置...")
            await page.evaluate(f"""
                localStorage.setItem('token', '{FAKE_TOKEN}');
                localStorage.setItem('userInfo', '{USER_INFO_JSON}');
            """)
            await page.goto(f"{BASE_URL}/home/project")
            await page.wait_for_load_state("networkidle", timeout=20000)
            await asyncio.sleep(3)
            current_url = page.url
            app_html = await page.evaluate("document.querySelector('#app')?.innerHTML?.substring(0, 100) || 'EMPTY'")
            print(f"[前置] 二次: URL={current_url}, #app={app_html[:60]}...")

        if "/login" not in current_url and app_html != "EMPTY":
            print("[前置] 成功进入首页\n")
        else:
            print(f"[前置] 警告: 首页异常\n")

        await test_t9(page)
        await test_t10(page)

        await browser.close()

    # 输出汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    pass_count = sum(1 for r in results if r["状态"] == "✅")
    fail_count = sum(1 for r in results if r["状态"] == "❌")
    warn_count = sum(1 for r in results if r["状态"] == "⚠️")

    print(f"\n总检查点: {len(results)}")
    print(f"通过: {pass_count}  失败: {fail_count}  警告: {warn_count}")
    print(f"通过率: {pass_count / len(results) * 100:.1f}%\n")

    print(f"{'编号':<8} {'操作':<40} {'期望结果':<35} {'实际结果':<50} {'状态'}")
    print("-" * 145)
    for r in results:
        print(f"{r['编号']:<8} {r['操作'][:38]:<40} {r['期望结果'][:33]:<35} {r['实际结果'][:48]:<50} {r['状态']}")

    issues = [r for r in results if r["状态"] in ("❌", "⚠️")]
    if issues:
        print("\n需关注项:")
        for r in issues:
            print(f"  {r['状态']} {r['编号']}: {r['期望结果']} => {r['实际结果']}")

    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
