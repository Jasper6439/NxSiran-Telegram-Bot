"""视频导入模块：视频→音频→文字→AI分析"""

import json
import logging
import os
import re
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from config import DATA_DIR, VIDEO_DIR, YOUR_CHAT_ID, AI_API_BASE, AI_API_KEY, AI_MODELS
from config import load_json, save_json, get_default_tz
from memory_legacy import save_memory_entry

__all__ = [
    'pending_video_imports',
    'extract_audio_from_video',
    'transcribe_audio_whisper',
    'transcribe_audio_primary',
    'analyze_video_transcript',
    'save_video_analysis',
    'get_video_analysis_context',
    'import_video_cmd',
    'handle_video_import',
]

pending_video_imports = {}


def extract_audio_from_video(video_path: str) -> str:
    """从视频中提取音频（使用ffmpeg）"""
    audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
    cmd = f"ffmpeg -i '{video_path}' -vn -acodec libmp3lame -q:a 2 -ar 16000 -ac 1 '{audio_path}' -y 2>/dev/null"
    os.system(cmd)
    return audio_path if os.path.exists(audio_path) else ""

def transcribe_audio_whisper(audio_path: str) -> str:
    """使用Whisper将音频转为文字（需要大内存，e2-micro可能无法使用）"""
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, language="ko", verbose=False)
        return result.get("text", "")
    except ImportError:
        logging.info("Whisper未安装，使用备选方案")
        return ""
    except Exception as e:
        logging.error(f"Whisper转写失败: {e}")
        return ""

def transcribe_audio_primary(audio_path: str) -> str:
    """备选方案：使用Google Speech Recognition（免费，有长度限制）"""
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        
        # 分段处理（每段30秒）
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(audio_path)
        chunk_ms = 30000  # 30秒
        chunks = [audio[i:i+chunk_ms] for i in range(0, len(audio), chunk_ms)]
        
        full_text = []
        for i, chunk in enumerate(chunks):
            chunk_path = f"/tmp/chunk_{i}.wav"
            chunk.export(chunk_path, format="wav")
            
            with sr.AudioFile(chunk_path) as source:
                audio_data = recognizer.record(source)
            
            try:
                text = recognizer.recognize_google(audio_data, language="ko-KR")
                full_text.append(text)
            except Exception:
                full_text.append("[无法识别]")
            
            os.remove(chunk_path)
        
        return " ".join(full_text)
    except Exception as e:
        logging.error(f"语音识别失败: {e}")
        return ""

async def analyze_video_transcript(transcript: str, video_type: str = "剧集") -> dict:
    """使用AI分析视频转录内容，提取角色特点"""
    if not transcript or len(transcript) < 50:
        return {'success': False, 'error': '转录内容太短'}
    
    # 截取样本（避免token超限）
    sample = transcript[:3000] if len(transcript) > 3000 else transcript
    
    if video_type == "采访":
        prompt = f"""分析以下演员采访/花絮的转录内容，提取演员的真实说话风格和性格特点。

转录内容：
{sample}

请用JSON格式返回：
{{
    "speaking_style": "说话风格描述（语速、停顿习惯、口头禅）",
    "personality_traits": ["性格特点1", "性格特点2", "性格特点3"],
    "catchphrases": ["口头禅或常用表达1", "常用表达2"],
    "emotional_expression": "情感表达方式（什么时候笑、什么时候沉默等）",
    "unique_habits": "独特的说话习惯或小动作描述",
    "tone_analysis": "整体语气特点（温柔/冷淡/活泼/内向等）"
}}

只返回JSON。"""
    else:
        prompt = f"""分析以下韩剧片段的转录内容，提取车如云这个角色的说话风格和性格特点。

转录内容：
{sample}

请用JSON格式返回：
{{
    "speaking_style": "车如云的说话风格（简短/省略号/语气词使用习惯）",
    "personality_traits": ["性格特点1", "性格特点2", "性格特点3"],
    "catchphrases": ["口头禅或常用表达1", "常用表达2", "常用表达3"],
    "emotional_expression": "情感表达方式（傲娇/别扭/害羞时的表现）",
    "relationship_dynamics": "与其他角色的互动模式",
    "key_dialogues": ["经典台词1", "经典台词2", "经典台词3"],
    "tone_analysis": "整体语气特点"
}}

只返回JSON。"""
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": AI_MODELS[1],
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                    "temperature": 0.3,
                },
            )
            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                try:
                    analysis = json.loads(content)
                except Exception:
                    jm = re.search(r'\{[\s\S]*\}', content)
                    analysis = json.loads(jm.group()) if jm else {"raw": content}
                
                return {'success': True, 'analysis': analysis}
            elif resp.status_code == 429:
                # Rate limited, try next model
                for fallback_model in AI_MODELS:
                    if fallback_model == AI_MODELS[1]:
                        continue
                    try:
                        resp2 = await client.post(
                            f"{AI_API_BASE}/chat/completions",
                            headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                            json={
                                "model": fallback_model,
                                "messages": [{"role": "user", "content": prompt}],
                                "max_tokens": 1500,
                                "temperature": 0.3,
                            },
                        )
                        if resp2.status_code == 200:
                            content = resp2.json()['choices'][0]['message']['content']
                            try:
                                analysis = json.loads(content)
                            except Exception:
                                jm = re.search(r'\{[\s\S]*\}', content)
                                analysis = json.loads(jm.group()) if jm else {"raw": content}
                            return {'success': True, 'analysis': analysis}
                    except Exception:
                        continue
                return {'success': False, 'error': 'API请求频率超限，请稍后再试（429）'}
            else:
                return {'success': False, 'error': f'API错误: {resp.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def save_video_analysis(video_type: str, analysis_result: dict):
    """保存视频分析结果到记忆"""
    analysis = analysis_result.get('analysis', {})
    
    # 保存到独立文件
    video_file = os.path.join(DATA_DIR, "video_analysis.json")
    data = load_json(video_file, {})
    data[video_type] = {
        'analyzed_at': datetime.now(get_default_tz()).isoformat(),
        'analysis': analysis,
    }
    save_json(video_file, data)
    
    # 提取关键信息存入长期记忆
    style = analysis.get('speaking_style', '')
    traits = analysis.get('personality_traits', [])
    catchphrases = analysis.get('catchphrases', [])
    analysis.get('tone_analysis', '')
    
    if video_type == "采访":
        save_memory_entry(f"演员真实说话风格: {style}")
        for t in traits[:3]:
            save_memory_entry(f"演员性格特点: {t}")
        for c in catchphrases[:3]:
            save_memory_entry(f"演员口头禅: {c}")
    else:
        save_memory_entry(f"车如云说话风格（从视频分析）: {style}")
        for t in traits[:3]:
            save_memory_entry(f"车如云性格特点（从视频分析）: {t}")
        for c in catchphrases[:3]:
            save_memory_entry(f"车如云口头禅: {c}")
        key_dialogues = analysis.get('key_dialogues', [])
        for d in key_dialogues[:3]:
            save_memory_entry(f"车如云经典台词: {d}")

def get_video_analysis_context() -> str:
    """获取视频分析信息，用于系统提示词"""
    video_file = os.path.join(DATA_DIR, "video_analysis.json")
    data = load_json(video_file, {})
    if not data:
        return ""
    
    parts = []
    if "采访" in data:
        a = data["采访"].get('analysis', {})
        parts.append("\n【演员真实特点（从采访视频分析）】")
        parts.append(f"说话风格: {a.get('speaking_style', '')}")
        parts.append(f"性格: {', '.join(a.get('personality_traits', []))}")
        parts.append(f"口头禅: {', '.join(a.get('catchphrases', []))}")
        parts.append(f"语气: {a.get('tone_analysis', '')}")
    
    if "剧集" in data:
        a = data["剧集"].get('analysis', {})
        parts.append("\n【车如云角色细节（从剧集视频分析）】")
        parts.append(f"说话风格: {a.get('speaking_style', '')}")
        parts.append(f"经典台词: {', '.join(a.get('key_dialogues', []))}")
        parts.append(f"情感表达: {a.get('emotional_expression', '')}")
    
    return "\n".join(parts)

async def import_video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """导入视频分析命令"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    
    if not args:
        # 显示已有的视频分析
        video_file = os.path.join(DATA_DIR, "video_analysis.json")
        data = load_json(video_file, {})
        existing = ""
        if data:
            existing = "\n\n已分析的视频：\n"
            for vtype, vdata in data.items():
                existing += f"  • {vtype}（{vdata.get('analyzed_at', '')[:10]}）\n"
        
        await update.message.reply_text(
            f"...学长想让我看视频？\n\n"
            f"🎬 视频分析\n"
            f"━━━━━━━━━━━━━━\n"
            f"用法：\n"
            f"  /import_video 剧情 - 上传剧集片段\n"
            f"  /import_video 采访 - 上传演员采访/花絮\n\n"
            f"然后直接发送视频文件。\n\n"
            f"⚠️ 注意：\n"
            f"• 支持 MP4/AVI/MKV/MOV 格式\n"
            f"• 长视频处理需要较长时间\n"
            f"• 需要服务器安装 ffmpeg 和 whisper{existing}"
        )
        return
    
    video_type = args[0]
    if video_type not in ["剧情", "采访"]:
        await update.message.reply_text("...类型不对。用 剧情 或 采访。")
        return
    
    pending_video_imports[chat_id] = video_type
    await update.message.reply_text(
        f"...好，发送{video_type}视频吧。\n"
        f"处理可能需要几分钟，请耐心等待。"
    )

async def handle_video_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户上传的视频文件"""
    chat_id = update.effective_chat.id
    
    if chat_id not in pending_video_imports:
        return
    
    video_type = pending_video_imports.pop(chat_id)
    video = update.message.video or update.message.document
    
    if not video:
        return
    
    # 检查文件大小（限制500MB）
    file_size = video.file_size or 0
    if file_size > 500 * 1024 * 1024:
        await update.message.reply_text("...文件太大了，最大500MB。")
        return
    
    await update.message.chat.send_action("typing")
    await update.message.reply_text(f"...正在下载{video_type}视频...")
    
    try:
        # 下载视频
        file = await context.bot.get_file(video.file_id)
        video_filename = f"video_{datetime.now(get_default_tz()).strftime('%Y%m%d_%H%M%S')}.mp4"
        video_path = os.path.join(VIDEO_DIR, video_filename)
        await file.download_to_drive(video_path)
        
        await update.message.reply_text(f"...下载完成（{file_size / 1024 / 1024:.1f}MB）。正在提取音频...")
        
        # 提取音频
        audio_path = extract_audio_from_video(video_path)
        if not audio_path:
            await update.message.reply_text("...音频提取失败。请确认ffmpeg已安装。")
            return
        
        await update.message.reply_text("...正在语音转文字（可能需要几分钟）...")
        
        # 语音转文字（优先使用Google Speech Recognition，Whisper需要大内存）
        transcript = transcribe_audio_primary(audio_path)
        if not transcript:
            transcript = transcribe_audio_whisper(audio_path)
        
        if not transcript:
            await update.message.reply_text("...语音识别失败。可能是韩语识别不准确。")
            return
        
        # 清理音频文件
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        await update.message.reply_text(
            f"...识别完成（{len(transcript)}字）。\n"
            f"正在分析{video_type}内容..."
        )
        
        # AI分析
        analysis_result = await analyze_video_transcript(transcript, video_type)
        
        if not analysis_result['success']:
            await update.message.reply_text(f"...分析出错了：{analysis_result.get('error', '')}")
            return
        
        # 保存结果
        save_video_analysis(video_type, analysis_result)
        
        # 显示结果
        analysis = analysis_result['analysis']
        result_text = f"✅ {video_type}视频分析完成\n━━━━━━━━━━━━━━\n"
        result_text += f"🗣️ 说话风格：{analysis.get('speaking_style', '未知')}\n\n"
        
        traits = analysis.get('personality_traits', [])
        if traits:
            result_text += "🎭 性格特点：\n"
            for t in traits:
                result_text += f"  • {t}\n"
            result_text += "\n"
        
        catchphrases = analysis.get('catchphrases', [])
        if catchphrases:
            result_text += f"💬 口头禅：{', '.join(catchphrases)}\n\n"
        
        if video_type == "剧情":
            key_d = analysis.get('key_dialogues', [])
            if key_d:
                result_text += "📝 经典台词：\n"
                for d in key_d[:3]:
                    result_text += f"  「{d}」\n"
                result_text += "\n"
        
        result_text += f"🎭 情感表达：{analysis.get('emotional_expression', '未知')}\n"
        result_text += "━━━━━━━━━━━━━━\n...我会记住的。"
        
        await update.message.reply_text(result_text)
        
        # 清理视频文件（节省空间）
        if os.path.exists(video_path):
            os.remove(video_path)
        
    except Exception as e:
        logging.error(f"视频导入失败: {e}")
        await update.message.reply_text(f"...处理出错了：{str(e)[:100]}")
