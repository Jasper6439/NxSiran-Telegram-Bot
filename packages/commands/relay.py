import logging

import httpx

from system.config import RELAY_API_KEY


# ============================================================
# Telegram消息历史搜索
# ============================================================

async def search_relay_messages(query: str, limit: int = 10) -> str:
    """通过Relay API搜索Telegram消息历史
    Args:
        query: 搜索关键词
        limit: 最大结果数
    Returns:
        搜索结果文本或错误信息
    """
    if not RELAY_API_KEY:
        return None

    try:
        from characters.ai_client import _get_http_client
        client = _get_http_client()
        response = await client.get(
            "https://relayfortelegram.com/api/v1/search",
            params={"q": query, "limit": limit},
            headers={"Authorization": f"Bearer {RELAY_API_KEY}"},
        )
        if response.status_code != 200:
            logging.warning(f"搜索API返回 {response.status_code}")
            return f"搜索失败（HTTP {response.status_code}）"

        data = response.json()
        results = data.get("results", [])
        if not results:
            return f"没有找到与「{query}」相关的消息。"

        # 格式化搜索结果
        output_lines = [f"找到 {len(results)} 条相关消息：\n"]
        for i, msg in enumerate(results[:limit]):
            chat_name = msg.get("chatName", "未知聊天")
            sender = msg.get("senderName", "未知")
            content = msg.get("content", "")[:100]
            date = msg.get("messageDate", "")[:10]
            output_lines.append(f"{i+1}. [{chat_name}] {sender} ({date})\n   {content}\n")

        return "\n".join(output_lines)
    except Exception as e:
        logging.error(f"搜索失败: {e}")
        return f"搜索出错：{e}"


async def list_relay_chats() -> str:
    """通过Relay API列出同步的聊天列表
    Returns:
        聊天列表文本或错误信息
    """
    if not RELAY_API_KEY:
        return None

    try:
        from characters.ai_client import _get_http_client
        client = _get_http_client()
        response = await client.get(
            "https://relayfortelegram.com/api/v1/chats",
            headers={"Authorization": f"Bearer {RELAY_API_KEY}"},
        )
        if response.status_code != 200:
            logging.warning(f"聊天列表API返回 {response.status_code}")
            return f"获取聊天列表失败（HTTP {response.status_code}）"

        data = response.json()
        chats = data.get("chats", [])
        if not chats:
            return "没有已同步的聊天。请先在 relayfortelegram.com 同步你的聊天。"

        output_lines = [f"已同步 {len(chats)} 个聊天：\n"]
        for i, chat in enumerate(chats):
            name = chat.get("name", "未知")
            chat_type = chat.get("type", "")
            members = chat.get("memberCount", "")
            last_msg = chat.get("lastMessageDate", "")[:10]
            unread = chat.get("unreadCount", 0)
            type_icon = {"group": "👥", "private": "👤", "channel": "📢", "supergroup": "👥"}.get(chat_type, "💬")
            info = f"{name}"
            if members:
                info += f" ({members}人)"
            if unread:
                info += f" [{unread}条未读]"
            output_lines.append(f"{i+1}. {type_icon} {info} (最后消息: {last_msg})")

        return "\n".join(output_lines)
    except Exception as e:
        logging.error(f"获取聊天列表失败: {e}")
        return f"获取聊天列表出错：{e}"
