"""Self-test prompt helpers for AI test case generation."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

TESTID_MAP_PATH = Path("docs/testid-map.json")

SELF_TEST_LOCATOR_MAP_FALLBACK = """## 平台元素定位器映射
以下元素已配置 data-testid，生成自测用例时优先使用这些稳定定位器：
- 用户名输入框: [data-testid="login-username"]
- 密码输入框: [data-testid="login-password"]
- 登录按钮: [data-testid="login-submit"]
- 创建项目按钮: [data-testid="create-project"]
- 项目卡片: [data-testid="project-card"]
- 用例搜索框: [data-testid="case-search"]
- 创建用例按钮: [data-testid="create-case"]
- 执行按钮: [data-testid="execute-btn"]
- 停止按钮: [data-testid="stop-btn"]
- 项目导航: [data-testid="nav-/home/project"]"""

SELF_TEST_ASSERTION_SYNTAX = """## 结构化断言语法
自测用例的 expected_result 必须优先使用可执行断言表达：
- [text_contains] 页面包含指定文案
- [text_equals] 文案完全匹配
- [text_matches] 文案满足正则
- [visible] 元素可见
- [not_visible] 元素不可见
- [url_contains] URL 包含路径片段
- [url_equals] URL 完全匹配"""

SELF_TEST_NAVIGATION_GUIDE = """## 导航说明
平台前端使用 History 模式，导航路径不带 #/ 前缀。
- action_type 使用 navigate 表示页面跳转
- 导航到项目页时 target_element 使用 /home/project
- 导航到用例页时 target_element 使用 /home/case
- 不使用 #/home/project 这类 hash 路径"""

SELF_TEST_CORE_FLOWS = """## 必须覆盖的核心流程
- 登录流程
- 项目管理
- 测试点提取
- 用例生成
- 任务执行
- 报告查看"""

SELF_TEST_DEFECT_BOUNDARY = """## 缺陷挖掘指导 - 边界值攻击
针对每个输入字段，必须生成以下边界测试用例：
- 最大长度输入：输入字段允许的最大字符数（如用户名256字符）
- 最小长度输入：输入字段允许的最小字符数（如密码6字符）
- 空值输入：不填写必填字段直接提交
- 特殊字符注入：在输入框中填入 `<script>alert(1)</script>`、`'; DROP TABLE--`、`{{7*7}}`
- 超长字符串：输入500+字符的字符串，验证前端截断或后端校验
- 零值与负值：数值型字段输入0、-1、999999999
- 格式边界：邮箱缺少@、手机号少一位、日期格式错误"""

SELF_TEST_DEFECT_EXCEPTION = """## 缺陷挖掘指导 - 异常路径覆盖
针对每个核心流程，必须生成以下异常路径测试用例：
- 网络断开操作：断网后点击提交按钮，验证前端提示网络错误且不丢失已填数据
- 重复提交：快速连续点击提交按钮两次，验证后端幂等处理、不产生重复数据
- 并发操作：两个浏览器标签页同时编辑同一用例，验证后端乐观锁或冲突提示
- 未授权访问：清除Token后访问 /home/project，验证跳转登录页而非白屏
- 资源不存在：访问已删除项目的详情页，验证404提示而非报错
- 依赖缺失：不选择项目直接生成用例，验证前端禁用按钮或提示选择项目"""

SELF_TEST_DEFECT_PERMISSION = """## 缺陷挖掘指导 - 权限绕过测试
针对认证与权限相关模块，必须生成以下权限绕过测试用例：
- 普通用户访问管理员功能：以普通用户身份访问用户管理页面，验证返回403或重定向
- 跨项目数据访问：使用项目A的Token直接请求项目B的用例API，验证返回403
- 越权删除：非项目所有者尝试删除项目，验证返回403且项目未被删除
- 角色降级操作：管理员降级为普通用户后，验证无法再访问管理员功能
- API直接调用：绕过前端直接调用后端API（如POST /api/users），验证后端权限校验"""

SELF_TEST_DEFECT_STATE = """## 缺陷挖掘指导 - 状态不一致测试
针对状态流转相关功能，必须生成以下状态不一致测试用例：
- 错误时机操作：draft状态的用例直接点击执行，验证提示"用例未就绪"而非报错
- 跳过必要步骤：不选择项目直接生成用例，验证前端禁用或提示而非后端异常
- 任务执行中删除关联用例：任务执行中删除其关联的测试用例，验证任务状态正确更新或阻止删除
- 状态回退：已完成的任务重新执行，验证产生新的执行记录而非覆盖旧记录
- 并发状态变更：同一用例同时被两个任务引用执行，验证数据一致性"""

SELF_TEST_DEFECT_SECURITY = """## 缺陷挖掘指导 - 安全测试
针对认证、权限、用户管理模块，必须生成以下安全测试用例：
- 敏感数据暴露：验证页面DOM和网络响应中不包含密码明文、JWT Token、API Key，使用 [no_sensitive_data] 断言
- XSS防护：在输入框注入 `<script>alert('xss')</script>`，验证页面不执行脚本且正确转义显示，使用 [no_xss] 断言
- Token安全：使用过期Token请求API，验证返回401而非500；使用伪造Token验证返回401
- SQL注入：在搜索框输入 `' OR 1=1--`，验证返回空结果而非全部数据
- CSRF防护：验证关键操作（删除项目、修改密码）需要有效CSRF Token"""

SELF_TEST_DEFECT_REQUIREMENT = """## 缺陷挖掘指导 - 基于需求文档生成用例
以需求文档中的"业务规则"和"异常处理"章节为主要输入：
- 针对每条业务规则，生成违反规则的测试用例（而非验证规则正确的用例）
  示例：规则"密码长度6-20位" → 生成输入5位和21位密码的用例
- 针对每个异常处理机制，生成触发该异常的测试用例
  示例：异常"用户不存在时返回404" → 生成查询不存在用户ID的用例
- 针对每个输入规范，生成超出规范的边界输入用例
  示例：规范"邮箱格式" → 生成缺少@、多个@、超长邮箱的用例"""

SELF_TEST_DEFECT_DISTRIBUTION = """## 缺陷挖掘指导 - 用例类型分布控制
生成的用例必须满足以下分布要求：
- 缺陷挖掘用例（边界/异常/安全/压力）占比 ≥ 60%
- 功能验证用例（正常路径）占比 ≤ 40%
- 每个核心功能模块至少包含1个边界场景用例和1个异常路径用例
- 安全相关模块（认证、权限、用户管理）至少包含1个安全测试用例
- 用例的case_category字段需标注类型：boundary、exception、security、stress、normal"""


def _format_testid_entries(testids: List[Dict[str, Any]]) -> str:
    lines = [
        "## 平台元素定位器映射",
        "以下元素已配置 data-testid，生成自测用例时优先使用这些稳定定位器：",
    ]
    for item in testids:
        selector = item.get("selector") or (
            f'[data-testid="{item.get("id", "")}"]' if item.get("id") else ""
        )
        if not selector:
            continue
        context = (item.get("context") or "").strip()
        if context:
            lines.append(f"- {context}: {selector}")
        else:
            lines.append(f"- {selector}")
    return "\n".join(lines)


def load_testid_map() -> str:
    if not TESTID_MAP_PATH.exists():
        return SELF_TEST_LOCATOR_MAP_FALLBACK
    try:
        data = json.loads(TESTID_MAP_PATH.read_text(encoding="utf-8"))
    except Exception:
        return SELF_TEST_LOCATOR_MAP_FALLBACK

    testids = data.get("testids")
    if not isinstance(testids, list) or not testids:
        return "\n".join([
            "## 平台元素定位器映射",
            "以下元素已配置 data-testid，当前未发现动态映射条目。",
            SELF_TEST_LOCATOR_MAP_FALLBACK,
        ])
    return _format_testid_entries(testids)


def build_self_test_prompt(
    requirement_content: str,
    ui_description: str,
    module: str,
    function: str,
    point: str,
    priority: int,
    ui_specs: Optional[List[Dict[str, Any]]] = None,
    history_cases: Optional[List[Dict[str, Any]]] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> str:
    from app.services.prompt_builder.builder import PromptBuilder

    base_prompt = PromptBuilder.build_linear_prompt(
        requirement_content=requirement_content,
        ui_description=ui_description,
        module=module,
        function=function,
        point=point,
        priority=priority,
        ui_specs=ui_specs,
        extra_context=extra_context,
    )

    sections = [
        base_prompt,
        load_testid_map(),
        SELF_TEST_ASSERTION_SYNTAX,
        SELF_TEST_NAVIGATION_GUIDE,
        SELF_TEST_CORE_FLOWS,
        "## 自测项目约束\n- 优先生成 ui_automation 用例\n- 优先使用 data-testid 定位器\n- 每个步骤必须可自动执行和断言",
        SELF_TEST_DEFECT_BOUNDARY,
        SELF_TEST_DEFECT_EXCEPTION,
        SELF_TEST_DEFECT_PERMISSION,
        SELF_TEST_DEFECT_STATE,
        SELF_TEST_DEFECT_SECURITY,
        SELF_TEST_DEFECT_REQUIREMENT,
        SELF_TEST_DEFECT_DISTRIBUTION,
    ]

    if history_cases:
        sections.append("## 历史用例参考")
        for case in history_cases[:20]:
            title = case.get("title") or case.get("case_title") or ""
            module_name = case.get("module") or ""
            sections.append(f"- [{module_name}] {title}".strip())

    return "\n\n".join(sections)


__all__ = [
    "TESTID_MAP_PATH",
    "SELF_TEST_LOCATOR_MAP_FALLBACK",
    "SELF_TEST_ASSERTION_SYNTAX",
    "SELF_TEST_NAVIGATION_GUIDE",
    "SELF_TEST_CORE_FLOWS",
    "SELF_TEST_DEFECT_BOUNDARY",
    "SELF_TEST_DEFECT_EXCEPTION",
    "SELF_TEST_DEFECT_PERMISSION",
    "SELF_TEST_DEFECT_STATE",
    "SELF_TEST_DEFECT_SECURITY",
    "SELF_TEST_DEFECT_REQUIREMENT",
    "SELF_TEST_DEFECT_DISTRIBUTION",
    "load_testid_map",
    "build_self_test_prompt",
]
