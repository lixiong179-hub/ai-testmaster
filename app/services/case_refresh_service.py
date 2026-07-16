import json
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case_refresh_suggestion import CaseRefreshSuggestion
from app.models.test_case import TestCase
from app.models.requirement import Requirement
from app.models.test_point import TestPoint
from app.services._case_refresh_apply import (
    apply_suggestion as _apply_suggestion_impl,
    create_version_snapshot as _create_version_snapshot_impl,
    review_suggestion as _review_suggestion_impl,
)


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
    """用例保鲜服务（async 版本）。

    迁移说明（P0 服务 async 化）:
        __init__(db: Session) → __init__(db: AsyncSession)
        所有 DB 查询改为 select() + await db.execute() 模式。
        sync 外部依赖（AI client）保留同步调用，仅在 BackgroundTasks 场景触发。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_suggestion(
        self,
        case_id: int,
        trigger_reason: str,
        requirement_id: Optional[int] = None,
        ai_result: Optional[Dict[str, Any]] = None,
        model_version: Optional[str] = None,
    ) -> CaseRefreshSuggestion:
        """创建保鲜建议记录。

        Args:
            case_id: 关联用例ID。
            trigger_reason: 触发原因。
            requirement_id: 关联需求ID。
            ai_result: AI 生成结果字典，包含建议字段。
            model_version: AI 模型版本。

        Returns:
            已持久化的保鲜建议实例。
        """
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
        await self.db.flush()
        return suggestion

    def build_refresh_prompt(self, case: TestCase, requirement: Requirement) -> str:
        """构建保鲜建议 AI 提示词。"""
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
        """解析 AI 保鲜响应文本为字典，失败时返回兜底结果。"""
        import re
        text = response_text.strip()
        code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?\s*```', text)
        if code_block_match:
            text = code_block_match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        return {"is_valid": True, "diff_description": "AI响应解析失败，需人工判断"}

    async def get_suggestion_by_id(self, suggestion_id: int) -> Optional[CaseRefreshSuggestion]:
        """根据ID获取保鲜建议。"""
        result = await self.db.execute(
            select(CaseRefreshSuggestion).where(
                CaseRefreshSuggestion.id == suggestion_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_case_by_id(self, case_id: int) -> Optional[TestCase]:
        """根据ID获取测试用例。"""
        result = await self.db.execute(
            select(TestCase).where(TestCase.id == case_id)
        )
        return result.scalar_one_or_none()

    async def list_suggestions(
        self,
        project_id: int,
        page: int = 1,
        page_size: int = 20,
        suggestion_status: Optional[str] = None,
        review_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """分页查询项目下的保鲜建议列表。"""
        query = (
            select(CaseRefreshSuggestion)
            .join(TestCase, CaseRefreshSuggestion.case_id == TestCase.id)
            .where(TestCase.project_id == project_id)
        )
        if suggestion_status:
            query = query.where(
                CaseRefreshSuggestion.suggestion_status == suggestion_status
            )
        if review_status:
            query = query.where(
                CaseRefreshSuggestion.review_status == review_status
            )
        query = query.order_by(CaseRefreshSuggestion.triggered_at.desc())

        count_query = (
            select(func.count())
            .select_from(CaseRefreshSuggestion)
            .join(TestCase, CaseRefreshSuggestion.case_id == TestCase.id)
            .where(TestCase.project_id == project_id)
        )
        if suggestion_status:
            count_query = count_query.where(
                CaseRefreshSuggestion.suggestion_status == suggestion_status
            )
        if review_status:
            count_query = count_query.where(
                CaseRefreshSuggestion.review_status == review_status
            )
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * page_size
        result = await self.db.execute(query.offset(offset).limit(page_size))
        items = result.scalars().all()
        return {
            "items": [self._suggestion_to_dict(s) for s in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_suggestions_stats(self, project_id: int) -> Dict[str, Any]:
        """统计项目下保鲜建议按状态的分布。

        业务边界：未知状态（如 expired）需累加进 total，不能丢弃。
        """
        rows = (
            await self.db.execute(
                select(
                    CaseRefreshSuggestion.suggestion_status,
                    func.count(CaseRefreshSuggestion.id),
                )
                .join(TestCase, CaseRefreshSuggestion.case_id == TestCase.id)
                .where(TestCase.project_id == project_id)
                .group_by(CaseRefreshSuggestion.suggestion_status)
            )
        ).all()
        stats = {"pending": 0, "applied": 0, "rejected": 0}
        unknown_total = 0
        for status_val, count in rows:
            if status_val in stats:
                stats[status_val] = count
            else:
                unknown_total += count
        stats["total"] = sum(stats.values()) + unknown_total
        return stats

    async def review_suggestion(
        self,
        suggestion_id: int,
        action: str,
        reviewer_id: int,
        reviewer_name: str,
        reject_reason: Optional[str] = None,
    ) -> CaseRefreshSuggestion:
        """审核保鲜建议，委托至 _case_refresh_apply.review_suggestion。"""
        return await _review_suggestion_impl(
            self.db, suggestion_id, action, reviewer_id, reviewer_name, reject_reason
        )

    async def _apply_suggestion(self, suggestion: CaseRefreshSuggestion) -> int:
        """应用保鲜建议（内部方法）。"""
        return await _apply_suggestion_impl(self.db, suggestion)

    async def _create_version_snapshot(self, case: TestCase, change_type: str) -> int:
        """创建版本快照（内部方法）。"""
        return await _create_version_snapshot_impl(self.db, case, change_type)

    def _suggestion_to_dict(self, suggestion: CaseRefreshSuggestion) -> Dict[str, Any]:
        """将保鲜建议实例序列化为字典。"""
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

    async def auto_scan_and_suggest(self, project_id: int, max_cases: int = 10) -> Dict[str, Any]:
        """自动扫描过期用例并生成保鲜建议。

        扫描项目中需求已变更但用例未同步更新的过期用例，
        对前 max_cases 条调用AI生成保鲜建议。

        Args:
            project_id: 项目ID
            max_cases: 最多处理的过期用例数量，默认10

        Returns:
            包含created（已创建建议ID列表）、errors（失败列表）、total_scanned（扫描总数）的字典
        """
        stale_cases = await self.scan_stale_cases(project_id)
        created: List[int] = []
        errors: List[Dict[str, Any]] = []
        for stale_info in stale_cases[:max_cases]:
            case = await self.get_case_by_id(stale_info["case_id"])
            if not case:
                continue
            req_result = await self.db.execute(
                select(Requirement).where(Requirement.id == stale_info["requirement_id"])
            )
            req = req_result.scalar_one_or_none()
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
                suggestion = await self.create_suggestion(
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

    async def scan_stale_cases(self, project_id: int) -> List[Dict[str, Any]]:
        """扫描项目下需求已变更但用例未同步的过期用例。"""
        cases_result = await self.db.execute(
            select(TestCase).where(
                TestCase.project_id == project_id,
                TestCase.is_deleted.is_(False),
                TestCase.lifecycle_status.in_(["active", "pending_review"]),
            )
        )
        cases = cases_result.scalars().all()
        stale_cases: List[Dict[str, Any]] = []
        for case in cases:
            if not case.test_point_id:
                continue
            tp_result = await self.db.execute(
                select(TestPoint).where(TestPoint.id == case.test_point_id)
            )
            tp = tp_result.scalar_one_or_none()
            if not tp or not tp.requirement_id:
                continue
            req_result = await self.db.execute(
                select(Requirement).where(Requirement.id == tp.requirement_id)
            )
            req = req_result.scalar_one_or_none()
            if not req or not req.update_time or not case.update_time:
                continue
            if req.update_time > case.update_time:
                existing_result = await self.db.execute(
                    select(CaseRefreshSuggestion).where(
                        CaseRefreshSuggestion.case_id == case.id,
                        CaseRefreshSuggestion.suggestion_status == "pending",
                    )
                )
                existing = existing_result.scalar_one_or_none()
                if not existing:
                    stale_cases.append({
                        "case_id": case.id,
                        "case_title": case.title,
                        "requirement_id": req.id,
                        "requirement_title": req.title,
                        "trigger_reason": "requirement_changed",
                    })
        return stale_cases
