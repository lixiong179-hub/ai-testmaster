"""基线服务（Task 5）- VisualBaseline CRUD 与版本管理。

设计目的：
    BaselineService 封装视觉基线的创建、查询、更新、删除与版本管理逻辑。
    基线截图持久化至 StorageBackend，元数据持久化至 MySQL，通过 project_id
    实现多项目隔离。

核心能力：
    - create_baseline      : 上传截图创建基线，自动生成 StorageBackend key
    - get_active_baseline  : 按项目+页面+视口查询当前活跃基线
    - get_baseline_by_id   : 按主键查询基线
    - list_baselines       : 按项目列出基线（支持状态/用例过滤）
    - update_baseline      : 更新基线截图，旧版本归档，新版本递增
    - delete_baseline      : 删除基线及其存储文件
    - get_baseline_history : 获取页面+视口的基线版本历史

设计原则：
    - 依赖注入：AsyncSession 与 StorageBackend 由调用方注入
    - 版本管理：更新基线时旧版本 status→superseded，新版本 status=active
    - 存储隔离：StorageBackend key 按 project_id 分前缀
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from loguru import logger
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.visual_baseline import VisualBaseline, MATCH_LEVEL_VALUES
from app.services.storage.base import StorageBackend


class BaselineService:
    """视觉基线 CRUD 服务。

    使用方式：
        service = BaselineService(db=session, storage=get_storage())
        baseline = await service.create_baseline(
            project_id=1, page_url="http://...", viewport_width=1280,
            viewport_height=800, image_bytes=png_bytes, created_by=42,
        )
    """

    def __init__(self, db: AsyncSession, storage: StorageBackend) -> None:
        """初始化基线服务。

        Args:
            db: 异步数据库会话
            storage: 存储后端实例（LocalStorage 或 S3Storage）
        """
        self._db = db
        self._storage = storage

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
        dom_snapshot_bytes: Optional[bytes] = None,
        created_by: Optional[int] = None,
    ) -> VisualBaseline:
        """创建新基线。

        若同一 project+page+viewport 已有活跃基线，新基线版本号递增，
        旧基线不自动归档（需调用 update_baseline 触发归档）。

        Args:
            project_id: 项目 ID
            name: 基线名称
            page_url: 被测页面 URL
            viewport_width: 视口宽度
            viewport_height: 视口高度
            image_bytes: 基线截图字节流（PNG/JPEG）
            match_level: 对比模式（strict/layout/ignore_colors）
            test_case_id: 关联测试用例 ID（可空）
            dom_snapshot_bytes: DOM 快照字节流（可空，Layout Match Level 使用）
            created_by: 创建者用户 ID

        Returns:
            VisualBaseline: 创建的基线记录
        """
        if match_level not in MATCH_LEVEL_VALUES:
            raise ValueError(f"非法 match_level: {match_level}，可选值: {MATCH_LEVEL_VALUES}")

        # 查询当前最大版本号
        max_version = await self._get_max_version(project_id, page_url, viewport_width, viewport_height)
        new_version = max_version + 1

        # 上传截图到 StorageBackend
        image_key = self._build_image_key(project_id, page_url, viewport_width, viewport_height, new_version)
        image_obj = await self._storage.save(image_key, image_bytes, content_type="image/png")

        # 获取图片尺寸
        image_width, image_height = self._get_image_dimensions(image_bytes)

        # 上传 DOM 快照（可选）
        dom_snapshot_key: Optional[str] = None
        if dom_snapshot_bytes:
            dom_snapshot_key = self._build_dom_key(project_id, page_url, viewport_width, viewport_height, new_version)
            await self._storage.save(dom_snapshot_key, dom_snapshot_bytes, content_type="application/json")

        baseline = VisualBaseline(
            project_id=project_id,
            test_case_id=test_case_id,
            name=name,
            page_url=page_url,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            image_key=image_key,
            image_width=image_width,
            image_height=image_height,
            match_level=match_level,
            dom_snapshot_key=dom_snapshot_key,
            status="active",
            version=new_version,
            created_by=created_by,
        )
        self._db.add(baseline)
        await self._db.commit()
        await self._db.refresh(baseline)

        logger.info(
            f"[VisualAI] 基线创建: project={project_id}, name={name}, "
            f"version={new_version}, key={image_key}"
        )
        return baseline

    async def get_active_baseline(
        self,
        project_id: int,
        page_url: str,
        viewport_width: int,
        viewport_height: int,
    ) -> Optional[VisualBaseline]:
        """查询当前活跃基线（status=active）。

        Args:
            project_id: 项目 ID
            page_url: 被测页面 URL
            viewport_width: 视口宽度
            viewport_height: 视口高度

        Returns:
            VisualBaseline 或 None（无活跃基线时）
        """
        stmt = (
            select(VisualBaseline)
            .where(
                VisualBaseline.project_id == project_id,
                VisualBaseline.page_url == page_url,
                VisualBaseline.viewport_width == viewport_width,
                VisualBaseline.viewport_height == viewport_height,
                VisualBaseline.status == "active",
            )
            .order_by(VisualBaseline.version.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def get_baseline_by_id(self, baseline_id: int) -> Optional[VisualBaseline]:
        """按主键查询基线。"""
        stmt = select(VisualBaseline).where(VisualBaseline.id == baseline_id)
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def list_baselines(
        self,
        project_id: int,
        status: Optional[str] = None,
        test_case_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> List[VisualBaseline]:
        """按项目列出基线，支持状态与用例过滤。"""
        stmt = select(VisualBaseline).where(VisualBaseline.project_id == project_id)
        if status:
            stmt = stmt.where(VisualBaseline.status == status)
        if test_case_id is not None:
            stmt = stmt.where(VisualBaseline.test_case_id == test_case_id)
        stmt = stmt.order_by(VisualBaseline.updated_at.desc()).offset(offset).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def update_baseline(
        self,
        baseline_id: int,
        new_image_bytes: bytes,
        match_level: Optional[str] = None,
        dom_snapshot_bytes: Optional[bytes] = None,
    ) -> VisualBaseline:
        """更新基线截图，旧版本归档，创建新版本。

        Args:
            baseline_id: 原基线 ID
            new_image_bytes: 新基线截图字节流
            match_level: 新对比模式（可空，默认沿用原基线）
            dom_snapshot_bytes: 新 DOM 快照（可空）

        Returns:
            VisualBaseline: 新创建的基线记录

        Raises:
            ValueError: 原基线不存在时抛出
        """
        old_baseline = await self.get_baseline_by_id(baseline_id)
        if old_baseline is None:
            raise ValueError(f"基线不存在: id={baseline_id}")

        # 归档旧基线
        await self._db.execute(
            update(VisualBaseline)
            .where(VisualBaseline.id == baseline_id)
            .values(status="superseded")
        )

        # 创建新版本
        new_baseline = await self.create_baseline(
            project_id=old_baseline.project_id,
            name=old_baseline.name,
            page_url=old_baseline.page_url,
            viewport_width=old_baseline.viewport_width,
            viewport_height=old_baseline.viewport_height,
            image_bytes=new_image_bytes,
            match_level=match_level or old_baseline.match_level,
            test_case_id=old_baseline.test_case_id,
            dom_snapshot_bytes=dom_snapshot_bytes,
            created_by=old_baseline.created_by,
        )

        logger.info(
            f"[VisualAI] 基线更新: old_id={baseline_id} → new_id={new_baseline.id}, "
            f"version={new_baseline.version}"
        )
        return new_baseline

    async def delete_baseline(self, baseline_id: int) -> bool:
        """删除基线及其存储文件。

        Args:
            baseline_id: 基线 ID

        Returns:
            bool: 是否实际删除（基线不存在返回 False）
        """
        baseline = await self.get_baseline_by_id(baseline_id)
        if baseline is None:
            return False

        # 删除存储文件（失败不阻断 DB 删除）
        try:
            await self._storage.delete(baseline.image_key)
            if baseline.dom_snapshot_key:
                await self._storage.delete(baseline.dom_snapshot_key)
        except Exception as exc:
            logger.warning(f"[VisualAI] 存储文件删除失败: baseline_id={baseline_id}, error={exc}")

        # 删除 DB 记录
        await self._db.delete(baseline)
        await self._db.commit()

        logger.info(f"[VisualAI] 基线删除: id={baseline_id}")
        return True

    async def get_baseline_history(
        self,
        project_id: int,
        page_url: str,
        viewport_width: int,
        viewport_height: int,
    ) -> List[VisualBaseline]:
        """获取页面+视口的基线版本历史（按版本号降序）。"""
        stmt = (
            select(VisualBaseline)
            .where(
                VisualBaseline.project_id == project_id,
                VisualBaseline.page_url == page_url,
                VisualBaseline.viewport_width == viewport_width,
                VisualBaseline.viewport_height == viewport_height,
            )
            .order_by(VisualBaseline.version.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def load_baseline_image(self, baseline_id: int) -> bytes:
        """加载基线截图字节流。

        Args:
            baseline_id: 基线 ID

        Returns:
            bytes: 截图字节流

        Raises:
            ValueError: 基线不存在或文件读取失败
        """
        baseline = await self.get_baseline_by_id(baseline_id)
        if baseline is None:
            raise ValueError(f"基线不存在: id={baseline_id}")
        return await self._storage.load(baseline.image_key)

    async def _get_max_version(
        self,
        project_id: int,
        page_url: str,
        viewport_width: int,
        viewport_height: int,
    ) -> int:
        """查询当前最大版本号。"""
        stmt = (
            select(func.max(VisualBaseline.version))
            .where(
                VisualBaseline.project_id == project_id,
                VisualBaseline.page_url == page_url,
                VisualBaseline.viewport_width == viewport_width,
                VisualBaseline.viewport_height == viewport_height,
            )
        )
        result = await self._db.execute(stmt)
        max_ver = result.scalar()
        return max_ver or 0

    @staticmethod
    def _build_image_key(
        project_id: int,
        page_url: str,
        viewport_width: int,
        viewport_height: int,
        version: int,
    ) -> str:
        """构造基线截图的 StorageBackend key。

        格式: visual-ai/baselines/{project_id}/{url_hash}/{viewport}v{version}.png
        """
        import hashlib

        url_hash = hashlib.md5(page_url.encode("utf-8")).hexdigest()[:12]
        return f"visual-ai/baselines/{project_id}/{url_hash}/{viewport_width}x{viewport_height}v{version}.png"

    @staticmethod
    def _build_dom_key(
        project_id: int,
        page_url: str,
        viewport_width: int,
        viewport_height: int,
        version: int,
    ) -> str:
        """构造 DOM 快照的 StorageBackend key。"""
        import hashlib

        url_hash = hashlib.md5(page_url.encode("utf-8")).hexdigest()[:12]
        return f"visual-ai/baselines/{project_id}/{url_hash}/{viewport_width}x{viewport_height}v{version}.dom.json"

    @staticmethod
    def _get_image_dimensions(image_bytes: bytes) -> tuple:
        """获取图片尺寸 (width, height)。"""
        import io

        from PIL import Image

        try:
            img = Image.open(io.BytesIO(image_bytes))
            return img.size
        except Exception:
            logger.warning("[VisualAI] 图片尺寸解析失败，默认 (0, 0)")
            return (0, 0)


__all__ = ["BaselineService"]
