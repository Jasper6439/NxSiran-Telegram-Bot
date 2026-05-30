"""
TTS 服务模块 - 本地角色声音模拟
=====================================
支持对接本地 GPT-SoVITS / CosyVoice 推理服务
实现角色专属声音的实时转换

用法:
    from services.tts_service import TTSService, text_to_speech
    
    tts = TTSService()
    audio_path = await text_to_speech("你好呀~", character_id="chayewoon")
"""

import os
import logging
import tempfile
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

import aiohttp

from system.config import CHAT_TOPIC_THREAD_ID, DATA_DIR

logger = logging.getLogger(__name__)

# ============================================================
# 配置区域 - 通过环境变量或 config.py 配置
# ============================================================

# 本地 TTS 服务地址（GPT-SoVITS / CosyVoice）
LOCAL_TTS_URL = os.environ.get(
    "LOCAL_TTS_URL", 
    "http://127.0.0.1:9880"
)

# TTS 服务类型: "sovits" | "cosyvoice" | "edge"
TTS_BACKEND = os.environ.get("TTS_BACKEND", "sovits")

# 音频缓存目录
TTS_CACHE_DIR = os.path.join(DATA_DIR, "tts_cache")
os.makedirs(TTS_CACHE_DIR, exist_ok=True)

# 单次合成最大字符数（防止超长文本）
MAX_TEXT_LENGTH = 300

# 请求超时（秒）
TTS_TIMEOUT = 30


class TTSService:
    """
    本地 TTS 服务封装
    
    支持多种后端:
    - GPT-SoVITS: 高质量音色克隆，需本地部署
    - CosyVoice: 阿里开源 TTS，支持情感控制
    - Edge TTS: 微软免费云端服务（fallback）
    """
    
    def __init__(self, backend: str = None, base_url: str = None):
        self.backend = backend or TTS_BACKEND
        self.base_url = base_url or LOCAL_TTS_URL
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=TTS_TIMEOUT)
            )
        return self._session
    
    async def synthesize(
        self, 
        text: str, 
        character_id: str = "chayewoon",
        emotion: str = "neutral",
        output_format: str = "wav"
    ) -> Optional[str]:
        """
        将文本合成为语音文件
        
        Args:
            text: 要合成的文本
            character_id: 角色 ID（用于选择音色）
            emotion: 情感标签（happy, sad, neutral, angry 等）
            output_format: 输出格式（wav, mp3, ogg）
        
        Returns:
            音频文件路径，失败返回 None
        """
        if not text or not text.strip():
            return None
        
        # 截断过长文本
        text = text[:MAX_TEXT_LENGTH]
        
        # 根据后端选择合成方法
        if self.backend == "sovits":
            return await self._synthesize_sovits(text, character_id, output_format)
        elif self.backend == "cosyvoice":
            return await self._synthesize_cosyvoice(text, character_id, emotion, output_format)
        else:
            # fallback 到 Edge TTS
            return await self._synthesize_edge(text, character_id, output_format)
    
    async def _synthesize_sovits(
        self, 
        text: str, 
        character_id: str,
        output_format: str
    ) -> Optional[str]:
        """GPT-SoVITS 后端合成"""
        try:
            session = await self._get_session()
            
            # GPT-SoVITS API 格式
            payload = {
                "text": text,
                "text_language": "zh",
                "character": character_id,  # 音色选择
                "top_k": 5,
                "top_p": 1.0,
                "temperature": 1.0,
                "speed": 1.0,
            }
            
            async with session.post(
                f"{self.base_url}/tts",
                json=payload
            ) as resp:
                if resp.status == 200:
                    audio_data = await resp.read()
                    
                    # 保存到缓存
                    output_path = self._get_cache_path(character_id, output_format)
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    
                    logger.info(f"[TTS] SoVITS 合成成功: {output_path}")
                    return output_path
                else:
                    error_text = await resp.text()
                    logger.error(f"[TTS] SoVITS API 错误 {resp.status}: {error_text}")
                    return None
                    
        except aiohttp.ClientError as e:
            logger.error(f"[TTS] SoVITS 连接失败: {e}")
            # 尝试 fallback 到 Edge TTS
            return await self._synthesize_edge(text, character_id, output_format)
        except Exception as e:
            logger.error(f"[TTS] SoVITS 合成异常: {e}")
            return None
    
    async def _synthesize_cosyvoice(
        self, 
        text: str, 
        character_id: str,
        emotion: str,
        output_format: str
    ) -> Optional[str]:
        """CosyVoice 后端合成（支持情感控制）"""
        try:
            session = await self._get_session()
            
            # CosyVoice API 格式
            payload = {
                "text": text,
                "speaker": character_id,
                "emotion": emotion,  # happy, sad, neutral, angry, etc.
                "format": output_format,
            }
            
            async with session.post(
                f"{self.base_url}/api/tts",
                json=payload
            ) as resp:
                if resp.status == 200:
                    audio_data = await resp.read()
                    
                    output_path = self._get_cache_path(character_id, output_format)
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    
                    logger.info(f"[TTS] CosyVoice 合成成功: {output_path}")
                    return output_path
                else:
                    error_text = await resp.text()
                    logger.error(f"[TTS] CosyVoice API 错误 {resp.status}: {error_text}")
                    return None
                    
        except aiohttp.ClientError as e:
            logger.error(f"[TTS] CosyVoice 连接失败: {e}")
            return await self._synthesize_edge(text, character_id, output_format)
        except Exception as e:
            logger.error(f"[TTS] CosyVoice 合成异常: {e}")
            return None
    
    async def _synthesize_edge(
        self, 
        text: str, 
        character_id: str,
        output_format: str
    ) -> Optional[str]:
        """Edge TTS fallback（微软免费云端服务）"""
        try:
            import edge_tts
            
            # 根据角色选择音色
            voice_map = {
                "chayewoon": "zh-CN-XiaoyiNeural",  # 可爱女声
                "default": "zh-CN-XiaoxiaoNeural",  # 温柔女声
            }
            voice = voice_map.get(character_id, voice_map["default"])
            
            # 创建临时文件
            output_path = self._get_cache_path(character_id, "ogg")
            
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            
            logger.info(f"[TTS] Edge TTS 合成成功: {output_path}")
            return output_path
            
        except ImportError:
            logger.warning("[TTS] edge-tts 未安装，运行: pip install edge-tts")
            return None
        except Exception as e:
            logger.error(f"[TTS] Edge TTS 合成失败: {e}")
            return None
    
    def _get_cache_path(self, character_id: str, format: str) -> str:
        """生成缓存文件路径"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"tts_{character_id}_{timestamp}.{format}"
        return os.path.join(TTS_CACHE_DIR, filename)
    
    async def close(self):
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    @staticmethod
    def cleanup_cache(max_age_hours: int = 24):
        """清理过期的缓存音频文件"""
        import time
        now = time.time()
        try:
            for f in os.listdir(TTS_CACHE_DIR):
                fpath = os.path.join(TTS_CACHE_DIR, f)
                if os.path.isfile(fpath):
                    if now - os.path.getmtime(fpath) > max_age_hours * 3600:
                        os.unlink(fpath)
                        logger.debug(f"[TTS] 清理缓存: {f}")
        except Exception as e:
            logger.error(f"[TTS] 清理缓存失败: {e}")


# ============================================================
# 便捷函数
# ============================================================

# 全局 TTS 服务实例
_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    """获取全局 TTS 服务实例"""
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service


async def text_to_speech(
    text: str, 
    character_id: str = "chayewoon",
    emotion: str = "neutral"
) -> Optional[str]:
    """
    将文本转换为语音（便捷函数）
    
    Args:
        text: 要合成的文本
        character_id: 角色 ID
        emotion: 情感标签
    
    Returns:
        音频文件路径
    """
    service = get_tts_service()
    return await service.synthesize(text, character_id, emotion)


# ============================================================
# FastAPI 集成
# ============================================================

async def send_voice_to_telegram(
    bot,
    chat_id: int,
    text: str,
    character_id: str = "chayewoon"
) -> bool:
    """
    将文本转换为语音并发送到 Telegram
    
    Args:
        bot: Telegram Bot 实例
        chat_id: 聊天 ID
        text: 要转换的文本
        character_id: 角色 ID
    
    Returns:
        是否发送成功
    """
    audio_path = await text_to_speech(text, character_id)
    
    if not audio_path or not os.path.exists(audio_path):
        logger.warning(f"[TTS] 语音文件不存在: {audio_path}")
        return False
    
    try:
        await bot.send_chat_action(chat_id=chat_id, action="record_voice")
        
        with open(audio_path, "rb") as f:
            await bot.send_voice(message_thread_id=CHAT_TOPIC_THREAD_ID,
                chat_id=chat_id,
                voice=f,
                caption="🎵"
            )
        
        logger.info(f"[TTS] 语音发送成功: chat_id={chat_id}")
        return True
        
    except Exception as e:
        logger.error(f"[TTS] 发送语音失败: {e}")
        return False


# ============================================================
# 测试
# ============================================================

async def test_tts_service():
    """测试 TTS 服务"""
    tts = TTSService()
    
    print(f"TTS 后端: {tts.backend}")
    print(f"TTS URL: {tts.base_url}")
    
    result = await tts.synthesize(
        "你好，我是车如云，很高兴认识你~",
        character_id="chayewoon",
        emotion="happy"
    )
    
    if result:
        print(f"✅ 合成成功: {result}")
        print(f"   文件大小: {os.path.getsize(result)} bytes")
    else:
        print("❌ 合成失败")
    
    await tts.close()


if __name__ == "__main__":
    asyncio.run(test_tts_service())
