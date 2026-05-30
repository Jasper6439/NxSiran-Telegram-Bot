"""
system/rate_limiter.py - 简单内存限流器
========================================
提供 API 端点限流和暴力破解保护。
无外部依赖，使用纯 Python dict + time 实现。
"""

import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """通用内存限流器。

    Args:
        max_requests: 时间窗口内最大请求数
        window_seconds: 时间窗口（秒）
        name: 限流器名称（用于日志）
    """

    def __init__(self, max_requests: int, window_seconds: int, name: str = ""):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self._records: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str):
        """清理过期的请求记录"""
        now = time.time()
        cutoff = now - self.window_seconds
        self._records[key] = [t for t in self._records[key] if t > cutoff]

    def is_allowed(self, key: str) -> bool:
        """检查请求是否允许。

        Args:
            key: 限流键（如 user_id、IP、username）

        Returns:
            True if allowed, False if rate limited
        """
        self._cleanup(key)
        if len(self._records[key]) >= self.max_requests:
            logger.warning(f"[限流] {self.name} 键 {key}: "
                           f"超过 {self.max_requests}/{self.window_seconds}s 限制")
            return False
        self._records[key].append(time.time())
        return True

    def remaining(self, key: str) -> int:
        """返回该 key 在当前窗口内剩余可用请求数"""
        self._cleanup(key)
        return max(0, self.max_requests - len(self._records[key]))

    def reset(self, key: str):
        """重置某 key 的计数"""
        self._records.pop(key, None)


# ============================================================
# 预定义限流器实例
# ============================================================

# /api/chat 端点: 每用户每分钟最多 20 次请求
chat_rate_limiter = RateLimiter(
    max_requests=20,
    window_seconds=60,
    name="ChatAPI"
)

# 登录暴力破解保护: 每用户名每 10 分钟最多 5 次失败尝试
login_bruteforce_limiter = RateLimiter(
    max_requests=5,
    window_seconds=600,
    name="LoginBruteForce"
)
