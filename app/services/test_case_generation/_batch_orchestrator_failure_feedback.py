"""test_case_generation - 批量生成编排器的模块历史失败归因 Mixin。

从 batch_orchestrator.py 拆分，提供 ModuleFailureFeedbackMixin，负责：
1. 批量预加载各模块历史执行失败类型（消除 N+1 查询）
2. 将失败归因注入单个测试点的生成上下文

供 BatchOrchestrator 通过多继承组合使用，依赖宿主类在 __init__ 中
注入 self.db（sqlalchemy.orm.Session）。
"""
from typing import Any, Dict, List, Optional

from loguru import logger


class ModuleFailureFeedbackMixin:
    """模块历史失败归因 Mixin。

    职责：
        1. _preload_module_failure_feedback: 批量预加载各模块历史执行失败类型
        2. _refine_context_for_point: 将失败归因注入单个测试点上下文

    依赖宿主类（BatchOrchestrator）在 __init__ 中注入 self.db
    （sqlalchemy.orm.Session）。
    """

    # ── 模块历史失败归因（合并自 _module_failure_feedback_mixin） ──
    def _preload_module_failure_feedback(
        self, project_id: int, test_points: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """批量预加载各模块的历史执行失败类型，消除 _refine_context_for_point 的 N+1 查询。

        业务原因：原实现每个测试点独立查询同模块失败用例，N 个测试点产生 N 次
        DB 查询。同 module 的测试点重复查询同一份数据。此处按 module IN(...) 一次
        查询全部，按模块分组取最近 5 条 failure_type，供 _refine_context_for_point
        从缓存读取。
        """
        modules = list({tp.get("module") for tp in test_points if tp.get("module")})
        if not modules:
            return {}
        db = getattr(self, "db", None)
        if db is None:
            return {}
        try:
            from app.models.test_case import TestCase
            rows = (
                db.query(TestCase.module, TestCase.execution_failure_type)
                .filter(
                    TestCase.project_id == project_id,
                    TestCase.module.in_(modules),
                    TestCase.execution_verified == False,  # noqa: E712
                    TestCase.is_deleted == False,  # noqa: E712
                )
                .order_by(TestCase.module, TestCase.last_verified_at.desc())
                .all()
            )
        except Exception as e:
            logger.warning(f"批量预加载历史执行失败归因失败: {e}")
            return {}

        grouped: Dict[str, List[str]] = {}
        for mod, ftype in rows:
            if mod not in grouped:
                grouped[mod] = []
            if len(grouped[mod]) < 5:
                grouped[mod].append(ftype or "other")
        return grouped

    async def _refine_context_for_point(
        self,
        context: Dict[str, Any],
        test_point: Dict[str, Any],
        project_id: int,
        module_failures: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """查询同模块历史执行失败归因并注入生成上下文（Task 12）。

        业务原因：同一模块的用例若历史上因元素定位失败/超时/断言失败等原因
        执行验证未通过（execution_verified=False），新一轮生成时应注入失败
        归因，指导AI避免同类问题。
        """
        module_name = test_point.get("module")
        if not module_name:
            return

        if module_failures is not None:
            failure_types: List[str] = module_failures.get(module_name, [])
        else:
            db = getattr(self, "db", None)
            if db is None:
                return
            try:
                from app.models.test_case import TestCase
                rows = (
                    db.query(TestCase.execution_failure_type)
                    .filter(
                        TestCase.project_id == project_id,
                        TestCase.module == module_name,
                        TestCase.execution_verified == False,  # noqa: E712
                        TestCase.is_deleted == False,  # noqa: E712
                    )
                    .order_by(TestCase.last_verified_at.desc())
                    .limit(5)
                    .all()
                )
                failure_types = [r[0] or "other" for r in rows]
            except Exception as e:
                logger.warning(f"查询历史执行失败归因失败: {e}")
                return

        if not failure_types:
            return

        failure_summary: Dict[str, int] = {}
        for ftype in failure_types:
            ftype = ftype or "other"
            failure_summary[ftype] = failure_summary.get(ftype, 0) + 1

        lines = [f"同模块历史上有 {len(failure_types)} 条用例执行失败，失败类型统计:"]
        for ftype, count in sorted(failure_summary.items(), key=lambda x: -x[1]):
            lines.append(f"  - {ftype}: {count}次")
        lines.append("请在新生成的用例中避免同类问题（如优化元素定位策略、增加等待逻辑、明确断言条件）。")
        context["execution_feedback"] = "\n".join(lines)
