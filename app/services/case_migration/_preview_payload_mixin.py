"""跨设备迁移预览载荷子 Mixin - 预览项构建与批次摘要。

将预览阶段的载荷构造逻辑集中到独立子 Mixin，与 AI 调用和持久化
解耦。本 Mixin 不持有独立的 __init__，依赖聚合类提供 self.db。
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List

from app.models.test_case import TestCase


class CaseMigrationPreviewPayloadMixin:
    """跨设备迁移预览载荷子 Mixin。

    提供克隆预览项、错误预览项、批次摘要、批次ID提取、用例字典化等方法；
    所有方法均为纯数据构造，不直接调用 AI 或 DB。
    """

    def _clone_preview_item(
        self,
        batch_id: str,
        source_case: TestCase,
        source_device: str,
        target_device: str,
    ) -> Dict[str, Any]:
        source_data = self._case_to_dict(source_case)
        preview_case = {
            "title": source_data["title"],
            "module": source_data["module"],
            "precondition": source_data["precondition"],
            "steps": source_data["steps_json"],
            "expected_result": source_data["expected_result"],
            "priority": source_data["priority"],
        }
        return {
            "batch_id": batch_id,
            "source_case_id": source_case.id,
            "source_device": source_device,
            "target_device": target_device,
            "migration_type": "cloned",
            "confidence": 1.0,
            "preview_cases": [preview_case],
            "step_changes": [],
            "warnings": [],
            "errors": [],
        }

    def _error_preview_item(self, batch_id: str, source_case_id: int, error: str) -> Dict[str, Any]:
        return {
            "batch_id": batch_id,
            "source_case_id": source_case_id,
            "migration_type": "deprecated",
            "confidence": 0.0,
            "preview_cases": [],
            "step_changes": [],
            "warnings": [],
            "errors": [error],
        }

    def _batch_payload(
        self,
        batch_id: str,
        source_device: str,
        target_device: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        summary = {
            "total": len(items),
            "success": sum(1 for item in items if not item.get("errors")),
            "failed": sum(1 for item in items if item.get("errors")),
            "cloned": sum(1 for item in items if item.get("migration_type") == "cloned"),
            "adapted": sum(1 for item in items if item.get("migration_type") == "adapted"),
            "split": sum(1 for item in items if item.get("migration_type") == "split"),
            "new": sum(1 for item in items if item.get("migration_type") == "new"),
            "deprecated": sum(1 for item in items if item.get("migration_type") == "deprecated"),
        }
        return {
            "batch_id": batch_id,
            "source_device": source_device,
            "target_device": target_device,
            "summary": summary,
            "items": items,
        }

    def _preview_batch_id(self, preview_items: List[Dict[str, Any]]) -> str:
        for item in preview_items:
            batch_id = item.get("batch_id")
            if batch_id:
                return str(batch_id)
        return f"commit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    def _case_to_dict(self, case: TestCase) -> Dict[str, Any]:
        steps_json = case.steps_json
        if isinstance(steps_json, str):
            try:
                steps_json = json.loads(steps_json)
            except (json.JSONDecodeError, TypeError):
                steps_json = []
        return {
            "title": case.title or "",
            "precondition": case.precondition or "",
            "steps_json": steps_json or [],
            "expected_result": case.expected_result or "",
            "priority": case.priority or 2,
            "case_type": case.case_type or "ui_automation",
            "module": case.module or "",
        }
