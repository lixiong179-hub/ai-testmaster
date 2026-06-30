"""S14 ExecutionValidation — 执行验证结果持久化 Step

将 Playwright 执行验证结果写入 generated_cases 的 case_data 字典，
通过 persist 步骤落库到 TestCase 表的执行验证字段。

执行验证结果来源：
    - 外部异步任务（如 Playwright 执行验证服务）将结果写入
      `execution_validation_results` artifact
    - 本 Step 读取该 artifact，按 case_title 匹配 generated_cases 中的 case_data
    - 将 execution_verified/element_verified_ratio/execution_failure_type/last_verified_at
      写入 case_data 字典，供 persist 步骤读取

执行失败类型映射（execution_failure_type）：
    - element_not_found : 元素定位失败（FailureCategory.LOCATOR_FAILURE）
    - timeout           : 执行超时（步骤 duration_ms 超过阈值）
    - assertion_failed  : 验证步骤失败（VERIFY 类型步骤失败）
    - other             : 其他失败（环境错误、前置条件失败等）
"""
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


# 执行失败类型常量
FAILURE_TYPE_ELEMENT_NOT_FOUND = "element_not_found"
FAILURE_TYPE_TIMEOUT = "timeout"
FAILURE_TYPE_ASSERTION_FAILED = "assertion_failed"
FAILURE_TYPE_NETWORK_ERROR = "network_error"
FAILURE_TYPE_OTHER = "other"

# 合法失败类型集合，用于校验外部输入
# 与迁移脚本 alembic/versions/20260624_add_execution_failure_type_and_verified_at.py
# 的 comment 列保持一致：element_not_found/timeout/assertion_failed/network_error/other
VALID_FAILURE_TYPES = frozenset({
    FAILURE_TYPE_ELEMENT_NOT_FOUND,
    FAILURE_TYPE_TIMEOUT,
    FAILURE_TYPE_ASSERTION_FAILED,
    FAILURE_TYPE_NETWORK_ERROR,
    FAILURE_TYPE_OTHER,
})


class ExecutionValidation(PipelineStep):
    """执行验证结果持久化 Step — 将 Playwright 验证结果写入 case_data。

    本 Step 不直接调用 Playwright，而是读取上游产生的
    `execution_validation_results` 产物，按 case_title 匹配
    generated_cases 中的 case_data，将4个验证字段写入字典。
    persist 步骤随后读取这些字段并落库到 TestCase 表。

    设计原则：
        - 防御性校验：所有外部输入字段经类型/范围校验后才写入 case_data
        - 幂等性：重复执行不会破坏已有验证结果（后写覆盖前写）
        - 降级安全：本 Step 失败不阻塞 persist，用例照常落库（验证字段为 None）
    """

    name: ClassVar[str] = "execution_validation"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["generated_cases"]
    produces: ClassVar[List[str]] = ["execution_validation_applied"]

    def should_run(self, ctx: PipelineContext) -> bool:
        """仅当存在执行验证结果产物且有用例待持久化时才执行。

        Args:
            ctx: Pipeline 运行时上下文。

        Returns:
            True 表示存在 execution_validation_results 产物且 generated_cases 非空。
        """
        validation_results = ctx.get_artifact("execution_validation_results")
        if not validation_results:
            return False
        cases = ctx.get_artifact("generated_cases")
        if not cases:
            return False
        return cases.get("success_count", 0) > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        """执行验证结果写入不应缓存，每次都需实际处理。

        Args:
            ctx: Pipeline 运行时上下文。

        Returns:
            空字符串，表示不缓存。
        """
        return ""

    def execute(self, ctx: PipelineContext) -> StepResult:
        """执行验证结果写入 case_data 字典。

        读取 execution_validation_results 产物，按 case_title 匹配
        generated_cases 中的 case_data，将验证字段写入字典。

        Args:
            ctx: Pipeline 运行时上下文。

        Returns:
            StepResult，包含已应用的用例数和统计信息。
        """
        cases_artifact = ctx.get_artifact("generated_cases")
        if not cases_artifact:
            return StepResult(success=False, error="缺少 generated_cases 产物")

        validation_results = ctx.get_artifact("execution_validation_results")
        if not validation_results:
            return StepResult(success=False, error="缺少 execution_validation_results 产物")

        results_by_title = self._build_results_by_title(validation_results)
        if not results_by_title:
            logger.info("execution_validation_results 为空，跳过写入")
            return StepResult(
                success=True,
                artifact_payload=self._build_payload(ctx, cases_artifact, 0, 0),
                artifact_kind="execution_validation_applied",
                artifact_confidence=0.0,
            )

        applied_count = self._apply_results_to_cases(cases_artifact, results_by_title)

        total_results = len(results_by_title)
        unmatched_count = total_results - applied_count
        if unmatched_count > 0:
            logger.warning(
                "执行验证结果有 {} 条未匹配到 generated_cases（共 {} 条结果）",
                unmatched_count, total_results,
            )

        payload = self._build_payload(ctx, cases_artifact, total_results, applied_count)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="execution_validation_applied",
            artifact_confidence=1.0 if applied_count > 0 else 0.0,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "matched_count": applied_count,
                "total_results": total_results,
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        """校验产物格式是否合法。

        Args:
            payload: 产物载荷。

        Returns:
            True 表示包含必需的统计字段。
        """
        return "matched_count" in payload and "total_results" in payload

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        """失败兜底：不写入任何验证字段，用例正常落库（验证字段为 None）。

        Args:
            ctx: Pipeline 运行时上下文。
            error: 触发降级的异常。

        Returns:
            降级成功的 StepResult。
        """
        logger.warning("执行验证结果写入降级，用例将不带验证字段落库: {}", error)
        return StepResult(
            success=True,
            artifact_payload={
                "iteration_id": ctx.iteration_id,
                "total_results": 0,
                "matched_count": 0,
                "unmatched_count": 0,
                "degraded": True,
            },
            artifact_kind="execution_validation_applied",
            artifact_confidence=0.0,
            degraded=True,
        )

    def _build_results_by_title(
        self, validation_results: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """将执行验证结果列表转为 case_title -> result 映射。

        Args:
            validation_results: execution_validation_results 产物载荷。

        Returns:
            case_title 到验证结果字典的映射。
            当上游返回多条同标题结果时，后写覆盖前写，
            前 N-1 条验证结果会被丢弃，此时记录 warning 以便排查。
        """
        from loguru import logger

        results_by_title: Dict[str, Dict[str, Any]] = {}
        duplicate_titles: List[str] = []
        for result in validation_results.get("results", []):
            if not isinstance(result, dict):
                continue
            title = result.get("case_title", "")
            if not title:
                continue
            if title in results_by_title:
                duplicate_titles.append(title)
            results_by_title[title] = result

        if duplicate_titles:
            logger.warning(
                "execution_validation: 检测到 {} 条同标题验证结果被覆盖: {}",
                len(duplicate_titles),
                duplicate_titles[:5],
            )
        return results_by_title

    def _apply_results_to_cases(
        self,
        cases_artifact: Dict[str, Any],
        results_by_title: Dict[str, Dict[str, Any]],
    ) -> int:
        """将执行验证结果写入 generated_cases 的 case_data 字典。

        遍历 generated_cases 中所有成功的用例，按 case_title 匹配
        执行验证结果，将4个验证字段写入 case_data 字典，
        供后续 persist 步骤读取并落库。

        Args:
            cases_artifact: generated_cases 产物载荷。
            results_by_title: case_title 到验证结果的映射。

        Returns:
            成功匹配并写入验证字段的用例数。
        """
        applied_count = 0
        for entry in cases_artifact.get("generated_cases", []):
            if entry.get("status") != "success":
                continue
            case_data_list = entry.get("case_data", [])
            if not isinstance(case_data_list, list):
                continue
            for case_data in case_data_list:
                if not isinstance(case_data, dict):
                    continue
                title = case_data.get("title", "")
                result = results_by_title.get(title)
                if not result:
                    continue
                self._write_validation_fields(case_data, result)
                applied_count += 1
        return applied_count

    def _write_validation_fields(
        self,
        case_data: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """将单个验证结果字段写入 case_data 字典（含防御性校验）。

        对外部输入做类型/范围校验：
            - execution_verified 必须是 bool 或 None
            - element_verified_ratio 必须是 [0.0, 1.0] 范围内的 float 或 None
            - execution_failure_type 必须是合法枚举值或 None
            - last_verified_at 原样透传（persist 步骤负责类型转换）

        Args:
            case_data: 单个用例数据字典，原地修改。
            result: 执行验证结果字典。
        """
        case_data["execution_verified"] = self._sanitize_verified(
            result.get("execution_verified"),
        )
        case_data["element_verified_ratio"] = self._sanitize_ratio(
            result.get("element_verified_ratio"),
        )
        case_data["execution_failure_type"] = self._sanitize_failure_type(
            result.get("execution_failure_type"),
        )
        case_data["last_verified_at"] = result.get("last_verified_at")

    @staticmethod
    def _build_payload(
        ctx: PipelineContext,
        cases_artifact: Dict[str, Any],
        total_results: int,
        matched_count: int,
    ) -> Dict[str, Any]:
        """构建 StepResult 产物载荷。

        Args:
            ctx: Pipeline 运行时上下文。
            cases_artifact: generated_cases 产物载荷。
            total_results: 执行验证结果总数。
            matched_count: 成功匹配的用例数。

        Returns:
            产物载荷字典。
        """
        return {
            "iteration_id": ctx.iteration_id,
            "project_id": cases_artifact.get("project_id"),
            "total_results": total_results,
            "matched_count": matched_count,
            "unmatched_count": max(total_results - matched_count, 0),
        }

    @staticmethod
    def _sanitize_verified(value: Any) -> Optional[bool]:
        """校验 execution_verified 字段。

        Args:
            value: 外部输入值。

        Returns:
            合法的 bool 值或 None。
        """
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        logger.warning(
            "execution_verified 非法类型: {}，已置为 None",
            type(value).__name__,
        )
        return None

    @staticmethod
    def _sanitize_ratio(value: Any) -> Optional[float]:
        """校验 element_verified_ratio 字段，约束在 [0.0, 1.0] 范围内。

        Args:
            value: 外部输入值。

        Returns:
            合法的 float 值或 None。
        """
        if value is None:
            return None
        try:
            ratio = float(value)
        except (TypeError, ValueError):
            logger.warning("element_verified_ratio 非法值: {}，已置为 None", value)
            return None
        if ratio < 0.0 or ratio > 1.0:
            logger.warning(
                "element_verified_ratio 越界: {}，已钳制到 [0.0, 1.0]", ratio,
            )
            ratio = max(0.0, min(1.0, ratio))
        return ratio

    @staticmethod
    def _sanitize_failure_type(value: Any) -> Optional[str]:
        """校验 execution_failure_type 字段，必须是合法枚举值。

        Args:
            value: 外部输入值。

        Returns:
            合法的失败类型字符串或 None。
        """
        if value is None:
            return None
        if isinstance(value, str) and value in VALID_FAILURE_TYPES:
            return value
        logger.warning("execution_failure_type 非法值: {}，已置为 None", value)
        return None


__all__ = [
    "ExecutionValidation",
    "VALID_FAILURE_TYPES",
    "FAILURE_TYPE_ELEMENT_NOT_FOUND",
    "FAILURE_TYPE_TIMEOUT",
    "FAILURE_TYPE_ASSERTION_FAILED",
    "FAILURE_TYPE_NETWORK_ERROR",
    "FAILURE_TYPE_OTHER",
]
