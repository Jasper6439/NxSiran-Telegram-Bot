import asyncio
import logging
import re

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from config import GEMINI_API_KEY


def auto_delete_messages(delay: int = 5):
    """装饰器：命令完成后自动删除用户命令和Bot回复，减少非真人聊天感"""
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_msg_id = update.message.message_id if update.message else None
            chat_id = update.effective_chat.id

            try:
                result = await func(update, context)

                # 延迟删除消息
                if user_msg_id and chat_id:
                    try:
                        await asyncio.sleep(delay)
                        await context.bot.delete_message(chat_id, user_msg_id)
                    except Exception:
                        pass  # 消息可能已被删除或权限不足

                return result
            except Exception as e:
                # 出错时也尝试删除用户消息
                if user_msg_id and chat_id:
                    try:
                        await context.bot.delete_message(chat_id, user_msg_id)
                    except Exception:
                        pass
                raise e
        return wrapper
    return decorator


async def call_gemini(prompt: str, image_data: str = None, model: str = "gemini-2.5-flash") -> str:
    """调用Gemini API进行文本或图片分析"""
    if not GEMINI_API_KEY:
        return None

    try:
        parts = []
        if image_data:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_data
                }
            })
        parts.append({"text": prompt})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": parts}],
                    "generationConfig": {
                        "temperature": 0.85,
                        "maxOutputTokens": 1024,
                    }
                },
            )
            if response.status_code != 200:
                logging.warning(f"Gemini API返回 {response.status_code}: {response.text[:200]}")
                return None

            data = response.json()
            if "candidates" in data and data["candidates"]:
                content = data["candidates"][0].get("content", {})
                text = content.get("parts", [{}])[0].get("text", "")
                return text.strip() if text else None
            return None
    except Exception as e:
        logging.error(f"Gemini API调用失败: {e}")
        return None


async def web_search(query: str, max_results: int = 3) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://lite.duckduckgo.com/lite/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True,
            )
            if response.status_code != 200:
                return ""
            text = response.text
            results = []
            snippets = re.findall(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', text, re.DOTALL)
            for i in range(min(max_results, len(snippets))):
                clean = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                if clean and len(clean) > 10:
                    results.append(clean)
            if results:
                return "\n".join([f"[{i+1}] {r}" for i, r in enumerate(results)])
            return ""
    except Exception as e:
        logging.error(f"搜索失败: {e}")
        return ""
