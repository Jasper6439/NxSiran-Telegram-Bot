"""TTS 声音克隆系统 - v1.4.7.2
支持上传语料训练角色专属声音
"""

import asyncio
import io
import logging
import os
import random

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from system.config import YOUR_CHAT_ID
from characters.tts_engine import TTSEngine

from packages.commands.utils import auto_delete_messages, _get_call_ai

from characters.music_skill import music_skill
from characters.novel_knowledge import query_novel, init_novel_knowledge
from characters.qdrant_memory import search_memories
from characters.chat_history import load_chat_history, save_chat_history

tts = TTSEngine()

__all__ = [
    "get_character_voice_config",
    "check_sovits_available",
    "send_voice_message",
    "_send_edge_tts_voice",
    "_send_sovits_voice",
    "upload_voice_sample",
    "get_voice_samples_status",
    "start_voice_training",
    "voice_cmd",
    "voice_sample_cmd",
    "voice_train_cmd",
    "voice_status_cmd",
    "music_cmd",
    "novel_cmd",
    "qdrant_memory_cmd",
    "tts_voice_toggle",
    "tts_status_cmd",
    "user_voice_enabled",
    "_pending_voice_samples",
]

# ============================================================
# 角色声音配置
# ============================================================

VOICE_CONFIG = {
    "chayewoon": {
        "name": "车如云",
        "gender": "male",
        "language": "ko",
        # Edge TTS 韩语男声
        "edge_voice": "ko-KR-InJoonNeural",
        # 声音克隆模型路径（训练后生成）
        "sovits_model": None,  # 训练后填充: data/voices/chayewoon/model.pth
        "sovits_config": None,  # 训练后填充: data/voices/chayewoon/config.json
        # 语料目录
        "audio_samples_dir": "data/voices/chayewoon/samples",
        "min_samples": 10,  # 最少需要10条语料开始训练
        "trained": False,
    }
}

# 全局TTS模式: "edge" | "sovits" | "fish"
TTS_MODE = "edge"


def get_character_voice_config(character_id: str = "chayewoon"):
    """获取角色声音配置"""
    return VOICE_CONFIG.get(character_id, VOICE_CONFIG["chayewoon"])


def check_sovits_available(character_id: str = "chayewoon") -> bool:
    """检查是否可以使用SoVITS声音克隆"""
    config = get_character_voice_config(character_id)
    if config.get("sovits_model") and os.path.exists(config["sovits_model"]):
        if config.get("sovits_config") and os.path.exists(config["sovits_config"]):
            return True
    return False


async def send_voice_message(app, chat_id: int, text: str, character_id: str = "chayewoon"):
    """使用TTS生成语音消息发送给用户 - v1.4.7.2 支持声音克隆"""
    try:
        config = get_character_voice_config(character_id)

        # 优先使用声音克隆（如果已训练）
        if TTS_MODE == "sovits" and check_sovits_available(character_id):
            return await _send_sovits_voice(app, chat_id, text, config)

        # 默认使用 Edge TTS（韩语男声）
        return await _send_edge_tts_voice(app, chat_id, text, config)

    except Exception as e:
        logging.error(f"TTS语音生成失败: {e}")
    return False


async def _send_edge_tts_voice(app, chat_id: int, text: str, config: dict):
    """使用 Edge TTS 生成语音（韩语男声）"""
    try:
        import edge_tts
        import tempfile

        voice = config.get("edge_voice", "ko-KR-InJoonNeural")
        communicate = edge_tts.Communicate(text, voice)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        await communicate.save(tmp_path)

        with open(tmp_path, "rb") as f:
            await app.bot.send_voice(chat_id=chat_id, voice=f)

        os.unlink(tmp_path)
        return True

    except Exception as e:
        logging.warning(f"Edge TTS 失败: {e}")
        return False


async def _send_sovits_voice(app, chat_id: int, text: str, config: dict):
    """使用 GPT-SoVITS 生成角色声音"""
    try:
        # 调用 SoVITS API
        import httpx

        sovits_url = os.environ.get("SOVITS_API_URL", "http://localhost:9880")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{sovits_url}/tts",
                json={
                    "text": text,
                    "text_language": "ko",
                    "refer_wav_path": config.get("sovits_model"),
                    "prompt_text": "",
                    "prompt_language": "ko",
                }
            )

            if resp.status_code == 200:
                voice_buf = io.BytesIO(resp.content)
                voice_buf.name = "voice.wav"
                await app.bot.send_voice(chat_id=chat_id, voice=voice_buf)
                return True

    except Exception as e:
        logging.warning(f"SoVITS TTS 失败，回退到 Edge TTS: {e}")
        return await _send_edge_tts_voice(app, chat_id, text, config)


# ============================================================
# [Skill: TTS] 声音语料管理
# ============================================================

VM_BRIDGE_URL = os.environ.get("VM_BRIDGE_URL", "")


async def upload_voice_sample(audio_file_path: str, character_id: str = "chayewoon") -> dict:
    """上传声音语料到训练服务器

    通过 VM Bridge 发送到训练服务器进行预处理
    """
    try:
        config = get_character_voice_config(character_id)
        samples_dir = config["audio_samples_dir"]

        # 确保目录存在
        os.makedirs(samples_dir, exist_ok=True)

        # 生成唯一文件名
        import uuid
        sample_id = str(uuid.uuid4())[:8]
        target_path = os.path.join(samples_dir, f"{sample_id}.wav")

        # 复制文件到语料目录
        import shutil
        shutil.copy2(audio_file_path, target_path)

        # 可选：通过 bridge 发送到训练服务器
        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('file', open(target_path, 'rb'), filename=f"{sample_id}.wav")
                data.add_field('character_id', character_id)

                async with session.post(f"{VM_BRIDGE_URL}/upload_sample", data=data, timeout=30) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return {
                            "success": True,
                            "sample_id": sample_id,
                            "message": f"语料已上传，当前共 {len(os.listdir(samples_dir))} 条",
                            "bridge_result": result
                        }
        except Exception as e:
            logging.warning(f"Bridge上传失败（本地已保存）: {e}")

        return {
            "success": True,
            "sample_id": sample_id,
            "message": f"语料已保存到本地，当前共 {len(os.listdir(samples_dir))} 条",
            "local_only": True
        }

    except Exception as e:
        logging.error(f"上传语料失败: {e}")
        return {"success": False, "error": str(e)}


async def get_voice_samples_status(character_id: str = "chayewoon") -> dict:
    """获取声音语料状态"""
    try:
        config = get_character_voice_config(character_id)
        samples_dir = config["audio_samples_dir"]

        if not os.path.exists(samples_dir):
            return {
                "character": config["name"],
                "samples_count": 0,
                "min_required": config["min_samples"],
                "ready_to_train": False,
                "trained": config.get("trained", False)
            }

        samples = [f for f in os.listdir(samples_dir) if f.endswith(('.wav', '.mp3', '.ogg'))]

        return {
            "character": config["name"],
            "samples_count": len(samples),
            "min_required": config["min_samples"],
            "ready_to_train": len(samples) >= config["min_samples"],
            "trained": config.get("trained", False),
            "samples": samples[:5]  # 只显示前5个
        }

    except Exception as e:
        return {"error": str(e)}


async def start_voice_training(character_id: str = "chayewoon") -> dict:
    """启动声音克隆训练

    通过 VM Bridge 发送训练命令到训练服务器
    """
    try:
        config = get_character_voice_config(character_id)
        samples_dir = config["audio_samples_dir"]

        # 检查语料数量
        if not os.path.exists(samples_dir):
            return {"success": False, "error": "还没有上传任何语料"}

        samples = [f for f in os.listdir(samples_dir) if f.endswith(('.wav', '.mp3', '.ogg'))]
        if len(samples) < config["min_samples"]:
            return {
                "success": False,
                "error": f"语料不足，需要至少 {config['min_samples']} 条，当前只有 {len(samples)} 条"
            }

        # 通过 bridge 发送训练命令
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{VM_BRIDGE_URL}/start_training",
                    json={
                        "character_id": character_id,
                        "samples_dir": samples_dir,
                        "language": "ko"
                    },
                    timeout=10
                ) as resp:
                    result = await resp.json()
                    return {
                        "success": True,
                        "message": "训练任务已启动",
                        "training_id": result.get("training_id"),
                        "estimated_time": "约30分钟"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"无法连接到训练服务器: {e}",
                "note": "请确保训练服务器已启动"
            }

    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================
# Global state
# ============================================================
user_voice_enabled = {}  # {user_id: bool}

@auto_delete_messages(delay=3)
async def voice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """让车如云发语音消息"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    # 生成一句简短的韩语语音
    voice_texts = [
        "...안녕.",  # ...你好
        "...보고 싶어.",  # ...想你
        "...잘 자.",  # ...晚安
        "...밥 먹었어?",  # ...吃饭了吗
        "...어디야.",  # ...在哪
        "...미안해.",  # ...对不起
        "...고마워.",  # ...谢谢
        "...기다려.",  # ...等我
    ]

    text = random.choice(voice_texts)
    await update.message.chat.send_action("record_voice")

    success = await send_voice_message(context.bot, chat_id, text)
    if success:
        # 同时发送文字翻译
        translations = {
            "...안녕.": "...你好。",
            "...보고 싶어.": "...想你。",
            "...잘 자.": "...晚安。",
            "...밥 먹었어?": "...吃饭了吗？",
            "...어디야.": "...在哪。",
            "...미안해.": "...对不起。",
            "...고마워.": "...谢谢。",
            "...기다려.": "...等我。",
        }
        await update.message.reply_text(translations.get(text, text))
    else:
        await update.message.reply_text("...（沉默）语音发不出去。")


# ============================================================
# [Skill: TTS v1.4.7.2] 声音语料上传与训练命令
# ============================================================

# 记录等待上传语料的用户
_pending_voice_samples = {}  # {chat_id: True}


async def voice_sample_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/voicesample - 上传声音语料用于训练角色声音

    使用方式:
    1. 发送 /voicesample
    2. 发送语音消息（10-30秒最佳）
    3. 系统自动保存并上传到训练服务器
    """
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    # 检查当前语料状态
    status = await get_voice_samples_status("chayewoon")

    msg = "🎙️ **声音语料上传**\n\n"
    msg += f"当前已收集: {status.get('samples_count', 0)} 条语料\n"
    msg += f"最少需要: {status.get('min_required', 10)} 条\n"
    msg += f"训练状态: {'✅ 已训练' if status.get('trained') else '⏳ 未训练'}\n\n"

    if status.get('ready_to_train'):
        msg += "✅ 语料充足，可以使用 /voicetrain 开始训练\n\n"

    msg += "请直接发送语音消息（10-30秒），我会保存为训练语料。"

    _pending_voice_samples[chat_id] = True
    await update.message.reply_text(msg, parse_mode="Markdown")


async def voice_train_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/voicetrain - 启动声音克隆训练

    需要至少10条语料才能开始训练
    训练时间约30分钟
    """
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    await update.message.chat.send_action("typing")

    # 先检查语料状态
    status = await get_voice_samples_status("chayewoon")

    if not status.get('ready_to_train'):
        await update.message.reply_text(
            f"...语料不够。需要 {status.get('min_required')} 条，"
            f"现在只有 {status.get('samples_count')} 条。"
            f"先用 /voicesample 上传更多。"
        )
        return

    # 启动训练
    result = await start_voice_training("chayewoon")

    if result.get('success'):
        await update.message.reply_text(
            f"🎙️ **训练已启动**\n\n"
            f"训练ID: `{result.get('training_id', 'N/A')}`\n"
            f"预计时间: {result.get('estimated_time', '约30分钟')}\n\n"
            f"训练完成后，车如云的声音会更像他本人。",
            parse_mode="Markdown"
        )
    else:
        error = result.get('error', '未知错误')
        await update.message.reply_text(f"...训练启动失败。{error}")


async def voice_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/voicestatus - 查看声音训练状态"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    status = await get_voice_samples_status("chayewoon")

    msg = "🎙️ **声音训练状态**\n\n"
    msg += f"角色: {status.get('character', '车如云')}\n"
    msg += f"语料数量: {status.get('samples_count', 0)} / {status.get('min_required', 10)}\n"
    msg += f"可训练: {'✅' if status.get('ready_to_train') else '❌'}\n"
    msg += f"训练状态: {'✅ 已完成' if status.get('trained') else '⏳ 未训练'}\n"

    if status.get('samples'):
        msg += f"\n最近语料: {', '.join(status['samples'])}"

    await update.message.reply_text(msg, parse_mode="Markdown")


# [Skill: Music] 音乐搜索与评价
async def music_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """搜索歌曲并给出车如云的评价"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    # 获取歌名（去掉 /music 命令）
    query = update.message.text.replace('/music', '').strip()
    if not query:
        await update.message.reply_text("...什么歌？（把歌名发给我）")
        return

    # 发送"正在搜索"状态
    await update.message.chat.send_action("typing")

    try:
        # 搜索歌曲
        result = await music_skill.process_music_request(query)

        if not result:
            await update.message.reply_text("...没找到这首歌。（歌名对吗？）")
            return

        song = result['song']
        style = result['style']
        review = result['review']

        # 构建回复
        reply = f"🎵 {song['title']}\n"
        reply += f"👤 {song['artist']}\n"
        reply += f"⏱️ {style['duration_formatted']}\n\n"
        reply += f"{review}\n\n"
        reply += f"▶️ {song['url']}"

        # 如果有封面，发送封面+文字
        if song.get('thumbnail'):
            try:
                await update.message.reply_photo(
                    photo=song['thumbnail'],
                    caption=reply
                )
            except Exception:
                # 封面发送失败，只发文字
                await update.message.reply_text(reply)
        else:
            await update.message.reply_text(reply)

        # 保存到聊天记录
        history = load_chat_history(chat_id)
        history.append({"role": "user", "content": f"/music {query}"})
        history.append({"role": "assistant", "content": review})
        save_chat_history(chat_id, history)

    except Exception as e:
        logging.error(f"[Music] 错误: {e}")
        await update.message.reply_text("...（搜索失败）网络问题。")

# [Skill: LightRAG] 小说知识查询 - v1.4.7 修复：添加依赖检查和更好错误提示

async def novel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询小说知识库"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    # 获取查询内容（去掉 /novel 命令）
    query = update.message.text.replace('/novel', '').strip()
    if not query:
        await update.message.reply_text("...想问小说里的什么？（把问题发给我）")
        return

    await update.message.chat.send_action("typing")

    try:
        # v1.4.7: 尝试初始化知识库（如果还没初始化）
        await init_novel_knowledge()

        # 查询知识库
        result = await query_novel(query)

        # 车如云风格的回应
        if result and len(result) > 10:
            # 让 AI 用车如云的口吻转述
            prompt = f"用户问：{query}\n\n小说中的相关内容：\n{result}\n\n请用车如云的口吻（极简、省略号、外冷内热）简短回答，不超过50个字。"
            response = await _get_call_ai()(prompt)
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("...小说里好像没有这个。")

    except ImportError as e:
        logging.error(f"[Novel] 缺少依赖: {e}")
        await update.message.reply_text("...（知识库依赖未安装）需要安装 LightRAG。")
    except Exception as e:
        logging.error(f"[Novel] 查询失败: {e}")
        await update.message.reply_text("...（查询失败）知识库还没准备好。")

# [Skill: ChromaDB] 记忆搜索 - v1.4.7 修复：改为 /semantic 命令避免冲突

async def qdrant_memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """搜索Qdrant语义记忆 - 使用 /semantic 命令"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    # 获取查询内容（支持 /semantic 或 /语义）
    query = update.message.text.replace('/semantic', '').replace('/语义', '').strip()
    if not query:
        await update.message.reply_text("...想找什么记忆？（比如：/semantic 我们聊过跑步吗）")
        return

    try:
        # 搜索记忆
        memories = search_memories(query, chat_id, n_results=3)

        if memories:
            # 找到相关记忆
            response = "...找到了。\n\n"
            for i, mem in enumerate(memories[:3]):
                content = mem.get('content', '')[:100]
                response += f"• {content}...\n"
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("...不记得有这个。")

    except Exception as e:
        logging.error(f"[Memory] 搜索失败: {e}")
        await update.message.reply_text("...（搜索失败）记忆系统出问题了。")

# [Skill: TTS] 语音模式切换
async def tts_voice_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切换语音回复模式"""
    user_id = update.effective_user.id
    user_voice_enabled[user_id] = not user_voice_enabled.get(user_id, False)
    if user_voice_enabled[user_id]:
        await update.message.reply_text(f"🎤 语音模式已开启\n当前引擎: {tts.current_backend}\n发送消息将自动语音回复")
    else:
        await update.message.reply_text("🔇 语音模式已关闭")

async def tts_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看 TTS 状态"""
    backends = []
    try:
        if await tts._backends["edge"].is_available():
            backends.append("Edge TTS ✅")
    except Exception:
        pass
    try:
        if tts._backends["sovits"].is_available():
            backends.append("GPT-SoVITS ✅")
    except Exception:
        pass
    try:
        if await tts._backends["fish"].is_available():
            backends.append("Fish Speech ✅")
    except Exception:
        pass
    status = "\n".join(backends) if backends else "无可用引擎 ❌"
    await update.message.reply_text(f"🔊 TTS 状态\n当前引擎: {tts.current_backend}\n可用引擎:\n{status}")
