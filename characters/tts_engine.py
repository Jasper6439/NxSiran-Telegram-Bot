"""
车如云 Bot - TTS 语音合成引擎
=============================
支持三种后端，按优先级自动切换：
  1. GPT-SoVITS (真人音色克隆，需外部 API)
  2. Edge TTS (微软免费，无需 GPU)
  3. Fish Speech (免费额度，高保真克隆)

用法：
  from tts_engine import TTSEngine
  tts = TTSEngine()
  audio_path = await tts.synthesize("你好呀~")
"""

import logging
import os
import tempfile
from typing import Optional

from system.config import DATA_DIR

logger = logging.getLogger(__name__)

# ============================================================
# 配置区域 - 根据实际情况修改
# ============================================================

# --- Edge TTS 配置 ---
EDGE_TTS_VOICE = "zh-CN-XiaoyiNeural"
# 可选音色:
#   zh-CN-XiaoxiaoNeural  - 温柔女声
#   zh-CN-YunxiNeural    - 活泼男声
#   zh-CN-YunjianNeural   - 成熟男声
#   zh-CN-XiaoyiNeural    - 可爱女声 (默认)
#   zh-CN-XiaochenNeural  - 知性女声
#   zh-CN-YunyangNeural   - 新闻男声

# --- GPT-SoVITS 配置 ---
SOVITS_API_URL = ""  # 例如: "https://xxxx.ngrok-free.app/api/tts"
# 留空则跳过 SoVITS，直接用 Edge TTS

# --- Fish Speech 配置 ---
FISH_API_KEY = ""       # Fish Audio API Key
FISH_REFERENCE_ID = ""  # 克隆音色 ID
# 留空则跳过 Fish Speech

# --- 通用配置 ---
TTS_TEMP_DIR = os.path.join(DATA_DIR, "tts_cache")  # 音频缓存目录
MAX_TEXT_LENGTH = 300  # 单次合成最大字符数
DEFAULT_BACKEND = "auto"  # "auto" | "edge" | "sovits" | "fish"


# ============================================================
# Edge TTS 后端
# ============================================================

class EdgeTTSBackend:
    """微软 Edge TTS - 完全免费，无需 GPU"""

    name = "edge"
    _available = None

    @classmethod
    async def is_available(cls) -> bool:
        if cls._available is None:
            try:
                import edge_tts  # noqa: F401
                cls._available = True
            except ImportError:
                cls._available = False
                logger.warning("edge-tts 未安装，运行: pip install edge-tts")
        return cls._available

    @classmethod
    async def synthesize(cls, text: str, output_path: str) -> bool:
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
            await communicate.save(output_path)
            return True
        except Exception as e:
            logger.error(f"Edge TTS 合成失败: {e}")
            return False


# ============================================================
# GPT-SoVITS 后端
# ============================================================

class SoVITSBackend:
    """GPT-SoVITS - 真人音色克隆，需外部 API 服务"""

    name = "sovits"

    @classmethod
    async def is_available(cls) -> bool:
        return bool(SOVITS_API_URL)

    @classmethod
    async def synthesize(cls, text: str, output_path: str) -> bool:
        if not SOVITS_API_URL:
            return False
        try:
            import aiohttp
            payload = {
                "text": text,
                "text_language": "zh",
                "top_k": 5,
                "top_p": 1,
                "temperature": 1,
                "speed": 1,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    SOVITS_API_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        audio_data = await resp.read()
                        with open(output_path, "wb") as f:
                            f.write(audio_data)
                        return True
                    else:
                        logger.error(f"SoVITS API 返回 {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"SoVITS 合成失败: {e}")
            return False


# ============================================================
# Fish Speech 后端
# ============================================================

class FishSpeechBackend:
    """Fish Speech - 高保真音色克隆，云端 API"""

    name = "fish"

    @classmethod
    async def is_available(cls) -> bool:
        return bool(FISH_API_KEY and FISH_REFERENCE_ID)

    @classmethod
    async def synthesize(cls, text: str, output_path: str) -> bool:
        if not FISH_API_KEY or not FISH_REFERENCE_ID:
            return False
        try:
            import aiohttp
            payload = {
                "text": text,
                "reference_id": FISH_REFERENCE_ID,
                "format": "mp3",
            }
            headers = {"Authorization": f"Bearer {FISH_API_KEY}"}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.fish.audio/v1/tts",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        audio_data = await resp.read()
                        with open(output_path, "wb") as f:
                            f.write(audio_data)
                        return True
                    else:
                        logger.error(f"Fish API 返回 {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Fish Speech 合成失败: {e}")
            return False


# ============================================================
# 统一 TTS 引擎
# ============================================================

class TTSEngine:
    """
    统一 TTS 引擎，自动选择可用后端

    用法:
        tts = TTSEngine()
        # 合成语音
        path = await tts.synthesize("你好呀~")
        # 获取当前后端名称
        print(tts.current_backend)
    """

    # 后端优先级
    BACKEND_PRIORITY = ["sovits", "fish", "edge"]

    def __init__(self, backend: str = DEFAULT_BACKEND):
        self._backends = {
            "edge": EdgeTTSBackend,
            "sovits": SoVITSBackend,
            "fish": FishSpeechBackend,
        }
        self._forced_backend = backend if backend != "auto" else None
        self._current_backend: Optional[str] = "检测中..."
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        os.makedirs(TTS_TEMP_DIR, exist_ok=True)

    async def _get_available_backends(self):
        """检测可用后端"""
        available = []
        for name in self.BACKEND_PRIORITY:
            backend_cls = self._backends[name]
            if await backend_cls.is_available():
                available.append(name)
        return available

    async def synthesize(self, text: str) -> Optional[str]:
        """
        将文本合成为语音文件

        Args:
            text: 要合成的文本

        Returns:
            音频文件路径，失败返回 None
        """
        if not text or not text.strip():
            return None

        # 截断过长文本
        text = text[:MAX_TEXT_LENGTH]

        # 创建临时文件
        tmp = tempfile.NamedTemporaryFile(
            suffix=".ogg",
            dir=TTS_TEMP_DIR,
            delete=False
        )
        tmp_path = tmp.name
        tmp.close()

        try:
            # 确定使用哪个后端
            if self._forced_backend:
                backends_to_try = [self._forced_backend]
            else:
                backends_to_try = await self._get_available_backends()

            for backend_name in backends_to_try:
                backend_cls = self._backends.get(backend_name)
                if not backend_cls:
                    continue

                logger.info(f"TTS 尝试后端: {backend_name}")
                success = await backend_cls.synthesize(text, tmp_path)
                if success and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                    self._current_backend = backend_name
                    logger.info(f"TTS 成功: {backend_name}, 文件: {tmp_path}")
                    return tmp_path

            # 所有后端都失败
            logger.error("所有 TTS 后端均失败")
            self._safe_delete(tmp_path)
            return None

        except Exception as e:
            logger.error(f"TTS 合成异常: {e}")
            self._safe_delete(tmp_path)
            return None

    @property
    def current_backend(self) -> str:
        return self._current_backend or "none"

    @staticmethod
    def _safe_delete(path: str):
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass

    @staticmethod
    def cleanup_old_files(max_age_hours: int = 24):
        """清理过期的缓存音频文件"""
        import time
        now = time.time()
        try:
            for f in os.listdir(TTS_TEMP_DIR):
                fpath = os.path.join(TTS_TEMP_DIR, f)
                if os.path.isfile(fpath):
                    if now - os.path.getmtime(fpath) > max_age_hours * 3600:
                        os.unlink(fpath)
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")


# ============================================================
# 快速测试
# ============================================================

async def test_tts():
    """测试 TTS 引擎"""
    tts = TTSEngine()
    print(f"当前后端: {tts.current_backend}")

    result = await tts.synthesize("你好，我是车如云，很高兴认识你~")
    if result:
        print(f"合成成功: {result}")
        print(f"文件大小: {os.path.getsize(result)} bytes")
    else:
        print("合成失败")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_tts())
