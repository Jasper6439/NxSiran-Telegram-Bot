import base64
import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import YOUR_CHAT_ID, GEMINI_API_KEY, RELAY_API_KEY
from packages.commands.misc import (
    call_gemini,
    deep_research,
    search_relay_messages,
    list_relay_chats,
)
from image_gen import analyze_image_with_gemini, ocr_document


__all__ = [
    "gemini_cmd",
    "analyze_img_cmd",
    "ocr_cmd",
    "research_cmd",
    "search_msg_cmd",
    "my_chats_cmd",
    "_pending_analyze_img",
    "_pending_ocr",
]


async def gemini_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """使用Gemini直接回答问题"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    if not context.args:
        await update.message.reply_text("...问什么。用法：/gemini <问题>")
        return

    if not GEMINI_API_KEY:
        await update.message.reply_text("...Gemini没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return

    question = " ".join(context.args)
    await update.message.chat.send_action("typing")

    try:
        result = await call_gemini(question)
        if result:
            # 截断过长回复
            if len(result) > 4000:
                result = result[:4000] + "\n\n...太长了，就这些。"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("...Gemini没有回复。再试试。")
    except Exception as e:
        logging.error(f"[Skill: gemini] /gemini命令失败: {e}")
        await update.message.reply_text("...出错了。")


# ============================================================
# [Skill: vision-sandbox] /analyze_img 命令 - 图片深度分析
# ============================================================

# [Skill: vision-sandbox] 记录待分析的图片
_pending_analyze_img = {}  # chat_id -> image_data (base64)

async def analyze_img_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """回复图片发送 /analyze_img 进行深度分析"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    if not GEMINI_API_KEY:
        await update.message.reply_text("...图片分析没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return

    # 检查是否回复了一张图片
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        # 如果没有回复图片，提示用户
        _pending_analyze_img[chat_id] = True
        await update.message.reply_text("...发一张图片过来，我来分析。")
        return

    # 直接分析回复的图片
    await update.message.chat.send_action("typing")
    try:
        photo = update.message.reply_to_message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")

        analysis_prompt = """请详细分析这张图片，包括：
1. 图片中有什么（主体内容）
2. 颜色、构图、风格
3. 如果有人物，描述其表情和动作
4. 图片的整体氛围和感受
5. 任何有趣的细节

用简洁的中文回答。"""

        result = await analyze_image_with_gemini(image_b64, analysis_prompt)
        if result:
            if len(result) > 4000:
                result = result[:4000] + "\n\n...太多了，就这些。"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("...分析失败了。再试试。")
    except Exception as e:
        logging.error(f"[Skill: vision-sandbox] /analyze_img失败: {e}")
        await update.message.reply_text("...出错了。")


# ============================================================
# [Skill: deepread-ocr] /ocr 命令 - 文档OCR文字提取
# ============================================================

# [Skill: deepread-ocr] 记录待OCR的图片
_pending_ocr = {}  # chat_id -> True

async def ocr_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """回复图片/文件发送 /ocr 提取文字"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    if not GEMINI_API_KEY:
        await update.message.reply_text("...OCR没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return

    # 检查是否回复了一张图片
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        _pending_ocr[chat_id] = True
        await update.message.reply_text("...发一张图片或文档过来，我来提取文字。")
        return

    await update.message.chat.send_action("typing")
    try:
        photo = update.message.reply_to_message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")

        result = await ocr_document(image_b64)
        if result:
            if len(result) > 4000:
                # 分段发送长文本
                for i in range(0, len(result), 4000):
                    await update.message.reply_text(result[i:i+4000])
            else:
                await update.message.reply_text(result)
        else:
            await update.message.reply_text("...没识别出文字。图片太模糊或者没有文字。")
    except Exception as e:
        logging.error(f"[Skill: deepread-ocr] /ocr失败: {e}")
        await update.message.reply_text("...出错了。")


# ============================================================
# [Skill: gemini-deep-research] /research 命令 - 深度研究
# ============================================================

async def research_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """使用Gemini进行深度研究"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    if not context.args:
        await update.message.reply_text("...研究什么。用法：/research <主题>")
        return

    if not GEMINI_API_KEY:
        await update.message.reply_text("...深度研究没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return

    topic = " ".join(context.args)
    await update.message.chat.send_action("typing")

    try:
        report = await deep_research(topic, chat_id, context)
        if report:
            # 分段发送长报告
            if len(report) > 4000:
                for i in range(0, len(report), 4000):
                    await context.bot.send_message(chat_id, report[i:i+4000])
            else:
                await context.bot.send_message(chat_id, report)
        else:
            await context.bot.send_message(chat_id, "...研究失败了。换个主题试试。")
    except Exception as e:
        logging.error(f"[Skill: gemini-deep-research] /research失败: {e}")
        await context.bot.send_message(chat_id, "...出错了。")


# ============================================================
# [Skill: relay-for-telegram] /search_msg 和 /my_chats 命令
# ============================================================

async def search_msg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """搜索Telegram消息历史"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    if not context.args:
        await update.message.reply_text("...搜什么。用法：/search_msg <关键词>")
        return

    if not RELAY_API_KEY:
        await update.message.reply_text(
            "...消息搜索没配置。\n\n"
            "需要设置 RELAY_API_KEY 环境变量。\n"
            "获取方式：\n"
            "1. 访问 https://relayfortelegram.com\n"
            "2. 用Telegram手机号注册\n"
            "3. 获取API Key\n"
            "4. 设置环境变量 RELAY_API_KEY=rl_live_xxx"
        )
        return

    query = " ".join(context.args)
    await update.message.chat.send_action("typing")

    try:
        result = await search_relay_messages(query)
        if result:
            if len(result) > 4000:
                result = result[:4000] + "\n\n...结果太多了，就这些。"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("...搜索失败了。")
    except Exception as e:
        logging.error(f"[Skill: relay-for-telegram] /search_msg失败: {e}")
        await update.message.reply_text("...出错了。")


async def my_chats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出已同步的Telegram聊天"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    if not RELAY_API_KEY:
        await update.message.reply_text(
            "...聊天列表没配置。\n\n"
            "需要设置 RELAY_API_KEY 环境变量。\n"
            "获取方式：\n"
            "1. 访问 https://relayfortelegram.com\n"
            "2. 用Telegram手机号注册\n"
            "3. 获取API Key\n"
            "4. 设置环境变量 RELAY_API_KEY=rl_live_xxx"
        )
        return

    await update.message.chat.send_action("typing")

    try:
        result = await list_relay_chats()
        if result:
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("...获取失败了。")
    except Exception as e:
        logging.error(f"[Skill: relay-for-telegram] /my_chats失败: {e}")
        await update.message.reply_text("...出错了。")
