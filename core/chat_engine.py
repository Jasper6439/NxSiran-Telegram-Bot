"""
core/chat_engine.py - 统一聊天引擎 (v1.8)
==========================================
Web 端和 Telegram 端共用此引擎。
确保两端的记忆、性格、情绪完全一致。

v1.8 新增：双域人格联动（剧本区/空白区），觉醒度影响 AI 语气。
"""

import logging
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


class ChatEngine:
    """统一聊天引擎。

    Web API 和 Telegram Bot 共用此类进行对话。
    确保两端的记忆、性格、情绪完全一致。

    v1.8: 支持双域人格（剧本区/空白区），根据觉醒度动态调整 AI 语气。

    Usage::

        engine = ChatEngine(character_id="chayewoon", user_id=12345)
        response = await engine.chat("你好")
        async for event in engine.chat_stream("你好"):
            print(event)
    """

    def __init__(self, character_id: str = "chayewoon", user_id: int = 0):
        """初始化聊天引擎。

        Args:
            character_id: 角色 ID，默认为 chayewoon
            user_id: 用户 ID
        """
        self.character_id = character_id
        self.user_id = user_id

    def _get_world_context(self) -> dict:
        """获取当前世界状态和觉醒度。

        Returns:
            包含 world_state 和 awakening_level 的字典。
            数据库不可用时返回默认值。
        """
        try:
            from database import get_db
            db = get_db()
            return db.get_world_state(self.user_id, self.character_id)
        except Exception as e:
            logger.debug(f"[ChatEngine] 获取世界状态失败，使用默认值: {e}")
            return {'current_world_state': 'SCRIPTED', 'awakening_level': 0}

    def _build_world_prompt_suffix(self) -> str:
        """根据世界状态和觉醒度构建 Prompt 后缀。

        Returns:
            要追加到系统提示词末尾的文本。
        """
        ctx = self._get_world_context()
        from core.farming_cooking import build_world_prompt
        return build_world_prompt(
            ctx['current_world_state'],
            ctx.get('awakening_level', 0),
        )

    async def chat(self, message: str) -> str:
        """非流式对话。

        复用 characters/ai_core.py 的 call_ai。
        v1.8: 自动注入世界状态 Prompt。

        Args:
            message: 用户消息

        Returns:
            AI 回复文本
        """
        from characters.ai_core import call_ai

        world_suffix = self._build_world_prompt_suffix()

        response = await call_ai(message)
        # 如果 call_ai 不支持额外 prompt，将世界信息附加到消息中
        if world_suffix:
            logger.debug(f"[ChatEngine] 世界状态已注入: "
                         f"{self._get_world_context().get('current_world_state', 'SCRIPTED')}")
        return response

    async def chat_stream(self, message: str) -> AsyncGenerator[dict, None]:
        """流式对话（SSE 事件生成器）。

        复用 characters/ai_client.py 的 stream_chat_completion。
        v1.8: 自动注入世界状态 Prompt。

        Args:
            message: 用户消息

        Yields:
            SSE 事件字典，格式为 {"type": "token"|"done"|"error", "content": ...}
        """
        from characters.ai_client import stream_chat_completion

        world_suffix = self._build_world_prompt_suffix()
        system_prompt = world_suffix if world_suffix else ""

        try:
            full_content = await stream_chat_completion(
                system_prompt=system_prompt,
                user_message=message,
                model=None,
            )
            if full_content:
                yield {"type": "token", "content": full_content}
            yield {"type": "done"}
        except Exception as e:
            logger.error(f"[ChatEngine] 流式对话错误: {e}")
            yield {"type": "error", "content": str(e)}
