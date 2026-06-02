"""跨设备用例迁移服务 - 单条用例迁移、AI改写、结果入库。"""
import json
import uuid
from typing import Dict, Any, List, Optional, Protocol, runtime_checkable
from datetime import datetime
from loguru import logger

from sqlalchemy.orm import Session

from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.models.project import Project
from app.services.prompt_builder.migration_prompt import build_migration_prompt
from app.utils.ai_client_parser import parse_ai_json_object


@runtime_checkable
class MigrationAIClient(Protocol):
    """跨设备迁移所需的 AI 客户端协议。

    实现方必须提供 ``chat`` 方法，接受 prompt 字符串并返回文本响应。
    """

    def chat(self, prompt: str) -> str: ...


class CaseMigrationService:
    """跨设备用例迁移服务。"""

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
                case_nos = self._generate_case_nos(target_project_id, len(preview_cases))
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

    def _get_source_case(self, case_id: int) -> Optional[TestCase]:
        try:
            return (
                self.db.query(TestCase)
                .filter(TestCase.id == case_id, TestCase.is_deleted.is_(False))
                .first()
            )
        except Exception as e:
            logger.error(f"查询源用例失败: {e}")
            return None

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

    def _ai_preview_item(
        self,
        batch_id: str,
        source_case: TestCase,
        source_data: Dict[str, Any],
        source_device: str,
        target_device: str,
        target_ui_specs: str,
        ai_client: Any,
    ) -> Dict[str, Any]:
        prompt = build_migration_prompt(
            source_case=source_data,
            source_device=source_device,
            target_device=target_device,
            target_ui_specs=target_ui_specs,
        )
        ai_response = self._call_ai(ai_client, prompt)
        if not ai_response:
            return self._error_preview_item(batch_id, source_case.id, "AI调用失败，未返回结果")
        migration_result = self._parse_ai_response(ai_response)
        if not migration_result:
            return self._error_preview_item(batch_id, source_case.id, "AI返回格式解析失败")
        preview_cases = migration_result.get("adapted_cases", [])
        return {
            "batch_id": batch_id,
            "source_case_id": source_case.id,
            "source_device": source_device,
            "target_device": target_device,
            "migration_type": migration_result.get("migration_type", "adapted"),
            "confidence": float(migration_result.get("confidence") or 0),
            "preview_cases": preview_cases if isinstance(preview_cases, list) else [],
            "step_changes": migration_result.get("step_changes", []),
            "warnings": migration_result.get("new_scenarios", []),
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

    def _get_target_project(self, project_id: int) -> Optional[Project]:
        try:
            return self.db.query(Project).filter(Project.id == project_id).first()
        except Exception as e:
            logger.error(f"查询目标项目失败: {e}")
            return None

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

    def _clone_case(
        self,
        source_case: TestCase,
        target_device: str,
        target_project_id: int,
        source_device: str,
        batch_id: str,
    ) -> Dict[str, Any]:
        enable_lifecycle_transition()
        try:
            new_case = TestCase(
                project_id=target_project_id,
                case_no=self._generate_case_no(target_project_id),
                module=source_case.module,
                title=source_case.title,
                precondition=source_case.precondition,
                steps_json=source_case.steps_json,
                expected_result=source_case.expected_result,
                priority=source_case.priority,
                case_type=source_case.case_type,
                generate_status=1,
                target_device=target_device,
                migration_source_id=source_case.id,
                migration_type="cloned",
                migration_batch_id=batch_id,
                lifecycle_status="draft",
            )
            self.db.add(new_case)
            self.db.flush()
            self.db.commit()
            self.db.refresh(new_case)
            logger.info(f"用例克隆成功: {source_case.id} -> {new_case.id}")
            return {
                "success": True,
                "migration_type": "cloned",
                "new_case_id": new_case.id,
                "batch_id": batch_id,
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"用例克隆失败: {e}")
            return {"success": False, "error": f"克隆失败: {e}"}
        finally:
            disable_lifecycle_transition()

    def _ai_migrate_case(
        self,
        source_case: TestCase,
        source_data: Dict[str, Any],
        target_device: str,
        target_project_id: int,
        source_device: str,
        target_ui_specs: str,
        ai_client: Any,
        batch_id: str,
    ) -> Dict[str, Any]:
        try:
            prompt = build_migration_prompt(
                source_case=source_data,
                source_device=source_device,
                target_device=target_device,
                target_ui_specs=target_ui_specs,
            )
            ai_response = self._call_ai(ai_client, prompt)
            if not ai_response:
                return {"success": False, "error": "AI调用失败，未返回结果"}
            migration_result = self._parse_ai_response(ai_response)
            if not migration_result:
                return {"success": False, "error": "AI返回格式解析失败"}
        except RuntimeError as e:
            self.db.rollback()
            logger.error(f"AI迁移遇到系统约束错误: {e}")
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"AI迁移Prompt构建或调用失败: {e}")
            return {"success": False, "error": f"AI迁移失败: {e}"}

        created_cases = self._create_migrated_cases(
            migration_result, source_case, target_device,
            target_project_id, batch_id,
        )
        if not created_cases and migration_result.get("migration_type") != "deprecated":
            return {
                "success": False,
                "error": f"AI未返回改写用例内容，migration_type={migration_result.get('migration_type')}",
            }
        logger.info(
            f"AI迁移完成: 源用例{source_case.id}, "
            f"类型={migration_result.get('migration_type')}, "
            f"产出{len(created_cases)}条用例"
        )
        return {
            "success": True,
            "migration_type": migration_result.get("migration_type", "adapted"),
            "new_case_ids": [c.id for c in created_cases],
            "batch_id": batch_id,
            "step_changes": migration_result.get("step_changes", []),
            "new_scenarios": migration_result.get("new_scenarios", []),
            "deprecated_scenarios": migration_result.get("deprecated_scenarios", []),
        }

    def _call_ai(self, ai_client: Any, prompt: str) -> Optional[str]:
        try:
            if isinstance(ai_client, MigrationAIClient):
                response = ai_client.chat(prompt)
            elif callable(ai_client):
                response = ai_client(prompt)
            else:
                logger.error(
                    "AI客户端未实现 MigrationAIClient 协议且不可调用，"
                    "类型: %s", type(ai_client).__name__
                )
                return None
            return str(response) if response else None
        except Exception as e:
            logger.error(f"AI调用异常: {e}")
            return None

    def _parse_ai_response(self, response: str) -> Optional[Dict[str, Any]]:
        try:
            json_str = response.strip()
            if "```json" in json_str:
                parts = json_str.split("```json")
                if len(parts) > 1:
                    json_content = parts[1].split("```")
                    json_str = json_content[0].strip() if json_content else ""
            elif "```" in json_str:
                parts = json_str.split("```")
                if len(parts) > 2:
                    json_str = parts[1].strip()
            if not json_str:
                logger.error("AI返回的JSON内容为空")
                return None
            result = parse_ai_json_object(json_str)
            if result is None:
                logger.error("AI响应JSON解析失败")
                return None
            if "migration_type" not in result:
                logger.error("AI返回缺少migration_type字段")
                return None
            return result
        except (TypeError, IndexError) as e:
            logger.error(f"AI响应解析异常: {e}")
            return None

    def _create_migrated_cases(
        self,
        migration_result: Dict[str, Any],
        source_case: TestCase,
        target_device: str,
        target_project_id: int,
        batch_id: str,
    ) -> List[TestCase]:
        migration_type = migration_result.get("migration_type", "adapted")
        if migration_type == "deprecated":
            logger.info(f"用例{source_case.id}标记为废弃，不创建新用例")
            return []
        adapted_cases = migration_result.get("adapted_cases", [])
        if not adapted_cases:
            logger.error(f"AI返回adapted_cases为空，migration_type={migration_type}")
            return []
        case_nos = self._generate_case_nos(target_project_id, len(adapted_cases))
        created: List[TestCase] = []
        enable_lifecycle_transition()
        try:
            for idx, case_data in enumerate(adapted_cases):
                title = case_data.get("title", source_case.title)
                if migration_type == "split" and len(adapted_cases) > 1:
                    title = f"{title}({idx + 1})"
                steps = case_data.get("steps", [])
                steps_json = steps if isinstance(steps, list) else []
                new_case = TestCase(
                    project_id=target_project_id,
                    case_no=case_nos[idx],
                    module=case_data.get("module", source_case.module),
                    title=title,
                    precondition=case_data.get("precondition", source_case.precondition),
                    steps_json=steps_json,
                    expected_result=case_data.get("expected_result", source_case.expected_result),
                    priority=case_data.get("priority", source_case.priority),
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
                created.append(new_case)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            created = []
            logger.error(f"创建迁移用例失败，已回滚: {e}")
        finally:
            disable_lifecycle_transition()
        return created

    def _generate_case_nos(self, project_id: int, count: int) -> List[str]:
        """[deprecated] 批量生成用例编号，内部委托到 CaseNumberService。

        Args:
            project_id: 项目ID。
            count: 需要生成的编号数量。

        Returns:
            编号列表。
        """
        from app.services.case_number_service import CaseNumberService
        return CaseNumberService.generate_batch(project_id, count, self.db)

    def _generate_case_no(self, project_id: int) -> str:
        """[deprecated] 生成单条用例编号，内部委托到 CaseNumberService。

        Args:
            project_id: 项目ID。

        Returns:
            用例编号。
        """
        from app.services.case_number_service import CaseNumberService
        return CaseNumberService.generate(project_id, self.db)
