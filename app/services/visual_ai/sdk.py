"""视觉调用统一 SDK 化（Task 9）。

设计目的：
    VisualAISDK 封装 BaselineService、ComparisonEngine、DOM 序列化与 Token
    估算器，提供面向业务场景的高层 API。调用方无需直接操作 StorageBackend、
    AsyncSession 或 ComparisonEngine，通过 SDK 即可完成完整的视觉回归流程。

核心能力：
    - create_baseline   : 上传截图创建基线
    - get_baseline      : 查询页面活跃基线
    - compare           : 对比当前截图与基线
    - run_visual_check  : 一站式视觉校验（见 _sdk_check_mixin）
    - approve_diff      : 审批 Diff
    - update_baseline   : 更新基线截图
    - list_baselines    : 列出基线
    - list_diffs        : 列出 Diff

设计原则：
    - 门面模式：SDK 作为子系统入口，隐藏内部组件交互
    - 依赖注入：AsyncSession、StorageBackend、AIClient 由调用方注入
    - 成本可控：run_visual_check 内置 Token 预检，超限自动降级跳过 LLM
    - 流程拆分：Diff 持久化/DOM 报告等流程化逻辑抽到 _sdk_helpers，主类聚焦编排；
      一站式校验流程抽到 _sdk_check_mixin，控制单文件行数
"""
from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import select

from app.core.config import settings
from app.models.baseline_approval import BaselineApproval
from app.models.visual_baseline import VisualBaseline
from app.models.visual_diff import VisualDiff
from app.services.storage.base import StorageBackend
from app.services.visual_ai._sdk_check_mixin import VisualCheckMixin, VisualCheckResult
from app.services.visual_ai.baseline_service import BaselineService
from app.services.visual_ai.comparison_engine import ComparisonEngine, ComparisonResult
from app.services.visual_ai.token_estimator import VisualTokenEstimator


class VisualAISDK(VisualCheckMixin):
    """视觉 AI 统一 SDK。

    封装视觉回归测试全流程，提供面向业务场景的高层 API。

    使用方式：
        sdk = VisualAISDK(db=session, storage=get_storage())
        # 创建基线
        baseline = await sdk.create_baseline(
            project_id=1, page_url="http://...", viewport_width=1280,
            viewport_height=800, image_bytes=png_bytes, name="登录页基线",
        )
        # 一站式视觉校验
        result = await sdk.run_visual_check(
            project_id=1, page_url="http://...", viewport_width=1280,
            viewport_height=800, current_image_bytes=png_bytes,
        )
    """

    def __init__(
        self,
        db: Any,
        storage: StorageBackend,
        ai_client: Optional[Any] = None,
        redis_client: Optional[Any] = None,
    ) -> None:
        """初始化 SDK。

        Args:
            db: 异步数据库会话
            storage: 存储后端实例
            ai_client: AI 客户端（为 None 时跳过 LLM 分析）
            redis_client: Redis 客户端（为 None 时 Token 预算走内存降级）
        """
        self._db = db
        self._storage = storage
        self._ai_client = ai_client
        self._redis_client = redis_client
        self._baseline_service = BaselineService(db=db, storage=storage)
        self._estimator = VisualTokenEstimator()

    async def create_baseline(
        self,
        project_id: int,
        name: str,
        page_url: str,
        viewport_width: int,
        viewport_height: int,
        image_bytes: bytes,
        match_level: str = "strict",
        test_case_id: Optional[int] = None,
        dom_html: Optional[str] = None,
        created_by: Optional[int] = None,
    ) -> VisualBaseline:
        """创建视觉基线。"""
        dom_bytes = dom_html.encode("utf-8") if dom_html else None
        return await self._baseline_service.create_baseline(
            project_id=project_id,
            name=name,
            page_url=page_url,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            image_bytes=image_bytes,
            match_level=match_level,
            test_case_id=test_case_id,
            dom_snapshot_bytes=dom_bytes,
            created_by=created_by,
        )

    async def get_baseline(
        self,
        project_id: int,
        page_url: str,
        viewport_width: int,
        viewport_height: int,
    ) -> Optional[VisualBaseline]:
        """查询页面活跃基线。"""
        return await self._baseline_service.get_active_baseline(
            project_id=project_id,
            page_url=page_url,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )

    async def list_baselines(
        self,
        project_id: int,
        status: Optional[str] = None,
        test_case_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> List[VisualBaseline]:
        """列出基线。"""
        return await self._baseline_service.list_baselines(
            project_id=project_id,
            status=status,
            test_case_id=test_case_id,
            offset=offset,
            limit=limit,
        )

    async def update_baseline(
        self,
        baseline_id: int,
        new_image_bytes: bytes,
        match_level: Optional[str] = None,
        dom_html: Optional[str] = None,
    ) -> VisualBaseline:
        """更新基线截图，旧版本归档。"""
        dom_bytes = dom_html.encode("utf-8") if dom_html else None
        return await self._baseline_service.update_baseline(
            baseline_id=baseline_id,
            new_image_bytes=new_image_bytes,
            match_level=match_level,
            dom_snapshot_bytes=dom_bytes,
        )

    async def delete_baseline(self, baseline_id: int) -> bool:
        """删除基线及其存储文件。"""
        return await self._baseline_service.delete_baseline(baseline_id)

    async def compare(
        self,
        baseline_id: int,
        current_image_bytes: bytes,
        match_level: Optional[str] = None,
        enable_llm_analysis: bool = True,
    ) -> ComparisonResult:
        """对比当前截图与指定基线。"""
        baseline = await self._baseline_service.get_baseline_by_id(baseline_id)
        if baseline is None:
            raise ValueError(f"基线不存在: id={baseline_id}")

        baseline_image = await self._baseline_service.load_baseline_image(baseline_id)

        engine = ComparisonEngine(
            ai_client=self._ai_client,
            llm_analysis_threshold=settings.VISUAL_AI_LLM_ANALYSIS_THRESHOLD,
            llm_token_limit=settings.VISUAL_AI_LLM_TOKEN_LIMIT,
        )
        return await engine.compare(
            baseline_bytes=baseline_image,
            current_bytes=current_image_bytes,
            match_level=match_level or baseline.match_level,
            enable_llm_analysis=enable_llm_analysis,
        )

    async def approve_diff(
        self,
        project_id: int,
        diff_id: int,
        action: str,
        comment: Optional[str] = None,
        reviewer_id: Optional[int] = None,
    ) -> BaselineApproval:
        """审批 Diff 记录。

        Args:
            project_id: 项目 ID
            diff_id: Diff ID
            action: 审批动作（approve/reject/update_baseline）
            comment: 审批意见
            reviewer_id: 审批人用户 ID

        Returns:
            BaselineApproval: 审批记录
        """
        diff = await self._db.get(VisualDiff, diff_id)
        if diff is None or diff.project_id != project_id:
            raise ValueError(f"Diff 不存在: id={diff_id}")

        approval = BaselineApproval(
            project_id=project_id,
            diff_id=diff_id,
            baseline_id=diff.baseline_id,
            action=action,
            comment=comment,
            reviewer_id=reviewer_id,
        )
        self._db.add(approval)

        if action == "approve":
            diff.status = "approved"
        elif action == "reject":
            diff.status = "rejected"
        elif action == "update_baseline":
            diff.status = "approved"

        await self._db.commit()
        await self._db.refresh(approval)
        return approval

    async def list_diffs(
        self,
        project_id: int,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> List[VisualDiff]:
        """列出 Diff 记录。"""
        stmt = select(VisualDiff).where(VisualDiff.project_id == project_id)
        if status:
            stmt = stmt.where(VisualDiff.status == status)
        stmt = stmt.order_by(VisualDiff.created_at.desc()).offset(offset).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())


__all__ = ["VisualAISDK", "VisualCheckResult"]
