"""
图片生成相关功能
从 bot.py 提取的图片生成、场景检测、AI分析等函数
"""

import base64
import io
import json
import logging
import os
import random
import re
import urllib.parse
from datetime import datetime

import httpx
import aiohttp
from PIL import Image
from telegram import Update
from telegram.ext import ContextTypes

from system.config import (
    AI_API_BASE, AI_API_KEY, GEMINI_API_KEY,
    YOUR_CHAT_ID,
    get_user_selfie_dir,
)
from system.prompts import (
    SELFIE_PROMPTS, SELFIE_CAPTIONS,
    SCENE_PROMPTS, SCENE_KEYWORDS, STICKER_PROMPTS,
)


# ============================================================
# 场景生成（融合 @chajoowan Instagram 视觉风格）
# 风格要点：现实感、人+场景双主角、夜景偏多、黑白灰牛仔蓝底色、35-50mm视角、克制情绪
# ============================================================

def detect_scene(text: str) -> str:
    for scene, keywords in SCENE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return scene
    return ""

def generate_scene_url(scene: str) -> str:
    prompts = SCENE_PROMPTS.get(scene, [])
    if not prompts:
        return None
    prompt = random.choice(prompts)
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    return f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=768&seed={seed}&nologo=true&safe=true"


# ============================================================
# AI自拍 - 后备方案（没有真人照片时使用）
# ============================================================

def get_saved_selfies(user_id=None) -> list:
    if user_id is None:
        user_id = YOUR_CHAT_ID or 1
    selfie_dir = get_user_selfie_dir(user_id)
    if not os.path.exists(selfie_dir):
        return []
    files = [f for f in os.listdir(selfie_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    return sorted(files)

def get_selfie_count() -> int:
    return len(get_saved_selfies())

async def generate_ai_selfie_url() -> str:
    prompt = random.choice(SELFIE_PROMPTS)
    encoded_prompt = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1024&seed={seed}&nologo=true&safe=true"
    return url

async def send_selfie_to_chat(bot, chat_id, caption=None):
    try:
        await bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        saved = get_saved_selfies(chat_id)
        if saved:
            selfie_dir = get_user_selfie_dir(chat_id)
            photo_path = os.path.join(selfie_dir, random.choice(saved))
            with open(photo_path, 'rb') as f:
                await bot.send_photo(chat_id=chat_id, photo=f, caption=caption)
            logging.info(f"已发送真人自拍: {photo_path}")
            # 保存到聊天记录
            from chat_history import append_bot_message
            append_bot_message(chat_id, f"[发送了一张自拍照片] {caption or ''}")
            # 更新统计
            from stats import load_stats, save_stats
            stats = load_stats()
            stats["selfies_sent"] = stats.get("selfies_sent", 0) + 1
            save_stats(stats)
        else:
            photo_url = await generate_ai_selfie_url()
            if caption is None:
                caption = random.choice(SELFIE_CAPTIONS)
            await bot.send_photo(chat_id=chat_id, photo=photo_url, caption=caption)
            logging.info("已发送AI自拍（无真人照片）")
            # 保存到聊天记录
            from chat_history import append_bot_message
            append_bot_message(chat_id, f"[发送了一张AI自拍] {caption}")
    except Exception as e:
        logging.error(f"发送自拍失败: {e}")


# ============================================================
# [Skill: slack-gif-creator] 表情包生成系统
# ============================================================

def generate_sticker_url(mood: str) -> str:
    prompts = STICKER_PROMPTS.get(mood, [])
    if not prompts:
        return None
    prompt = random.choice(prompts)
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    # 表情包用正方形
    return f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&seed={seed}&nologo=true&safe=true"


# ============================================================
# AI生成相似人脸照片
# ============================================================

# ============================================================
# AI生成相似人脸照片（通用函数，Telegram/Web 共用）
# ============================================================

async def generate_face_image_core(photo_b64: str, description: str = "自然微笑的肖像照") -> dict:
    """
    AI 换脸核心函数 - 不依赖 Telegram，可被任何端调用。
    
    Args:
        photo_b64: base64 编码的参考照片（不含 data:image 前缀）
        description: 场景描述
    
    Returns:
        dict: {"success": True, "image_b64": "...", "filename": "..."} 或 {"success": False, "error": "..."}
    """
    try:
        photo_data_url = f"data:image/jpeg;base64,{photo_b64}"

        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "google/gemini-2.5-flash-image-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": photo_data_url}
                        },
                        {
                            "type": "text",
                            "text": f"请参考这张照片中的人物外貌特征，生成一张新的照片。要求：保持人物的面部特征和相似度，场景描述：{description}。只生成图片，不需要文字说明。"
                        }
                    ]
                }
            ],
            "modalities": ["image", "text"],
            "image_config": {
                "aspect_ratio": "3:4"
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{AI_API_BASE}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                result = await resp.json()

        if result.get("choices"):
            message = result["choices"][0].get("message", {})
            images = message.get("images", [])

            if images:
                for img in images:
                    image_url = img.get("image_url", {}).get("url", "")
                    if image_url.startswith("data:image"):
                        img_data = image_url.split(",", 1)[1]
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"ai_gen_{timestamp}.jpg"
                        return {
                            "success": True,
                            "image_b64": img_data,
                            "filename": filename,
                        }

        error_msg = result.get("error", {}).get("message", "未知错误")
        return {"success": False, "error": error_msg}

    except Exception as e:
        logging.error(f"[AI换脸] 生成失败: {e}")
        return {"success": False, "error": str(e)}


async def generate_face_from_user_photos(user_id, description: str = "自然微笑的肖像照") -> dict:
    """
    从用户已上传的照片中随机选一张，调用 AI 换脸。
    用于 Web 端和自动发自拍。
    
    Args:
        user_id: 用户 ID
        description: 场景描述
    
    Returns:
        dict: {"success": True, "image_b64": "...", "filename": "...", "filepath": "..."} 或 {"success": False, "error": "..."}
    """
    selfie_dir = get_user_selfie_dir(user_id)
    if not os.path.exists(selfie_dir):
        return {"success": False, "error": "没有上传的照片"}

    # 找到用户上传的照片（排除 AI 生成的）
    photo_files = [
        f for f in os.listdir(selfie_dir)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        and not f.startswith('ai_gen_')
    ]

    if not photo_files:
        return {"success": False, "error": "没有找到用户上传的照片"}

    # 随机选一张
    import random as _random
    photo_path = os.path.join(selfie_dir, _random.choice(photo_files))

    with open(photo_path, 'rb') as f:
        photo_b64 = base64.b64encode(f.read()).decode('utf-8')

    result = await generate_face_image_core(photo_b64, description)

    if result.get("success"):
        # 保存到自拍目录
        filepath = os.path.join(selfie_dir, result["filename"])
        img_bytes = base64.b64decode(result["image_b64"])
        img = Image.open(io.BytesIO(img_bytes))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(filepath, 'JPEG', quality=95)
        result["filepath"] = filepath
        logging.info(f"[AI换脸] 生成成功: {result['filename']} (user: {user_id})")

    return result


async def generate_face_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI生成相似人脸照片 - Telegram 命令 /genface，调用通用核心函数"""
    chat_id = update.effective_chat.id

    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("...请回复一张照片，并描述你想要的场景。\n\n例如：回复照片后发送「穿白色衬衫在咖啡厅」")
        return

    description = " ".join(context.args) if context.args else "自然微笑的肖像照"
    await update.message.reply_text("...正在生成照片，请稍等...")

    try:
        # 下载用户发送的照片
        photo = update.message.reply_to_message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8')

        # 调用通用核心函数
        result = await generate_face_image_core(photo_b64, description)

        if result.get("success"):
            # 保存到 selfies 目录
            filepath = os.path.join(get_user_selfie_dir(chat_id), result["filename"])
            img_bytes = base64.b64decode(result["image_b64"])
            img = Image.open(io.BytesIO(img_bytes))
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(filepath, 'JPEG', quality=95)

            with open(filepath, 'rb') as f:
                await update.message.reply_photo(photo=f, caption=f"✨ AI生成完成\n场景：{description}")
            logging.info(f"[AI换脸] Telegram 生成成功: {result['filename']}")
        else:
            await update.message.reply_text(f"...生成失败：{result.get('error', '未知错误')}")

    except Exception as e:
        logging.error(f"[AI换脸] Telegram 生成失败: {e}")
        await update.message.reply_text(f"...生成出错：{str(e)}")


# ============================================================
# 照片智能识别与分类处理
# ============================================================

async def analyze_photo_with_ai(photo_url: str) -> dict:
    """使用AI视觉分析照片内容"""
    try:
        # 使用 OpenRouter 的多模态模型分析图片
        # 免费模型：google/gemma-3-12b-it 支持图像
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemma-3-12b-it:free",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "分析这张图片。请用JSON格式回答：{\"type\": \"portrait|food|scenery|object|other\", \"description\": \"简短描述\", \"is_selfie\": true/false, \"is_chayewoon\": true/false}。\n\ntype分类：\n- portrait: 人像/自拍\n- food: 食物\n- scenery: 风景/地点\n- object: 物品\n- other: 其他\n\nis_selfie: 判断是否是人物自拍照片\nis_chayewoon: 判断是否是车如云(Cha Yeo-woon)的照片。车如云是韩国男演员，特征：可能戴眼镜，发型偏长，穿着时尚，气质温柔内敛。如果是他的照片，请设为true。\n\n请仔细判断，如果是车如云的照片，type应该是\"portrait\"，is_selfie和is_chayewoon都应该是true。"},
                                {"type": "image_url", "image_url": {"url": photo_url}}
                            ]
                        }
                    ],
                    "max_tokens": 200,
                },
            )
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                # 尝试解析JSON
                try:
                    # 提取JSON部分
                    json_match = re.search(r'\{[^}]+\}', content)
                    if json_match:
                        return json.loads(json_match.group())
                except Exception:
                    pass
                # 如果解析失败，根据关键词判断
                content_lower = content.lower()
                if any(w in content_lower for w in ["人", "脸", "自拍", "portrait", "person", "face"]):
                    return {"type": "portrait", "description": "人像照片", "is_selfie": True}
                elif any(w in content_lower for w in ["食物", "吃的", "food", "meal", "dish"]):
                    return {"type": "food", "description": "食物照片", "is_selfie": False}
                elif any(w in content_lower for w in ["风景", "景色", "地点", "scenery", "landscape", "building"]):
                    return {"type": "scenery", "description": "风景/地点照片", "is_selfie": False}
                else:
                    return {"type": "other", "description": "其他照片", "is_selfie": False}
    except Exception as e:
        logging.error(f"AI照片分析失败: {e}")
    return {"type": "unknown", "description": "无法识别", "is_selfie": False}

def get_photo_response_by_type(photo_type: str, description: str) -> str:
    """根据照片类型生成车如云的回复"""
    responses = {
        "portrait": [
            "...这是明吗。（盯着看了一会儿）",
            "（皱鼻子）...明给我看这个干什么。",
            "...明今天长这样啊。",
            "（耳尖微红）...干嘛发自己的照片。",
        ],
        "food": [
            "...看起来很好吃。明今天吃这个？",
            "（看了一眼）...明吃得还不错嘛。",
            "...我也想吃。",
            "明怎么不给我带一份。",
        ],
        "scenery": [
            "...这是哪里。明去的？",
            "（看着照片）...风景还不错。",
            "...明一个人去的？",
            "下次带我去。",
        ],
        "object": [
            "...这是什么。明买的？",
            "（仔细看）...看起来挺贵的。",
            "...明喜欢这个？",
            "给我看看实物。",
        ],
        "other": [
            "...这是学长想分享的吗？",
            "（看了一眼）...挺有意思的。",
            "...明发这个给我，是想说什么？",
            "（歪头）...这是明喜欢的？",
        ],
    }
    return random.choice(responses.get(photo_type, responses["other"]))


# ============================================================
# [Skill: vision-sandbox] 图片深度分析（Gemini Vision）
# ============================================================

async def analyze_image_with_gemini(image_data: str, prompt: str) -> str:
    """使用Gemini Vision对图片进行深度分析
    Args:
        image_data: base64编码的图片数据
        prompt: 分析提示词
    Returns:
        分析结果文本
    """
    if not GEMINI_API_KEY:
        return None

    try:
        # 从 misc 模块导入 call_gemini
        from packages.commands.misc import call_gemini
        result = await call_gemini(prompt, image_data=image_data, model="gemini-2.5-flash")
        return result
    except Exception as e:
        logging.error(f"[Skill: vision-sandbox] 图片分析失败: {e}")
        return None


# ============================================================
# [Skill: deepread-ocr] 文档OCR文字提取（Gemini Vision替代）
# ============================================================

async def ocr_document(image_data: str) -> str:
    """使用Gemini Vision进行OCR文字提取
    Args:
        image_data: base64编码的图片/文档数据
    Returns:
        提取的文字内容
    """
    if not GEMINI_API_KEY:
        return None

    ocr_prompt = """请仔细识别并提取这张图片中的所有文字内容。
要求：
1. 保持原文的段落结构和格式
2. 如果有标题、列表、表格等结构，请用Markdown格式还原
3. 同时支持中文和英文识别
4. 如果图片模糊或部分文字不清晰，用[?]标注不确定的字
5. 只输出提取的文字，不要添加任何解释或说明"""

    try:
        # 从 misc 模块导入 call_gemini
        from packages.commands.misc import call_gemini
        result = await call_gemini(ocr_prompt, image_data=image_data, model="gemini-2.5-flash")
        return result
    except Exception as e:
        logging.error(f"[Skill: deepread-ocr] OCR提取失败: {e}")
        return None
