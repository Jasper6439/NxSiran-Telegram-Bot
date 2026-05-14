import base64
import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import YOUR_CHAT_ID, GEMINI_API_KEY
from characters.image_gen import analyze_image_with_gemini, ocr_document


__all__ = [
    "analyze_img_cmd",
    "ocr_cmd",
    "_pending_analyze_img",
    "_pending_ocr",
]


# ============================================================
# /analyze_img 命令 - 图片深度分析
# ============================================================

# 记录待分析的图片
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
        logging.error(f"/analyze_img失败: {e}")
        await update.message.reply_text("...出错了。")


# ============================================================
# /ocr 命令 - 文档OCR文字提取
# ============================================================

# 记录待OCR的图片
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
        logging.error(f"/ocr失败: {e}")
        await update.message.reply_text("...出错了。")
