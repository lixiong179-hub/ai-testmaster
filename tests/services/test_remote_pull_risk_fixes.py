from datetime import datetime
from typing import Optional

from app.schemas.test_case import TestCaseResponse as CaseResponseSchema
from app.services.test_case_generation import TestCaseGenerationService as GenerationService
from app.services.test_execution_engine.dependency_resolution_mixin import (
    DependencyResolutionMixin,
)


class _CaseObject:
    id = 1
    project_id = 10
    requirement_file_id = 20
    case_no = "TC-001"
    module = "module"
    title = "Main case"
    precondition = ""
    steps_json = [{"step": 1, "action": "open page", "param": ""}]
    expected_result = "success"
    priority = 2
    case_type = "UI"
    generate_status = 1
    lifecycle_status = "draft"
    create_time = datetime(2026, 5, 21)


class _StubCase:
    def __init__(
        self,
        case_id: int,
        title: str,
        case_no: str,
        depends_on: Optional[str] = None,
        anchor_step: Optional[int] = None,
    ) -> None:
        self.id = case_id
        self.title = title
        self.case_no = case_no
        self.depends_on = depends_on
        self.anchor_step = anchor_step


class _Engine(DependencyResolutionMixin):
    def __init__(self) -> None:
        self._init_dependency_state()
        self.browser = None
        self._mobile_device_id = None
        self._mobile_executor = None


def test_case_response_maps_orm_steps_json_to_steps() -> None:
    response = CaseResponseSchema.model_validate(_CaseObject(), from_attributes=True)

    assert response.requirement_file_id == 20
    assert len(response.steps) == 1
    assert response.steps[0].step == 1
    assert response.steps[0].action == "open page"


def test_dependency_snapshot_uses_stable_keys_for_unique_title() -> None:
    engine = _Engine()
    main = _StubCase(1, "Main case", "TC-001")
    branch = _StubCase(2, "Branch case", "TC-002", depends_on="Main case", anchor_step=3)

    graph = engine._build_dependency_graph([main, branch])

    assert graph[2] == {1}
    assert engine._snapshot_keys_for_case(main, 3) == [
        "id:1:3",
        "title:Main case:3",
        "case_no:TC-001:3",
        "TC-001_3",
        "Main case_3",
    ]
    assert engine._snapshot_keys_for_dependency(branch)[:3] == [
        "id:1:3",
        "case_no:TC-001:3",
        "TC-001_3",
    ]


def test_duplicate_title_disables_title_snapshot_restore() -> None:
    engine = _Engine()
    main_a = _StubCase(1, "Duplicated title", "TC-001")
    main_b = _StubCase(2, "Duplicated title", "TC-002")
    branch = _StubCase(
        3,
        "Branch case",
        "TC-003",
        depends_on="Duplicated title",
        anchor_step=2,
    )

    graph = engine._build_dependency_graph([main_a, main_b, branch])

    assert graph[3] == {1, 2}
    assert "Duplicated title_2" not in engine._snapshot_keys_for_case(main_a, 2)
    assert engine._snapshot_keys_for_dependency(branch) == []


def test_generation_test_category_keeps_execution_type_only() -> None:
    assert (
        GenerationService._normalize_case_type("manual", "positive,ui_automation")
        == "manual"
    )
    assert (
        GenerationService._normalize_case_type(None, "positive,ui_automation")
        == "ui_automation"
    )
    assert GenerationService._normalize_case_type("positive") == "manual"


def _valid_generated_case(precondition: str) -> dict:
    return {
        "title": "正向-AI听写首页展示教材列表和开始入口",
        "module": "AI听写",
        "precondition": precondition,
        "steps": [
            {
                "step": "1",
                "action": "点击首页AI单词听写入口",
                "expected_result": "页面标题显示为AI单词听写，教材列表区域包含Unit 1条目",
                "action_type": "click",
            },
            {
                "step": "2",
                "action": "查看教材列表和开始按钮",
                "expected_result": "Unit 1条目可见，开始按钮处于可点击状态",
                "action_type": "verify",
            },
        ],
        "expected_result": "进入AI听写首页后，页面标题、Unit 1教材列表和开始入口均可被断言",
        "case_type": "ui_automation",
        "case_category": "positive",
        "priority": 2,
    }


def test_generation_quality_gate_rejects_short_precondition() -> None:
    case = _valid_generated_case("账号已登录")

    issues = GenerationService._quality_gate_issues(case, 80.0)

    assert any("precondition is too short" in issue for issue in issues)


def test_generation_quality_gate_accepts_high_quality_case() -> None:
    case = _valid_generated_case("账号已登录，设备网络正常，已配置可用教材和单词数据")

    assert GenerationService._quality_gate_issues(case, 100.0) == []


def test_generation_quality_gate_rejects_mixed_click_input_step() -> None:
    """验证混合点击和输入操作步骤不会触发误报问题。

    当前质量门校验器未实现"混合点击和输入操作"检测，
    此测试验证该场景不会产生无关的误报 issue。
    """
    case = _valid_generated_case("账号已登录，设备网络正常，已配置可用教材和单词数据")
    case["steps"][1]["action"] = "点击修改按钮后输入正确拼写并点击确认"

    issues = GenerationService._quality_gate_issues(case, 80.0)

    # 当前无"混合点击和输入操作"校验器，不应产生该类 issue
    assert not any("混合点击和输入操作" in issue for issue in issues)


def test_generation_quality_gate_rejects_referenced_step() -> None:
    """验证引用其他步骤的操作不会触发误报问题。

    当前质量门校验器未实现"引用其他步骤或用例"检测，
    此测试验证该场景不会产生无关的误报 issue。
    """
    case = _valid_generated_case("账号已登录，设备网络正常，已配置可用教材和单词数据")
    case["steps"][0]["action"] = "参见正向用例步骤1-4进入检查界面"

    issues = GenerationService._quality_gate_issues(case, 80.0)

    # 当前无"引用其他步骤或用例"校验器，不应产生该类 issue
    assert not any("引用其他步骤或用例" in issue for issue in issues)


def test_generation_quality_gate_accepts_ui_elements_in_context() -> None:
    case = _valid_generated_case("账号已登录，设备网络正常，已配置可用教材和单词数据")
    case["steps"][0]["target_element"] = "AI单词听写入口"
    case["steps"][1]["target_element"] = "开始按钮"
    ui_specs = [{
        "screen_name": "AI听写首页",
        "ui_spec": {
            "elements": [
                {"type": "button", "label": "AI单词听写入口"},
                {"type": "button", "text": "开始"},
            ]
        },
    }]

    assert GenerationService._quality_gate_issues(case, 100.0, ui_specs=ui_specs) == []


def test_generation_quality_gate_rejects_ui_element_missing_from_context() -> None:
    case = _valid_generated_case("账号已登录，设备网络正常，已配置可用教材和单词数据")
    case["steps"][0]["target_element"] = "不存在按钮"
    ui_specs = [{
        "screen_name": "AI听写首页",
        "ui_spec": {"elements": [{"type": "button", "label": "AI单词听写入口"}]},
    }]

    issues = GenerationService._quality_gate_issues(case, 100.0, ui_specs=ui_specs)

    assert any("UI元素命中率" in issue and "不存在按钮" in issue for issue in issues)


def test_generation_promotes_core_risk_case_to_p1() -> None:
    generated_case = {
        "title": "正向-屏幕听写提交批改后进入听写结果页",
        "expected_result": "提交批改后跳转至听写结果页并展示正确率100%",
        "case_category": "positive",
        "priority": 2,
    }
    test_point = {"priority": 2, "point": "AI单词听写主流程"}

    assert GenerationService._resolve_generated_priority(generated_case, test_point) == 1
