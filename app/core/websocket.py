"""
WebSocket连接管理器

本模块实现了WebSocket连接的全生命周期管理，为测试执行过程提供实时消息推送能力。
前端通过WebSocket连接订阅特定测试执行（execution_id）的实时事件，
包括执行日志、截图、进度更新和状态变更。

核心设计思路：
    - 按execution_id分组管理连接：同一测试执行可能有多个前端页面同时监听
      （如多个浏览器标签页、多个用户查看同一次执行），通过execution_id分组
      实现精准广播，避免消息发送到无关的连接。
    - 线程安全设计：connect/disconnect/broadcast等操作涉及共享数据结构
      （active_connections字典）的读写，使用threading.Lock保证并发安全。
    - 连接数限制：单个execution_id最多允许10个WebSocket连接，防止资源泄漏
      和恶意连接耗尽服务器资源。

核心组件概览：
    - ConnectionManager: WebSocket连接管理器，管理连接的建立、断开、消息推送
    - connect(): 建立连接，含连接数限制检查
    - disconnect(): 断开连接，含空组自动清理
    - send_message(): 单播，向指定客户端发送消息
    - broadcast(): 广播，向同一execution_id的所有客户端发送消息
    - send_log(): 推送执行日志（步骤级别）
    - send_screenshot(): 推送截图（含高亮区域）
    - send_progress(): 推送进度更新（百分比+预估剩余时间）
    - send_status(): 推送执行状态变更（started/running/completed/failed）
    - get_connection_count(): 连接数统计
    - manager: 全局单例，供各模块直接引用

消息类型说明：
    - log: 执行日志，包含步骤编号、操作描述、执行状态
    - screenshot: 执行截图，包含Base64编码的截图数据和可选的高亮区域
    - progress: 进度更新，包含当前步骤/总步骤/百分比/预估剩余时间
    - status: 状态变更，包含执行生命周期状态（started/running/completed/failed）

依赖关系：
    - fastapi.WebSocket: WebSocket连接对象
    - loguru.logger: 日志记录
"""
from typing import Dict, List, Optional, TYPE_CHECKING
from fastapi import WebSocket
from loguru import logger
from datetime import datetime
import threading

if TYPE_CHECKING:
    pass  # 避免循环导入


class ConnectionManager:
    """
    WebSocket连接管理器

    负责WebSocket连接的建立、断开、消息推送等全生命周期管理。
    采用按execution_id分组的连接管理模式，支持同一测试执行的多个客户端
    同时订阅实时事件。

    设计意图：
        - 分组管理：测试执行是核心业务实体，前端需要按执行维度订阅事件，
          而非按用户维度。同一执行可能被多个用户/标签页同时查看。
        - 线程安全：FastAPI在多线程环境下处理WebSocket连接，
          active_connections字典的读写操作必须加锁保护。
        - 自动清理：断开连接时检查该execution_id是否还有活跃连接，
          无连接时删除整个key，防止内存泄漏。

    关键属性：
        active_connections: 连接存储字典，key为execution_id，value为WebSocket列表
        _lock: 线程锁，保护active_connections的并发读写

    使用场景：
        # 路由中建立连接
        @router.websocket("/ws/{execution_id}")
        async def websocket_endpoint(websocket: WebSocket, execution_id: str):
            if await manager.connect(websocket, execution_id):
                try:
                    while True:
                        data = await websocket.receive_text()
                except WebSocketDisconnect:
                    manager.disconnect(websocket, execution_id)

        # 业务代码中推送消息
        await manager.send_log(execution_id, step_number=1, action="点击按钮", status="success")
    """

    # 单个execution_id的最大连接数
    # 限制原因：防止单次测试执行占用过多服务器资源（每个WebSocket连接占用内存和文件描述符），
    # 10个连接足以覆盖正常使用场景（多个标签页 + 多人协作查看）
    MAX_CONNECTIONS_PER_EXECUTION = 10

    def __init__(self):
        """
        初始化连接管理器

        创建空的连接存储字典和线程锁实例。
        active_connections使用Dict[str, List[WebSocket]]结构，
        支持按execution_id快速查找所有关联的WebSocket连接。
        """
        # 存储活跃的WebSocket连接
        # key: execution_id（测试执行ID），value: 该执行下的所有WebSocket连接列表
        # 使用Dict + List结构，支持O(1)的按execution_id查找和O(n)的组内遍历
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # 线程锁，保证线程安全
        # 保护active_connections字典的增删改操作，防止并发导致的连接丢失或重复
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket, execution_id: str) -> bool:
        """
        建立WebSocket连接

        执行WebSocket握手（accept），检查连接数限制，将连接注册到对应execution_id组。
        必须在收到WebSocket请求后立即调用，否则连接无法建立。

        线程安全：使用_lock保护active_connections的读写操作。

        Args:
            websocket: WebSocket连接对象，由FastAPI路由参数注入
            execution_id: 测试执行ID，用于将连接分组到对应的测试执行

        Returns:
            bool: True表示连接成功建立并注册，False表示连接被拒绝（超限）

        Note:
            - 连接超限时，会主动关闭WebSocket并返回False，调用方不应继续使用该连接
            - accept()必须在连接数检查之前调用，因为客户端期望先完成握手
        """
        # 先完成WebSocket握手，客户端进入连接状态
        await websocket.accept()

        with self._lock:
            # 检查该execution_id的当前连接数是否已达上限
            current_connections = len(self.active_connections.get(execution_id, []))
            if current_connections >= self.MAX_CONNECTIONS_PER_EXECUTION:
                # 连接数超限，记录警告日志并主动关闭连接
                # 关闭码1008表示策略违规（Policy Violation），符合WebSocket协议规范
                logger.warning(f"连接数超限: execution_id={execution_id}, 当前连接数={current_connections}")
                await websocket.close(code=1008, reason="Too many connections")
                return False

            # 首次有连接接入该execution_id时，初始化连接列表
            if execution_id not in self.active_connections:
                self.active_connections[execution_id] = []

            # 将新连接添加到对应execution_id的连接列表
            self.active_connections[execution_id].append(websocket)
            logger.info(f"WebSocket连接建立: execution_id={execution_id}, 当前连接数={len(self.active_connections[execution_id])}")
            return True

    def disconnect(self, websocket: WebSocket, execution_id: str):
        """
        断开WebSocket连接并清理资源

        从active_connections中移除指定连接，如果该execution_id下已无活跃连接，
        则删除整个key，释放内存。

        线程安全：使用_lock保护active_connections的修改操作。

        自动清理机制：
            当某个execution_id的最后一个连接断开时，自动删除该key，
            防止已完成的测试执行残留空列表，造成内存泄漏。
            这在长期运行的服务中尤为重要，因为测试执行会不断创建和销毁。

        Args:
            websocket: 要断开的WebSocket连接对象
            execution_id: 该连接所属的测试执行ID
        """
        with self._lock:
            if execution_id in self.active_connections:
                if websocket in self.active_connections[execution_id]:
                    # 从连接列表中移除该WebSocket
                    self.active_connections[execution_id].remove(websocket)
                    logger.info(f"WebSocket连接断开: execution_id={execution_id}")

                # 如果该execution_id下已无活跃连接，清理整个key
                # 避免残留空列表占用内存，特别是在测试执行频繁创建/销毁的场景
                if not self.active_connections[execution_id]:
                    del self.active_connections[execution_id]

    async def send_message(self, websocket: WebSocket, message: dict) -> bool:
        """
        向单个客户端发送消息（单播）

        直接向指定的WebSocket连接发送JSON格式消息。
        适用于需要定向推送的场景（如仅通知发起操作的用户）。

        Args:
            websocket: 目标WebSocket连接对象
            message: 消息字典，将被序列化为JSON发送

        Returns:
            bool: True表示发送成功，False表示发送失败（连接可能已断开）

        Note:
            发送失败时不主动断开连接，由调用方决定后续处理逻辑。
            这与broadcast中的行为不同，broadcast会自动清理发送失败的连接。
        """
        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            # 发送失败通常意味着连接已断开（网络异常、客户端关闭等）
            logger.error(f"发送WebSocket消息失败: {e}")
            return False

    async def broadcast(self, execution_id: str, message: dict):
        """
        向指定execution_id的所有客户端广播消息

        将消息推送给订阅同一测试执行的所有WebSocket连接。
        广播过程中自动检测并清理已断开的连接，保证连接列表的准确性。

        线程安全策略：
            1. 加锁期间仅复制连接列表引用，不执行耗时的IO操作
            2. 释放锁后再遍历连接发送消息，避免长时间持锁阻塞其他操作
            3. 清理断开连接时再次加锁，确保断开操作的线程安全

        Args:
            execution_id: 测试执行ID，只有订阅该执行的客户端才会收到消息
            message: 消息字典，会自动添加timestamp字段后发送

        Note:
            - 消息会自动注入timestamp字段（ISO格式），前端可用于消息排序和去重
            - 发送失败的连接会被自动断开并清理，防止后续广播重复尝试发送
        """
        with self._lock:
            # 检查该execution_id是否有活跃连接
            if execution_id not in self.active_connections:
                return

            # 复制连接列表，避免遍历时持锁导致其他操作阻塞
            # copy()创建浅拷贝，复制列表引用但不复制WebSocket对象本身
            connections = self.active_connections[execution_id].copy()

        # 添加时间戳，供前端排序和去重使用
        message["timestamp"] = datetime.now().isoformat()

        # 遍历所有连接发送消息，收集发送失败的连接
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                # 发送失败记录日志，将该连接加入待清理列表
                logger.error(f"广播消息失败: {e}")
                disconnected.append(websocket)

        # 清理发送失败的连接（连接已断开，需要从active_connections中移除）
        # disconnect()内部会加锁，保证线程安全
        for websocket in disconnected:
            self.disconnect(websocket, execution_id)

    async def send_log(self, execution_id: str, step_number: int, action: str, status: str, message: str = ""):
        """
        推送执行日志消息

        在测试执行的每个步骤完成时推送，前端据此实时展示执行过程。
        这是最频繁推送的消息类型，每个测试步骤至少产生一条日志。

        使用场景：
            - 测试引擎执行每个步骤后调用，推送步骤操作和结果
            - 前端实时滚动展示执行日志，帮助用户了解测试进展

        Args:
            execution_id: 测试执行ID
            step_number: 步骤编号（从1开始），用于前端排序和定位
            action: 操作描述，如"点击登录按钮"、"输入用户名"
            status: 步骤执行状态，可选值：
                - "running": 步骤正在执行中
                - "success": 步骤执行成功
                - "failed": 步骤执行失败
            message: 详细消息，通常包含辅助信息或错误原因，默认为空字符串
        """
        await self.broadcast(execution_id, {
            "type": "log",
            "step_number": step_number,
            "action": action,
            "status": status,
            "message": message
        })

    async def send_screenshot(self, execution_id: str, step_number: int, screenshot_base64: str, highlight_region: Optional[dict] = None):
        """
        推送截图消息

        在测试执行的关键步骤推送当前页面截图，前端可实时展示测试界面。
        截图数据量较大（Base64编码），应控制推送频率避免网络拥堵。

        使用场景：
            - 步骤执行失败时自动截图，帮助定位问题
            - 关键操作步骤（如提交表单、页面跳转）的视觉确认
            - 前端展示测试执行的实时画面

        Args:
            execution_id: 测试执行ID
            step_number: 步骤编号，与日志消息的step_number对应
            screenshot_base64: Base64编码的截图数据，前端可直接用于<img>标签的src
            highlight_region: 可选的高亮区域，标注当前操作的元素位置，
                格式为 {"x": int, "y": int, "width": int, "height": int}，
                前端可在截图上叠加高亮框，直观展示操作目标
        """
        message = {
            "type": "screenshot",
            "step_number": step_number,
            "screenshot": screenshot_base64
        }

        # 仅在有高亮区域时添加该字段，减少消息体积
        if highlight_region:
            message["highlight_region"] = highlight_region

        await self.broadcast(execution_id, message)

    async def send_progress(self, execution_id: str, current_step: int, total_steps: int, estimated_remaining_seconds: Optional[int] = None):
        """
        推送进度更新消息

        在测试执行过程中定期推送进度信息，前端据此展示进度条和预估剩余时间。
        建议在每完成一个步骤时推送一次，而非每个步骤推送多次。

        使用场景：
            - 前端展示进度条（百分比 + 步骤数）
            - 显示预估剩余时间，提升用户等待体验
            - 长时间执行的测试用例，让用户了解执行进展

        Args:
            execution_id: 测试执行ID
            current_step: 当前已完成的步骤数（从1开始）
            total_steps: 总步骤数，用于计算百分比
            estimated_remaining_seconds: 预估剩余时间（秒），基于已完成步骤的平均耗时计算，
                为None时前端不显示剩余时间

        Raises:
            ZeroDivisionError: 当total_steps为0时，百分比计算会除零，
                调用方应确保total_steps > 0
        """
        progress = {
            "type": "progress",
            "current_step": current_step,
            "total_steps": total_steps,
            # 百分比保留1位小数，如 66.7%，避免浮点数精度问题
            "percentage": round((current_step / total_steps) * 100, 1)
        }

        # 仅在有预估值时添加该字段，避免传递None值
        if estimated_remaining_seconds is not None:
            progress["estimated_remaining_seconds"] = estimated_remaining_seconds

        await self.broadcast(execution_id, progress)

    async def send_status(self, execution_id: str, status: str, message: str = ""):
        """
        推送执行状态变更消息

        在测试执行的生命周期状态变更时推送，前端据此更新执行状态展示。
        这是最高优先级的消息类型，状态变更直接影响UI的展示模式。

        使用场景：
            - "started": 测试执行开始，前端切换到执行中视图
            - "running": 测试执行进行中（与started的区别：started是首次启动，
                running可能是暂停后恢复）
            - "completed": 测试执行完成，前端展示结果汇总
            - "failed": 测试执行异常终止，前端展示错误信息

        Args:
            execution_id: 测试执行ID
            status: 执行状态，可选值：
                - "started": 执行已启动
                - "running": 执行正在运行
                - "completed": 执行已完成
                - "failed": 执行失败
            message: 状态补充说明，如失败原因、完成摘要等，默认为空字符串
        """
        await self.broadcast(execution_id, {
            "type": "status",
            "status": status,
            "message": message
        })

    def get_connection_count(self, execution_id: Optional[str] = None) -> int:
        """
        获取WebSocket连接数统计

        支持两种查询模式：按execution_id查询该执行的连接数，或查询全局总连接数。
        用于监控和运维场景，如健康检查、负载评估。

        线程安全：使用_lock保护读取操作，确保获取到一致的连接数快照。

        Args:
            execution_id: 测试执行ID，指定时返回该执行的连接数；
                为None时返回所有execution_id的连接总数

        Returns:
            int: 连接数。指定execution_id时返回该组的连接数（不存在则返回0），
                 未指定时返回所有组的连接总数

        使用示例：
            # 查询某次执行的连接数
            count = manager.get_connection_count("exec-123")
            # 查询全局总连接数
            total = manager.get_connection_count()
        """
        with self._lock:
            if execution_id:
                # 查询指定execution_id的连接数，不存在则返回0
                return len(self.active_connections.get(execution_id, []))

            # 统计所有execution_id的连接总数
            total = 0
            for connections in self.active_connections.values():
                total += len(connections)
            return total


# 全局连接管理器单例
# 整个应用共享同一个ConnectionManager实例，确保所有WebSocket连接统一管理
# 各模块（路由、服务层）通过from app.core.websocket import manager引用
manager = ConnectionManager()
