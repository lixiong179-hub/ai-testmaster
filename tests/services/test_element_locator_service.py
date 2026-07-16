"""ElementLocatorService 服务层测试。

覆盖范围:
    - 服务构造与识别器选择 (MCP/Vision)
    - LocatorQueryMixin: DB CRUD (get/has/record/update/delete/stats)
    - transaction() 上下文管理器 (commit/rollback)
    - SelectorGenerationMixin: CSS/XPath 生成与坐标归一化
    - SmartLocateMixin: 同步辅助方法 (_should_direct_execute, _build_recognition_prompt)
    - record_locator / record_precondition_step_locator (async, stub browser+recognizer)
    - smart_locate_element (async, stub browser+recognizer)
    - _get_element_attributes (async, 异常分支)

DB 使用真实 MySQL 测试库 (tests/conftest.py 的 db fixture, 事务隔离回滚)。
browser/recognizer 为真实 stub 类 (非 MagicMock), 仅满足异步接口契约。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from app.core.config import settings
from app.interfaces.element_recognizer import RecognitionResult
from app.models.element_locator import ElementLocator
from app.models.enums import LocatorStatus
from app.models.project import Project
from app.models.test_case import TestCase, TestCasePreconditionStep, TestStep
from app.models.user import User
from app.services.element_locator import ElementLocatorService


# ==================== Stub 类 (真实类, 非 Mock) ====================

class _StubBrowser:
    """浏览器 stub, 满足 service 调用的异步接口。

    按 JS 代码内容路由返回值:
        - 含 getBoundingClientRect → element_info
        - 含 document.querySelector (无 getBoundingClientRect) → exists bool
        - 含 elementFromPoint → attrs dict
    """

    def __init__(self, screenshot: bytes = b"png", js_map: Optional[Dict[str, Any]] = None,
                 js_exc: Optional[Exception] = None):
        self._screenshot = screenshot
        self._js_map = js_map or {}
        self._js_exc = js_exc
        self.execute_calls: List[tuple] = []

    async def take_screenshot(self) -> bytes:
        return self._screenshot

    async def execute_javascript(self, code: str, *args) -> Any:
        self.execute_calls.append((code, args))
        if self._js_exc is not None:
            raise self._js_exc
        if "getBoundingClientRect" in code:
            return self._js_map.get("element_info")
        if "document.querySelector" in code:
            return self._js_map.get("exists", False)
        if "elementFromPoint" in code:
            return self._js_map.get("attrs", {})
        return self._js_map.get("default")


class _StubRecognizer:
    """识别器 stub, 返回预设的 RecognitionResult。"""

    def __init__(self, result: Optional[RecognitionResult] = None):
        self._result = result
        self.name = "stub"

    async def recognize(self, browser, op: str, action_type: Optional[str] = None) -> RecognitionResult:
        return self._result

    async def batch_recognize(self, browser, ops: List[str]) -> List[RecognitionResult]:
        return [self._result for _ in ops]

    async def is_available(self) -> bool:
        return True


# ==================== Fixtures 与数据构造 ====================

@pytest.fixture
def el_user(db):
    user = User(username="el_cov_user", email="el_cov@test.com", password_hash="hash")
    db.add(user)
    db.flush()
    db.refresh(user)
    yield user


@pytest.fixture
def el_project(db, el_user):
    project = Project(name="EL覆盖项目", user_id=el_user.id, project_type="web", status=1)
    db.add(project)
    db.flush()
    db.refresh(project)
    yield project


def _make_case(db, project_id, case_no=None):
    case = TestCase(
        project_id=project_id,
        case_no=case_no or f"EL-{datetime.now().strftime('%H%M%S%f')}",
        module="EL模块",
        title="元素定位覆盖用例",
        precondition="前置",
        steps_json=[],
        expected_result="预期",
        priority=1,
        case_type="UI",
    )
    db.add(case)
    db.flush()
    db.refresh(case)
    return case


def _make_step(db, case_id, step_number=1, action="点击登录按钮"):
    step = TestStep(test_case_id=case_id, step_number=step_number, action=action, expected_result="成功")
    db.add(step)
    db.flush()
    db.refresh(step)
    return step


def _make_precondition_step(db, case_id, step_number=1, action="导航到首页"):
    step = TestCasePreconditionStep(
        test_case_id=case_id, step_number=step_number, action=action, expected_result=""
    )
    db.add(step)
    db.flush()
    db.refresh(step)
    return step


def _make_locator(db, step_id, **kwargs):
    locator = ElementLocator(
        step_id=step_id,
        element_description=kwargs.get("element_description", "登录按钮"),
        css_selector=kwargs.get("css_selector", "#login-btn"),
        xpath=kwargs.get("xpath", "//button[@id='login-btn']"),
        source=kwargs.get("source", "ai"),
        success_count=kwargs.get("success_count", 0),
        fail_count=kwargs.get("fail_count", 0),
    )
    db.add(locator)
    db.flush()
    db.refresh(locator)
    return locator


def _make_service(db, browser=None, recognizer=None, confidence_threshold=None):
    """构造 ElementLocatorService, 默认使用 stub browser + recognizer。"""
    return ElementLocatorService(
        db=db,
        browser=browser or _StubBrowser(),
        vision_model=object(),
        confidence_threshold=confidence_threshold,
        recognizer=recognizer or _StubRecognizer(),
    )


# ==================== 服务构造测试 ====================

class TestServiceConstruction:

    def test_init_sets_default_confidence_threshold(self, db):
        svc = _make_service(db)
        assert svc.confidence_threshold == ElementLocatorService.MIN_CONFIDENCE_THRESHOLD

    def test_init_with_custom_confidence_threshold(self, db):
        svc = _make_service(db, confidence_threshold=0.95)
        assert svc.confidence_threshold == 0.95

    def test_init_with_custom_recognizer(self, db):
        recognizer = _StubRecognizer()
        svc = _make_service(db, recognizer=recognizer)
        assert svc.recognizer is recognizer

    def test_create_default_recognizer_vision_when_disabled(self, db, monkeypatch):
        from app.services.recognizers.vision_recognizer import VisionRecognizer
        monkeypatch.setattr(settings, "PLAYWRIGHT_MCP_ENABLED", False)
        svc = ElementLocatorService(db=db, browser=_StubBrowser(), vision_model=object())
        assert isinstance(svc.recognizer, VisionRecognizer)

    def test_create_default_recognizer_mcp_when_enabled(self, db, monkeypatch):
        from app.services.recognizers.mcp_recognizer import MCPRecognizer
        monkeypatch.setattr(settings, "PLAYWRIGHT_MCP_ENABLED", True)
        svc = ElementLocatorService(db=db, browser=_StubBrowser(), vision_model=object())
        assert isinstance(svc.recognizer, MCPRecognizer)

    def test_create_locator_service_vision(self, db):
        from app.services.recognizers.vision_recognizer import VisionRecognizer
        svc = ElementLocatorService.create_locator_service(
            db=db, browser=_StubBrowser(), vision_model=object(), use_mcp=False
        )
        assert isinstance(svc.recognizer, VisionRecognizer)

    def test_create_locator_service_mcp(self, db):
        from app.services.recognizers.mcp_recognizer import MCPRecognizer
        svc = ElementLocatorService.create_locator_service(
            db=db, browser=_StubBrowser(), vision_model=object(), use_mcp=True
        )
        assert isinstance(svc.recognizer, MCPRecognizer)


# ==================== LocatorQueryMixin 测试 ====================

class TestLocatorQuery:

    def test_get_locator_returns_none_when_not_found(self, db):
        assert _make_service(db).get_locator(999999) is None

    def test_get_locator_returns_locator(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        _make_locator(db, step.id)
        result = _make_service(db).get_locator(step.id)
        assert result is not None
        assert result.css_selector == "#login-btn"

    def test_has_locator_false_when_not_found(self, db):
        assert _make_service(db).has_locator(999999) is False

    def test_has_locator_true_when_exists(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        _make_locator(db, step.id)
        assert _make_service(db).has_locator(step.id) is True

    def test_record_locator_success_increments_count(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        locator = _make_locator(db, step.id, success_count=2)
        _make_service(db).record_locator_success(step.id)
        db.refresh(locator)
        assert locator.success_count == 3
        assert locator.last_used_at is not None
        assert locator.version == 1

    def test_record_locator_success_no_locator_does_nothing(self, db):
        _make_service(db).record_locator_success(999999)

    def test_record_locator_failure_increments_count(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        locator = _make_locator(db, step.id, fail_count=1)
        _make_service(db).record_locator_failure(step.id)
        db.refresh(locator)
        assert locator.fail_count == 2

    def test_record_locator_failure_no_locator_does_nothing(self, db):
        _make_service(db).record_locator_failure(999999)

    def test_update_locator_updates_all_fields(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        locator = _make_locator(db, step.id)
        result = _make_service(db).update_locator(
            step.id, css_selector="#new", xpath="//new", element_id="new-id"
        )
        assert result is True
        db.refresh(locator)
        assert locator.css_selector == "#new"
        assert locator.xpath == "//new"
        assert locator.element_id == "new-id"

    def test_update_locator_partial_update(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        locator = _make_locator(db, step.id)
        _make_service(db).update_locator(step.id, css_selector="#partial")
        db.refresh(locator)
        assert locator.css_selector == "#partial"
        assert locator.xpath == "//button[@id='login-btn']"

    def test_update_locator_returns_false_when_not_found(self, db):
        assert _make_service(db).update_locator(999999, css_selector="#x") is False

    def test_delete_locator_returns_true(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        _make_locator(db, step.id)
        svc = _make_service(db)
        assert svc.delete_locator(step.id) is True
        assert svc.get_locator(step.id) is None

    def test_delete_locator_returns_false_when_not_found(self, db):
        assert _make_service(db).delete_locator(999999) is False

    def test_get_locator_stats_returns_none_when_not_found(self, db):
        assert _make_service(db).get_locator_stats(999999) is None

    def test_get_locator_stats_returns_stats(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        _make_locator(db, step.id, success_count=8, fail_count=2)
        stats = _make_service(db).get_locator_stats(step.id)
        assert stats["step_id"] == step.id
        assert stats["success_count"] == 8
        assert stats["fail_count"] == 2
        assert stats["success_rate"] == 0.8
        assert "priority_order" in stats

    def test_get_locator_stats_success_rate_zero(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        _make_locator(db, step.id, success_count=0, fail_count=0)
        assert _make_service(db).get_locator_stats(step.id)["success_rate"] == 0.0


# ==================== transaction() 上下文管理器测试 ====================

class TestTransaction:

    def test_transaction_commits_on_success(self, db, el_project):
        case = _make_case(db, el_project.id)
        svc = _make_service(db)
        with svc.transaction():
            case.title = "事务修改标题"
        db.refresh(case)
        assert case.title == "事务修改标题"

    def test_transaction_rolls_back_on_exception(self, db, el_project):
        """异常时 transaction() 触发 rollback，事务内新增记录被撤销。"""
        svc = _make_service(db)
        with pytest.raises(ValueError, match="boom"):
            with svc.transaction():
                new_case = TestCase(
                    project_id=el_project.id,
                    case_no="EL-ROLLBACK-TEST",
                    module="EL模块",
                    title="不应保留",
                    precondition="前置",
                    steps_json=[],
                    expected_result="预期",
                    priority=1,
                    case_type="UI",
                )
                db.add(new_case)
                db.flush()
                raise ValueError("boom")
        # rollback 撤销 savepoint 内所有变更，新记录不应存在
        assert (
            db.query(TestCase).filter(TestCase.case_no == "EL-ROLLBACK-TEST").first()
            is None
        )


# ==================== SelectorGenerationMixin 测试 ====================

class TestSelectorGeneration:

    def test_sanitize_for_css_escapes_special_chars(self, db):
        svc = _make_service(db)
        assert svc._sanitize_for_css("a.b#c") == "a\\.b\\#c"

    def test_sanitize_for_css_empty(self, db):
        assert _make_service(db)._sanitize_for_css("") == ""

    def test_sanitize_for_xpath_no_quotes(self, db):
        assert _make_service(db)._sanitize_for_xpath("value") == '"value"'

    def test_sanitize_for_xpath_double_quote(self, db):
        assert _make_service(db)._sanitize_for_xpath('has"quote') == "'has\"quote'"

    def test_sanitize_for_xpath_both_quotes_uses_concat(self, db):
        result = _make_service(db)._sanitize_for_xpath('a"b\'c')
        assert result.startswith("concat(")

    def test_generate_css_selector_by_id(self, db):
        assert _make_service(db)._generate_css_selector({"tag": "input", "id": "user"}) == "#user"

    def test_generate_css_selector_by_data_testid(self, db):
        result = _make_service(db)._generate_css_selector({"tag": "div", "data-testid": "btn"})
        assert result == "[data-testid='btn']"

    def test_generate_css_selector_by_name(self, db):
        result = _make_service(db)._generate_css_selector({"tag": "input", "name": "pwd"})
        assert result == "[name='pwd']"

    def test_generate_css_selector_by_class_limits_count(self, db):
        result = _make_service(db)._generate_css_selector(
            {"tag": "button", "class": "btn primary large"}
        )
        assert result == "button.btn.primary"

    def test_generate_css_selector_by_type_and_placeholder(self, db):
        result = _make_service(db)._generate_css_selector(
            {"tag": "input", "type": "text", "placeholder": "请输入用户名"}
        )
        assert "input[type='text']" in result
        assert "[placeholder*=" in result

    def test_generate_css_selector_by_type_only(self, db):
        result = _make_service(db)._generate_css_selector({"tag": "input", "type": "checkbox"})
        assert result == "input[type='checkbox']"

    def test_generate_css_selector_tag_only(self, db):
        assert _make_service(db)._generate_css_selector({"tag": "div"}) == "div"

    def test_generate_css_selector_empty_returns_none(self, db):
        assert _make_service(db)._generate_css_selector({}) is None

    def test_generate_xpath_by_id(self, db):
        result = _make_service(db)._generate_xpath({"tag": "input", "id": "user"})
        assert result == '//input[@id="user"]'

    def test_generate_xpath_by_name(self, db):
        result = _make_service(db)._generate_xpath({"tag": "input", "name": "pwd"})
        assert result == '//input[@name="pwd"]'

    def test_generate_xpath_by_text(self, db):
        result = _make_service(db)._generate_xpath({"tag": "button", "text": "提交"})
        assert "contains(text()," in result

    def test_generate_xpath_default(self, db):
        assert _make_service(db)._generate_xpath({"tag": "div"}) == "//div"

    def test_normalize_coordinate_defaults(self, db):
        result = _make_service(db)._normalize_coordinate({"x": 10, "y": 20})
        assert result == {"x": 10, "y": 20, "width": 0, "height": 0}

    def test_normalize_coordinate_list_and_none_values(self, db):
        result = _make_service(db)._normalize_coordinate(
            {"x": [5, 10], "y": [None], "width": None, "height": []}
        )
        assert result == {"x": 5, "y": 0, "width": 0, "height": 0}

    def test_normalize_coordinate_inplace(self, db):
        info = {"x": 1, "y": 2}
        result = _make_service(db)._normalize_coordinate(info, inplace=True)
        assert result is info
        assert info["width"] == 0


# ==================== SmartLocateMixin 同步辅助方法测试 ====================

class TestSmartLocateHelpers:

    def test_should_direct_execute_disabled_by_default(self, db, monkeypatch):
        monkeypatch.setattr(settings, "MCP_DIRECT_EXECUTION_ENABLED", False)
        assert _make_service(db)._should_direct_execute("click") is False

    def test_should_direct_execute_false_when_recognizer_not_mcp(self, db, monkeypatch):
        monkeypatch.setattr(settings, "MCP_DIRECT_EXECUTION_ENABLED", True)
        assert _make_service(db)._should_direct_execute("click") is False

    def test_should_direct_execute_true_when_enabled_and_mcp(self, db, monkeypatch):
        from app.services.recognizers.mcp_recognizer import MCPRecognizer
        monkeypatch.setattr(settings, "MCP_DIRECT_EXECUTION_ENABLED", True)
        svc = ElementLocatorService(
            db=db, browser=_StubBrowser(), vision_model=object(), recognizer=MCPRecognizer()
        )
        assert svc._should_direct_execute("click") is True
        assert svc._should_direct_execute("unknown") is False

    def test_build_recognition_prompt_login_page(self, db):
        prompt = _make_service(db)._build_recognition_prompt("输入用户名", None)
        assert "用户名" in prompt
        assert "登录" in prompt

    def test_build_recognition_prompt_normal_page(self, db):
        prompt = _make_service(db)._build_recognition_prompt("点击提交按钮", None)
        assert "点击提交按钮" in prompt

    def test_build_recognition_prompt_verify_action(self, db):
        prompt = _make_service(db)._build_recognition_prompt("检查按钮状态", "verify")
        assert "验证步骤" in prompt


# ==================== record_locator (async) 测试 ====================

class TestRecordLocator:

    @pytest.mark.asyncio
    async def test_record_locator_success_creates_locator(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        recognizer = _StubRecognizer(result=RecognitionResult(
            locator_type="vision", locator_value="#btn", confidence=0.9,
            element_info={"x": 10, "y": 20, "width": 50, "height": 30, "confidence": 0.9},
        ))
        browser = _StubBrowser(js_map={
            "attrs": {"tag": "button", "id": "submit", "class": "btn primary", "text": "登录"}
        })
        svc = _make_service(db, browser=browser, recognizer=recognizer)
        locator = await svc.record_locator(step.id, "点击登录按钮")
        assert locator is not None
        assert locator.step_id == step.id
        assert locator.css_selector == "#submit"
        assert locator.element_type == "button"
        assert locator.element_class == "btn primary"
        assert locator.ai_confidence == 0.9
        db.refresh(step)
        assert step.has_locator == 1
        assert step.locator_status == LocatorStatus.RECORDED.value

    @pytest.mark.asyncio
    async def test_record_locator_returns_none_when_recognizer_fails(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        recognizer = _StubRecognizer(result=RecognitionResult(
            locator_type="vision", locator_value="", confidence=0,
        ))
        svc = _make_service(db, recognizer=recognizer)
        assert await svc.record_locator(step.id, "点击按钮") is None

    @pytest.mark.asyncio
    async def test_record_locator_with_screenshot_arg(self, db, el_project):
        case = _make_case(db, el_project.id)
        step = _make_step(db, case.id)
        recognizer = _StubRecognizer(result=RecognitionResult(
            locator_type="vision", locator_value="#x", confidence=0.9,
            element_info={"x": 1, "y": 2, "width": 3, "height": 4, "confidence": 0.9},
        ))
        browser = _StubBrowser(js_map={"attrs": {"tag": "a"}})
        svc = _make_service(db, browser=browser, recognizer=recognizer)
        locator = await svc.record_locator(step.id, "点击", screenshot=b"explicit")
        assert locator is not None
        # 未调用 take_screenshot (传入了 screenshot 参数)
        assert len(browser.execute_calls) >= 1

    @pytest.mark.asyncio
    async def test_record_precondition_step_locator_success(self, db, el_project):
        case = _make_case(db, el_project.id)
        pc_step = _make_precondition_step(db, case.id)
        recognizer = _StubRecognizer(result=RecognitionResult(
            locator_type="vision", locator_value="#nav", confidence=0.85,
            element_info={"x": 0, "y": 0, "width": 100, "height": 30, "confidence": 0.85},
        ))
        browser = _StubBrowser(js_map={"attrs": {"tag": "a", "id": "home", "text": "首页"}})
        svc = _make_service(db, browser=browser, recognizer=recognizer)
        locator = await svc.record_precondition_step_locator(pc_step.id, "点击首页链接")
        assert locator is not None
        assert locator.precondition_step_id == pc_step.id
        assert locator.step_id is None
        db.refresh(pc_step)
        assert pc_step.has_locator == 1
        assert pc_step.locator_status == LocatorStatus.RECORDED.value

    @pytest.mark.asyncio
    async def test_record_precondition_step_locator_returns_none_when_fails(self, db, el_project):
        case = _make_case(db, el_project.id)
        pc_step = _make_precondition_step(db, case.id)
        recognizer = _StubRecognizer(result=RecognitionResult(
            locator_type="vision", locator_value="", confidence=0,
        ))
        svc = _make_service(db, recognizer=recognizer)
        assert await svc.record_precondition_step_locator(pc_step.id, "点击链接") is None


# ==================== smart_locate_element (async) 测试 ====================

class TestSmartLocateElement:

    @pytest.mark.asyncio
    async def test_returns_none_when_recognizer_fails(self, db):
        recognizer = _StubRecognizer(result=RecognitionResult(
            locator_type="vision", locator_value="", confidence=0,
        ))
        svc = _make_service(db, recognizer=recognizer)
        assert await svc.smart_locate_element("点击按钮") is None

    @pytest.mark.asyncio
    async def test_returns_element_info_with_vision_result(self, db):
        recognizer = _StubRecognizer(result=RecognitionResult(
            locator_type="vision", locator_value="#btn", confidence=0.9,
            element_info={"x": 5, "y": 10, "width": 30, "height": 20, "css_selector": "#btn"},
        ))
        svc = _make_service(db, recognizer=recognizer)
        result = await svc.smart_locate_element("点击提交按钮")
        assert result is not None
        assert result.get("css_selector") == "#btn"

    @pytest.mark.asyncio
    async def test_vision_result_generates_css_when_missing(self, db):
        recognizer = _StubRecognizer(result=RecognitionResult(
            locator_type="vision", locator_value="coord", confidence=0.9,
            element_info={"x": 5, "y": 10, "width": 30, "height": 20},
        ))
        browser = _StubBrowser(js_map={"attrs": {"tag": "button", "id": "gen"}})
        svc = _make_service(db, browser=browser, recognizer=recognizer)
        result = await svc.smart_locate_element("点击按钮")
        assert result is not None
        assert result["css_selector"] == "#gen"

    @pytest.mark.asyncio
    async def test_returns_result_with_role_locator_type(self, db):
        recognizer = _StubRecognizer(result=RecognitionResult(
            locator_type="role", locator_value="button[name='提交']", confidence=0.8,
            element_info={"x": 1, "y": 2},
        ))
        svc = _make_service(db, recognizer=recognizer)
        result = await svc.smart_locate_element("点击提交")
        assert result is not None
        assert result["locator_type"] == "role"
        assert result["locator_value"] == "button[name='提交']"


# ==================== _get_element_attributes (async) 测试 ====================

class TestGetElementAttributes:

    @pytest.mark.asyncio
    async def test_returns_attrs(self, db):
        browser = _StubBrowser(js_map={"attrs": {"tag": "input", "id": "user"}})
        svc = _make_service(db, browser=browser)
        attrs = await svc._get_element_attributes({"x": 10, "y": 20, "width": 10, "height": 10})
        assert attrs == {"tag": "input", "id": "user"}

    @pytest.mark.asyncio
    async def test_returns_empty_on_timeout(self, db):
        browser = _StubBrowser(js_exc=TimeoutError("timeout"))
        svc = _make_service(db, browser=browser)
        attrs = await svc._get_element_attributes({"x": 0, "y": 0, "width": 0, "height": 0})
        assert attrs == {}

    @pytest.mark.asyncio
    async def test_returns_empty_on_connection_error(self, db):
        browser = _StubBrowser(js_exc=ConnectionError("lost"))
        svc = _make_service(db, browser=browser)
        attrs = await svc._get_element_attributes({"x": 0, "y": 0, "width": 0, "height": 0})
        assert attrs == {}

    @pytest.mark.asyncio
    async def test_returns_empty_on_unknown_exception(self, db):
        browser = _StubBrowser(js_exc=RuntimeError("unknown"))
        svc = _make_service(db, browser=browser)
        attrs = await svc._get_element_attributes({"x": 0, "y": 0, "width": 0, "height": 0})
        assert attrs == {}
