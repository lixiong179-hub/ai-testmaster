"""
接口限流中间件

本模块实现了基于IP的请求限流机制，防止恶意或异常高频请求压垮服务。
采用双模式设计，根据部署环境自动选择最优策略。

双模式设计原因：
    - Redis模式：适用于生产环境多worker/多进程部署，多个进程共享同一份限流计数器，
      确保全局限流生效。使用Redis Sorted Set实现滑动窗口算法。
    - 内存模式：适用于开发环境单worker部署，无需额外依赖Redis，使用deque实现
      进程内限流。在多worker环境下各进程独立计数，限流精度降低。

核心组件概览：
    - RateLimitMiddleware: Starlette中间件，拦截所有HTTP请求进行限流判断
    - _init_redis(): Redis连接初始化，失败时自动降级到内存模式
    - _dispatch_redis(): Redis模式限流调度，基于Sorted Set滑动窗口算法
    - _dispatch_memory(): 内存模式限流调度，基于deque的时间窗口清理
    - _cleanup_old_requests(): 清理超出时间窗口的过期请求记录

限流算法说明：
    - Redis模式采用滑动窗口（Sliding Window）算法：利用Sorted Set的score排序特性，
      以时间戳为score存储请求记录，通过zremrangebyscore移除窗口外记录，
      zcard统计窗口内请求数，实现精确的滑动窗口限流。
    - 内存模式采用固定窗口清理策略：deque存储请求时间戳，每次请求前清理过期记录，
      通过len(deque)判断是否超限。

依赖关系：
    - app.core.config.settings: 读取REDIS_URL配置
    - redis（可选）: 生产环境限流后端，未安装时自动降级
"""
import time
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    基于IP的接口限流中间件

    继承Starlette的BaseHTTPMiddleware，在请求到达业务逻辑前进行频率检查。
    每个客户端IP在指定时间窗口内的请求数超过阈值时，返回HTTP 429。

    双模式运行：
        - Redis模式（生产推荐）：多worker共享限流状态，通过Sorted Set实现滑动窗口
        - 内存模式（开发默认）：单进程内限流，通过deque存储请求时间戳

    容错设计：
        - Redis连接失败时自动降级到内存模式，不影响服务启动
        - Redis运行时异常时单次请求降级到内存模式，不影响请求处理
        - 所有降级过程对调用方透明

    Attributes:
        max_requests: 时间窗口内允许的最大请求数，默认100
        time_window: 限流时间窗口（秒），默认60秒
        _redis_client: Redis客户端实例，None表示未初始化或初始化失败
        _use_redis: 是否使用Redis模式，False则使用内存模式
        requests: 内存模式的请求记录，key为IP，value为请求时间戳的deque
    """

    def __init__(self, app, max_requests: int = 100, time_window: int = 60) -> None:
        """
        初始化限流中间件

        Args:
            app: ASGI应用实例，由Starlette框架传入
            max_requests: 时间窗口内允许的最大请求数，默认100次/分钟
            time_window: 限流时间窗口（秒），默认60秒
        """
        super().__init__(app)
        self.max_requests = max_requests
        self.time_window = time_window
        self._redis_client = None
        self._use_redis = False
        # 内存模式的请求记录存储
        # defaultdict: 访问不存在的IP时自动创建空deque
        # deque(maxlen=max_requests): 限制队列最大长度等于最大请求数，
        #   当请求数超过maxlen时自动丢弃最旧的记录，起到粗粒度限流兜底作用
        #   注意：maxlen仅限制队列长度，精确限流仍依赖_cleanup_old_requests的时间窗口判断
        self.requests = defaultdict(lambda: deque(maxlen=max_requests))

        # 尝试初始化Redis连接，失败则回退到内存模式
        self._init_redis()

    def _init_redis(self) -> None:
        """
        尝试初始化Redis连接，失败则回退到内存模式

        降级策略：
            1. 检查settings中是否配置了REDIS_URL
            2. 尝试导入redis库并创建连接
            3. 执行ping()验证连接可用性
            4. 任何步骤失败均静默降级到内存模式，不阻断服务启动

        Redis连接参数说明：
            - max_connections=10: 连接池上限，避免Redis连接数泄漏
            - decode_responses=True: 自动将Redis返回值解码为字符串
            - socket_timeout=2: 读写超时2秒，防止Redis慢查询阻塞请求
            - socket_connect_timeout=2: 连接超时2秒，快速感知Redis不可用
        """
        try:
            import redis

            redis_url = getattr(settings, 'REDIS_URL', None)
            if redis_url:
                self._redis_client = redis.from_url(
                    redis_url,
                    max_connections=10,
                    decode_responses=True,
                    socket_timeout=2,
                    socket_connect_timeout=2,
                )
                # ping验证连接可用性，不可用时抛出异常进入降级逻辑
                self._redis_client.ping()
                self._use_redis = True
        except Exception as e:
            # 降级到内存模式：redis库未安装、REDIS_URL未配置、连接失败等均走此分支
            logger.warning(f"Redis 不可用，降级为内存模式限流: {e}")
            self._use_redis = False

    async def dispatch(self, request: Request, call_next):
        """
        请求拦截入口，根据当前模式选择对应的限流调度策略

        Args:
            request: FastAPI请求对象，用于获取客户端IP
            call_next: 下一个中间件或路由处理函数

        Returns:
            Response: 正常请求的响应，或HTTP 429限流响应

        Raises:
            HTTPException: 请求频率超限时抛出429状态码
        """
        # 获取客户端IP作为限流的唯一标识
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        if self._use_redis:
            return await self._dispatch_redis(client_ip, current_time, request, call_next)
        else:
            return await self._dispatch_memory(client_ip, current_time, request, call_next)

    async def _dispatch_redis(self, client_ip: str, current_time: float, request: Request, call_next):
        """
        Redis模式限流调度：基于Sorted Set的滑动窗口算法

        算法步骤（通过pipeline原子执行）：
            1. zremrangebyscore: 移除score（时间戳）超出时间窗口的所有记录
            2. zcard: 统计当前窗口内的请求数量
            3. zadd: 将当前请求时间戳作为member和score添加到Sorted Set
            4. expire: 设置key过期时间，防止僵尸数据长期占用内存

        使用Redis Pipeline的原因：
            将多个Redis命令打包为一次网络往返执行，减少RTT延迟，
            同时pipeline内命令按顺序执行，保证原子性（非严格事务原子性，
            但对于限流场景足够，因为少量竞态不会导致严重后果）。

        Args:
            client_ip: 客户端IP地址
            current_time: 当前时间戳
            request: FastAPI请求对象
            call_next: 下一个处理函数

        Returns:
            Response: 正常请求的响应

        Raises:
            HTTPException: 请求频率超限时抛出429
        """
        try:
            # 限流key格式：ratelimit:{IP}，每个IP独立计数
            key = f"ratelimit:{client_ip}"

            # 使用pipeline批量执行Redis命令，减少网络开销
            pipe = self._redis_client.pipeline()

            # 步骤1：移除时间窗口外的过期记录（滑动窗口的核心操作）
            # score范围为[0, current_time - time_window]，即早于窗口起始时间的记录
            pipe.zremrangebyscore(key, 0, current_time - self.time_window)

            # 步骤2：统计当前窗口内的请求数量
            pipe.zcard(key)

            # 步骤3：记录当前请求，member和score均为时间戳
            # member使用str(current_time)确保唯一性（同一秒内多次请求时间戳可能相同，
            # 但Sorted Set的member相同时会更新score，不影响计数准确性）
            pipe.zadd(key, {str(current_time): current_time})

            # 步骤4：设置key过期时间，比时间窗口多1秒，确保窗口外记录自动清理
            # +1秒是为了避免边界条件下key在窗口结束前过期导致计数丢失
            pipe.expire(key, self.time_window + 1)

            # 执行pipeline，results为各命令返回值的列表
            results = pipe.execute()

            # results[1]对应zcard的返回值，即当前窗口内的请求数
            count = results[1]

            # 判断是否超限：当前窗口请求数 >= 最大允许数
            # 注意：当前请求已在步骤3中添加，所以count包含了本次请求
            # 因此用 >= 而非 >，当count等于max_requests时说明已达上限
            if count >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail="请求过于频繁，请稍后再试"
                )

        except HTTPException:
            # 限流异常需要向上抛出，不能被通用异常处理吞掉
            raise
        except Exception as e:
            # Redis运行时异常（连接断开、命令超时等），降级到内存模式处理本次请求
            # 降级而非拒绝，保证服务可用性优先于限流精确性
            logger.warning(f"Redis 运行时异常，降级本次请求为内存模式: {e}")
            return await self._dispatch_memory(client_ip, current_time, request, call_next)

        # 限流通过，继续处理请求。业务处理异常不能被当成 Redis 异常重试，
        # 否则上传请求体被消费后会出现二次执行卡住的问题。
        response = await call_next(request)
        return response

    async def _dispatch_memory(self, client_ip: str, current_time: float, request: Request, call_next):
        """
        内存模式限流调度：基于deque的时间窗口清理策略

        工作流程：
            1. 清理该IP超出时间窗口的过期请求记录
            2. 检查当前窗口内的请求数是否超限
            3. 未超限则记录本次请求时间戳，继续处理

        注意：内存模式仅在单worker下限流准确，多worker部署时各进程独立计数，
        实际限流阈值 = max_requests * worker数量。

        Args:
            client_ip: 客户端IP地址
            current_time: 当前时间戳
            request: FastAPI请求对象
            call_next: 下一个处理函数

        Returns:
            Response: 正常请求的响应

        Raises:
            HTTPException: 请求频率超限时抛出429
        """
        # 先清理过期记录，确保计数准确
        self._cleanup_old_requests(client_ip, current_time)

        # 检查当前窗口内的请求数是否已达上限
        if len(self.requests[client_ip]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail="请求过于频繁，请稍后再试"
            )

        # 记录本次请求的时间戳，deque自动维护maxlen上限
        self.requests[client_ip].append(current_time)

        # 限流通过，继续处理请求
        response = await call_next(request)
        return response

    def _cleanup_old_requests(self, client_ip: str, current_time: float) -> None:
        """
        清理指定IP超出时间窗口的过期请求记录

        从deque头部（最早的时间戳）开始检查，逐个移除超出时间窗口的记录。
        由于deque按时间顺序排列，遇到第一个未过期的记录即可停止。

        为什么不用deque的maxlen自动清理：
            maxlen仅基于队列长度淘汰，不考虑时间维度。当请求集中在短时间内
            （如1秒内100次请求），maxlen会丢弃旧记录但时间窗口内请求数仍然超限。
            因此需要基于时间的精确清理，maxlen仅作为极端情况下的兜底保护。

        Args:
            client_ip: 客户端IP地址
            current_time: 当前时间戳，用于计算记录是否过期
        """
        # deque[0]是最早的请求时间戳，逐个检查是否超出时间窗口
        while self.requests[client_ip] and current_time - self.requests[client_ip][0] > self.time_window:
            # popleft()移除deque头部（最早）的过期记录，时间复杂度O(1)
            self.requests[client_ip].popleft()
        # 清理空 deque 以释放长期闲置 IP 的内存占用
        if not self.requests[client_ip]:
            del self.requests[client_ip]
