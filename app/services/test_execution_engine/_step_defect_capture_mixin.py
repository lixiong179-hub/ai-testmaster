"""步骤执行 - 浏览器缺陷捕获子 Mixin。

从 step_executor_mixin.py 拆分，承载步骤执行前后的浏览器缺陷证据采集：
- _clear_browser_defect_evidence: 步骤执行前清空缺陷收集器
- _collect_step_defect_evidence: 步骤完成后采集内存快照并收集缺陷证据
"""
from loguru import logger

from app.services.test_execution_engine.models import StepExecutionResult


class StepDefectCaptureMixin:
    """浏览器缺陷捕获子 Mixin。

    依赖聚合类提供 self.browser（来自 TestExecutionEngineV2）。
    """

    def _clear_browser_defect_evidence(self) -> None:
        """步骤执行前清空浏览器缺陷收集器。"""
        if self.browser and hasattr(self.browser, 'clear_defect_evidence'):
            try:
                self.browser.clear_defect_evidence()
            except Exception as e:
                logger.debug(f"清空缺陷收集器异常(不影响执行): {e}")

    async def _collect_step_defect_evidence(self, result: StepExecutionResult) -> None:
        """步骤完成后采集内存快照并收集缺陷证据，写入 result.defect_evidence。

        即使用例通过（status=passed），defect_evidence 仍可能有内容（隐性缺陷）。
        """
        if not self.browser or not hasattr(self.browser, 'collect_memory_sample'):
            return
        try:
            await self.browser.collect_memory_sample()
        except Exception as e:
            logger.debug(f"采集内存快照异常(不影响执行): {e}")

        if hasattr(self.browser, 'get_defect_evidence'):
            try:
                evidence = self.browser.get_defect_evidence()
                # 仅当存在实质缺陷内容时才写入，避免存储空结构
                has_evidence = (
                    evidence.get("console_errors")
                    or evidence.get("network_failures")
                    or evidence.get("memory_leak_suspect")
                    or evidence.get("uncaught_exceptions")
                )
                if has_evidence:
                    result.defect_evidence = evidence
            except Exception as e:
                logger.debug(f"收集缺陷证据异常(不影响执行): {e}")


__all__ = ["StepDefectCaptureMixin"]
