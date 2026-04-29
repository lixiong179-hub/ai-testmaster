"""时间线构建Mixin - 构建执行过程的时间线视图。
"""
import os
from typing import Optional, Dict, Any, List
from loguru import logger
from sqlalchemy.orm import Session

from app.models.test_case import TestCaseExecution, TestStep, TestCasePreconditionStep
from app.services.execution_replay.models import (
    ReplayEvent, ReplayEventType, ExecutionTimeline,
)


class TimelineMixin:
    """执行回放时间线构建mixin，从TestStep和TestCasePreconditionStep构建ReplayEvent序列。"""

    async def _load_execution_timeline(self, execution_id: int) -> Optional[ExecutionTimeline]:
        """加载指定执行ID的时间线，包含前置条件和用例步骤的事件序列。

        Args:
            execution_id: TestCaseExecution记录ID。

        Returns:
            ExecutionTimeline对象，不存在时返回None。
        """
        execution = self.db.query(TestCaseExecution).filter(
            TestCaseExecution.id == execution_id
        ).first()

        if not execution:
            logger.warning(f"执行记录不存在: {execution_id}")
            return None

        start_time = execution.started_at
        end_time = execution.completed_at
        duration_ms = 0
        if start_time and end_time:
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

        timeline = ExecutionTimeline(
            execution_id=execution_id,
            test_case_id=execution.test_case_id,
            start_time=start_time,
            end_time=end_time,
            total_duration_ms=duration_ms,
        )

        steps = self.db.query(TestStep).filter(
            TestStep.test_case_id == execution.test_case_id
        ).order_by(TestStep.step_number).all()

        base_timestamp = 0.0

        for step in steps:
            event_type = self._map_action_to_event_type(step.action)
            screenshot_path = self._resolve_screenshot_path(execution_id, step.id)

            event = ReplayEvent(
                timestamp=base_timestamp,
                event_type=event_type,
                action=step.action,
                step_number=step.step_number,
                screenshot_path=screenshot_path,
                duration_ms=0,
            )
            timeline.events.append(event)
            base_timestamp += max(step.estimated_duration_ms or 2000, 500) / 1000.0

        precondition_steps = self.db.query(TestCasePreconditionStep).filter(
            TestCasePreconditionStep.test_case_id == execution.test_case_id
        ).order_by(TestCasePreconditionStep.step_number).all()

        pc_events = []
        pc_timestamp = 0.0
        for pc_step in precondition_steps:
            event_type = self._map_action_to_event_type(pc_step.action)
            screenshot_path = self._resolve_screenshot_path(execution_id, None, pc_step.id)

            event = ReplayEvent(
                timestamp=pc_timestamp,
                event_type=event_type,
                action=pc_step.action,
                step_number=pc_step.step_number,
                screenshot_path=screenshot_path,
                duration_ms=0,
            )
            pc_events.append(event)
            pc_timestamp += 2.0

        timeline.events = pc_events + timeline.events

        for i, event in enumerate(timeline.events):
            if i > 0:
                event.timestamp = timeline.events[i - 1].timestamp + max(event.duration_ms, 500) / 1000.0
            else:
                event.timestamp = 0.0

        return timeline

    @staticmethod
    def _map_action_to_event_type(action: str) -> ReplayEventType:
        """将动作描述字符串映射为ReplayEventType枚举，支持中英文关键词匹配。

        Args:
            action: 动作描述文本。

        Returns:
            对应的ReplayEventType枚举值。
        """
        action_lower = action.lower()
        if "导航" in action or "访问" in action or "navigate" in action_lower:
            return ReplayEventType.NAVIGATE
        elif "输入" in action or "填写" in action or "input" in action_lower:
            return ReplayEventType.INPUT
        elif "验证" in action or "检查" in action or "verify" in action_lower:
            return ReplayEventType.VERIFY
        elif "等待" in action or "wait" in action_lower:
            return ReplayEventType.WAIT
        elif "滚动" in action or "scroll" in action_lower:
            return ReplayEventType.SCROLL
        elif "悬停" in action or "hover" in action_lower:
            return ReplayEventType.HOVER
        elif "选择" in action or "select" in action_lower:
            return ReplayEventType.SELECT
        elif "点击" in action or "click" in action_lower:
            return ReplayEventType.CLICK
        else:
            return ReplayEventType.CLICK

    def _resolve_screenshot_path(
        self,
        execution_id: int,
        step_id: Optional[int] = None,
        precondition_step_id: Optional[int] = None
    ) -> Optional[str]:
        """根据执行ID和步骤ID解析截图文件路径，支持多种命名模式的查找。

        Args:
            execution_id: 执行记录ID。
            step_id: 用例步骤ID，传递时优先匹配。
            precondition_step_id: 前置条件步骤ID。

        Returns:
            存在的截图文件绝对路径，均不存在时返回None。
        """
        base_dir = getattr(self, '_screenshot_base_dir', '/tmp/test_screenshots')
        path_patterns = []

        if step_id:
            path_patterns.append(os.path.join(base_dir, str(execution_id), f"step_{step_id}.png"))
            path_patterns.append(os.path.join(base_dir, f"exec_{execution_id}_step_{step_id}.png"))
        elif precondition_step_id:
            path_patterns.append(os.path.join(base_dir, str(execution_id), f"pc_step_{precondition_step_id}.png"))
            path_patterns.append(os.path.join(base_dir, f"exec_{execution_id}_pc_{precondition_step_id}.png"))

        for pattern in path_patterns:
            if os.path.exists(pattern):
                return pattern

        return None
