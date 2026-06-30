"""跨设备用例迁移服务 - 单条用例迁移、批量预览/提交/回滚。

聚合 AI 交互、持久化、预览载荷三种子 Mixin，对外暴露迁移服务的
公共 API。本模块保留 CaseMigrationService 类定义以维持导入路径
兼容（``from app.services.case_migration import CaseMigrationService``）。
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.services.case_number_service import CaseNumberService
from app.services.case_migration._ai_mixin import CaseMigrationAiMixin
from app.services.case_migration._persistence_mixin import CaseMigrationPersistenceMixin
from app.services.case_migration._preview_payload_mixin import (
    CaseMigrationPreviewPayloadMixin,
)


class CaseMigrationService(
    CaseMigrationPreviewPayloadMixin,
    CaseMigrationAiMixin,
    CaseMigrationPersistenceMixin,
):
    """跨设备用例迁移服务。

    通过继承三种子 Mixin（预览载荷/AI 交互/持久化）聚合完整迁移能力，
    对外提供单条迁移、批量预览、批量提交、批次查询、批次回滚 5 个公共方法。
    """

    def __init__(self, db: Session):
        self.db = db

    def migrate_single_case(
        self,
        source_case_id: int,
        target_device: str,
        target_project_id: int,
        source_device: str = "tablet",
        target_ui_specs: str = "",
        ai_client: Any = None,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        source_case = self._get_source_case(source_case_id)
        if not source_case:
            return {"success": False, "error": f"源用例不存在: {source_case_id}"}
        if source_device == target_device:
            return {"success": False, "error": f"源设备与目标设备相同({source_device})，无需迁移"}
        target_project = self._get_target_project(target_project_id)
        if not target_project:
            return {"success": False, "error": f"目标项目不存在: {target_project_id}"}
        if batch_id is None:
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        source_data = self._case_to_dict(source_case)
        if source_data.get("case_type") == "api_automation":
            return self._clone_case(
                source_case, target_device, target_project_id, source_device, batch_id
            )
        if not ai_client:
            return {"success": False, "error": "UI用例迁移需要AI客户端"}
        return self._ai_migrate_case(
            source_case, source_data, target_device, target_project_id,
            source_device, target_ui_specs, ai_client, batch_id,
        )

    def preview_batch(
        self,
        source_case_ids: List[int],
        target_device: str,
        target_project_id: int,
        source_device: str = "tablet",
        target_ui_specs: str = "",
        ai_client: Any = None,
    ) -> Dict[str, Any]:
        """批量迁移预览，不写入正式目标用例。"""
        batch_id = f"preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        items: List[Dict[str, Any]] = []
        for case_id in source_case_ids:
            source_case = self._get_source_case(case_id)
            if not source_case:
                items.append(self._error_preview_item(batch_id, case_id, f"源用例不存在: {case_id}"))
                continue
            source_data = self._case_to_dict(source_case)
            if source_data.get("case_type") == "api_automation":
                items.append(self._clone_preview_item(batch_id, source_case, source_device, target_device))
                continue
            if not ai_client:
                items.append(self._error_preview_item(batch_id, case_id, "UI用例迁移需要AI客户端"))
                continue
            items.append(
                self._ai_preview_item(
                    batch_id=batch_id,
                    source_case=source_case,
                    source_data=source_data,
                    source_device=source_device,
                    target_device=target_device,
                    target_ui_specs=target_ui_specs,
                    ai_client=ai_client,
                )
            )
        return self._batch_payload(batch_id, source_device, target_device, items)

    def commit_batch(
        self,
        preview_items: List[Dict[str, Any]],
        target_project_id: int,
        target_device: str,
    ) -> Dict[str, Any]:
        """确认批量迁移预览结果并写入目标项目。"""
        batch_id = self._preview_batch_id(preview_items)
        created_case_ids: List[int] = []
        errors: List[str] = []
        try:
            enable_lifecycle_transition()
            for item in preview_items:
                if item.get("errors"):
                    continue
                migration_type = item.get("migration_type", "adapted")
                if migration_type == "deprecated":
                    continue
                source_case = self._get_source_case(int(item.get("source_case_id") or 0))
                if not source_case:
                    errors.append(f"源用例不存在: {item.get('source_case_id')}")
                    continue
                preview_cases = item.get("preview_cases")
                if not isinstance(preview_cases, list) or not preview_cases:
                    errors.append(f"预览用例为空: {source_case.id}")
                    continue
                case_nos = CaseNumberService.generate_batch(target_project_id, len(preview_cases), self.db)
                for idx, case_data in enumerate(preview_cases):
                    if not isinstance(case_data, dict):
                        continue
                    new_case = TestCase(
                        project_id=target_project_id,
                        case_no=case_nos[idx],
                        module=str(case_data.get("module") or source_case.module or "迁移用例"),
                        title=str(case_data.get("title") or source_case.title or "迁移用例"),
                        precondition=str(case_data.get("precondition") or source_case.precondition or ""),
                        steps_json=case_data.get("steps") if isinstance(case_data.get("steps"), list) else [],
                        expected_result=str(
                            case_data.get("expected_result") or source_case.expected_result or ""
                        ),
                        priority=int(case_data.get("priority") or source_case.priority or 2),
                        case_type=source_case.case_type,
                        generate_status=1,
                        target_device=target_device,
                        migration_source_id=source_case.id,
                        migration_type=migration_type,
                        migration_batch_id=batch_id,
                        lifecycle_status="draft",
                    )
                    self.db.add(new_case)
                    self.db.flush()
                    created_case_ids.append(new_case.id)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error(f"批量迁移提交失败: {exc}")
            return {"success": False, "batch_id": batch_id, "created_case_ids": [], "errors": [str(exc)]}
        finally:
            disable_lifecycle_transition()
        return {
            "success": len(errors) == 0,
            "batch_id": batch_id,
            "created_case_ids": created_case_ids,
            "errors": errors,
        }

    def get_batch_cases(self, batch_id: str) -> Dict[str, Any]:
        cases = (
            self.db.query(TestCase)
            .filter(TestCase.migration_batch_id == batch_id, TestCase.is_deleted.is_(False))
            .all()
        )
        return {
            "batch_id": batch_id,
            "case_count": len(cases),
            "case_ids": [case.id for case in cases],
        }

    def rollback_batch(self, batch_id: str) -> Dict[str, Any]:
        cases = (
            self.db.query(TestCase)
            .filter(TestCase.migration_batch_id == batch_id, TestCase.is_deleted.is_(False))
            .all()
        )
        for case in cases:
            case.is_deleted = True
        self.db.commit()
        return {"batch_id": batch_id, "rolled_back_count": len(cases)}
