"""
增强版视频导入模块
v1.6.4.2 — 支持字幕提取、角色学习整合

功能：
1. 视频 → 音频提取（ffmpeg）
2. 音频 → 语音转文字（Whisper / Google Speech）
3. 视频 → 字幕提取（embedded subtitle / OCR）
4. 转录内容 → AI 分析 → 更新 persona.md
5. 视频声音 → 保存为角色声音样本

与 character_learning.py 整合，实现：
视频上传 → 提取音频/字幕 → AI 分析 → 更新角色设定
"""

import os
import json
import logging
import shutil
import tempfile
from datetime import datetime
from typing import Dict, List, Optional

from system.config import DATA_DIR, VIDEO_DIR, AI_API_BASE, AI_API_KEY, AI_MODELS
from system.config import get_default_tz

logger = logging.getLogger(__name__)


class VideoImporter:
    """视频导入处理器"""

    def __init__(self, character_id: str = 'chayewoon'):
        self.character_id = character_id
        self.video_dir = VIDEO_DIR
        os.makedirs(self.video_dir, exist_ok=True)

    # ============================================================
    # 1. 音频提取
    # ============================================================

    def extract_audio(self, video_path: str) -> str:
        """从视频提取音频"""
        audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
        cmd = f"ffmpeg -i '{video_path}' -vn -acodec libmp3lame -q:a 2 -ar 16000 -ac 1 '{audio_path}' -y 2>/dev/null"
        os.system(cmd)
        return audio_path if os.path.exists(audio_path) else ""

    # ============================================================
    # 2. 语音转文字
    # ============================================================

    def transcribe_whisper(self, audio_path: str, language: str = "ko") -> str:
        """使用 OpenAI Whisper 转录"""
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(audio_path, language=language, verbose=False)
            return result.get("text", "")
        except ImportError:
            logger.warning("Whisper 未安装")
            return ""
        except Exception as e:
            logger.error(f"Whisper 转录失败: {e}")
            return ""

    def transcribe_google(self, audio_path: str, language: str = "ko-KR") -> str:
        """使用 Google Speech Recognition（备选）"""
        try:
            import speech_recognition as sr
            from pydub import AudioSegment

            recognizer = sr.Recognizer()
            audio = AudioSegment.from_mp3(audio_path)

            # 分段处理（每段30秒）
            chunk_ms = 30000
            chunks = [audio[i:i+chunk_ms] for i in range(0, len(audio), chunk_ms)]

            full_text = []
            for i, chunk in enumerate(chunks):
                chunk_path = f"/tmp/chunk_{i}.wav"
                chunk.export(chunk_path, format="wav")

                with sr.AudioFile(chunk_path) as source:
                    audio_data = recognizer.record(source)

                try:
                    text = recognizer.recognize_google(audio_data, language=language)
                    full_text.append(text)
                except Exception:
                    full_text.append("[无法识别]")

                os.remove(chunk_path)

            return " ".join(full_text)
        except Exception as e:
            logger.error(f"Google 语音识别失败: {e}")
            return ""

    # ============================================================
    # 3. 字幕提取
    # ============================================================

    def extract_subtitles(self, video_path: str) -> str:
        """提取内嵌字幕（如果有）"""
        try:
            # 使用 ffmpeg 提取字幕流
            subtitle_path = video_path.rsplit('.', 1)[0] + '.srt'
            cmd = f"ffmpeg -i '{video_path}' -map 0:s:0 '{subtitle_path}' -y 2>/dev/null"
            os.system(cmd)

            if os.path.exists(subtitle_path) and os.path.getsize(subtitle_path) > 0:
                with open(subtitle_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                # 清理 SRT 格式，只保留文本
                return self._clean_srt(content)

            return ""
        except Exception as e:
            logger.error(f"字幕提取失败: {e}")
            return ""

    def _clean_srt(self, srt_content: str) -> str:
        """清理 SRT 字幕格式，只保留文本"""
        import re
        # 移除时间码和序号
        lines = []
        for line in srt_content.split('\n'):
            line = line.strip()
            # 跳过空行、序号、时间码
            if not line or line.isdigit():
                continue
            if re.match(r'\d{2}:\d{2}:\d{2}', line):
                continue
            lines.append(line)
        return ' '.join(lines)

    # ============================================================
    # 4. AI 分析转录内容
    # ============================================================

    async def analyze_content(self, transcript: str, content_type: str = "剧集") -> Dict:
        """AI 分析视频内容，提取角色特点"""
        if not transcript or len(transcript) < 50:
            return {'success': False, 'error': '转录内容太短'}

        sample = transcript[:4000] if len(transcript) > 4000 else transcript

        prompts = {
            "采访": f"""分析以下演员采访/花絮的转录内容，提取演员的真实说话风格和性格特点。

转录内容：
{sample}

请用JSON格式返回：
{{
    "speaking_style": "说话风格描述",
    "personality_traits": ["性格特点1", "性格特点2"],
    "catchphrases": ["口头禅1", "口头禅2"],
    "emotional_expression": "情感表达方式",
    "unique_habits": "独特的说话习惯",
    "tone_analysis": "整体语气特点"
}}""",
            "剧集": f"""分析以下韩剧片段的转录内容，提取车如云这个角色的说话风格和性格特点。

转录内容：
{sample}

请用JSON格式返回：
{{
    "speaking_style": "车如云的说话风格",
    "personality_traits": ["性格特点1", "性格特点2", "性格特点3"],
    "catchphrases": ["口头禅1", "口头禅2", "口头禅3"],
    "emotional_expression": "情感表达方式",
    "relationship_dynamics": "与其他角色的互动模式",
    "key_dialogues": ["经典台词1", "经典台词2", "经典台词3"],
    "tone_analysis": "整体语气特点"
}}""",
            "纪录片": f"""分析以下纪录片/幕后花絮的转录内容。

转录内容：
{sample}

请用JSON格式返回：
{{
    "speaking_style": "说话风格",
    "personality_traits": ["性格特点1", "性格特点2"],
    "behind_the_scenes": "幕后花絮中的有趣信息",
    "tone_analysis": "整体语气"
}}"""
        }

        prompt = prompts.get(content_type, prompts["剧集"])

        try:
            from characters.ai_client import _get_http_client
            client = _get_http_client()
            resp = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}"},
                json={
                    "model": AI_MODELS[1],
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                    "temperature": 0.3,
                }
            )

            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                try:
                    analysis = json.loads(content)
                except json.JSONDecodeError:
                    import re
                    match = re.search(r'\{[\s\S]*\}', content)
                    analysis = json.loads(match.group()) if match else {"raw": content}

                return {'success': True, 'analysis': analysis}
            else:
                return {'success': False, 'error': f'API 错误: {resp.status_code}'}

        except Exception as e:
            logger.error(f"AI 分析失败: {e}")
            return {'success': False, 'error': str(e)}

    # ============================================================
    # 5. 保存声音样本
    # ============================================================

    def save_voice_sample(self, audio_path: str, label: str = "视频提取") -> Dict:
        """将视频音频保存为角色声音样本"""
        from characters.voice_manager import get_voice_manager

        vm = get_voice_manager(self.character_id)
        return vm.save_voice_sample(audio_path, label=label, 
                                    description=f"从视频提取于 {datetime.now(get_default_tz()).strftime('%Y-%m-%d')}")

    # ============================================================
    # 6. 更新角色 persona
    # ============================================================

    async def update_persona(self, analysis: Dict, source: str = "视频分析"):
        """将分析结果更新到角色 persona.md"""
        from characters.character_learning import get_learning

        learning = get_learning(self.character_id)

        # 构建学习内容
        analysis_text = json.dumps(analysis, ensure_ascii=False, indent=2)
        facts = [f"【{source}】\n{analysis_text}"]

        await learning._update_persona_learned(facts)

    # ============================================================
    # 7. 完整处理流程
    # ============================================================

    async def process_video(self, video_path: str, content_type: str = "剧集",
                          save_voice: bool = True, update_persona: bool = True) -> Dict:
        """完整视频处理流程

        Args:
            video_path: 视频文件路径
            content_type: 内容类型（采访/剧集/纪录片）
            save_voice: 是否保存声音样本
            update_persona: 是否更新角色设定

        Returns:
            处理结果
        """
        result = {
            "video_path": video_path,
            "content_type": content_type,
            "stages": {},
        }

        # Stage 1: 提取音频
        logger.info(f"[Video] 提取音频: {video_path}")
        audio_path = self.extract_audio(video_path)
        if not audio_path:
            result["stages"]["extract_audio"] = {"success": False, "error": "音频提取失败"}
            return result

        result["stages"]["extract_audio"] = {"success": True, "audio_path": audio_path}

        # Stage 2: 提取字幕
        logger.info(f"[Video] 提取字幕")
        subtitles = self.extract_subtitles(video_path)
        if subtitles:
            result["stages"]["extract_subtitles"] = {"success": True, "length": len(subtitles)}
        else:
            result["stages"]["extract_subtitles"] = {"success": False, "error": "无内嵌字幕"}

        # Stage 3: 语音转文字
        logger.info(f"[Video] 语音转文字")
        transcript = ""
        if subtitles:
            transcript = subtitles
            result["stages"]["transcribe"] = {"success": True, "source": "subtitles", "length": len(transcript)}
        else:
            transcript = self.transcribe_whisper(audio_path)
            if not transcript:
                transcript = self.transcribe_google(audio_path)
            if transcript:
                result["stages"]["transcribe"] = {"success": True, "source": "whisper/google", "length": len(transcript)}
            else:
                result["stages"]["transcribe"] = {"success": False, "error": "语音识别失败"}
                return result

        # Stage 4: AI 分析
        logger.info(f"[Video] AI 分析内容")
        analysis_result = await self.analyze_content(transcript, content_type)
        result["stages"]["analyze"] = analysis_result

        if not analysis_result.get('success'):
            return result

        # Stage 5: 保存声音样本
        if save_voice:
            logger.info(f"[Video] 保存声音样本")
            voice_result = self.save_voice_sample(audio_path, label=f"{content_type}声音")
            result["stages"]["save_voice"] = voice_result

        # Stage 6: 更新角色设定
        if update_persona and analysis_result.get('success'):
            logger.info(f"[Video] 更新角色设定")
            await self.update_persona(analysis_result['analysis'], source=f"{content_type}视频分析")
            result["stages"]["update_persona"] = {"success": True}

        # 清理临时音频文件
        if os.path.exists(audio_path):
            os.remove(audio_path)

        result["success"] = True
        return result


# ===== 便捷函数 =====

_importers: Dict[str, VideoImporter] = {}


def get_video_importer(character_id: str = 'chayewoon') -> VideoImporter:
    """获取视频导入器"""
    if character_id not in _importers:
        _importers[character_id] = VideoImporter(character_id)
    return _importers[character_id]


async def import_video_for_learning(video_path: str, character_id: str = 'chayewoon',
                                    content_type: str = "剧集") -> Dict:
    """导入视频进行角色学习"""
    importer = get_video_importer(character_id)
    return await importer.process_video(video_path, content_type)
