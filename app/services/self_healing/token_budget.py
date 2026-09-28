"""自愈体系 Token 预算守卫。

实现自愈体系的单次与日预算双控：
    - 单次超限（AI_SELF_HEALING_TOKEN_LIMIT）：熔断 AI 推理，避免单步拖垮整体。
    - 日预算耗尽（AI_SELF_HEALING_DAILY_TOKEN_BUDGET）：降级为 rollback/skip 策略。

日计数持久化到 Redis（key=self_heal:token:{YYYYMMDD}，TTL 25h，跨时区覆盖一天），
Redis 不可用时降级为进程内内存计数，不阻断主流程。

重构说明（add-agent-architecture Task 3）：
    通用 Redis 累计 + 内存降级逻辑已抽出至 app.services.common.token_budget.BaseTokenBudgetGuard，
    本模块仅保留自愈场景的 limit / daily_budget 配置绑定与 namespace 常量。
    原有公开方法签名与模块常量保留以避免破坏性变更，自愈测试用例无需改动。
"""
from app.core.config import settings
from app.services.common.token_budget import BaseTokenBudgetGuard

# 日计数 Redis key 前缀与 TTL（25h，确保跨时区的一天内 key 始终存活）
# 保留模块级常量以维持现有测试导入兼容
_TOKEN_KEY_PREFIX = "self_heal:token:"
_TTL_SECONDS = 25 * 3600


class TokenBudgetGuard(BaseTokenBudgetGuard):
    """自愈场景 Token 预算守卫，单次与日预算双控。

    继承 BaseTokenBudgetGuard 的通用 Redis 累计 + 内存降级逻辑，
    仅实现 check_single_call / is_daily_budget_exhausted 以绑定自愈配置项。
    """

    def __init__(self, redis_client) -> None:
        """注入 Redis 客户端；为 None 时直接走内存降级。

        Args:
            redis_client: 同步 redis.Redis 实例（推荐 decode_responses=True）。
        """
        super().__init__(
            redis_client=redis_client,
            namespace=_TOKEN_KEY_PREFIX,
            ttl_seconds=_TTL_SECONDS,
        )

    def check_single_call(self, token_estimate: int) -> bool:
        """校验单次 Token 预估是否超限。

        Args:
            token_estimate: 单次自愈预估 Token 消耗。

        Returns:
            bool: True 表示预估超限，应熔断；False 表示在限额内可调用。
        """
        return token_estimate > settings.AI_SELF_HEALING_TOKEN_LIMIT

    def is_daily_budget_exhausted(self) -> bool:
        """判断当日累计消耗是否超 AI_SELF_HEALING_DAILY_TOKEN_BUDGET。

        Redis 不可用时读取内存计数。

        Returns:
            bool: True 表示日预算已耗尽，应降级为非 AI 策略。
        """
        consumed = self._get_consumed()
        return consumed >= settings.AI_SELF_HEALING_DAILY_TOKEN_BUDGET
