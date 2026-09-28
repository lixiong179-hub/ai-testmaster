"""
执行控制管理器（P1 E-04）

为后台执行中的测试任务提供暂停/恢复控制能力。
通过 threading.Event 实现跨线程通信：执行引擎在步间检查暂停信号，
暂停时阻塞等待恢复信号，从而实现"冻结当前执行进度"的效果。

设计要点：
- 全局单例 execution_controller，避免依赖注入的侵入式改造
- 每个 task_id 对应一个 _TaskController，在 start 端点注册、执行完成后注销
- pause 不中断当前步骤，仅在下一步开始前生效（避免半途截断造成脏状态）
- 使用 threading.Event 而非 asyncio.Event，因为引擎通过
  run_async_coro_in_thread 在独立线程+独立事件循环中运行，
  asyncio.Event 无法跨事件循环使用
"""
import threading
from typing import Dict, Optional

from loguru import logger


class _TaskController:
    """单个任务的执行控制器（线程安全）"""

    def __init__(self) -> None:
        # _run_event: set 表示允许继续执行（非暂停态），clear 表示暂停中
        # 初始为 set（非暂停态），引擎无需等待
        self._run_event: threading.Event = threading.Event()
        self._run_event.set()
        self._is_paused: bool = False

    def pause(self) -> None:
        """暂停任务：清除事件，引擎调用 wait_if_paused 时将阻塞"""
        self._is_paused = True
        self._run_event.clear()
        logger.info("任务已标记为暂停，引擎将在当前步骤完成后阻塞")

    def resume(self) -> None:
        """恢复任务：设置事件，解除引擎阻塞"""
        self._is_paused = False
        self._run_event.set()
        logger.info("任务已恢复，引擎继续执行")

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def wait_if_paused(self) -> None:
        """引擎步间调用：若处于暂停态则阻塞当前线程，直到 resume 被调用。

        引擎在独立线程中运行（run_async_coro_in_thread），
        阻塞该线程不会影响主事件循环。
        """
        self._run_event.wait()


class ExecutionControlManager:
    """全局执行控制管理器，维护 task_id → _TaskController 映射"""

    def __init__(self) -> None:
        self._controllers: Dict[int, _TaskController] = {}
        self._lock = threading.Lock()

    def register(self, task_id: int) -> _TaskController:
        """注册任务控制器（在 start 端点调用）"""
        ctrl = _TaskController()
        with self._lock:
            self._controllers[task_id] = ctrl
        logger.info(f"已注册执行控制器: task_id={task_id}")
        return ctrl

    def unregister(self, task_id: int) -> None:
        """注销任务控制器（在执行完成/失败/停止后调用）"""
        with self._lock:
            self._controllers.pop(task_id, None)

    def get(self, task_id: int) -> Optional[_TaskController]:
        with self._lock:
            return self._controllers.get(task_id)

    def pause(self, task_id: int) -> bool:
        """暂停任务，返回是否成功"""
        ctrl = self.get(task_id)
        if ctrl is None:
            logger.warning(f"暂停失败：未找到执行控制器 task_id={task_id}")
            return False
        ctrl.pause()
        return True

    def resume(self, task_id: int) -> bool:
        """恢复任务，返回是否成功"""
        ctrl = self.get(task_id)
        if ctrl is None:
            logger.warning(f"恢复失败：未找到执行控制器 task_id={task_id}")
            return False
        ctrl.resume()
        return True

    def is_paused(self, task_id: int) -> bool:
        ctrl = self.get(task_id)
        return ctrl.is_paused if ctrl else False

    def wait_if_paused(self, task_id: int) -> None:
        """引擎步间调用：若任务被暂停则阻塞，直到恢复"""
        ctrl = self.get(task_id)
        if ctrl is not None:
            ctrl.wait_if_paused()


# 全局单例
execution_controller = ExecutionControlManager()
