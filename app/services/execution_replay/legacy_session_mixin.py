"""Legacy 会话管理Mixin - execution_replay_service.py 原始会话管理逻辑。"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session

from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.services.execution_replay.legacy_models import ReplayEvent, ExecutionTimeline, ReplaySession


class LegacySessionMixin:
    """回放会话管理：创建、加载时间轴、清理。"""

    def __init__(self):
        self._active_replays: Dict[str, ReplaySession] = {}
        self._replay_speed: float = 1.0
        self._session_timeout_minutes: int = 30
        self._cleanup_task: Optional[asyncio.Task] = None

    def _start_cleanup_task(self):
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                self._cleanup_task = None
                return
            self._cleanup_task = loop.create_task(self._cleanup_expired_sessions())

    async def _cleanup_expired_sessions(self):
        while True:
            try:
                await asyncio.sleep(300)
                await self._remove_expired_sessions()
            except Exception as e:
                logger.error(f"清理过期会话失败: {e}")

    async def _remove_expired_sessions(self):
        now = datetime.now()
        expired_sessions = []
        for execution_id, session in self._active_replays.items():
            last_activity = session.get('last_activity', session['created_at'])
            if (now - last_activity).total_seconds() > self._session_timeout_minutes * 60:
                expired_sessions.append(execution_id)
        for execution_id in expired_sessions:
            await self.close_replay_session(execution_id)
            logger.info(f"过期回放会话已清理: {execution_id}")

    def _update_activity(self, execution_id: str):
        if execution_id in self._active_replays:
            self._active_replays[execution_id]['last_activity'] = datetime.now()

    async def create_replay_session(
        self,
        db: Session,
        execution_id: str,
        video_path: Optional[str] = None,
        screenshots: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        timeline = await self._load_execution_timeline(db, execution_id)
        session: ReplaySession = {
            "execution_id": execution_id,
            "timeline": timeline,
            "video_path": video_path,
            "screenshots": screenshots or [],
            "current_time": 0.0,
            "is_playing": False,
            "speed": 1.0,
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }
        self._active_replays[execution_id] = session
        logger.info(f"回放会话已创建: {execution_id}")
        return {
            "execution_id": execution_id,
            "total_duration": timeline.total_duration if timeline else 0,
            "has_video": video_path is not None,
            "screenshot_count": len(screenshots) if screenshots else 0,
            "event_count": len(timeline.events) if timeline else 0
        }

    async def _load_execution_timeline(
        self, db: Session, execution_id: str
    ) -> Optional[ExecutionTimeline]:
        try:
            parts = execution_id.split('_')
            if len(parts) >= 4:
                task_id = int(parts[1])
                case_id = int(parts[3])
                task = db.query(TestTask).filter(TestTask.id == task_id).first()
                case = db.query(TestCase).filter(TestCase.id == case_id).first()
                if not task or not case:
                    logger.warning(f"执行记录不存在: {execution_id}")
                    return None
                result = db.query(TestResult).filter(
                    TestResult.task_id == task_id,
                    TestResult.case_id == case_id
                ).order_by(TestResult.create_time.desc()).first()
                timeline = ExecutionTimeline(
                    execution_id=execution_id,
                    start_time=task.create_time if task else datetime.now(),
                    total_duration=0.0,
                    events=[]
                )
                timeline.events.append(ReplayEvent(
                    timestamp=0.0,
                    event_type="execution_start",
                    data={
                        "task_id": task_id,
                        "case_id": case_id,
                        "task_name": task.task_name if task else "",
                        "case_name": case.title if case else ""
                    }
                ))
                if result and hasattr(result, 'step_results'):
                    step_results = result.step_results
                    if isinstance(step_results, list):
                        for i, step in enumerate(step_results):
                            step_number = i + 1
                            timestamp = step.get('execution_time', 0) if isinstance(step, dict) else 0
                            timeline.events.append(ReplayEvent(
                                timestamp=timestamp,
                                event_type="step_start",
                                data={
                                    "step_number": step_number,
                                    "action": step.get('action', '') if isinstance(step, dict) else '',
                                    "target": step.get('target', '') if isinstance(step, dict) else ''
                                }
                            ))
                            if step.get('screenshot') if isinstance(step, dict) else None:
                                timeline.events.append(ReplayEvent(
                                    timestamp=timestamp + 0.5,
                                    event_type="screenshot",
                                    data={
                                        "step_number": step_number,
                                        "url": step.get('screenshot', '')
                                    }
                                ))
                            status = step.get('status', 'unknown') if isinstance(step, dict) else 'unknown'
                            timeline.events.append(ReplayEvent(
                                timestamp=timestamp + 1.0,
                                event_type="step_end",
                                data={
                                    "step_number": step_number,
                                    "status": status,
                                    "success": status == "success"
                                }
                            ))
                total_duration = max(
                    (event.timestamp for event in timeline.events),
                    default=0.0
                ) + 1.0
                timeline.events.append(ReplayEvent(
                    timestamp=total_duration,
                    event_type="execution_end",
                    data={
                        "result": result.exec_status if result else "unknown",
                        "total_steps": len(timeline.events) // 3
                    }
                ))
                timeline.total_duration = total_duration
                timeline.end_time = timeline.start_time + timedelta(seconds=total_duration)
                return timeline
            else:
                logger.warning(f"无效的执行ID格式: {execution_id}")
                return None
        except Exception as e:
            logger.error(f"加载执行时间轴失败: {e}")
            return None

    async def close_replay_session(self, execution_id: str) -> bool:
        session = self._active_replays.get(execution_id)
        if not session:
            return False
        session["is_playing"] = False
        del self._active_replays[execution_id]
        logger.info(f"回放会话已关闭: {execution_id}")
        return True
