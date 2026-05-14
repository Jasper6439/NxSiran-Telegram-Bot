import logging
import re

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from system.config import AI_API_BASE, AI_API_KEY, AI_MODELS, YOUR_CHAT_ID
from packages.commands.utils import auto_delete_messages


# ============================================================
# 摘要生成系统
# ============================================================

async def fetch_url_content(url: str) -> str:
    """抓取网页内容，提取纯文本"""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                return ""
            html_content = response.text
            # 提取 <body> 中的文本
            body_match = re.search(r'<body[^>]*>([\s\S]*?)</body>', html_content, re.IGNORECASE)
            if body_match:
                body_text = body_match.group(1)
            else:
                body_text = html_content
            # 去除 HTML 标签
            text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', body_text, flags=re.IGNORECASE)
            text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text, flags=re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            # 清理空白
            text = re.sub(r'\s+', ' ', text).strip()
            # 限制长度
            return text[:5000]
    except Exception as e:
        logging.error(f"[摘要] 抓取网页失败: {e}")
        return ""

async def generate_summary(text: str) -> str:
    """使用 AI 生成文本摘要"""
    if not text or len(text) < 20:
        return "...内容太短了，没什么好总结的。"

    prompt = f"""请对以下内容生成简洁的摘要，用3-5个要点总结核心内容。使用中文。

内容：
{text[:4000]}

请按以下格式输出：
1. 要点一
2. 要点二
3. 要点三
（如有更多要点继续编号）

只输出摘要内容，不要加标题或其他说明。"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODELS[0],
                    "messages": [
                        {"role": "system", "content": "你是一个专业的摘要生成助手。请简洁准确地总结内容。"},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                return f"...摘要生成失败（HTTP {response.status_code}）。"
    except Exception as e:
        logging.error(f"[摘要] AI生成失败: {e}")
        return "...摘要生成出错了。"

@auto_delete_messages(delay=3)
async def summarize_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """摘要生成命令"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    args = context.args or []
    text_to_summarize = ""

    if not args and update.message.reply_to_message:
        # 回复消息模式：总结被回复的消息
        replied = update.message.reply_to_message
        if replied.text:
            text_to_summarize = replied.text
        elif replied.caption:
            text_to_summarize = replied.caption
        else:
            await update.message.reply_text("...这条消息没有文字内容可以总结。")
            return
    elif args:
        input_text = " ".join(args)
        # 检查是否是 URL
        url_pattern = r'https?://[^\s]+'
        url_match = re.search(url_pattern, input_text)
        if url_match:
            url = url_match.group()
            await update.message.reply_text("...正在抓取网页内容...")
            text_to_summarize = await fetch_url_content(url)
            if not text_to_summarize:
                await update.message.reply_text("...抓取网页失败了。可能是网站不允许访问。")
                return
        else:
            text_to_summarize = input_text
    else:
        await update.message.reply_text(
            "...学长想让我总结什么？\n\n"
            "用法：\n"
            "  /summarize <文本> - 总结文本\n"
            "  /summarize <URL> - 总结网页\n"
            "  回复消息 + /summarize - 总结该消息"
        )
        return

    await update.message.chat.send_action("typing")
    summary = await generate_summary(text_to_summarize)
    await update.message.reply_text(f"...给你总结好了。\n\n{summary}")
