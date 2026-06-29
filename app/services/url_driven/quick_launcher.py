"""网址驱动快速测试 - QuickLauncher 编排入口。

编排顺序：AutoProjectBuilder.build → TaskAssembler.create_skeleton_task（预创建占位
任务拿 task_id）→ SiteExplorer.explore → AutoCaseGenerator.generate →
TaskAssembler.assemble，每步异常捕获并降级，全程通过 WebSocket 推送 4 阶段进度
到 `quick_test:{task_id}` 通道。

设计要点：
- 预创建占位任务：建项成功后立即 create_skeleton_task 拿 task_id，使前 2 阶段
  （站点探索/用例生成）的进度能实时推送到 `quick_test:{task_id}`，满足 spec
  "4 阶段进度条实时刷新"体验；assemble 阶段以 task_id=已有 更新 case_ids 并启动；
- 降级策略：建项失败抛出（无法继续）；探索失败降级空 SiteMap；生成失败降级空
  用例仍 assemble；assemble 失败仍返回已预创建 task_id 供查询；
- 全程异常捕获不整体崩溃，单步失败记录并推送对应 stage 的 failed 状态；
- 推送复用 PushService.push(channel, data)，通道不以 "task:" 开头，作为独立
  execution_id 广播，与执行引擎的 `task:{task_id}` 通道互不干扰。
"""
from typing import Callable, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.ai.client import AIClient
from app.models.test_case import TestCase
from app.schemas.quick_test import QuickTestLaunchResponse
from app.services.push_service import PushService, get_push_service
from app.services.url_driven.auto_case_generator import AutoCaseGenerator
from app.services.url_driven.auto_project_builder import AutoProjectBuilder
from app.services.url_driven.site_explorer import SiteExplorer, SiteMap
from app.services.url_driven.task_assembler import TaskAssembler

# WebSocket 推送通道模板（与 spec 通道命名 quick_test:{task_id} 一致）
_CHANNEL_TEMPLATE = "quick_test:{task_id}"
# 4 阶段进度标识（与 spec Task 8 一致）
_STAGE_SITE_EXPLORING = "site_exploring"
_STAGE_CASE_GENERATING = "case_generating"
_STAGE_TASK_ASSEMBLING = "task_assembling"
_STAGE_COMPLETED = "completed"
# 预估执行时长：每用例 30 秒（spec: estimated_duration_sec 按 case_count * 30）
_DURATION_PER_CASE_SEC = 30


class QuickLauncher:
    """一键快速测试编排入口。

    依赖注入：project_builder / explorer_factory / case_generator_factory /
    assembler / push_service / ai_client 均可注入，便于测试隔离外部依赖
    （浏览器/AI/WebSocket）。
    """

    def __init__(
        self,
        project_builder: Optional[AutoProjectBuilder] = None,
        explorer_factory: Optional[Callable[[], SiteExplorer]] = None,
        case_generator_factory: Optional[Callable[[], AutoCaseGenerator]] = None,
        assembler: Optional[TaskAssembler] = None,
        push_service: Optional[PushService] = None,
        ai_client: Optional[AIClient] = None,
    ) -> None:
        """注入编排链路组件，None 时用默认实现。

        Args:
            project_builder: URL 自动建项器。
            explorer_factory: 返回 SiteExplorer 的工厂（每次调用新建实例，
                避免 SiteExplorer 内部浏览器状态复用）。
            case_generator_factory: 返回 AutoCaseGenerator 的工厂。
            assembler: 任务编排器。
            push_service: WebSocket 推送服务。
            ai_client: AI 客户端，透传给 case_generator_factory，None 时由
                AutoCaseGenerator 内部懒加载默认主备切换客户端。
        """
        self._project_builder = project_builder or AutoProjectBuilder()
        self._explorer_factory = explorer_factory or (lambda: SiteExplorer())
        self._case_generator_factory = (
            case_generator_factory or self._default_case_generator_factory
        )
        self._push_service = push_service or get_push_service()
        self._assembler = assembler or TaskAssembler(push_service=self._push_service)
        self._ai_client = ai_client

    def _default_case_generator_factory(self) -> AutoCaseGenerator:
        """默认用例生成器工厂，透传 ai_client 支持测试注入。"""
        return AutoCaseGenerator(self._ai_client)

    async def launch(
        self,
        url: str,
        description: Optional[str],
        credentials: Optional[Dict[str, str]],
        user_id: int,
        session: Session,
    ) -> QuickTestLaunchResponse:
        """一键启动快速测试：建项 → 预创建任务 → 探索 → 生成 → 装配。

        Args:
            url: 被测站点 URL。
            description: 可选自然语言描述，聚焦测试范围。
            credentials: 可选登录凭据 {username, password}。
            user_id: 触发用户 ID（项目所有者与任务执行人）。
            session: SQLAlchemy 会话，由调用方管理事务。

        Returns:
            QuickTestLaunchResponse: task_id / project_id /
            estimated_duration_sec / websocket_channel。

        Raises:
            Exception: 建项失败时抛出（无法继续编排）。
        """
        # ① 建项（失败抛出，无法继续）
        project = self._project_builder.build(url, description, user_id, session)
        # ② 预创建占位任务，拿 task_id 用于 WebSocket 通道（建项成功后必做）
        task = self._assembler.create_skeleton_task(project.id, user_id, session)
        channel = _CHANNEL_TEMPLATE.format(task_id=task.id)

        # ③ 站点探索（失败降级为空 SiteMap）
        await self._push(channel, _STAGE_SITE_EXPLORING, "running", 10, {"url": url})
        site_map = await self._explore_safely(url, credentials, channel)

        # ④ 用例生成（失败降级为空用例）
        await self._push(channel, _STAGE_CASE_GENERATING, "running", 40, {})
        cases = await self._generate_cases_safely(
            site_map, project.id, description, user_id, session, channel
        )
        case_ids = [case.id for case in cases]

        # ⑤ 任务装配（失败仍返回已预创建 task_id）
        await self._push(
            channel, _STAGE_TASK_ASSEMBLING, "running", 70, {"case_count": len(case_ids)}
        )
        await self._assemble_safely(project.id, case_ids, user_id, session, task, channel)

        # ⑥ 完成
        estimated = len(case_ids) * _DURATION_PER_CASE_SEC
        await self._push(
            channel, _STAGE_COMPLETED, "done", 100,
            {"task_id": task.id, "project_id": project.id, "case_count": len(case_ids)},
        )
        return QuickTestLaunchResponse(
            task_id=task.id,
            project_id=project.id,
            estimated_duration_sec=estimated,
            websocket_channel=channel,
        )

    async def _explore_safely(
        self, url: str, credentials: Optional[Dict[str, str]], channel: str
    ) -> SiteMap:
        """站点探索，异常降级为空 SiteMap 并推送 failed 状态。"""
        try:
            site_map = await self._explorer_factory().explore(url, credentials)
            await self._push(
                channel, _STAGE_SITE_EXPLORING, "done", 30,
                {"pages": len(site_map.pages), "explored": site_map.explored_count},
            )
            return site_map
        except Exception as exc:
            logger.warning(f"站点探索失败，降级为空 SiteMap: url={url} err={exc}")
            await self._push(
                channel, _STAGE_SITE_EXPLORING, "failed", 30,
                {"error": str(exc), "degraded": True},
            )
            return SiteMap(
                entry_url=url, pages=[], max_depth_reached=0,
                explored_count=0, skipped_count=1, cache_key="",
            )

    async def _generate_cases_safely(
        self, site_map: SiteMap, project_id: int, description: Optional[str],
        user_id: int, session: Session, channel: str,
    ) -> List[TestCase]:
        """用例生成，异常降级为空用例并推送 failed 状态。"""
        try:
            generator = self._case_generator_factory()
            cases = generator.generate(site_map, project_id, description, user_id, session)
            await self._push(
                channel, _STAGE_CASE_GENERATING, "done", 60,
                {"case_count": len(cases)},
            )
            return cases
        except Exception as exc:
            logger.warning(f"用例生成失败，降级为空用例: project_id={project_id} err={exc}")
            await self._push(
                channel, _STAGE_CASE_GENERATING, "failed", 60,
                {"error": str(exc), "degraded": True},
            )
            return []

    async def _assemble_safely(
        self, project_id: int, case_ids: List[int], user_id: int,
        session: Session, task, channel: str,
    ) -> None:
        """任务装配，异常不阻断（仍返回已预创建 task_id）。

        assemble 成功时同步更新外层 task 对象的 case_ids/total_count，
        保证 launch 返回的 estimated_duration_sec 基于真实用例数。
        """
        try:
            updated = await self._assembler.assemble(
                project_id, case_ids, user_id, session, task_id=task.id
            )
            task.case_ids = updated.case_ids
            task.total_count = updated.total_count
            await self._push(
                channel, _STAGE_TASK_ASSEMBLING, "done", 90, {"task_id": task.id}
            )
        except Exception as exc:
            logger.error(
                f"任务装配失败，仍返回已预创建 task_id: task_id={task.id} err={exc}"
            )
            await self._push(
                channel, _STAGE_TASK_ASSEMBLING, "failed", 90,
                {"error": str(exc), "task_id": task.id},
            )

    async def _push(
        self, channel: str, stage: str, status: str, progress: int, detail: Dict,
    ) -> None:
        """推送阶段进度到 WebSocket，失败仅记录不阻断业务。"""
        data = {
            "stage": stage, "status": status, "progress": progress, "detail": detail,
        }
        try:
            await self._push_service.push(channel, data)
        except Exception as exc:
            logger.warning(
                f"WebSocket 推送失败: channel={channel} stage={stage} err={exc}"
            )
