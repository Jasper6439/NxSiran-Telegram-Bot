"""
core/memory.py - Redis 短期记忆模块 (v1.7 Phase 7)
====================================================
为每个用户维护滑动对话窗口，实现 AI 上下文连贯性。

使用 Redis List 结构，自动限制存储条数，防止内存溢出。
"""

import json
import logging
from typing import List, Dict, Optional

# Redis (可选依赖)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

from system.config import REDIS_URL

logger = logging.getLogger(__name__)


class ChatMemory:
    """Redis 短期对话记忆管理器。

    为每个用户维护最近 N 条对话记录，支持滑动窗口自动丢弃旧消息。

    Usage::
        memory = ChatMemory()
        memory.add_message(12345, "user", "你好")
        memory.add_message(12345, "assistant", "你好呀")
        history = memory.get_history(12345, limit=10)
        memory.clear_history(12345)
    """

    # 每个用户最多保留的消息条数（防止内存溢出）
    MAX_HISTORY_SIZE = 50

    # Redis key 前缀
    KEY_PREFIX = "chat:memory:"

    def __init__(self, redis_url: Optional[str] = None):
        """初始化 ChatMemory。

        Args:
            redis_url: Redis 连接 URL，默认从 config 读取
        """
        self.redis_url = redis_url or REDIS_URL
        self._redis = None
        # 内存回退（Redis 不可用时使用）— 必须在 early return 之前初始化
        self._memory_fallback: Dict[int, List[Dict]] = {}

        if not REDIS_AVAILABLE:
            return

        if self.redis_url:
            try:
                self._redis = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # 测试连接
                self._redis.ping()
                logger.info("[ChatMemory] Redis 连接成功")
            except Exception as e:
                logger.warning(f"[ChatMemory] Redis 连接失败，将使用内存回退: {e}")
                self._redis = None
        else:
            logger.warning("[ChatMemory] 未配置 REDIS_URL，将使用内存回退")

    def _get_key(self, user_id: int) -> str:
        """生成 Redis key。"""
        return f"{self.KEY_PREFIX}{user_id}"

    def add_message(self, user_id: int, role: str, content: str) -> bool:
        """添加消息到用户记忆。

        使用 Redis LPUSH 添加消息，LTRIM 限制列表长度。

        Args:
            user_id: 用户 ID
            role: 消息角色 ("user" 或 "assistant")
            content: 消息内容

        Returns:
            是否添加成功
        """
        if not content or not content.strip():
            return False

        message = {
            "role": role,
            "content": content.strip(),
        }

        try:
            if self._redis:
                # Redis 模式：LPUSH 添加，LTRIM 限制长度
                key = self._get_key(user_id)
                self._redis.lpush(key, json.dumps(message, ensure_ascii=False))
                self._redis.ltrim(key, 0, self.MAX_HISTORY_SIZE - 1)
                logger.debug(f"[ChatMemory] 用户 {user_id} 消息已存入 Redis")
            else:
                # 内存回退模式
                if user_id not in self._memory_fallback:
                    self._memory_fallback[user_id] = []
                self._memory_fallback[user_id].append(message)
                # 限制长度
                if len(self._memory_fallback[user_id]) > self.MAX_HISTORY_SIZE:
                    self._memory_fallback[user_id] = self._memory_fallback[user_id][-self.MAX_HISTORY_SIZE:]
                logger.debug(f"[ChatMemory] 用户 {user_id} 消息已存入内存")

            return True

        except Exception as e:
            logger.warning(f"[ChatMemory] 添加消息失败: {e}")
            return False

    def get_history(self, user_id: int, limit: int = 10) -> List[Dict[str, str]]:
        """获取用户最近对话历史。

        从 Redis 获取最近 N 条消息，格式化为 LLM 需要的 messages 列表。
        消息按时间顺序返回（旧 -> 新）。

        Args:
            user_id: 用户 ID
            limit: 获取消息条数（默认 10）

        Returns:
            messages 列表，每项为 {"role": str, "content": str}
        """
        limit = min(limit, self.MAX_HISTORY_SIZE)

        try:
            if self._redis:
                key = self._get_key(user_id)
                # LRANGE 获取列表（Redis 中是从新到旧存储）
                raw_messages = self._redis.lrange(key, 0, limit - 1)
                # 反转顺序（旧 -> 新），解析 JSON
                messages = []
                for raw in reversed(raw_messages):
                    try:
                        msg = json.loads(raw)
                        messages.append(msg)
                    except json.JSONDecodeError:
                        continue
                return messages
            else:
                # 内存回退模式
                messages = self._memory_fallback.get(user_id, [])
                return messages[-limit:] if messages else []

        except Exception as e:
            logger.warning(f"[ChatMemory] 获取历史失败: {e}")
            return []

    def clear_history(self, user_id: int) -> bool:
        """清空用户对话历史。

        当用户输入"忘记一切"等指令时调用。

        Args:
            user_id: 用户 ID

        Returns:
            是否清空成功
        """
        try:
            if self._redis:
                key = self._get_key(user_id)
                self._redis.delete(key)
                logger.info(f"[ChatMemory] 用户 {user_id} Redis 记忆已清空")
            else:
                if user_id in self._memory_fallback:
                    del self._memory_fallback[user_id]
                logger.info(f"[ChatMemory] 用户 {user_id} 内存记忆已清空")

            return True

        except Exception as e:
            logger.warning(f"[ChatMemory] 清空历史失败: {e}")
            return False

    def get_memory_size(self, user_id: int) -> int:
        """获取用户当前记忆条数。

        Args:
            user_id: 用户 ID

        Returns:
            当前存储的消息条数
        """
        try:
            if self._redis:
                key = self._get_key(user_id)
                return self._redis.llen(key)
            else:
                return len(self._memory_fallback.get(user_id, []))
        except Exception:
            return 0


# 全局 ChatMemory 实例（单例模式）
_chat_memory: Optional[ChatMemory] = None


def get_chat_memory() -> ChatMemory:
    """获取全局 ChatMemory 实例。"""
    global _chat_memory
    if _chat_memory is None:
        _chat_memory = ChatMemory()
    return _chat_memory
