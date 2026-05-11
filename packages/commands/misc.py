import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from config import (
    AI_API_BASE,
    AI_API_KEY,
    AI_MODELS,
    BOT_VERSION,
    CORRECTIONS_FILE,
    GEMINI_API_KEY,
    RELAY_API_KEY,
    VERSION_FILE,
    YOUR_CHAT_ID,
    get_default_tz,
    load_json,
    save_json,
)
from stats import format_quota_report, load_quota_usage, save_quota_usage
import stats
from anniversary import load_anniversaries, get_upcoming_anniversary, add_anniversary, delete_anniversary


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
                logging.warning(f"[Skill: gemini] Gemini API返回 {response.status_code}: {response.text[:200]}")
                return None

            data = response.json()
            if "candidates" in data and data["candidates"]:
                content = data["candidates"][0].get("content", {})
                text = content.get("parts", [{}])[0].get("text", "")
                return text.strip() if text else None
            return None
    except Exception as e:
        logging.error(f"[Skill: gemini] Gemini API调用失败: {e}")
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
            re.findall(r'<a[^>]*class="result-link"[^>]*href="([^"]*)"', text)
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

__all__ = [
    "quota_cmd",
    "quota_reset_cmd",
    "learned_cmd",
    "fetch_url_content",
    "generate_summary",
    "summarize_cmd",
    "calculate_bot_hash",
    "check_for_updates",
    "version_cmd",
    "check_update_cmd",
    "anniversary_cmd",
    "deep_research",
    "search_relay_messages",
    "list_relay_chats",
]


async def quota_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看免费额度使用情况"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    report = format_quota_report()
    await update.message.reply_text(report)

@auto_delete_messages(delay=3)
async def quota_reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """重置额度告警和断开状态"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    stats._quota_shutdown = False

    usage = load_quota_usage()
    usage['warnings_sent'] = []
    usage['shutdown_triggered'] = False
    save_quota_usage(usage)

    await update.message.reply_text(
        "...额度监控已重置。\n\n"
        "🟢 告警已清除，自动断开已解除。\n"
        "⚠️ 注意：这只是重置了Bot内部的监控状态，\n"
        "Google Cloud 的实际额度不会重置。"
    )

# ============================================================
# [Skill: self-improving] /learned 命令 - 查看学到了什么
# ============================================================

@auto_delete_messages(delay=3)
async def learned_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看 Bot 从纠正中学到了什么"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    corrections = load_json(CORRECTIONS_FILE, [])

    if not corrections:
        await update.message.reply_text(
            "...我还没学到什么。\n\n"
            "（小声）...明纠正我的时候，我会记住的。"
        )
        return

    # 显示最近 10 条纠正记录
    recent = corrections[-10:]
    parts = [f"...明要看我学到了什么吗。\n\n📊 最近 {len(recent)} 条纠正记录：\n━━━━━━━━━━━━━━"]

    for i, c in enumerate(recent, 1):
        user_said = c.get("user_said", "")[:40]
        bot_said = c.get("bot_said", "")[:30]
        timestamp = c.get("timestamp", "")[:16]
        parts.append(f"\n{i}. [{timestamp}]")
        parts.append(f"   学长说：{user_said}")
        parts.append(f"   我说：{bot_said}...")

    parts.append("\n━━━━━━━━━━━━━━")
    parts.append(f"...一共记住了 {len(corrections)} 条。")
    parts.append("（低头）...我会努力改的。")

    await update.message.reply_text("\n".join(parts))

# ============================================================
# [Skill: claw-summarize-pro] 摘要生成系统
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

# ============================================================
# [Skill: auto-updater] 自动更新检查系统
# ============================================================

def calculate_bot_hash() -> str:
    """计算 bot.py 的 MD5 hash"""
    try:
        bot_path = os.path.abspath(__file__)
        with open(bot_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logging.error(f"[自动更新] 计算 hash 失败: {e}")
        return ""

def check_for_updates() -> dict:
    """检查 bot.py 是否有更新，返回更新信息"""
    current_hash = calculate_bot_hash()
    if not current_hash:
        return {"updated": False, "reason": "hash计算失败"}

    version_data = load_json(VERSION_FILE, {})

    if not version_data:
        # 首次运行，记录当前 hash
        version_data = {
            "version": BOT_VERSION,
            "last_check": datetime.now(get_default_tz()).strftime("%Y-%m-%d"),
            "bot_hash": current_hash,
        }
        save_json(VERSION_FILE, version_data)
        return {"updated": False, "reason": "首次运行，已记录版本信息"}

    saved_hash = version_data.get("bot_hash", "")
    saved_version = version_data.get("version", "未知")

    # 更新检查时间
    version_data["last_check"] = datetime.now(get_default_tz()).strftime("%Y-%m-%d")
    version_data["bot_hash"] = current_hash
    version_data["version"] = BOT_VERSION
    save_json(VERSION_FILE, version_data)

    if saved_hash and saved_hash != current_hash:
        return {
            "updated": True,
            "old_version": saved_version,
            "new_version": BOT_VERSION,
            "reason": "代码已变更",
        }

    return {"updated": False, "old_version": saved_version, "new_version": BOT_VERSION}

@auto_delete_messages(delay=3)
async def version_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看当前版本信息"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    version_data = load_json(VERSION_FILE, {})
    last_check = version_data.get("last_check", "未知")
    saved_version = version_data.get("version", "未知")
    current_hash = calculate_bot_hash()

    await update.message.reply_text(
        f"...版本信息。\n\n"
        f"📋 当前版本：{BOT_VERSION}\n"
        f"📦 记录版本：{saved_version}\n"
        f"🔍 代码Hash：{current_hash[:12]}...\n"
        f"📅 上次检查：{last_check}\n\n"
        f"使用 /check_update 手动检查更新。"
    )

@auto_delete_messages(delay=3)
async def check_update_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """手动检查更新"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    await update.message.chat.send_action("typing")
    result = check_for_updates()

    if result["updated"]:
        await update.message.reply_text(
            f"...明。\n\n"
            f"🔄 Bot 代码已更新！\n"
            f"   {result.get('old_version', '?')} → {result.get('new_version', BOT_VERSION)}\n\n"
            f"...好像变强了一点点。"
        )
    else:
        await update.message.reply_text(
            f"...没有更新。\n\n"
            f"📋 当前版本：{BOT_VERSION}\n"
            f"📅 上次检查：{result.get('last_check', datetime.now(get_default_tz()).strftime('%Y-%m-%d'))}\n\n"
            f"...一切正常。"
        )

# ============================================================
# [Skill: 纪念日系统] /anniversary 命令
# ============================================================

@auto_delete_messages(delay=3)
async def anniversary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    args = context.args or []

    if not args:
        # 显示所有纪念日
        anniversaries = load_anniversaries()
        if not anniversaries:
            await update.message.reply_text(
                "...还没有纪念日。\n\n"
                "添加方法：\n"
                "/anniversary 添加 名称 YYYY-MM-DD\n"
                "/anniversary 删除 名称\n\n"
                "例如：/anniversary 添加 第一次见面 2025-01-15"
            )
            return

        # 显示列表 + 即将到来
        upcoming = get_upcoming_anniversary(30)
        parts = ["...学长想看纪念日吗。\n\n📌 我们的纪念日："]
        for a in anniversaries:
            parts.append(f"  • {a['name']}（{a['date']}）")

        if upcoming:
            parts.append("\n⏰ 即将到来：")
            for u in upcoming:
                if u["days_until"] == 0:
                    parts.append(f"  🎂 {u['name']} — 今天！！")
                else:
                    parts.append(f"  📅 {u['name']} — 还有 {u['days_until']} 天")

        parts.append("\n\n/anniversary 添加 名称 YYYY-MM-DD")
        parts.append("/anniversary 删除 名称")
        await update.message.reply_text("\n".join(parts))
        return

    action = args[0]

    if action == "添加" and len(args) >= 3:
        name = args[1]
        date_str = args[2]
        if add_anniversary(name, date_str):
            await update.message.reply_text(f"...记住了。{name} — {date_str}。\n\n（偷偷在心里数着日子）")
        else:
            await update.message.reply_text("...日期格式不对，或者这个名字已经有了。\n\n格式：YYYY-MM-DD（例如 2025-01-15）")

    elif action == "删除" and len(args) >= 2:
        name = " ".join(args[1:])
        if delete_anniversary(name):
            await update.message.reply_text(f"...删掉了{name}。\n\n（低头，不说话）")
        else:
            await update.message.reply_text(f"...没有叫'{name}'的纪念日。")

    else:
        await update.message.reply_text(
            "...用法不对。\n\n"
            "/anniversary → 查看所有纪念日\n"
            "/anniversary 添加 名称 YYYY-MM-DD\n"
            "/anniversary 删除 名称"
        )

# ============================================================
# [Skill: gemini-deep-research] 深度研究功能
# ============================================================

async def deep_research(topic: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """使用Gemini进行简化版深度研究
    Args:
        topic: 研究主题
        chat_id: Telegram聊天ID（用于发送进度）
        context: Bot上下文
    Returns:
        Markdown格式的研究报告
    """
    if not GEMINI_API_KEY:
        return None

    try:
        # 步骤1：将主题分解为子问题
        await context.bot.send_message(chat_id, "...开始研究了，等一下。")

        decompose_prompt = f"""请将以下研究主题分解为3-5个具体的子问题，每个子问题应该覆盖主题的不同方面。
只输出子问题列表，每行一个，不要加序号或其他格式。

研究主题：{topic}"""

        sub_questions = await call_gemini(decompose_prompt)
        if not sub_questions:
            return None

        questions = [q.strip() for q in sub_questions.strip().split("\n") if q.strip()]
        if not questions:
            return None

        # 步骤2：对每个子问题进行研究
        all_findings = []
        for i, question in enumerate(questions):
            await context.bot.send_message(chat_id, f"...正在研究第{i+1}/{len(questions)}个问题...")

            # 先尝试联网搜索
            search_result = await web_search(question)

            # 构建搜索参考（避免f-string中的反斜杠问题）
            search_ref = ""
            if search_result:
                search_ref = f"参考搜索结果：\n{search_result}\n\n"

            research_prompt = f"""研究问题：{question}

{search_ref}
请对这个问题进行详细分析，包括：
1. 核心事实和关键信息
2. 不同观点和角度
3. 重要数据或案例

用简洁的段落回答，每段不超过3句话。"""

            finding = await call_gemini(research_prompt)
            if finding:
                all_findings.append(f"### {question}\n\n{finding}")

            # 避免API限流
            await asyncio.sleep(1)

        if not all_findings:
            return None

        # 步骤3：综合生成报告
        await context.bot.send_message(chat_id, "...正在整理报告...")

        synthesis_prompt = f"""请根据以下研究结果，生成一份关于「{topic}」的综合研究报告。

研究结果：
{chr(10).join(all_findings)}

报告格式要求（Markdown）：
# {topic} - 研究报告

## 摘要
（200字以内的核心发现总结）

## 详细分析
（按子问题组织，每个子问题一个小节）

## 结论
（关键发现和洞察）

## 延伸阅读建议
（3-5个相关搜索关键词）"""

        report = await call_gemini(synthesis_prompt)
        return report

    except Exception as e:
        logging.error(f"[Skill: gemini-deep-research] 深度研究失败: {e}")
        return None


# ============================================================
# [Skill: relay-for-telegram] Telegram消息历史搜索
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
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://relayfortelegram.com/api/v1/search",
                params={"q": query, "limit": limit},
                headers={"Authorization": f"Bearer {RELAY_API_KEY}"},
            )
            if response.status_code != 200:
                logging.warning(f"[Skill: relay-for-telegram] 搜索API返回 {response.status_code}")
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
        logging.error(f"[Skill: relay-for-telegram] 搜索失败: {e}")
        return f"搜索出错：{e}"


async def list_relay_chats() -> str:
    """通过Relay API列出同步的聊天列表
    Returns:
        聊天列表文本或错误信息
    """
    if not RELAY_API_KEY:
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://relayfortelegram.com/api/v1/chats",
                headers={"Authorization": f"Bearer {RELAY_API_KEY}"},
            )
            if response.status_code != 200:
                logging.warning(f"[Skill: relay-for-telegram] 聊天列表API返回 {response.status_code}")
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
        logging.error(f"[Skill: relay-for-telegram] 获取聊天列表失败: {e}")
        return f"获取聊天列表出错：{e}"
