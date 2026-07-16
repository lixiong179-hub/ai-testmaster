"""网址驱动快速测试 - QuickLauncher 编排入口。

编排顺序：AutoProjectBuilder.build → TaskAssembler.create_skeleton_task（预创建占位
任务拿 task_id）→ 后台 asyncio.create_task 异步执行：SiteExplorer.explore →
AutoCaseGenerator.generate → TaskAssembler.assemble，每步异常捕获并降级，全程
通过 WebSocket 推送 4 阶段进度到 `quick_test:{task_id}` 通道。

设计要点：
- launch 立即返回 task_id：同步部分仅建项+预创建任务（用 request session），
  探索+生成+装配在后台 asyncio.create_task 异步执行（用独立 session），避免
  同步执行 4 阶段阻塞 HTTP 连接（nginx/uvicorn 默认 60s 超时），且消除"前端
  订阅前已发推送"的设计缺陷（spec BUG 8 onOpen refreshStatus 补丁的根因）；
- 独立 session 隔离：后台任务用 PrimarySessionLocal 创建独立 session，避免
  request-scoped session 在请求结束后被 get_db() 关闭导致后续 commit 静默
  失败（与 BUG 1 同根因）；
- 降级策略：建项失败抛出（无法继续）；探索失败降级空 SiteMap；生成失败降级空
  用例仍 assemble；assemble 失败仍返回已预创建 task_id 供查询；
- 全程异常捕获不整体崩溃，单步失败记录并推送对应 stage 的 failed 状态；
- 推送复用 PushService.push(channel, data)，通道不以 "task:" 开头，作为独立
  execution_id 广播，与执行引擎的 `task:{task_id}` 通道互不干扰。
"""
import asyncio
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

# 4 阶段进度标识（与 spec Task 8 一致）
_STAGE_SITE_EXPLORING = "site_exploring"
_STAGE_CASE_GENERATING = "case_generating"
_STAGE_TASK_ASSEMBLING = "task_assembling"
_STAGE_COMPLETED = "completed"


class QuickLauncher:
    """一键快速测试编排入口。

    依赖注入：project_builder / explorer_factory / case_generator_factory /
    assembler / push_service / ai_client / pipeline_session_factory 均可注入，
    便于测试隔离外部依赖（浏览器/AI/WebSocket/DB session）。
    """

    def __init__(
        self,
        project_builder: Optional[AutoProjectBuilder] = None,
        explorer_factory: Optional[Callable[[], SiteExplorer]] = None,
        case_generator_factory: Optional[Callable[[], AutoCaseGenerator]] = None,
        assembler: Optional[TaskAssembler] = None,
        push_service: Optional[PushService] = None,
        ai_client: Optional[AIClient] = None,
        pipeline_session_factory: Optional[Callable[[], Session]] = None,
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
            pipeline_session_factory: 后台编排 session 工厂，None 时 lazy
                import PrimarySessionLocal 创建独立 session（生产场景）；
                测试场景注入 db fixture session 工厂，使 _run_pipeline_async
                写入的数据落在 db fixture 事务隔离内，保证测试结束自动回滚。
        """
        self._project_builder = project_builder or AutoProjectBuilder()
        self._explorer_factory = explorer_factory or (lambda: SiteExplorer())
        self._case_generator_factory = (
            case_generator_factory or self._default_case_generator_factory
        )
        self._push_service = push_service or get_push_service()
        self._assembler = assembler or TaskAssembler(push_service=self._push_service)
        self._ai_client = ai_client
        self._pipeline_session_factory = pipeline_session_factory

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
        """一键启动快速测试：建项 → 预创建任务 → 后台异步执行探索+生成+装配。

        launch 立即返回 task_id，编排在后台 asyncio.create_task 异步执行，
        避免同步执行 4 阶段阻塞 HTTP 连接（nginx/uvicorn 默认 60s 超时）。
        前端拿到 task_id 后立即订阅 WebSocket 接收 4 阶段进度推送。

        Args:
            url: 被测站点 URL。
            description: 可选自然语言描述，聚焦测试范围。
            credentials: 可选登录凭据 {username, password}。
            user_id: 触发用户 ID（项目所有者与任务执行人）。
            session: SQLAlchemy 会话（request-scoped，仅用于建项与预创建任务）。

        Returns:
            QuickTestLaunchResponse: task_id / project_id /
            estimated_duration_sec / websocket_channel。estimated_duration_sec
            为 0（case_count 未知，前端按 WebSocket 推送的 case_count 动态更新）。

        Raises:
            Exception: 建项失败时抛出（无法继续编排）。
        """
        # ① 建项（失败抛出，无法继续）
        project = self._project_builder.build(url, description, user_id, session)
        # ② 预创建占位任务，拿 task_id 用于 WebSocket 通道（建项成功后必做）
        task = self._assembler.create_skeleton_task(project.id, user_id, session)
        channel = f"quick_test:{task.id}"
        # ③ 推送 site_exploring running 后立即启动后台编排
        await self._push(channel, _STAGE_SITE_EXPLORING, "running", 10, {"url": url})
        asyncio.create_task(self._run_pipeline_async(
            task_id=task.id, project_id=project.id, url=url,
            credentials=credentials, description=description,
            user_id=user_id, channel=channel,
        ))
        logger.info(
            f"快速测试编排已异步启动: task_id={task.id} project_id={project.id}"
        )
        # ④ 立即返回，前端拿到 task_id 后立即订阅 WebSocket 接收推送
        return QuickTestLaunchResponse(
            task_id=task.id,
            project_id=project.id,
            estimated_duration_sec=0,
            websocket_channel=channel,
        )

    async def _run_pipeline_async(
        self,
        task_id: int,
        project_id: int,
        url: str,
        credentials: Optional[Dict[str, str]],
        description: Optional[str],
        user_id: int,
        channel: str,
    ) -> None:
        """后台执行编排：探索 → 生成 → 装配，使用独立 session。

        每阶段推送进度到 quick_test:{task_id} 通道，异常兜底推送 failed 状态。
        编排完成后由 TaskAssembler._start_task 内的 _run_executor_safely 接力
        推送执行引擎进度与终态。使用独立 session（PrimarySessionLocal 或
        pipeline_session_factory 注入），避免 request-scoped session 在请求
        结束后被关闭导致后续 commit 静默失败（与 BUG 1 同根因）。
        """
        session = self._create_pipeline_session()
        try:
            # ① 站点探索（失败降级为空 SiteMap）
            site_map = await self._explore_safely(url, credentials, channel)
            # ② 用例生成（失败降级为空用例）
            await self._push(channel, _STAGE_CASE_GENERATING, "running", 40, {})
            cases = await self._generate_cases_safely(
                site_map, project_id, description, user_id, session, channel
            )
            case_ids = [case.id for case in cases]
            # ③ 任务装配（失败仍返回已预创建 task_id）
            await self._push(
                channel, _STAGE_TASK_ASSEMBLING, "running", 70, {"case_count": len(case_ids)}
            )
            await self._assemble_safely(
                project_id, case_ids, user_id, session, task_id, channel
            )
            # ④ 编排完成（执行引擎进度由 _run_executor_safely 推送）
            await self._push(
                channel, _STAGE_COMPLETED, "done", 100,
                {"task_id": task_id, "project_id": project_id, "case_count": len(case_ids)},
            )
        except Exception as exc:
            logger.error(f"编排异常: task_id={task_id} err={exc}")
            await self._push(
                channel, _STAGE_COMPLETED, "failed", 100,
                {"error": str(exc), "task_id": task_id, "degraded": True},
            )
        finally:
            session.close()

    def _create_pipeline_session(self) -> Session:
        """创建后台编排专用 session。

        生产场景：lazy import PrimarySessionLocal 创建独立会话；
        测试场景：通过构造参数 pipeline_session_factory 注入测试 session，
        使 _run_pipeline_async 写入的数据落在 db fixture 事务隔离内，
        保证测试结束自动回滚清理。
        """
        if self._pipeline_session_factory is not None:
            return self._pipeline_session_factory()
        from app.db.database import PrimarySessionLocal
        return PrimarySessionLocal()

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
        """用例生成，异常降级为空用例并推送 failed 状态。

        sync generate 通过 asyncio.to_thread 放到独立线程执行，避免阻塞事件循环；
        AI 生成调用受模块级信号量保护，限制跨请求总并发（P-2 修复）。
        session 在本方法执行期间不会被主线程访问，跨线程使用安全。
        """
        from app.utils.ai_concurrency import ai_generation_slot

        try:
            generator = self._case_generator_factory()
            async with ai_generation_slot():
                cases = await asyncio.to_thread(
                    generator.generate,
                    site_map, project_id, description, user_id, session,
                )
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
        session: Session, task_id: int, channel: str,
    ) -> None:
        """任务装配，异常不阻断（仍返回已预创建 task_id）。

        异步化后 launch 已立即返回，不再需要更新外层 task 对象；assemble
        内部已更新 DB 中的 task.case_ids/total_count 并启动执行引擎。
        """
        try:
            await self._assembler.assemble(
                project_id, case_ids, user_id, session, task_id=task_id
            )
            await self._push(
                channel, _STAGE_TASK_ASSEMBLING, "done", 90, {"task_id": task_id}
            )
        except Exception as exc:
            logger.error(
                f"任务装配失败，仍返回已预创建 task_id: task_id={task_id} err={exc}"
            )
            await self._push(
                channel, _STAGE_TASK_ASSEMBLING, "failed", 90,
                {"error": str(exc), "task_id": task_id},
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
