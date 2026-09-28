"""自愈审计服务模块。

提供自愈审计记录写入、分页查询与回滚能力。审计表为仅追加表，
回滚通过"写入新审计记录（strategy='rollback'）+ 乐观锁更新定位器"实现，
保留完整决策链条。
"""

from fastapi import HTTPException
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.element_locator import ElementLocator
from app.models.self_healing_audit import SelfHealingAudit
from app.models.test_case import TestCase


class SelfHealingAuditService:
    """自愈审计记录与回滚服务。"""

    def __init__(self, db: Session) -> None:
        """注入数据库会话，禁止内部新建 Session。"""
        self._db = db

    def record_audit(
        self, *,
        test_case_id: int, step_index: int, locator_id: int | None,
        old_selector: str | None, new_selector: str | None,
        failure_type: str, strategy: str, confidence: float | None,
        token_cost: int, low_confidence: bool = False,
    ) -> SelfHealingAudit:
        """写入审计记录。new_selector 为 None 表示自愈失败仅留痕。"""
        audit = SelfHealingAudit(
            test_case_id=test_case_id, step_index=step_index, locator_id=locator_id,
            old_selector=old_selector, new_selector=new_selector,
            failure_type=failure_type, strategy=strategy, confidence=confidence,
            token_cost=token_cost, low_confidence=low_confidence,
        )
        self._db.add(audit)
        self._db.commit()
        self._db.refresh(audit)
        logger.info(
            f"自愈审计写入: case_id={test_case_id} step={step_index} "
            f"strategy={strategy} low_confidence={low_confidence}"
        )
        return audit

    def rollback_audit(self, audit_id: int) -> SelfHealingAudit:
        """回滚：将定位器 css_selector 恢复为原审计 old_selector，乐观锁 version+1，
        并写入新审计记录 strategy='rollback'。

        Raises:
            HTTPException 404: 审计记录或定位器不存在。
            ValueError: 原审计 old_selector/locator_id 为空，无法回滚。
            HTTPException 409: 定位器版本已变更，乐观锁回滚失败。
        """
        origin = (
            self._db.query(SelfHealingAudit)
            .filter(SelfHealingAudit.id == audit_id)
            .first()
        )
        if origin is None:
            raise HTTPException(status_code=404, detail=f"审计记录 {audit_id} 不存在")
        if origin.old_selector is None or origin.locator_id is None:
            raise ValueError(f"审计记录 {audit_id} 的 old_selector/locator_id 为空，无法回滚")

        locator = (
            self._db.query(ElementLocator)
            .filter(ElementLocator.id == origin.locator_id)
            .first()
        )
        if locator is None:
            raise HTTPException(
                status_code=404, detail=f"定位器 {origin.locator_id} 不存在"
            )

        current_selector = locator.css_selector
        # 参数化更新防 SQL 注入；WHERE version 实现乐观锁，rowcount=0 表示并发冲突
        result = self._db.execute(
            text(
                "UPDATE element_locators SET css_selector = :old, "
                "version = version + 1, updated_at = UTC_TIMESTAMP() "
                "WHERE id = :id AND version = :ver"
            ),
            {"old": origin.old_selector, "id": origin.locator_id, "ver": locator.version},
        )
        if result.rowcount == 0:
            raise HTTPException(
                status_code=409,
                detail=f"定位器 {origin.locator_id} 版本已变更，回滚失败",
            )

        rollback_audit = SelfHealingAudit(
            test_case_id=origin.test_case_id, step_index=origin.step_index,
            locator_id=origin.locator_id, old_selector=current_selector,
            new_selector=origin.old_selector, failure_type=origin.failure_type,
            strategy="rollback", confidence=None, token_cost=0, low_confidence=False,
        )
        self._db.add(rollback_audit)
        self._db.commit()
        self._db.refresh(rollback_audit)
        logger.info(
            f"自愈回滚完成: audit_id={audit_id} locator_id={origin.locator_id} "
            f"restored_selector={origin.old_selector}"
        )
        return rollback_audit

    def list_audits(
        self, *, project_id: int | None = None, test_case_id: int | None = None,
        page: int = 1, page_size: int = 20,
    ) -> tuple[list[SelfHealingAudit], int]:
        """分页查询审计记录（按 id 倒序）。

        project_id 过滤需 join test_cases 表；page 小于 1 按 1 处理。
        返回 (记录列表, 总数)。
        """
        query = self._db.query(SelfHealingAudit)
        if project_id is not None:
            query = query.join(
                TestCase, TestCase.id == SelfHealingAudit.test_case_id
            ).filter(TestCase.project_id == project_id)
        if test_case_id is not None:
            query = query.filter(SelfHealingAudit.test_case_id == test_case_id)

        total = query.count()
        offset = (max(page, 1) - 1) * page_size
        records = (
            query.order_by(SelfHealingAudit.id.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return records, total

    def get_audit(self, audit_id: int) -> SelfHealingAudit | None:
        """获取单条审计记录，不存在返回 None。"""
        return (
            self._db.query(SelfHealingAudit)
            .filter(SelfHealingAudit.id == audit_id)
            .first()
        )
