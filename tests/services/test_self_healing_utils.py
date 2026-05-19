import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.test_execution_engine.self_healing_utils_mixin import SelfHealingUtilsMixin


class _ConcreteMixin(SelfHealingUtilsMixin):
    def __init__(self, db):
        self.db = db
        self._self_healing_attempts = 5
        self._self_healing_successes = 3


class TestSanitizeCssIdentifier:
    def test_normal_text(self):
        result = SelfHealingUtilsMixin._sanitize_css_identifier("myButton")
        assert result == "myButton"

    def test_special_chars(self):
        result = SelfHealingUtilsMixin._sanitize_css_identifier("my-btn!@#")
        assert result == "my-btn"

    def test_multiple_dashes(self):
        result = SelfHealingUtilsMixin._sanitize_css_identifier("my---btn")
        assert result == "my-btn"

    def test_leading_trailing_dashes(self):
        result = SelfHealingUtilsMixin._sanitize_css_identifier("-my-btn-")
        assert result == "my-btn"

    def test_empty_string(self):
        result = SelfHealingUtilsMixin._sanitize_css_identifier("")
        assert result == ""

    def test_only_special_chars(self):
        result = SelfHealingUtilsMixin._sanitize_css_identifier("!@#$%")
        assert result == ""


class TestBuildHealedSelector:
    def setup_method(self):
        self.mixin = _ConcreteMixin(MagicMock())

    def test_by_id(self):
        result = self.mixin._build_healed_selector({"id": "submit-btn"})
        assert result == "#submit-btn"

    def test_by_name(self):
        result = self.mixin._build_healed_selector({"name": "username"})
        assert result == "[name='username']"

    def test_by_placeholder(self):
        result = self.mixin._build_healed_selector({"placeholder": "enter username"})
        assert result is not None
        assert "placeholder" in result

    def test_by_class(self):
        result = self.mixin._build_healed_selector({"class": "btn primary", "tag": "button"})
        assert result is not None
        assert "btn" in result

    def test_by_class_no_tag(self):
        result = self.mixin._build_healed_selector({"class": "btn primary"})
        assert result is not None

    def test_by_tag_and_type(self):
        result = self.mixin._build_healed_selector({"tag": "input", "type": "text"})
        assert result == "input[type='text']"

    def test_by_tag_only(self):
        result = self.mixin._build_healed_selector({"tag": "button"})
        assert result == "button"

    def test_empty_attrs(self):
        result = self.mixin._build_healed_selector({})
        assert result is None

    def test_id_priority_over_name(self):
        result = self.mixin._build_healed_selector({"id": "myId", "name": "myName"})
        assert result == "#myId"


class TestGetSelfHealingSummary:
    def test_summary(self):
        mixin = _ConcreteMixin(MagicMock())
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.AI_SELF_HEALING_ENABLED = True
            mock_settings.BROWSERBASE_API_KEY = ""
            mock_settings.BROWSERBASE_PROJECT_ID = ""
            summary = mixin.get_self_healing_summary()
            assert summary["self_healing_attempts"] == 5
            assert summary["self_healing_successes"] == 3
            assert summary["self_healing_success_rate"] == 0.6
            assert summary["self_healing_enabled"] is True

    def test_zero_attempts(self):
        mixin = _ConcreteMixin(MagicMock())
        mixin._self_healing_attempts = 0
        mixin._self_healing_successes = 0
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.AI_SELF_HEALING_ENABLED = False
            mock_settings.BROWSERBASE_API_KEY = ""
            mock_settings.BROWSERBASE_PROJECT_ID = ""
            summary = mixin.get_self_healing_summary()
            assert summary["self_healing_success_rate"] == 0.0


class TestUpdateLocatorAfterHealing:
    @pytest.mark.asyncio
    async def test_empty_selector(self):
        mixin = _ConcreteMixin(MagicMock())
        result = await mixin._update_locator_after_healing(1, "")
        assert result is False

    @pytest.mark.asyncio
    async def test_locator_not_found(self):
        mixin = _ConcreteMixin(MagicMock())
        mixin.db.query.return_value.filter.return_value.first.return_value = None
        result = await mixin._update_locator_after_healing(999, "#new-selector")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_success(self, db, testUser):
        from app.models.test_case import TestCase, TestStep
        from app.models.project import Project
        proj = Project(
            name="sh_test_proj",
            description="test",
            status=1,
            user_id=testUser.id,
            project_type="web",
        )
        db.add(proj)
        db.flush()
        tc = TestCase(
            project_id=proj.id,
            case_no="TC_SH_TEST",
            module="self_healing_test",
            title="self healing test",
            precondition="none",
            expected_result="ok",
            priority=1,
            case_type="UI",
            steps_json=[],
        )
        db.add(tc)
        db.flush()
        step = TestStep(
            test_case_id=tc.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        mixin = _ConcreteMixin(db)
        from app.models.element_locator import ElementLocator
        locator = ElementLocator(
            step_id=step.id,
            css_selector="#old",
            source="manual",
            version=1,
        )
        db.add(locator)
        db.flush()
        result = await mixin._update_locator_after_healing(locator.id, "#new", "#old")
        assert isinstance(result, bool)
        db.query(ElementLocator).filter(ElementLocator.id == locator.id).delete(synchronize_session=False)
        db.query(TestStep).filter(TestStep.id == step.id).delete(synchronize_session=False)
        db.query(TestCase).filter(TestCase.id == tc.id).delete(synchronize_session=False)
        db.query(Project).filter(Project.id == proj.id).delete(synchronize_session=False)
        db.commit()

    @pytest.mark.asyncio
    async def test_update_exception(self):
        mixin = _ConcreteMixin(MagicMock())
        mock_locator = MagicMock()
        mock_locator.version = 1
        mock_locator.css_selector = "#old"
        mixin.db.query.return_value.filter.return_value.first.return_value = mock_locator
        mixin.db.execute.side_effect = Exception("db error")
        result = await mixin._update_locator_after_healing(1, "#new")
        assert result is False


class TestGetNlDescription:
    @pytest.mark.asyncio
    async def test_step_not_found(self):
        mixin = _ConcreteMixin(MagicMock())
        mixin.db.query.return_value.filter.return_value.first.return_value = None
        result = await mixin._get_nl_description(999)
        assert result == ""

    @pytest.mark.asyncio
    async def test_step_with_action(self):
        mixin = _ConcreteMixin(MagicMock())
        mock_step = MagicMock()
        mock_step.action = "点击登录"
        mock_step.input_value = None
        mixin.db.query.return_value.filter.return_value.first.return_value = mock_step
        result = await mixin._get_nl_description(1)
        assert "点击登录" in result

    @pytest.mark.asyncio
    async def test_step_with_input_value(self):
        mixin = _ConcreteMixin(MagicMock())
        mock_step = MagicMock()
        mock_step.action = "输入"
        mock_step.input_value = "用户名"
        mixin.db.query.return_value.filter.return_value.first.return_value = mock_step
        result = await mixin._get_nl_description(1)
        assert "输入" in result
        assert "用户名" in result

    @pytest.mark.asyncio
    async def test_step_no_action_fallback_to_locator(self):
        mixin = _ConcreteMixin(MagicMock())
        mock_step = MagicMock()
        mock_step.action = ""
        mock_step.input_value = None
        mock_locator = MagicMock()
        mock_locator.element_description = "登录按钮"
        mixin.db.query.return_value.filter.return_value.first.side_effect = [mock_step, mock_locator]
        result = await mixin._get_nl_description(1)
        assert result == "登录按钮"

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        mixin = _ConcreteMixin(MagicMock())
        mixin.db.query.side_effect = Exception("db error")
        result = await mixin._get_nl_description(1)
        assert result == ""
