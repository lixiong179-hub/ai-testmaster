"""跨设备迁移 AI 交互子 Mixin - Prompt 构建、AI 调用、响应解析。

将 AI 相关逻辑独立成子 Mixin，便于单独维护 Prompt 构建与响应解析的
复杂分支。本 Mixin 不持有独立的 __init__，依赖聚合类提供 self.db。
"""
import json
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from loguru import logger

from app.models.test_case import TestCase
from app.services.prompt_builder.migration_prompt import build_migration_prompt
from app.utils.ai_client_parser import parse_ai_json_object


@runtime_checkable
class MigrationAIClient(Protocol):
    """跨设备迁移所需的 AI 客户端协议。

    优先实现标准 ``AIClient.complete()`` 方法（返回 ``AIResponse``，取 ``.content``）；
    兼容旧 ``chat()`` 方法（返回 ``str``），仅供测试 MockAIClient 使用。
    ``_call_ai`` 通过 duck-typing 自动选择可用接口。
    """

    def complete(self, prompt: str) -> Any: ...


class CaseMigrationAiMixin:
    """跨设备迁移 AI 交互子 Mixin。

    提供 AI 调用、响应解析、AI 预览/迁移执行等方法；依赖聚合类提供
    ``self.db`` 与跨 Mixin 的 ``_error_preview_item`` / ``_create_migrated_cases``。
    """

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

    async def _ai_migrate_case(
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
            await self.db.rollback()
            logger.error(f"AI迁移遇到系统约束错误: {e}")
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"AI迁移Prompt构建或调用失败: {e}")
            return {"success": False, "error": f"AI迁移失败: {e}"}

        created_cases = await self._create_migrated_cases(
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
        """调用 AI 客户端获取响应文本。

        优先使用标准 AIClient.complete() 接口（返回 AIResponse，取 .content），
        兼容旧 chat() 接口（返回 str，供测试 MockAIClient 使用），
        最后回退到可调用对象。所有分支统一返回 str 或 None。
        """
        try:
            if hasattr(ai_client, "complete"):
                response = ai_client.complete(prompt)
                return response.content if response else None
            if hasattr(ai_client, "chat"):
                response = ai_client.chat(prompt)
                return str(response) if response else None
            if callable(ai_client):
                response = ai_client(prompt)
                return str(response) if response else None
            logger.error(
                "AI客户端未实现 complete/chat 方法且不可调用，"
                "类型: %s", type(ai_client).__name__
            )
            return None
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
