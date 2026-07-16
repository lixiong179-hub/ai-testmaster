"""跨设备用例迁移服务测试 - 正常/空值/异常/边界场景覆盖。

迁移说明:
    DB 相关测试（TestMigrateSingleCase / TestBatchMigration / TestDeviceFilter）
    已迁移到 async + async_db fixture 模式，与 tests/services/conftest.py 对齐。
    纯逻辑测试（TestMigrationPrompt / TestExcelNormalize / TestAIClientIntegration）
    保持 sync，不依赖 DB。
"""
import json
from typing import Any, Dict

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.test_case import (
    TestCase,
    disable_lifecycle_transition,
    enable_lifecycle_transition,
)
from app.services.case_migration import CaseMigrationService

TestCase.__test__ = False


class MockAIClient:
    """模拟AI客户端，返回预设的迁移结果。"""

    def __init__(self, response_type: str = "adapted") -> None:
        self.response_type: str = response_type

    def chat(self, prompt: str) -> str:
        if self.response_type == "adapted":
            return json.dumps({
                "migration_type": "adapted",
                "confidence": 0.9,
                "adapted_cases": [{
                    "title": "手机端-通过底部Tab导航到设置页",
                    "precondition": "在手机端已登录",
                    "precondition_changes": [
                        {"original": "在平板端已登录", "adapted": "在手机端已登录", "reason": "设备描述适配"}
                    ],
                    "steps": [
                        {"step": 1, "action": "点击底部Tab栏的'更多'", "expected_result": "显示更多菜单", "action_type": "click"}
                    ],
                    "expected_result": "跳转到设置页面",
                    "expected_result_changes": [
                        {"original": "右侧显示设置面板", "adapted": "跳转到设置页面", "reason": "手机端无侧面板"}
                    ],
                    "priority": 2,
                    "priority_change": None,
                }],
                "step_changes": [
                    {"case_index": 0, "step_index": 0, "change_type": "modified", "reason": "侧边栏→底部Tab", "original_step": "点击侧边栏的设置", "new_step": "点击底部Tab栏的'更多'"}
                ],
                "split_reason": None,
                "new_scenarios": ["手机端需覆盖底部Tab导航切换"],
                "deprecated_scenarios": [],
            })
        elif self.response_type == "split":
            return json.dumps({
                "migration_type": "split",
                "confidence": 0.85,
                "adapted_cases": [
                    {"title": "查看答题方案A", "precondition": "在手机端已登录", "steps": [{"step": 1, "action": "点击方案A卡片", "expected_result": "跳转到方案A详情页", "action_type": "click"}], "expected_result": "显示方案A详情", "priority": 2, "priority_change": None, "precondition_changes": [], "expected_result_changes": []},
                    {"title": "查看答题方案B", "precondition": "在手机端已登录", "steps": [{"step": 1, "action": "点击方案B卡片", "expected_result": "跳转到方案B详情页", "action_type": "click"}], "expected_result": "显示方案B详情", "priority": 2, "priority_change": None, "precondition_changes": [], "expected_result_changes": []},
                ],
                "step_changes": [],
                "split_reason": "手机端无法同屏对比，需拆分为独立查看",
                "new_scenarios": [],
                "deprecated_scenarios": [],
            })
        elif self.response_type == "deprecated":
            return json.dumps({
                "migration_type": "deprecated",
                "confidence": 0.95,
                "adapted_cases": [],
                "step_changes": [],
                "split_reason": None,
                "new_scenarios": [],
                "deprecated_scenarios": ["分屏功能手机端不支持"],
            })
        elif self.response_type == "invalid_json":
            return "这不是JSON格式"
        elif self.response_type == "missing_field":
            return json.dumps({"adapted_cases": []})
        elif self.response_type == "empty":
            return ""
        return json.dumps({
            "migration_type": "adapted", "confidence": 0.5,
            "adapted_cases": [{
                "title": "默认迁移用例", "precondition": "已登录",
                "steps": [{"step": 1, "action": "执行操作", "expected_result": "操作成功", "action_type": "click"}],
                "expected_result": "操作成功", "priority": 2,
                "precondition_changes": [], "expected_result_changes": [], "priority_change": None,
            }],
            "step_changes": [], "new_scenarios": [], "deprecated_scenarios": [],
        })


@pytest_asyncio.fixture
async def migration_service(async_db: AsyncSession) -> CaseMigrationService:
    return CaseMigrationService(async_db)


@pytest_asyncio.fixture
async def tablet_case(
    async_db: AsyncSession, async_test_project: Project
) -> TestCase:
    enable_lifecycle_transition()
    case = TestCase(
        project_id=async_test_project.id,
        case_no="TC_TABLET_001",
        module="设置模块",
        title="通过侧边栏导航到设置页",
        precondition="在平板端已登录",
        steps_json=[{"step": 1, "action": "点击侧边栏的设置", "expected_result": "右侧显示设置面板", "action_type": "click"}],
        expected_result="右侧显示设置面板",
        priority=2,
        case_type="ui_automation",
        generate_status=1,
        target_device="tablet",
        lifecycle_status="active",
    )
    async_db.add(case)
    await async_db.flush()
    disable_lifecycle_transition()
    return case


@pytest_asyncio.fixture
async def api_case(
    async_db: AsyncSession, async_test_project: Project
) -> TestCase:
    enable_lifecycle_transition()
    case = TestCase(
        project_id=async_test_project.id,
        case_no="TC_API_001",
        module="接口模块",
        title="登录接口参数校验",
        precondition="无",
        steps_json=[{"step": 1, "action": "发送登录请求", "expected_result": "返回400错误", "action_type": "verify"}],
        expected_result="返回400错误",
        priority=2,
        case_type="api_automation",
        generate_status=1,
        target_device="tablet",
        lifecycle_status="active",
    )
    async_db.add(case)
    await async_db.flush()
    disable_lifecycle_transition()
    return case


class TestMigrateSingleCase:
    """单条用例迁移测试。"""

    async def test_api_case_cloned(
        self, migration_service: CaseMigrationService,
        api_case: TestCase, async_test_project: Project,
    ) -> None:
        result = await migration_service.migrate_single_case(
            source_case_id=api_case.id,
            target_device="phone",
            target_project_id=async_test_project.id,
            source_device="tablet",
        )
        assert result["success"] is True
        assert result["migration_type"] == "cloned"
        assert result["new_case_id"] is not None
        stmt = select(TestCase).where(TestCase.id == result["new_case_id"])
        new_case = (await migration_service.db.execute(stmt)).scalar_one_or_none()
        assert new_case is not None
        assert new_case.target_device == "phone"
        assert new_case.migration_type == "cloned"
        assert new_case.migration_source_id == api_case.id
        assert new_case.lifecycle_status == "draft"

    async def test_ui_case_ai_adapted(
        self, migration_service: CaseMigrationService,
        tablet_case: TestCase, async_test_project: Project,
    ) -> None:
        ai_client = MockAIClient("adapted")
        result = await migration_service.migrate_single_case(
            source_case_id=tablet_case.id,
            target_device="phone",
            target_project_id=async_test_project.id,
            source_device="tablet",
            ai_client=ai_client,
        )
        assert result["success"] is True
        assert result["migration_type"] == "adapted"
        assert len(result["new_case_ids"]) == 1
        stmt = select(TestCase).where(TestCase.id == result["new_case_ids"][0])
        new_case = (await migration_service.db.execute(stmt)).scalar_one_or_none()
        assert new_case is not None
        assert new_case.target_device == "phone"
        assert new_case.migration_type == "adapted"
        assert "手机端" in new_case.precondition

    async def test_ui_case_ai_split(
        self, migration_service: CaseMigrationService,
        tablet_case: TestCase, async_test_project: Project,
    ) -> None:
        ai_client = MockAIClient("split")
        result = await migration_service.migrate_single_case(
            source_case_id=tablet_case.id,
            target_device="phone",
            target_project_id=async_test_project.id,
            source_device="tablet",
            ai_client=ai_client,
        )
        assert result["success"] is True
        assert result["migration_type"] == "split"
        assert len(result["new_case_ids"]) == 2

    async def test_ui_case_ai_deprecated(
        self, migration_service: CaseMigrationService,
        tablet_case: TestCase, async_test_project: Project,
    ) -> None:
        ai_client = MockAIClient("deprecated")
        result = await migration_service.migrate_single_case(
            source_case_id=tablet_case.id,
            target_device="phone",
            target_project_id=async_test_project.id,
            source_device="tablet",
            ai_client=ai_client,
        )
        assert result["success"] is True
        assert result["migration_type"] == "deprecated"
        assert len(result.get("new_case_ids", [])) == 0

    async def test_source_case_not_found(
        self, migration_service: CaseMigrationService, async_test_project: Project,
    ) -> None:
        result = await migration_service.migrate_single_case(
            source_case_id=99999,
            target_device="phone",
            target_project_id=async_test_project.id,
        )
        assert result["success"] is False
        assert "不存在" in result["error"]

    async def test_ui_case_without_ai_client(
        self, migration_service: CaseMigrationService,
        tablet_case: TestCase, async_test_project: Project,
    ) -> None:
        result = await migration_service.migrate_single_case(
            source_case_id=tablet_case.id,
            target_device="phone",
            target_project_id=async_test_project.id,
            ai_client=None,
        )
        assert result["success"] is False
        assert "AI客户端" in result["error"]

    async def test_ai_returns_invalid_json(
        self, migration_service: CaseMigrationService,
        tablet_case: TestCase, async_test_project: Project,
    ) -> None:
        ai_client = MockAIClient("invalid_json")
        result = await migration_service.migrate_single_case(
            source_case_id=tablet_case.id,
            target_device="phone",
            target_project_id=async_test_project.id,
            ai_client=ai_client,
        )
        assert result["success"] is False
        assert "解析失败" in result["error"]


class TestBatchMigration:
    """批量迁移预览、提交与回滚。"""

    async def test_preview_batch_mixes_api_and_ui_cases(
        self,
        migration_service: CaseMigrationService,
        api_case: TestCase,
        tablet_case: TestCase,
        async_test_project: Project,
    ) -> None:
        result = await migration_service.preview_batch(
            source_case_ids=[api_case.id, tablet_case.id],
            target_device="phone",
            target_project_id=async_test_project.id,
            source_device="tablet",
            target_ui_specs="手机端设置页",
            ai_client=MockAIClient("adapted"),
        )
        assert result["summary"]["total"] == 2
        assert result["summary"]["success"] == 2
        assert result["summary"]["cloned"] == 1
        assert result["summary"]["adapted"] == 1
        assert result["items"][0]["batch_id"] == result["batch_id"]

    async def test_commit_and_rollback_batch(
        self,
        migration_service: CaseMigrationService,
        tablet_case: TestCase,
        async_test_project: Project,
    ) -> None:
        preview = await migration_service.preview_batch(
            source_case_ids=[tablet_case.id],
            target_device="phone",
            target_project_id=async_test_project.id,
            source_device="tablet",
            target_ui_specs="手机端设置页",
            ai_client=MockAIClient("adapted"),
        )
        commit = await migration_service.commit_batch(
            preview_items=preview["items"],
            target_project_id=async_test_project.id,
            target_device="phone",
        )
        assert commit["success"] is True
        assert len(commit["created_case_ids"]) == 1
        batch = await migration_service.get_batch_cases(preview["batch_id"])
        assert batch["case_count"] == 1
        rollback = await migration_service.rollback_batch(preview["batch_id"])
        assert rollback["rolled_back_count"] == 1
        batch_after = await migration_service.get_batch_cases(preview["batch_id"])
        assert batch_after["case_count"] == 0

    async def test_ai_returns_missing_field(
        self, migration_service: CaseMigrationService,
        tablet_case: TestCase, async_test_project: Project,
    ) -> None:
        ai_client = MockAIClient("missing_field")
        result = await migration_service.migrate_single_case(
            source_case_id=tablet_case.id,
            target_device="phone",
            target_project_id=async_test_project.id,
            ai_client=ai_client,
        )
        assert result["success"] is False
        assert "解析失败" in result["error"]

    async def test_ai_returns_empty(
        self, migration_service: CaseMigrationService,
        tablet_case: TestCase, async_test_project: Project,
    ) -> None:
        ai_client = MockAIClient("empty")
        result = await migration_service.migrate_single_case(
            source_case_id=tablet_case.id,
            target_device="phone",
            target_project_id=async_test_project.id,
            ai_client=ai_client,
        )
        assert result["success"] is False

    async def test_batch_id_consistency(
        self, migration_service: CaseMigrationService,
        tablet_case: TestCase, async_test_project: Project,
    ) -> None:
        ai_client = MockAIClient("split")
        result = await migration_service.migrate_single_case(
            source_case_id=tablet_case.id,
            target_device="phone",
            target_project_id=async_test_project.id,
            ai_client=ai_client,
        )
        batch_id = result["batch_id"]
        for case_id in result["new_case_ids"]:
            stmt = select(TestCase).where(TestCase.id == case_id)
            case = (await migration_service.db.execute(stmt)).scalar_one_or_none()
            assert case.migration_batch_id == batch_id

    async def test_same_device_rejected(
        self, migration_service: CaseMigrationService,
        tablet_case: TestCase, async_test_project: Project,
    ) -> None:
        result = await migration_service.migrate_single_case(
            source_case_id=tablet_case.id,
            target_device="tablet",
            target_project_id=async_test_project.id,
            source_device="tablet",
        )
        assert result["success"] is False
        assert "相同" in result["error"]

    async def test_target_project_not_found(
        self, migration_service: CaseMigrationService, tablet_case: TestCase,
    ) -> None:
        result = await migration_service.migrate_single_case(
            source_case_id=tablet_case.id,
            target_device="phone",
            target_project_id=99999,
        )
        assert result["success"] is False
        assert "项目不存在" in result["error"]


class TestMigrationPrompt:
    """迁移Prompt构建测试。"""

    def test_build_migration_prompt_tablet_to_phone(self) -> None:
        from app.services.prompt_builder.migration_prompt import build_migration_prompt
        source: Dict[str, Any] = {
            "title": "通过侧边栏导航",
            "precondition": "在平板端已登录",
            "steps_json": [{"step": 1, "action": "点击侧边栏", "action_type": "click"}],
            "expected_result": "右侧显示面板",
            "priority": 2,
            "case_type": "ui_automation",
        }
        prompt = build_migration_prompt(source, "tablet", "phone")
        assert "tablet" in prompt
        assert "phone" in prompt
        assert "侧边栏" in prompt or "导航" in prompt
        assert "migration_type" in prompt
        assert "cloned" in prompt
        assert "adapted" in prompt
        assert "split" in prompt

    def test_build_migration_prompt_with_ui_specs(self) -> None:
        from app.services.prompt_builder.migration_prompt import build_migration_prompt
        source: Dict[str, Any] = {
            "title": "测试", "precondition": "", "steps_json": [],
            "expected_result": "", "priority": 2, "case_type": "ui_automation",
        }
        prompt = build_migration_prompt(source, "tablet", "phone", target_ui_specs="底部Tab栏：首页/发现/我的")
        assert "底部Tab栏" in prompt

    def test_build_migration_prompt_phone_to_tablet(self) -> None:
        from app.services.prompt_builder.migration_prompt import build_migration_prompt
        source: Dict[str, Any] = {
            "title": "测试", "precondition": "", "steps_json": [],
            "expected_result": "", "priority": 2, "case_type": "ui_automation",
        }
        prompt = build_migration_prompt(source, "phone", "tablet")
        assert "phone" in prompt
        assert "tablet" in prompt


class TestExcelNormalize:
    """Excel规范化预处理测试。"""

    def test_normalize_detects_format(self, tmp_path: Any) -> None:
        import pandas as pd
        from app.services.test_case_view.excel_normalize_mixin import ExcelNormalizeMixin
        mixin = ExcelNormalizeMixin()
        file_path = tmp_path / "test_format.xlsx"
        df = pd.DataFrame({"用例描述": ["测试1"], "操作步骤": ["点击按钮"], "期望结果": ["显示成功"]})
        df.to_excel(str(file_path), index=False)
        result = mixin.normalize_excel(str(file_path))
        assert result["detected_format"] == "functional"
        assert "column_mapping" in result

    def test_normalize_empty_file(self, tmp_path: Any) -> None:
        import pandas as pd
        from app.services.test_case_view.excel_normalize_mixin import ExcelNormalizeMixin
        mixin = ExcelNormalizeMixin()
        file_path = tmp_path / "test_empty.xlsx"
        df = pd.DataFrame()
        df.to_excel(str(file_path), index=False)
        result = mixin.normalize_excel(str(file_path))
        assert len(result["issues"]) > 0

    def test_column_mapping_inference(self) -> None:
        from app.services.test_case_view.excel_normalize_mixin import ExcelNormalizeMixin
        mixin = ExcelNormalizeMixin()
        columns = ["用例描述", "操作步骤", "期望结果", "前置条件", "优先级"]
        mapping = mixin._infer_column_mapping(columns)
        assert mapping.get("用例描述") == "title"
        assert mapping.get("操作步骤") == "action"
        assert mapping.get("期望结果") == "expected_result"

    def test_mapping_confidence(self) -> None:
        from app.services.test_case_view.excel_normalize_mixin import ExcelNormalizeMixin
        mixin = ExcelNormalizeMixin()
        full_mapping: Dict[str, str] = {"用例描述": "title", "操作步骤": "action", "期望结果": "expected_result"}
        confidence = mixin._calc_mapping_confidence(full_mapping, ["用例描述", "操作步骤", "期望结果"])
        assert confidence == 1.0
        partial_mapping: Dict[str, str] = {"用例描述": "title"}
        confidence = mixin._calc_mapping_confidence(partial_mapping, ["用例描述"])
        assert confidence < 1.0


class TestDeviceFilter:
    """设备类型筛选测试。"""

    async def test_filter_by_target_device(
        self, async_db: AsyncSession, async_test_project: Project
    ) -> None:
        enable_lifecycle_transition()
        tablet_case = TestCase(
            project_id=async_test_project.id, case_no="FILTER_T_001", module="测试模块",
            title="平板用例", precondition="无", steps_json=[], expected_result="pass",
            priority=2, case_type="ui_automation", generate_status=1,
            target_device="tablet", lifecycle_status="draft",
        )
        phone_case = TestCase(
            project_id=async_test_project.id, case_no="FILTER_P_001", module="测试模块",
            title="手机用例", precondition="无", steps_json=[], expected_result="pass",
            priority=2, case_type="ui_automation", generate_status=1,
            target_device="phone", lifecycle_status="draft",
        )
        general_case = TestCase(
            project_id=async_test_project.id, case_no="FILTER_G_001", module="测试模块",
            title="通用用例", precondition="无", steps_json=[], expected_result="pass",
            priority=2, case_type="ui_automation", generate_status=1,
            target_device=None, lifecycle_status="draft",
        )
        async_db.add_all([tablet_case, phone_case, general_case])
        await async_db.flush()
        disable_lifecycle_transition()
        stmt_tablet = select(TestCase).where(
            TestCase.project_id == async_test_project.id,
            TestCase.target_device == "tablet",
            TestCase.is_deleted.is_(False),
        )
        tablet_results = (await async_db.execute(stmt_tablet)).scalars().all()
        assert all(c.target_device == "tablet" for c in tablet_results)
        stmt_general = select(TestCase).where(
            TestCase.project_id == async_test_project.id,
            TestCase.target_device.is_(None),
            TestCase.is_deleted.is_(False),
        )
        general_results = (await async_db.execute(stmt_general)).scalars().all()
        assert all(c.target_device is None for c in general_results)


class TestAIClientIntegration:
    """AI 客户端集成测试 — 验证 _get_ai_client 与 _call_ai 标准 complete() 接口。

    回归覆盖：
        - _get_ai_client 返回非 None 且具备 complete() 方法的 OpenAIClient
        - _call_ai 优先使用 complete() 接口，提取 AIResponse.content
        - complete() 返回 None / 抛异常时 _call_ai 返回 None
        - ai_client=None 时不崩溃
    """

    def test_get_ai_client_returns_complete_client(self) -> None:
        """_get_ai_client 返回非 None 且具备 complete() 方法的客户端"""
        from app.api.v1.endpoints import case_migration
        case_migration._ai_client_instance = None
        client = case_migration._get_ai_client()
        assert client is not None
        assert hasattr(client, "complete")

    def test_call_ai_with_complete_interface(self) -> None:
        """_call_ai 优先使用 complete() 接口，提取 AIResponse.content"""
        from app.ai.client import AIResponse, TokenUsage
        from app.services.case_migration._ai_mixin import CaseMigrationAiMixin

        class CompleteClient:
            def complete(self, prompt: str) -> AIResponse:
                return AIResponse(
                    content='{"migration_type": "adapted"}',
                    usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
                )

        mixin = CaseMigrationAiMixin()
        result = mixin._call_ai(CompleteClient(), "test prompt")
        assert result == '{"migration_type": "adapted"}'

    def test_call_ai_with_complete_returns_none(self) -> None:
        """complete() 返回 None 时 _call_ai 返回 None"""
        from app.services.case_migration._ai_mixin import CaseMigrationAiMixin

        class NoneCompleteClient:
            def complete(self, prompt: str) -> None:
                return None

        mixin = CaseMigrationAiMixin()
        result = mixin._call_ai(NoneCompleteClient(), "test prompt")
        assert result is None

    def test_call_ai_with_none_client(self) -> None:
        """ai_client=None 时返回 None 不崩溃"""
        from app.services.case_migration._ai_mixin import CaseMigrationAiMixin
        mixin = CaseMigrationAiMixin()
        result = mixin._call_ai(None, "test prompt")
        assert result is None

    def test_call_ai_complete_raises_exception(self) -> None:
        """complete() 抛异常时 _call_ai 返回 None"""
        from app.services.case_migration._ai_mixin import CaseMigrationAiMixin

        class RaisingClient:
            def complete(self, prompt: str) -> None:
                raise RuntimeError("API timeout")

        mixin = CaseMigrationAiMixin()
        result = mixin._call_ai(RaisingClient(), "test prompt")
        assert result is None
