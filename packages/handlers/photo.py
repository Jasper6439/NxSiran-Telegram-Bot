"""照片和文档处理"""

import base64
import logging
import os
import random
import zipfile
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from system.config import (
    YOUR_CHAT_ID, TELEGRAM_TOKEN, GEMINI_API_KEY,
    DATA_DIR, get_user_selfie_dir, get_user_dir,
    get_user_memory_file, load_json,
)
from characters.stats import load_stats, save_stats
from characters.image_gen import (
    analyze_photo_with_ai, analyze_image_with_gemini, ocr_document,
    get_photo_response_by_type, get_selfie_count,
)
from characters.memory_legacy import save_memory_entry
from characters import get_current_character
from packages.commands.extra import _pending_analyze_img, _pending_ocr
from packages.commands.import_cmds import (
    pending_chat_imports,
    handle_chatlog_document,
)

__all__ = ["handle_photo", "handle_document"]


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """智能处理收到的照片"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    photos = update.message.photo
    if not photos:
        return

    photo = photos[-1]

    # [Skill: vision-sandbox] [Skill: deepread-ocr] 检查是否有待处理的图片分析/OCR请求
    if chat_id in _pending_analyze_img:
        del _pending_analyze_img[chat_id]
        if GEMINI_API_KEY:
            try:
                await update.message.chat.send_action("typing")
                file = await update.get_bot().get_file(photo.file_id)
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
                return
            except Exception as e:
                logging.error(f"[Skill: vision-sandbox] 图片分析失败: {e}")
                await update.message.reply_text("...出错了。")
                return

    if chat_id in _pending_ocr:
        del _pending_ocr[chat_id]
        if GEMINI_API_KEY:
            try:
                await update.message.chat.send_action("typing")
                file = await update.get_bot().get_file(photo.file_id)
                photo_bytes = await file.download_as_bytearray()
                image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")

                result = await ocr_document(image_b64)
                if result:
                    if len(result) > 4000:
                        for i in range(0, len(result), 4000):
                            await update.message.reply_text(result[i:i+4000])
                    else:
                        await update.message.reply_text(result)
                else:
                    await update.message.reply_text("...没识别出文字。")
                return
            except Exception as e:
                logging.error(f"[Skill: deepread-ocr] OCR失败: {e}")
                await update.message.reply_text("...出错了。")
                return

    try:
        # 先发送分析中的提示
        await update.message.chat.send_action("typing")

        # 获取照片文件
        file = await update.get_bot().get_file(photo.file_id)

        # 下载到临时位置进行分析
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(file.file_path)[1] or ".jpg"

        # 使用AI分析照片（通过文件URL）
        photo_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file.file_path}"
        analysis = await analyze_photo_with_ai(photo_url)

        photo_type = analysis.get("type", "other")
        description = analysis.get("description", "")
        is_selfie = analysis.get("is_selfie", False)
        is_chayewoon = analysis.get("is_chayewoon", False)

        # 如果AI识别为车如云，强制设为自拍
        if is_chayewoon:
            is_selfie = True
            photo_type = "portrait"

        # 根据类型决定保存位置和回复
        if is_selfie or photo_type == "portrait" or is_chayewoon:
            # 保存为车如云的自拍
            filename = f"selfie_{timestamp}{ext}"
            char = get_current_character()
            char_id = char.config.id if char else None
            filepath = os.path.join(get_user_selfie_dir(chat_id, char_id), filename)
            await file.download_to_drive(filepath)
            count = get_selfie_count()

            # 更新统计
            stats = load_stats()
            stats["photos_received"] = stats.get("photos_received", 0) + 1
            save_stats(stats)

            responses = [
                f"...你给我发照片干什么。（已保存，现在共{count}张）",
                f"（看了一眼）...哦。（已保存，现在共{count}张）",
                f"...我保存了。现在共{count}张了。",
                f"（皱鼻子）...干嘛发这个。（已保存，现在共{count}张）",
                f"...收到了。现在共{count}张。",
            ]
            await update.message.reply_text(random.choice(responses))
        else:
            # 保存为用户照片（不统计在自拍里）
            filename = f"user_{timestamp}{ext}"
            filepath = os.path.join(USER_PHOTOS_DIR, filename)
            await file.download_to_drive(filepath)

            # 根据类型生成回复
            reply = get_photo_response_by_type(photo_type, description)
            await update.message.reply_text(reply)

            # 记录到记忆中
            if photo_type == "food":
                save_memory_entry(f"明喜欢吃{description}")
            elif photo_type == "scenery":
                save_memory_entry(f"明去过{description}")

            # [Skill: vision-sandbox] 使用Gemini对图片进行深度分析并保存描述到记忆
            if GEMINI_API_KEY:
                try:
                    photo_bytes = await file.download_as_bytearray()
                    image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")
                    detail_prompt = "请用一句简短的中文描述这张图片的内容（不超过30字）："
                    detail_desc = await analyze_image_with_gemini(image_b64, detail_prompt)
                    if detail_desc and len(detail_desc) > 5:
                        save_memory_entry(f"明发了一张图片：{detail_desc.strip()}")
                except Exception as e:
                    logging.debug(f"[Skill: vision-sandbox] 深度分析跳过: {e}")

    except Exception as e:
        logging.error(f"处理照片失败: {e}")
        await update.message.reply_text("...（照片处理失败了，再发一次试试）")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    doc = update.message.document
    if not doc:
        return

    # 检查是否在等待导入聊天记录
    if chat_id in pending_chat_imports and doc.file_name.lower().endswith('.txt'):
        await handle_chatlog_document(update, context)
        return

    if not doc.file_name.endswith('.zip'):
        return

    try:
        await update.message.chat.send_action("upload_document")

        file = await update.get_bot().get_file(doc.file_id)
        tmp_path = f"/tmp/import_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
        await file.download_to_drive(tmp_path)

        imported_memories = 0
        imported_photos = 0
        imported_history = False
        imported_anniversaries = False
        imported_stats = False

        with zipfile.ZipFile(tmp_path, 'r') as zf:
            for name in zf.namelist():
                if name == "long_term_memory.json":
                    zf.extract(name, get_user_dir(chat_id))
                    imported_memories = len(load_json(get_user_memory_file(chat_id), []))
                elif name == "chat_history.json":
                    zf.extract(name, DATA_DIR)
                    imported_history = True
                elif name == "anniversaries.json":
                    zf.extract(name, DATA_DIR)
                    imported_anniversaries = True
                elif name == "chat_stats.json":
                    zf.extract(name, DATA_DIR)
                    imported_stats = True
                elif name.startswith("selfies/"):
                    user_selfie_dir = get_user_selfie_dir(chat_id)
                    zf.extract(name, os.path.dirname(user_selfie_dir))
                    imported_photos += 1

        os.remove(tmp_path)

        if imported_history:
            chat_histories[chat_id] = load_chat_history(chat_id)

        parts = ["...收到了。\n\n"]
        parts.append(f"🧠 {imported_memories} 条记忆")
        parts.append(f"📸 {imported_photos} 张照片")
        if imported_history:
            parts.append("💬 对话历史")
        if imported_anniversaries:
            parts.append("🎉 纪念日")
        if imported_stats:
            parts.append("📊 聊天统计")
        parts.append("\n\n...都回来了。")

        await update.message.reply_text("\n".join(parts))
        logging.info(f"数据导入完成: {imported_memories}条记忆, {imported_photos}张照片")
    except Exception as e:
        logging.error(f"导入数据失败: {e}")
        await update.message.reply_text("...（导入失败了，再发一次试试）")
