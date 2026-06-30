"""跨设备迁移持久化子 Mixin - 用例克隆/创建/查询。

将 DB 操作集中到独立子 Mixin，便于事务边界与 lifecycle 切换的管理。
本 Mixin 不持有独立的 __init__，依赖聚合类提供 self.db。
"""
from typing import Any, Dict, List, Optional

from loguru import logger

from app.models.test_case import (
    TestCase,
    enable_lifecycle_transition,
    disable_lifecycle_transition,
)
from app.models.project import Project
from app.services.case_number_service import CaseNumberService


class CaseMigrationPersistenceMixin:
    """跨设备迁移持久化子 Mixin。

    提供源用例查询、目标项目查询、用例克隆、迁移用例批量创建等方法；
    依赖聚合类提供 ``self.db``。
    """

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

    def _get_target_project(self, project_id: int) -> Optional[Project]:
        try:
            return self.db.query(Project).filter(Project.id == project_id).first()
        except Exception as e:
            logger.error(f"查询目标项目失败: {e}")
            return None

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
                case_no=CaseNumberService.generate(target_project_id, self.db),
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
        case_nos = CaseNumberService.generate_batch(target_project_id, len(adapted_cases), self.db)
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
