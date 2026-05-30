import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.orm import Session

from app.models.case_refresh_suggestion import CaseRefreshSuggestion
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.models.test_case_version import TestCaseVersion
from app.models.requirement import Requirement
from app.models.test_point import TestPoint
from app.services.lifecycle_service._service import transition as lifecycle_transition


REFRESH_PROMPT_TEMPLATE = """你是一名测试用例维护专家。请依据最新需求评估以下历史用例。

[最新需求]
{requirement_description}

[历史用例]
标题：{case_title}
步骤：{case_steps}
预期结果：{case_expected_result}

[任务]
1. 判断该用例在当前需求下是否仍然有效。
2. 若有效，输出建议更新内容和差异说明。
3. 若无效，输出建议废弃原因。
4. 不要引入需求中未提及的规则或UI元素。

请严格按以下JSON格式输出（不要添加markdown代码块标记）：
{{
  "is_valid": true或false,
  "suggested_title": "建议标题（若有效）",
  "suggested_steps": [步骤数组（若有效）],
  "suggested_expected_result": "建议预期结果（若有效）",
  "diff_description": "差异说明",
  "deprecation_reason": "废弃原因（若无效，否则为空字符串）"
}}"""


class CaseRefreshService:
    def __init__(self, db: Session):
        self.db = db

    def create_suggestion(
        self,
        case_id: int,
        trigger_reason: str,
        requirement_id: Optional[int] = None,
        ai_result: Optional[Dict[str, Any]] = None,
        model_version: Optional[str] = None,
    ) -> CaseRefreshSuggestion:
        suggestion = CaseRefreshSuggestion(
            case_id=case_id,
            requirement_id=requirement_id,
            trigger_reason=trigger_reason,
            suggestion_status="pending",
            review_status="pending",
            retry_count=0,
            model_version=model_version,
        )
        if ai_result:
            suggestion.suggested_title = ai_result.get("suggested_title")
            suggestion.suggested_steps = ai_result.get("suggested_steps")
            suggestion.suggested_expected_result = ai_result.get("suggested_expected_result")
            suggestion.diff_description = ai_result.get("diff_description")
            suggestion.deprecation_reason = ai_result.get("deprecation_reason")
            if not ai_result.get("is_valid", True):
                suggestion.suggestion_status = "pending"
        self.db.add(suggestion)
        self.db.flush()
        return suggestion

    def build_refresh_prompt(self, case: TestCase, requirement: Requirement) -> str:
        steps_text = ""
        if case.steps_json:
            if isinstance(case.steps_json, list):
                steps_text = json.dumps(case.steps_json, ensure_ascii=False, indent=2)
            else:
                steps_text = str(case.steps_json)
        return REFRESH_PROMPT_TEMPLATE.format(
            requirement_description=requirement.description or "",
            case_title=case.title or "",
            case_steps=steps_text,
            case_expected_result=case.expected_result or "",
        )

    def parse_refresh_response(self, response_text: str) -> Dict[str, Any]:
        text = response_text.strip()
        code_block_match = __import__("re").search(r'```(?:json)?\s*\n?([\s\S]*?)\n?\s*```', text)
        if code_block_match:
            text = code_block_match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            json_match = __import__("re").search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        return {"is_valid": True, "diff_description": "AI响应解析失败，需人工判断"}

    def get_suggestion_by_id(self, suggestion_id: int) -> Optional[CaseRefreshSuggestion]:
        return self.db.query(CaseRefreshSuggestion).filter(
            CaseRefreshSuggestion.id == suggestion_id,
        ).first()

    def get_case_by_id(self, case_id: int) -> Optional[TestCase]:
        return self.db.query(TestCase).filter(TestCase.id == case_id).first()

    def list_suggestions(
        self,
        project_id: int,
        page: int = 1,
        page_size: int = 20,
        suggestion_status: Optional[str] = None,
        review_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        query = self.db.query(CaseRefreshSuggestion).join(
            TestCase, CaseRefreshSuggestion.case_id == TestCase.id
        ).filter(
            TestCase.project_id == project_id,
        )
        if suggestion_status:
            query = query.filter(CaseRefreshSuggestion.suggestion_status == suggestion_status)
        if review_status:
            query = query.filter(CaseRefreshSuggestion.review_status == review_status)
        query = query.order_by(CaseRefreshSuggestion.triggered_at.desc())
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": [self._suggestion_to_dict(s) for s in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_suggestions_stats(self, project_id: int) -> Dict[str, Any]:
        from sqlalchemy import func
        rows = self.db.query(
            CaseRefreshSuggestion.suggestion_status,
            func.count(CaseRefreshSuggestion.id),
        ).join(
            TestCase, CaseRefreshSuggestion.case_id == TestCase.id
        ).filter(
            TestCase.project_id == project_id,
        ).group_by(
            CaseRefreshSuggestion.suggestion_status,
        ).all()
        stats = {"pending": 0, "applied": 0, "rejected": 0, "total": 0}
        for status_val, count in rows:
            key = status_val if status_val in stats else "total"
            stats[key] = count
        stats["total"] = sum(v for k, v in stats.items() if k != "total")
        return stats

    def review_suggestion(
        self,
        suggestion_id: int,
        action: str,
        reviewer_id: int,
        reviewer_name: str,
        reject_reason: Optional[str] = None,
    ) -> CaseRefreshSuggestion:
        suggestion = self.db.query(CaseRefreshSuggestion).filter(
            CaseRefreshSuggestion.id == suggestion_id,
        ).first()
        if not suggestion:
            raise ValueError(f"保鲜建议不存在: {suggestion_id}")
        if suggestion.review_status != "pending":
            raise ValueError(f"保鲜建议已审核: {suggestion.review_status}")

        suggestion.reviewer_id = reviewer_id
        suggestion.reviewer_name = reviewer_name
        suggestion.reviewed_at = datetime.now(timezone.utc)

        if action == "approve":
            suggestion.review_status = "approved"
            self._apply_suggestion(suggestion)
        elif action == "reject":
            suggestion.review_status = "rejected"
            suggestion.reject_reason = reject_reason or ""
            suggestion.suggestion_status = "rejected"
        else:
            raise ValueError(f"无效的审核操作: {action}")

        self.db.flush()
        return suggestion

    def _apply_suggestion(self, suggestion: CaseRefreshSuggestion) -> int:
        case = self.db.query(TestCase).filter(TestCase.id == suggestion.case_id).first()
        if not case:
            suggestion.failure_reason = f"关联用例不存在: {suggestion.case_id}"
            suggestion.suggestion_status = "expired"
            return 0

        version_id = self._create_version_snapshot(case, "refresh_apply")
        suggestion.snapshot_version_id = version_id

        if suggestion.deprecation_reason and not suggestion.suggested_title:
            enable_lifecycle_transition()
            try:
                lifecycle_transition(
                    db=self.db,
                    case_id=case.id,
                    to_status="deprecated",
                    actor_id=suggestion.reviewer_id,
                    reason=suggestion.deprecation_reason,
                )
            finally:
                disable_lifecycle_transition()
            suggestion.suggestion_status = "applied"
            return version_id

        if suggestion.suggested_title:
            case.title = suggestion.suggested_title
        if suggestion.suggested_expected_result:
            case.expected_result = suggestion.suggested_expected_result
        if suggestion.suggested_steps:
            case.steps_json = suggestion.suggested_steps
            from app.models.test_case import TestStep
            self.db.query(TestStep).filter(TestStep.test_case_id == case.id).delete()
            for idx, step_data in enumerate(suggestion.suggested_steps):
                if isinstance(step_data, dict):
                    step = TestStep(
                        test_case_id=case.id,
                        step_number=idx + 1,
                        action=step_data.get("action", step_data.get("description", "")),
                        expected_result=step_data.get("expected_result", ""),
                        action_type=step_data.get("action_type"),
                        input_value=step_data.get("input_value", ""),
                        target_element=step_data.get("target_element", ""),
                    )
                    self.db.add(step)

        suggestion.suggestion_status = "applied"
        return version_id

    def _create_version_snapshot(self, case: TestCase, change_type: str) -> int:
        latest_version = self.db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id,
        ).order_by(TestCaseVersion.version_number.desc()).first()
        next_version = (latest_version.version_number + 1) if latest_version else 1

        snapshot_data = {
            "title": case.title,
            "module": case.module,
            "precondition": case.precondition,
            "expected_result": case.expected_result,
            "priority": case.priority,
            "case_type": case.case_type,
            "steps_json": case.steps_json,
        }
        version = TestCaseVersion(
            test_case_id=case.id,
            version_number=next_version,
            change_type=change_type,
            change_description="保鲜建议应用前自动快照",
            snapshot_data=snapshot_data,
        )
        self.db.add(version)
        self.db.flush()
        return version.id

    def _suggestion_to_dict(self, suggestion: CaseRefreshSuggestion) -> Dict[str, Any]:
        return {
            "id": suggestion.id,
            "case_id": suggestion.case_id,
            "requirement_id": suggestion.requirement_id,
            "trigger_reason": suggestion.trigger_reason,
            "triggered_at": suggestion.triggered_at.isoformat() if suggestion.triggered_at else None,
            "suggestion_status": suggestion.suggestion_status,
            "suggested_title": suggestion.suggested_title,
            "suggested_steps": suggestion.suggested_steps,
            "suggested_expected_result": suggestion.suggested_expected_result,
            "diff_description": suggestion.diff_description,
            "deprecation_reason": suggestion.deprecation_reason,
            "review_status": suggestion.review_status,
            "reviewer_name": suggestion.reviewer_name,
            "reviewed_at": suggestion.reviewed_at.isoformat() if suggestion.reviewed_at else None,
            "reject_reason": suggestion.reject_reason,
            "model_version": suggestion.model_version,
            "snapshot_version_id": suggestion.snapshot_version_id,
            "created_at": suggestion.created_at.isoformat() if suggestion.created_at else None,
        }

    def auto_scan_and_suggest(self, project_id: int, max_cases: int = 10) -> Dict[str, Any]:
        """自动扫描过期用例并生成保鲜建议。

        扫描项目中需求已变更但用例未同步更新的过期用例，
        对前 max_cases 条调用AI生成保鲜建议。

        Args:
            project_id: 项目ID
            max_cases: 最多处理的过期用例数量，默认10

        Returns:
            包含created（已创建建议ID列表）、errors（失败列表）、total_scanned（扫描总数）的字典
        """
        stale_cases = self.scan_stale_cases(project_id)
        created: List[int] = []
        errors: List[Dict[str, Any]] = []
        for stale_info in stale_cases[:max_cases]:
            case = self.db.query(TestCase).filter(TestCase.id == stale_info["case_id"]).first()
            if not case:
                continue
            req = self.db.query(Requirement).filter(Requirement.id == stale_info["requirement_id"]).first()
            if not req:
                continue
            try:
                prompt = self.build_refresh_prompt(case, req)
                from app.utils.ai_client import get_ai_client
                client = get_ai_client()
                response = client.chat.completions.create(
                    model=client.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=4096,
                )
                result_text = response.choices[0].message.content
                ai_result = self.parse_refresh_response(result_text or "")
                suggestion = self.create_suggestion(
                    case_id=case.id,
                    trigger_reason=stale_info["trigger_reason"],
                    requirement_id=req.id,
                    ai_result=ai_result,
                    model_version=client.model_name,
                )
                created.append(suggestion.id)
            except Exception as e:
                logger.error(f"自动保鲜建议生成失败 case_id={stale_info['case_id']}: {e}")
                errors.append({"case_id": stale_info["case_id"], "error": str(e)})
        return {"created": created, "errors": errors, "total_scanned": len(stale_cases)}

    def scan_stale_cases(self, project_id: int) -> List[Dict[str, Any]]:
        cases = self.db.query(TestCase).filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted.is_(False),
            TestCase.lifecycle_status.in_(["active", "pending_review"]),
        ).all()
        stale_cases: List[Dict[str, Any]] = []
        for case in cases:
            if not case.test_point_id:
                continue
            tp = self.db.query(TestPoint).filter(TestPoint.id == case.test_point_id).first()
            if not tp or not tp.requirement_id:
                continue
            req = self.db.query(Requirement).filter(Requirement.id == tp.requirement_id).first()
            if not req or not req.update_time or not case.update_time:
                continue
            if req.update_time > case.update_time:
                existing = self.db.query(CaseRefreshSuggestion).filter(
                    CaseRefreshSuggestion.case_id == case.id,
                    CaseRefreshSuggestion.suggestion_status == "pending",
                ).first()
                if not existing:
                    stale_cases.append({
                        "case_id": case.id,
                        "case_title": case.title,
                        "requirement_id": req.id,
                        "requirement_title": req.title,
                        "trigger_reason": "requirement_changed",
                    })
        return stale_cases
