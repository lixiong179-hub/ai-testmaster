"""TestGenerationAgent 专用工具集 - 测试用例创建与语法校验。

设计目的：
    将测试用例生成场景的两个核心工具与 TestGenerationAgent 共置一处，
    便于后续 Agent（failure_analysis 等）按场景组织自有工具。工具基类
    复用 app.services.agent.tools.base_tool.Tool，经 ToolRegistry 注册后
    由 AgentRuntime 在 function calling 循环中调用。

工具清单：
    - CreateTestCaseTool : 写入 test_cases + test_steps，返回 test_case_id
    - ValidateTestCaseSyntaxTool : 校验步骤结构与 action 枚举，返回 warnings

action 枚举与 TestStep.action_type 注释保持一致
（click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress），
集中维护避免多处硬编码。
"""
from __future__ import annotations

from typing import Any, Dict, List

from loguru import logger

from app.models.enums import TestCaseLifecycleStatus
from app.models.test_case import TestCase, TestStep
from app.services.agent.tools.base_tool import Tool, ToolContext, ToolResult
from app.services.case_number_service import CaseNumberService

# 合法 action 枚举，与 TestStep.action_type 对齐
VALID_ACTIONS: frozenset[str] = frozenset({
    "click", "input", "navigate", "verify", "wait", "scroll",
    "hover", "select", "captcha", "refresh", "keypress",
})

# 工具入参 priority(字符串) → 模型 priority(1高/2中/3低)
_PRIORITY_MAP: Dict[str, int] = {"high": 1, "medium": 2, "low": 3}


def _normalize_step(step_data: Dict[str, Any]) -> Dict[str, Any]:
    """将工具入参 step（action/target/value/expected）归一化为模型字段。

    兼容两种 key 风格：Agent 友好型（action/target/value/expected）与
    模型原生平铺型（action_type/target_element/input_value/expected_result）。
    """
    action = step_data.get("action") or ""
    action_type = step_data.get("action_type")
    return {
        # action_text 作为步骤描述文本，优先取 description，退化为 action 本身
        "action_text": step_data.get("description") or action,
        "action_type": action if action in VALID_ACTIONS else (action_type or None),
        "target_element": step_data.get("target") or step_data.get("target_element") or None,
        "input_value": step_data.get("value") or step_data.get("input_value") or None,
        "expected": step_data.get("expected") or step_data.get("expected_result") or "",
    }


class CreateTestCaseTool(Tool):
    """创建测试用例（写入 test_cases 表），返回 test_case_id。"""

    name = "create_test_case"
    description = "创建测试用例（写入 test_cases 表），返回 test_case_id"
    parameters_schema = {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer", "description": "项目 ID"},
            "title": {"type": "string", "description": "用例标题"},
            "steps": {
                "type": "array",
                "description": "步骤列表，每项含 action(必填)/target/value/expected",
                "items": {"type": "object"},
            },
            "preconditions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "前置条件列表，默认空",
            },
            "priority": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "优先级，默认 medium",
            },
        },
        "required": ["project_id", "title", "steps"],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """写入一条测试用例及其结构化步骤。

        case_no 通过 CaseNumberService.generate_async 并发安全生成；
        module/case_type/precondition 等必填字段由工具按场景补默认值，
        避免要求 LLM 感知底层模型约束。
        """
        if context.db is None:
            return ToolResult(success=False, error="数据库会话不可用")
        project_id = params.get("project_id") or context.project_id
        if project_id is None:
            return ToolResult(success=False, error="project_id 不可用")
        title: str = params.get("title") or ""
        if not title:
            return ToolResult(success=False, error="title 不可为空")
        steps: List[Dict[str, Any]] = params.get("steps", []) or []
        preconditions: List[str] = params.get("preconditions", []) or []
        priority = _PRIORITY_MAP.get(params.get("priority", "medium"), 2)
        try:
            case_no = await CaseNumberService.generate_async(project_id, context.db)
            case = TestCase(
                case_no=case_no,
                project_id=project_id,
                module="AI生成",
                title=title,
                precondition="\n".join(preconditions) if preconditions else "无",
                steps_json=steps,
                expected_result=self._derive_expected(steps),
                priority=priority,
                case_type="UI",
                generate_status=1,
                lifecycle_status=TestCaseLifecycleStatus.DRAFT.value,
            )
            context.db.add(case)
            await context.db.flush()
            await self._persist_steps(context.db, case.id, steps)
            await context.db.commit()
            await context.db.refresh(case)
            logger.info(f"create_test_case 成功: id={case.id} case_no={case_no}")
            return ToolResult(
                success=True,
                output={"test_case_id": case.id, "title": case.title},
            )
        except Exception as e:
            await context.db.rollback()
            logger.exception(f"create_test_case 失败: {e}")
            return ToolResult(success=False, error=f"{type(e).__name__}: {e}")

    @staticmethod
    def _derive_expected(steps: List[Dict[str, Any]]) -> str:
        """推导用例整体预期结果：取最后一步 expected，缺失则用默认文案。"""
        last_expected = next(
            (s.get("expected") for s in reversed(steps)
             if isinstance(s, dict) and s.get("expected")),
            None,
        )
        return last_expected or "所有步骤执行成功"

    @staticmethod
    async def _persist_steps(db: Any, case_id: int, steps: List[Dict[str, Any]]) -> None:
        """将步骤列表写入 test_steps 表，与 create_test_case CRUD 逻辑对齐。"""
        for idx, raw in enumerate(steps, start=1):
            if not isinstance(raw, dict):
                continue
            norm = _normalize_step(raw)
            db.add(TestStep(
                test_case_id=case_id,
                step_number=idx,
                action=norm["action_text"],
                expected_result=norm["expected"],
                action_type=norm["action_type"],
                input_value=norm["input_value"],
                target_element=norm["target_element"],
                is_business_view=1,
                is_technical_view=1,
            ))


class ValidateTestCaseSyntaxTool(Tool):
    """校验测试用例步骤完整性（action/target/value/expected），返回 warnings 列表。"""

    name = "validate_test_case_syntax"
    description = "校验测试用例步骤完整性（action/target/value/expected），返回 warnings 列表"
    parameters_schema = {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "description": "测试用例步骤列表",
                "items": {"type": "object"},
            },
        },
        "required": ["steps"],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """纯内存校验：action 必填且须在合法枚举内，target/value/expected 可选。"""
        steps: List[Dict[str, Any]] = params.get("steps", []) or []
        warnings: List[str] = []
        if not steps:
            warnings.append("步骤列表为空")
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                warnings.append(f"步骤 {idx} 不是 dict")
                continue
            action = step.get("action")
            if not action:
                warnings.append(f"步骤 {idx} 缺少 action")
                continue
            if action not in VALID_ACTIONS:
                warnings.append(
                    f"步骤 {idx} action 非法: {action}，合法值 {sorted(VALID_ACTIONS)}"
                )
        return ToolResult(
            success=True,
            output={"valid": len(warnings) == 0, "warnings": warnings},
            metadata={"step_count": len(steps)},
        )


__all__ = ["CreateTestCaseTool", "ValidateTestCaseSyntaxTool"]
