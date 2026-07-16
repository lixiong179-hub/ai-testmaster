"""test_case_generation - 用例校验与持久化（组合模式组件）。

合并自 validate_mixin.py + _ui_validation_mixin.py + _quality_gate_mixin.py，
提供 CaseValidator 类负责生成用例的 UI 元素可执行性校验、质量门禁判定与
DB 持久化（含前置条件解析）。

quality_validator.py + _quality_field_validators.py + _quality_step_validators.py
因被外部模块引用保留独立文件，本模块不合并。
"""
import inspect
import re
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import DEFAULT_AI_FALLBACK_CASE_TYPE, normalize_priority
from app.models.test_case import TestCase, TestStep
from app.services.case_number_service import CaseNumberService
from app.services.case_quality.history_cache import invalidate_project_cache
from app.services.quality.grade import grade_status_to_letter
from app.services.quality.quality_gate_service import QualityGateService
from app.services.test_case_generation.quality_validator import compute_quality_score


class AIGenerationError(Exception):
    """AI 生成质量门禁阻断异常（spec L71）。

    业务原因：rejected 状态用例阻断入库时抛出此异常，与普通 ValueError 区分，
    便于上层（batch_orchestrator 的 except 分支）按异常类型精准识别质量门禁拦截，
    而非笼统捕获所有 ValueError。
    """


class CaseValidator:
    """测试用例校验与持久化器。

    职责：
        1. UI 元素可执行性校验（步骤引用的元素是否在 UI 规格中存在）
        2. 动作修正与质量门禁判定（QualityGateService + 本地硬性校验）
        3. 生成用例的 DB 持久化（TestCase + TestStep + 前置条件解析）

    构造函数注入 db: Session，对外保持 _save_test_case / _quality_gate_issues
    等方法签名兼容。
    """

    __test__ = False

    # ── UI 元素可执行性校验常量（合并自 _ui_validation_mixin） ──
    _MIN_UI_ELEMENT_HIT_RATE = 0.8
    _UI_ELEMENT_KEYS = frozenset({
        "id", "key", "name", "label", "text", "title", "placeholder",
        "content", "value", "aria_label", "element_name", "selector",
    })
    _GENERIC_UI_WORDS = frozenset({
        "按钮", "输入框", "文本框", "链接", "页面", "弹窗", "菜单", "选项",
        "入口", "控件",
    })

    # ── 质量门禁与动作修正常量（合并自 _quality_gate_mixin） ──
    _CLICK_KEYWORDS = frozenset({"点击", "勾选", "切换", "按下", "长按"})
    _INPUT_KEYWORDS = frozenset({"输入", "填写", "键入", "录入"})
    _ASSERT_KEYWORDS = frozenset({"查看", "检查", "验证", "确认", "核对", "观察", "获取"})
    _NAVIGATE_KEYWORDS = frozenset({"等待", "静置", "等待加载"})
    _ASSERT_CLICK_PATTERNS = re.compile(
        r'(检查.*(?:点击|可点击|是否可)|查看.*(?:点击|可点击|是否可)|'
        r'验证.*(?:点击|可点击|是否可)|确认.*(?:点击|可点击|是否可))'
    )
    _VALID_CASE_TYPES = frozenset({
        "ui_automation", "manual", "api_automation", "performance", "security",
    })
    _MIN_PERSIST_QUALITY_SCORE = 80.0
    _MIN_PRECONDITION_LENGTH = 15
    _PRIORITY_ONE_KEYWORDS = frozenset({
        "主流程", "全流程", "核心", "提交批改", "批改", "断网", "无网络",
        "网络异常", "数据丢失", "崩溃", "白屏", "未登录", "权限", "越权",
        "安全", "重复提交", "连续快速点击", "正确率100%", "听写结果", "结果页",
    })

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── UI 元素可执行性校验（合并自 _ui_validation_mixin） ──
    @staticmethod
    def _normalize_ui_element_name(value: Any) -> str:
        text = str(value or "").strip()
        text = re.sub(r"[\s【】「」\"'`<>《》:：,，。；;、\[\]()（）]", "", text)
        return text.lower()

    @classmethod
    def _collect_ui_element_names(cls, ui_specs: Optional[List[Dict[str, Any]]]) -> set[str]:
        names: set[str] = set()

        def add(value: Any) -> None:
            if not isinstance(value, str):
                return
            normalized = cls._normalize_ui_element_name(value)
            if len(normalized) < 2 or normalized in cls._GENERIC_UI_WORDS:
                return
            names.add(normalized)

        def walk(value: Any, key_hint: Optional[str] = None) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    key_text = str(key).lower()
                    if key_text in cls._UI_ELEMENT_KEYS:
                        add(item)
                    if isinstance(item, (dict, list)):
                        walk(item, key_text)
            elif isinstance(value, list):
                for item in value:
                    walk(item, key_hint)
            elif key_hint in cls._UI_ELEMENT_KEYS:
                add(value)

        for spec_item in ui_specs or []:
            if not isinstance(spec_item, dict):
                continue
            add(spec_item.get("screen_name"))
            walk(spec_item.get("ui_spec"))
        return names

    @classmethod
    def _extract_step_target_elements(cls, step: Dict[str, Any]) -> List[str]:
        candidates: List[str] = []
        explicit = step.get("target_element")
        if explicit:
            candidates.append(str(explicit))

        action = " ".join(
            str(value or "")
            for value in (
                step.get("action"),
                step.get("description"),
                step.get("param"),
            )
        )
        bracket_patterns = [
            r"(?:点击|选择|勾选|切换|按下|长按)\s*[【「《\"']([^】」》\"']{2,40})[】」》\"']",
            r"(?:在|向)\s*[【「《\"']([^】」》\"']{2,40})[】」》\"']\s*(?:输入|填写|键入|录入|选择)",
        ]
        for pattern in bracket_patterns:
            candidates.extend(re.findall(pattern, action))

        result: List[str] = []
        seen = set()
        for item in candidates:
            normalized = cls._normalize_ui_element_name(item)
            if len(normalized) < 2 or normalized in cls._GENERIC_UI_WORDS or normalized in seen:
                continue
            seen.add(normalized)
            result.append(item.strip())
        return result

    @classmethod
    def _ui_element_exists(cls, target: str, element_names: set[str]) -> bool:
        normalized = cls._normalize_ui_element_name(target)
        if not normalized:
            return False
        for element in element_names:
            if normalized == element:
                return True
            if len(normalized) >= 2 and normalized in element:
                return True
            if len(element) >= 2 and element in normalized:
                return True
        return False

    @classmethod
    def _ui_executability_issues(
        cls,
        steps: List[Dict[str, Any]],
        ui_specs: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        element_names = cls._collect_ui_element_names(ui_specs)
        if not element_names:
            return []

        checked = 0
        hit = 0
        missing: List[str] = []
        for step in steps or []:
            targets = cls._extract_step_target_elements(step)
            for target in targets:
                checked += 1
                if cls._ui_element_exists(target, element_names):
                    hit += 1
                else:
                    missing.append(target)

        if checked == 0:
            return []
        hit_rate = hit / checked
        if hit_rate >= cls._MIN_UI_ELEMENT_HIT_RATE:
            return []
        unique_missing = []
        seen = set()
        for item in missing:
            normalized = cls._normalize_ui_element_name(item)
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_missing.append(item)
        missing_text = "、".join(unique_missing[:5])
        return [
            f"UI元素命中率 {hit_rate:.0%} 低于 {cls._MIN_UI_ELEMENT_HIT_RATE:.0%}，未匹配元素: {missing_text}"
        ]

    # ── 质量门禁与动作修正（合并自 _quality_gate_mixin） ──
    @staticmethod
    def _correct_action_type(action: str, action_type: str) -> str:
        if not action:
            return action_type
        cls = CaseValidator
        has_assert = any(kw in action for kw in cls._ASSERT_KEYWORDS)
        has_click = any(kw in action for kw in cls._CLICK_KEYWORDS)
        if has_assert and has_click:
            if cls._ASSERT_CLICK_PATTERNS.search(action):
                return "verify"
            return "click"
        if has_click:
            return "click"
        if any(kw in action for kw in cls._INPUT_KEYWORDS):
            return "input"
        if has_assert:
            return "verify"
        if any(kw in action for kw in cls._NAVIGATE_KEYWORDS):
            return "navigate"
        return action_type

    @staticmethod
    def _clean_precondition(precondition: str) -> str:
        if not precondition:
            return precondition
        patterns = [
            r'[、，,]?\s*通过(?:Mock|cy\.intercept|ADB|devtools)[^、，,]*',
            r'[、，,]?\s*Mock[^、，,]*',
            r'[、，,]?\s*cy\.intercept\([^)]*\)[^、，,]*',
            r'[、，,]?\s*ADB[^、，,]*',
            r'[、，,]?\s*devtools[^、，,]*',
            r'[、，,]?\s*（?清除(?:token|cookie|session|缓存|localStorage|sessionStorage)[^）、，,]*）?',
            r'[、，,]?\s*清除(?:token|cookie|session|缓存|localStorage|sessionStorage)[^、，,]*',
            r'[、，,]?\s*（?(?:token|cookie|session)[^）、，,]*）?',
        ]
        cleaned = precondition
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'[、，,]\s*$', '', cleaned.strip())
        cleaned = re.sub(r'^[、，,]\s*', '', cleaned)
        cleaned = re.sub(r'（\s*）', '', cleaned)
        cleaned = re.sub(r'\(\s*\)', '', cleaned)
        return cleaned

    @classmethod
    def _normalize_case_type(cls, *values: Optional[str]) -> str:
        for value in values:
            if not value:
                continue
            for part in str(value).split(","):
                normalized = part.strip()
                if normalized in cls._VALID_CASE_TYPES:
                    return normalized
        return DEFAULT_AI_FALLBACK_CASE_TYPE

    @classmethod
    def _quality_gate_issues(
        cls,
        generated_case: Dict[str, Any],
        quality_score: Optional[float],
        ui_specs: Optional[List[Dict[str, Any]]] = None,
        project_id: Optional[int] = None,
        db: Any = None,
    ) -> Tuple[List[str], str]:
        """使用 QualityGateService 执行统一校验，返回 (issues, status) 元组。

        分级阻断规则:
            - rejected: 返回非空 issues，调用方应阻断入库
            - pending_review/warning/passed: 返回空 issues 列表，调用方不阻断

        本地硬性校验（quality_score/precondition/UI可执行性）失败时，
        状态提升为 rejected，确保硬性质量门槛始终阻断。
        """
        context: Dict[str, Any] = {
            "ui_specs": ui_specs or generated_case.get("_context_ui_specs"),
        }
        gate_service = QualityGateService(db=db)
        try:
            result = gate_service.validate(
                generated_case,
                context=context,
                project_id=project_id,
            )
            gate_status: str = result.status
            issues: List[str] = [issue.message for issue in result.issues]
        except Exception as e:
            logger.warning(f"QualityGate 编排异常，降级为 warning: {e}")
            gate_status = "warning"
            issues = []

        local_blocking = False
        if quality_score is None:
            issues.append("quality score is missing")
            local_blocking = True
        elif quality_score < cls._MIN_PERSIST_QUALITY_SCORE:
            issues.append(
                f"quality score {quality_score:.0f} is below "
                f"{cls._MIN_PERSIST_QUALITY_SCORE:.0f}"
            )
            local_blocking = True
        precondition = (generated_case.get("precondition") or "").strip()
        if len(precondition) < cls._MIN_PRECONDITION_LENGTH:
            issues.append(
                f"precondition is too short ({len(precondition)} chars)"
            )
            local_blocking = True
        ui_issues = cls._ui_executability_issues(
            generated_case.get("steps", []),
            ui_specs or generated_case.get("_context_ui_specs"),
        )
        if ui_issues:
            issues.extend(ui_issues)
            local_blocking = True

        if local_blocking:
            gate_status = "rejected"

        if gate_status == "rejected":
            return issues, gate_status
        return [], gate_status

    @classmethod
    def _resolve_generated_priority(
        cls,
        generated_case: Dict[str, Any],
        test_point: Dict[str, Any],
    ) -> int:
        priority = normalize_priority(
            generated_case.get("priority", test_point.get("priority", 2))
        )
        point_priority = normalize_priority(test_point.get("priority", priority))
        if priority == 1 or point_priority == 1:
            return 1

        text = " ".join(
            str(value or "")
            for value in (
                generated_case.get("title"),
                generated_case.get("expected_result"),
                generated_case.get("case_category"),
                test_point.get("point"),
                test_point.get("function"),
            )
        )
        if any(keyword in text for keyword in cls._PRIORITY_ONE_KEYWORDS):
            return 1
        return priority

    # ── DB 持久化（合并自 validate_mixin） ──
    def _case_title_exists(self, project_id: int, title: str) -> bool:
        if not title:
            return False
        # R3 修复：with_for_update() 在 InnoDB REPEATABLE READ 下对 (project_id, title)
        # 索引加 gap lock，使 check-then-insert 原子化，消除并发竞态导致的重复 title。
        existing = self.db.query(TestCase.id).filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,  # noqa: E712
            TestCase.generate_status == 1,
            TestCase.title == title,
        ).with_for_update().first()
        return existing is not None

    async def _save_test_case(
        self,
        project_id: int,
        generated_case: Dict[str, Any],
        test_point: Dict[str, Any],
        requirement_file_id: Optional[int] = None
    ) -> TestCase:
        """保存测试用例到数据库。

        Args:
            project_id: 项目ID
            generated_case: 生成的用例数据
            test_point: 来源测试点
            requirement_file_id: 关联的需求文件ID（可选）

        Returns:
            保存的测试用例对象
        """
        case_no = CaseNumberService.generate(project_id, self.db)

        steps = generated_case.get("steps", [])
        case_test_data = generated_case.get("test_data")
        steps_json = []
        for i, step in enumerate(steps):
            raw_action_type = step.get("action_type", "")
            corrected_action_type = self._correct_action_type(
                step.get("action", ""), raw_action_type
            )
            step_entry = {
                "step": step.get("step", str(i + 1)),
                "description": step.get("description", ""),
                "action": step.get("action", "执行"),
                "expected_result": step.get("expected_result", ""),
                "param": step.get("param", ""),
                "action_type": corrected_action_type,
                "input_value": step.get("input_value", ""),
                "target_element": step.get("target_element", ""),
                "test_data": step.get("test_data", []),
            }
            if i == 0 and case_test_data:
                step_entry["test_data"] = case_test_data
            steps_json.append(step_entry)

        case_type = self._normalize_case_type(
            generated_case.get("case_type"),
            generated_case.get("test_category"),
        )
        case_category = (generated_case.get("case_category") or "").strip()
        test_category_value = case_type

        raw_precondition = generated_case.get("precondition", "")
        cleaned_precondition = self._clean_precondition(raw_precondition)
        title = (
            generated_case.get("title")
            or test_point.get("point")
            or "(untitled)"
        ).strip()

        if self._case_title_exists(project_id, title):
            raise ValueError(f"duplicate generated case title: {title}")

        case_for_quality = dict(generated_case)
        case_for_quality.update({
            "title": title,
            "precondition": cleaned_precondition,
            "steps": steps_json,
            "case_type": case_type,
            "case_category": case_category,
        })
        quality_score = compute_quality_score([case_for_quality])
        quality_issues, gate_status = self._quality_gate_issues(
            case_for_quality,
            quality_score,
            ui_specs=generated_case.get("_context_ui_specs"),
            project_id=project_id,
            db=self.db,
        )
        if quality_issues:
            issue_text = "; ".join(quality_issues[:3])
            raise AIGenerationError(f"generated case failed quality gate: {issue_text}")
        if gate_status == "warning":
            logger.warning(
                f"generated case passed gate with warning status (title={title})"
            )
        pending_review = gate_status == "pending_review"
        priority = self._resolve_generated_priority(case_for_quality, test_point)

        # Task 17.3: 由 grade_status 映射质量等级（A=passed/B=warning/C=pending_review/D=rejected）
        quality_grade = grade_status_to_letter(gate_status)

        test_case = TestCase(
            project_id=project_id,
            requirement_file_id=requirement_file_id,
            test_point_id=test_point.get("id"),
            case_no=case_no,
            module=generated_case.get("module", test_point.get("module", "AI生成")),
            title=title,
            precondition=cleaned_precondition,
            steps_json=steps_json,
            expected_result=generated_case.get("expected_result", ""),
            priority=priority,
            case_type=case_type,
            test_category=test_category_value,
            parent_case_id=generated_case.get("parent_case_id"),
            ai_change_type=generated_case.get("change_type"),
            generate_status=1,
            prior_quality_score=quality_score,
            quality_grade=quality_grade,
            lifecycle_status="pending_review" if pending_review else "draft",
        )

        try:
            self.db.add(test_case)
            self.db.flush()
        except IntegrityError as e:
            self.db.rollback()
            if "title" in str(e).lower() or "duplicate" in str(e).lower():
                raise ValueError(
                    f"concurrent duplicate generated case title: {title}"
                ) from e
            raise

        invalidate_project_cache(project_id)

        for i, step in enumerate(steps):
            raw_action_type = step.get("action_type", "")
            corrected_action_type = self._correct_action_type(
                step.get("action", step.get("description", step.get("step", "执行"))),
                raw_action_type
            )
            test_step = TestStep(
                test_case_id=test_case.id,
                step_number=i + 1,
                action=step.get("action", step.get("description", step.get("step", "执行"))),
                expected_result=step.get("expected_result", step.get("param", "预期结果正常")),
                action_type=corrected_action_type,
                input_value=step.get("input_value", ""),
                target_element=step.get("target_element", ""),
                is_business_view=1,
                is_technical_view=1
            )
            self.db.add(test_step)

        self.db.commit()
        self.db.refresh(test_case)

        if settings.AUTO_PARSE_PRECONDITION and test_case.precondition and test_case.precondition.strip():
            try:
                from app.utils.ai_client import parse_precondition_to_steps
                from app.models.test_case import TestCasePreconditionStep

                parsed_steps = parse_precondition_to_steps(
                    precondition=test_case.precondition
                )
                if inspect.isawaitable(parsed_steps):
                    parsed_steps = await parsed_steps

                if parsed_steps:
                    for idx, step_data in enumerate(parsed_steps):
                        pc_step = TestCasePreconditionStep(
                            test_case_id=test_case.id,
                            step_number=idx + 1,
                            action=step_data.get("action", ""),
                            action_type=step_data.get("action_type", "click"),
                            input_value=step_data.get("input_value", ""),
                            target_element=step_data.get("target_element", ""),
                            expected_result=step_data.get("expected_result", ""),
                            has_locator=0,
                            locator_status="pending"
                        )
                        self.db.add(pc_step)
                    self.db.commit()
                    logger.info(f"自动解析前置条件成功，生成 {len(parsed_steps)} 个步骤 (用例ID={test_case.id})")
            except Exception as e:
                logger.warning(f"自动解析前置条件失败 (用例ID={test_case.id}): {e}")

        return test_case


# 向后兼容别名：历史代码以 TestCaseGenerationValidateMixin 名称实例化
TestCaseGenerationValidateMixin = CaseValidator
