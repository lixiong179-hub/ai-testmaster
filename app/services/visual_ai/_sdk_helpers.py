"""VisualAISDK 内部辅助函数（Task 9）。

设计目的：
    sdk.py 拆分出 Diff 持久化、DOM 对比报告生成、Diff 图片保存等流程化逻辑，
    保持 SDK 主类作为纯门面，控制在 350 行以内。

抽取边界：
    - build_diff_record      : 根据对比结果构造 VisualDiff ORM 对象
    - build_dom_diff_report  : 生成 Markdown Diff 报告（含 DOM 对比）
    - persist_diff_image     : 保存 Diff 图片到存储后端并回填 key
    - load_baseline_dom      : 加载基线 DOM 并与当前 DOM 对比

设计原则：
    - 纯函数 + 显式依赖：所有函数通过参数接收 db/storage，无全局状态
    - 异常容忍：DOM 加载失败不阻断主流程，仅记录日志
"""
from __future__ import annotations

import hashlib
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.visual_baseline import VisualBaseline
from app.models.visual_diff import VisualDiff
from app.services.storage.base import StorageBackend
from app.services.visual_ai.comparison_engine import ComparisonResult
from app.services.visual_ai.dom_serializer import (
    DOMDiffResult,
    compare_doms,
    generate_diff_report,
    serialize_dom,
)


async def load_baseline_dom(
    storage: StorageBackend,
    baseline: VisualBaseline,
    current_dom_html: str,
) -> Optional[DOMDiffResult]:
    """加载基线 DOM 并与当前 DOM 对比。

    业务用途：视觉校验时附加 DOM 结构差异，辅助定位视觉变更根因。
    异常容忍：基线 DOM 缺失或解析失败时返回 None，不阻断主流程。

    Args:
        storage: 存储后端实例
        baseline: 基线 ORM 对象（含 dom_snapshot_key）
        current_dom_html: 当前页面 HTML

    Returns:
        Optional[DOMDiffResult]: DOM 差异结果；基线无 DOM 或加载失败时为 None
    """
    if not current_dom_html or not baseline.dom_snapshot_key:
        return None
    try:
        dom_bytes = await storage.load(baseline.dom_snapshot_key)
        baseline_dom = serialize_dom(dom_bytes.decode("utf-8"))
        current_dom = serialize_dom(current_dom_html)
        return compare_doms(baseline_dom, current_dom)
    except Exception as exc:
        # DOM 加载/解析失败不阻断视觉校验主流程，仅记录警告
        logger.warning(
            f"[VisualAI SDK] 基线 DOM 加载或对比失败，跳过 DOM 报告: {exc}"
        )
        return None


def build_diff_record(
    *,
    project_id: int,
    baseline: VisualBaseline,
    result: ComparisonResult,
    test_case_id: Optional[int],
    test_result_id: Optional[int],
    diff_status: str,
) -> VisualDiff:
    """根据对比结果构造 VisualDiff ORM 对象（未持久化）。

    Args:
        project_id: 项目 ID
        baseline: 基线对象
        result: 图像对比结果
        test_case_id: 关联测试用例 ID
        test_result_id: 关联测试结果 ID
        diff_status: Diff 状态（auto_approved/pending）

    Returns:
        VisualDiff: 未持久化的 Diff 记录
    """
    return VisualDiff(
        project_id=project_id,
        baseline_id=baseline.id,
        test_case_id=test_case_id,
        test_result_id=test_result_id,
        current_image_key="",
        diff_image_key=None,
        diff_percentage=result.diff_percentage,
        diff_pixel_count=result.diff_pixel_count,
        total_pixel_count=result.total_pixel_count,
        match_level=result.match_level,
        status=diff_status,
        llm_analysis=result.llm_analysis.to_json() if result.llm_analysis else None,
        llm_token_cost=result.total_token_cost,
    )


async def persist_diff_image(
    storage: StorageBackend,
    db: AsyncSession,
    diff_record: VisualDiff,
    diff_image: bytes,
    *,
    project_id: int,
    page_url: str,
    baseline_id: int,
    diff_pixel_count: int,
) -> None:
    """保存 Diff 图片到存储后端并回填 diff_image_key。

    业务用途：Diff 图片用于人工审批时直观查看差异区域。
    异常容忍：保存失败仅记录警告，不阻断主流程（Diff 记录已持久化）。

    Args:
        storage: 存储后端实例
        db: 异步数据库会话
        diff_record: 已持久化的 Diff 记录（需回填 diff_image_key）
        diff_image: 差异图字节流
        project_id: 项目 ID（用于存储 key 隔离）
        page_url: 页面 URL（用于生成稳定 key）
        baseline_id: 基线 ID
        diff_pixel_count: 差异像素数（用于 key 区分）
    """
    url_hash = hashlib.md5(page_url.encode("utf-8")).hexdigest()[:12]
    diff_key = (
        f"visual-ai/diffs/{project_id}/{url_hash}/"
        f"{baseline_id}_{diff_pixel_count}.png"
    )
    try:
        await storage.save(diff_key, diff_image, content_type="image/png")
        diff_record.diff_image_key = diff_key
        await db.commit()
    except Exception as exc:
        logger.warning(f"[VisualAI SDK] Diff 图片保存失败: {exc}")


def build_dom_diff_report(
    pixel_diff_percentage: float,
    dom_diff: Optional[DOMDiffResult],
    llm_description: str,
) -> str:
    """生成 Markdown Diff 报告。

    Args:
        pixel_diff_percentage: 像素差异百分比
        dom_diff: DOM 差异结果（可空）
        llm_description: LLM 语义分析描述

    Returns:
        str: Markdown 格式 Diff 报告
    """
    return generate_diff_report(
        pixel_diff_percentage=pixel_diff_percentage,
        dom_diff=dom_diff,
        llm_description=llm_description,
    )


__all__ = [
    "build_diff_record",
    "build_dom_diff_report",
    "load_baseline_dom",
    "persist_diff_image",
]
