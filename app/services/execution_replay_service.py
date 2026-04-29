"""
执行回放服务

提供测试执行过程的回放功能，包括：
- 视频回放
- 截图回放
- 执行日志回放
- 步骤时间轴回放
"""
import asyncio
from typing import Optional, List, Dict, Any, Callable, TypedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

from sqlalchemy.orm import Session

from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.test_result import TestResult


@dataclass
class ReplayEvent:
    """回放事件"""
    timestamp: float  # 时间戳（相对于开始时间，秒）
    event_type: str  # 事件类型：step_start, step_end, action, screenshot, log, error
    data: Dict[str, Any] = field(default_factory=dict)  # 事件数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "data": self.data
        }


@dataclass
class ExecutionTimeline:
    """执行时间轴"""
    execution_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: float = 0.0  # 总时长（秒）
    events: List[ReplayEvent] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "execution_id": self.execution_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration": self.total_duration,
            "events": [e.to_dict() for e in self.events]
        }


class ReplaySession(TypedDict):
    """回放会话类型定义"""
    execution_id: str
    timeline: ExecutionTimeline
    video_path: Optional[str]
    screenshots: List[str]
    current_time: float
    is_playing: bool
    speed: float
    created_at: datetime
    last_activity: datetime  # 最后活动时间，用于过期检测


class ExecutionReplayService:
    """执行回放服务"""
    
    def __init__(self):
        """初始化回放服务"""
        self._active_replays: Dict[str, ReplaySession] = {}  # 活跃的回放会话
        self._replay_speed: float = 1.0  # 默认回放速度
        self._session_timeout_minutes: int = 30  # 会话超时时间（分钟）
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # 启动清理任务
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """启动会话清理任务"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
    
    async def _cleanup_expired_sessions(self):
        """定期清理过期会话"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟检查一次
                await self._remove_expired_sessions()
            except Exception as e:
                logger.error(f"清理过期会话失败: {e}")
    
    async def _remove_expired_sessions(self):
        """移除过期会话"""
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
        """更新会话活动时间"""
        if execution_id in self._active_replays:
            self._active_replays[execution_id]['last_activity'] = datetime.now()
    
    async def create_replay_session(
        self,
        db: Session,
        execution_id: str,
        video_path: Optional[str] = None,
        screenshots: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        创建回放会话
        
        Args:
            db: 数据库会话
            execution_id: 执行ID
            video_path: 视频文件路径（可选）
            screenshots: 截图文件路径列表（可选）
            
        Returns:
            回放会话信息
        """
        # 加载执行时间轴
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
        self,
        db: Session,
        execution_id: str
    ) -> Optional[ExecutionTimeline]:
        """
        加载执行时间轴
        
        从数据库加载真实的执行记录，构建执行时间轴
        
        Args:
            db: 数据库会话
            execution_id: 执行ID
            
        Returns:
            执行时间轴，如果执行记录不存在返回None
        """
        try:
            # 从数据库加载执行记录
            # 假设execution_id格式为 "task_{task_id}_case_{case_id}_{timestamp}"
            parts = execution_id.split('_')
            if len(parts) >= 4:
                task_id = int(parts[1])
                case_id = int(parts[3])
                
                # 加载任务和用例信息
                task = db.query(TestTask).filter(TestTask.id == task_id).first()
                case = db.query(TestCase).filter(TestCase.id == case_id).first()
                
                if not task or not case:
                    logger.warning(f"执行记录不存在: {execution_id}")
                    return None
                
                # 加载测试结果
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
                
                # 添加执行开始事件
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
                
                # 如果有测试结果，添加步骤事件
                if result and hasattr(result, 'step_results'):
                    step_results = result.step_results
                    if isinstance(step_results, list):
                        for i, step in enumerate(step_results):
                            step_number = i + 1
                            timestamp = step.get('execution_time', 0) if isinstance(step, dict) else 0
                            
                            # 步骤开始事件
                            timeline.events.append(ReplayEvent(
                                timestamp=timestamp,
                                event_type="step_start",
                                data={
                                    "step_number": step_number,
                                    "action": step.get('action', '') if isinstance(step, dict) else '',
                                    "target": step.get('target', '') if isinstance(step, dict) else ''
                                }
                            ))
                            
                            # 如果有截图，添加截图事件
                            if step.get('screenshot') if isinstance(step, dict) else None:
                                timeline.events.append(ReplayEvent(
                                    timestamp=timestamp + 0.5,
                                    event_type="screenshot",
                                    data={
                                        "step_number": step_number,
                                        "url": step.get('screenshot', '')
                                    }
                                ))
                            
                            # 步骤结束事件
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
                
                # 添加执行结束事件
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
    
    async def start_replay(
        self,
        execution_id: str,
        start_time: float = 0.0,
        speed: float = 1.0,
        event_callback: Optional[Callable[[ReplayEvent], None]] = None
    ) -> bool:
        """
        开始回放
        
        Args:
            execution_id: 执行ID
            start_time: 开始时间（秒）
            speed: 回放速度（1.0=正常速度，2.0=2倍速）
            event_callback: 事件回调函数
            
        Returns:
            是否成功开始
        """
        session = self._active_replays.get(execution_id)
        if not session:
            logger.error(f"回放会话不存在: {execution_id}")
            return False
        
        if session["is_playing"]:
            logger.warning(f"回放已在进行中: {execution_id}")
            return False
        
        session["is_playing"] = True
        session["current_time"] = start_time
        session["speed"] = speed
        
        logger.info(f"开始回放: {execution_id}, 速度={speed}x, 起始时间={start_time}s")
        
        # 启动回放任务
        asyncio.create_task(
            self._replay_loop(execution_id, event_callback)
        )
        
        return True
    
    async def _replay_loop(
        self,
        execution_id: str,
        event_callback: Optional[Callable[[ReplayEvent], None]] = None
    ):
        """
        回放循环
        
        Args:
            execution_id: 执行ID
            event_callback: 事件回调函数
        """
        session = self._active_replays.get(execution_id)
        if not session:
            return
        
        timeline = session["timeline"]
        speed = session["speed"]
        
        # 找到起始位置
        current_idx = 0
        while current_idx < len(timeline.events):
            if timeline.events[current_idx].timestamp >= session["current_time"]:
                break
            current_idx += 1
        
        last_event_time = session["current_time"]
        
        while session["is_playing"] and current_idx < len(timeline.events):
            event = timeline.events[current_idx]
            
            # 计算等待时间
            wait_time = (event.timestamp - last_event_time) / speed
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            # 更新当前时间
            session["current_time"] = event.timestamp
            last_event_time = event.timestamp
            
            # 触发事件回调
            if event_callback:
                try:
                    event_callback(event)
                except Exception as e:
                    logger.error(f"事件回调失败: {e}")
            
            current_idx += 1
        
        # 回放结束
        session["is_playing"] = False
        logger.info(f"回放结束: {execution_id}")
    
    async def pause_replay(self, execution_id: str) -> bool:
        """
        暂停回放
        
        Args:
            execution_id: 执行ID
            
        Returns:
            是否成功暂停
        """
        session = self._active_replays.get(execution_id)
        if not session:
            return False
        
        session["is_playing"] = False
        logger.info(f"回放已暂停: {execution_id}, 当前时间={session['current_time']}s")
        return True
    
    async def resume_replay(self, execution_id: str) -> bool:
        """
        恢复回放
        
        Args:
            execution_id: 执行ID
            
        Returns:
            是否成功恢复
        """
        session = self._active_replays.get(execution_id)
        if not session:
            return False
        
        if session["is_playing"]:
            return True
        
        session["is_playing"] = True
        logger.info(f"回放已恢复: {execution_id}")
        return True
    
    async def stop_replay(self, execution_id: str) -> bool:
        """
        停止回放
        
        Args:
            execution_id: 执行ID
            
        Returns:
            是否成功停止
        """
        session = self._active_replays.get(execution_id)
        if not session:
            return False
        
        session["is_playing"] = False
        session["current_time"] = 0.0
        logger.info(f"回放已停止: {execution_id}")
        return True
    
    async def seek_to(self, execution_id: str, timestamp: float) -> bool:
        """
        跳转到指定时间点
        
        Args:
            execution_id: 执行ID
            timestamp: 目标时间（秒）
            
        Returns:
            是否成功跳转
        """
        session = self._active_replays.get(execution_id)
        if not session:
            return False
        
        timeline = session["timeline"]
        if timestamp < 0:
            timestamp = 0
        if timestamp > timeline.total_duration:
            timestamp = timeline.total_duration
        
        session["current_time"] = timestamp
        logger.info(f"回放跳转: {execution_id} -> {timestamp}s")
        return True
    
    async def get_replay_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        获取回放状态
        
        Args:
            execution_id: 执行ID
            
        Returns:
            回放状态
        """
        session = self._active_replays.get(execution_id)
        if not session:
            return None
        
        timeline = session["timeline"]
        
        # 找到当前时间点对应的事件
        current_event_idx = 0
        for i, event in enumerate(timeline.events):
            if event.timestamp > session["current_time"]:
                break
            current_event_idx = i
        
        return {
            "execution_id": execution_id,
            "is_playing": session["is_playing"],
            "current_time": session["current_time"],
            "total_duration": timeline.total_duration,
            "progress_percent": (session["current_time"] / timeline.total_duration * 100) if timeline.total_duration > 0 else 0,
            "speed": session["speed"],
            "current_event_index": current_event_idx,
            "total_events": len(timeline.events)
        }
    
    async def get_screenshot_at_time(
        self,
        execution_id: str,
        timestamp: float
    ) -> Optional[str]:
        """
        获取指定时间点的截图
        
        Args:
            execution_id: 执行ID
            timestamp: 时间戳（秒）
            
        Returns:
            截图URL
        """
        session = self._active_replays.get(execution_id)
        if not session:
            return None
        
        screenshots = session.get("screenshots", [])
        if not screenshots:
            return None
        
        # 找到最接近的截图
        # 这里简化处理，实际应该根据截图时间戳匹配
        timeline = session["timeline"]
        for event in timeline.events:
            if event.event_type == "screenshot" and event.timestamp <= timestamp:
                return event.data.get("url")
        
        return screenshots[0] if screenshots else None
    
    async def get_events_in_range(
        self,
        execution_id: str,
        start_time: float,
        end_time: float
    ) -> List[ReplayEvent]:
        """
        获取时间范围内的事件
        
        Args:
            execution_id: 执行ID
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            
        Returns:
            事件列表
        """
        session = self._active_replays.get(execution_id)
        if not session:
            return []
        
        timeline = session["timeline"]
        events = []
        
        for event in timeline.events:
            if start_time <= event.timestamp <= end_time:
                events.append(event)
        
        return events
    
    async def close_replay_session(self, execution_id: str) -> bool:
        """
        关闭回放会话
        
        Args:
            execution_id: 执行ID
            
        Returns:
            是否成功关闭
        """
        session = self._active_replays.get(execution_id)
        if not session:
            return False
        
        # 停止回放
        session["is_playing"] = False
        
        # 移除会话
        del self._active_replays[execution_id]
        
        logger.info(f"回放会话已关闭: {execution_id}")
        return True
    
    def set_default_speed(self, speed: float):
        """
        设置默认回放速度
        
        Args:
            speed: 速度倍率
        """
        if speed < 0.1:
            speed = 0.1
        if speed > 10.0:
            speed = 10.0
        
        self._replay_speed = speed
        logger.info(f"默认回放速度已设置为: {speed}x")


def get_execution_replay_service() -> ExecutionReplayService:
    """获取执行回放服务实例（单例）"""
    global _execution_replay_service
    if _execution_replay_service is None:
        _execution_replay_service = ExecutionReplayService()
    return _execution_replay_service
