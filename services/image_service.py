"""
图像生成服务模块 — SDXL 1.0 LoRA 专属生图路由池
=====================================
多平台兜底生图，保证角色一致性。

路由策略:
1. Hugging Face Spaces (主力，挂载专属 LoRA)
2. SiliconFlow SDXL (兜底，LoRA 未生效)
3. OpenRouter SD3 (备选，LoRA 未生效)

用法:
    from services.image_service import ImageGenerationService, get_image_service

    svc = get_image_service()
    image_bytes = await svc.generate(prompt)
"""

import os
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime


from characters.ai_client import _get_http_client

from system.config import CHAT_TOPIC_THREAD_ID, DATA_DIR

logger = logging.getLogger(__name__)

# ============================================================
# 配置 — 从环境变量读取
# ============================================================

# SDXL LoRA 配置
HF_SPACE_API_URL = os.environ.get("HF_SPACE_API_URL", "")
LORA_TRIGGER_WORD = os.environ.get("LORA_TRIGGER_WORD", "")
LORA_FILE_NAME = os.environ.get("LORA_FILE_NAME", "")

# API Keys
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
SILICONFLOW_API_BASE = "https://api.siliconflow.cn/v1"
SILICONFLOW_IMAGE_MODEL = os.environ.get(
    "SILICONFLOW_IMAGE_MODEL", "stabilityai/stable-diffusion-xl-base-1.0"
)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_IMAGE_MODEL = os.environ.get(
    "OPENROUTER_IMAGE_MODEL", "stabilityai/stable-diffusion-3-medium"
)

# 项目信息
PROJECT_GITHUB = "https://github.com/Jasper6439/LoveSupremacy_Universe"
PROJECT_NAME = "LoveSupremacy Universe"

# 图像缓存目录
IMAGE_CACHE_DIR = os.path.join(DATA_DIR, "generated_images")
os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)

# 超时配置
HF_SPACE_TIMEOUT = 120.0  # HuggingFace Spaces 冷启动可能很慢
IMAGE_TIMEOUT = 60.0


class ImageGenerationService:
    """
    SDXL 1.0 LoRA 专属生图路由服务

    路由策略:
    1. HuggingFace Spaces (主力，挂载 LoRA，角色一致性)
    2. SiliconFlow SDXL (兜底，LoRA 未生效)
    3. OpenRouter SD3 (备选，LoRA 未生效)
    """
    # ============================================================
    # 统一入口
    # ============================================================

    async def generate(
        self,
        prompt: str,
        width: int = 512,
        height: int = 512,
    ) -> Optional[bytes]:
        """
        多平台降级生图，返回图片二进制流

        Args:
            prompt: 图像提示词
            width: 图片宽度
            height: 图片高度

        Returns:
            图片二进制流 (bytes)，全部失败返回 None
        """
        routes = [
            ("hf_space", self._generate_hf_space),
            ("siliconflow", self._generate_siliconflow),
            ("openrouter", self._generate_openrouter),
        ]

        last_error = None
        for source, handler in routes:
            try:
                image_bytes = await handler(prompt, width, height)
                if image_bytes:
                    logger.info(f"[ImageGen] ✅ 成功调用 {source}")
                    return image_bytes
            except Exception as e:
                last_error = e
                logger.warning(f"[ImageGen] ⚠️ {source} 失败: {e}")

        logger.error(f"[ImageGen] ❌ 所有生图路由均失败，最后错误: {last_error}")
        return None

    async def generate_and_save(
        self,
        prompt: str,
        width: int = 512,
        height: int = 512,
    ) -> Optional[str]:
        """
        生成图片并保存到缓存

        Returns:
            图片文件路径，失败返回 None
        """
        image_bytes = await self.generate(prompt, width, height)
        if not image_bytes:
            return None

        output_path = self._get_cache_path()
        with open(output_path, "wb") as f:
            f.write(image_bytes)

        logger.info(f"[ImageGen] 图片已保存: {output_path} ({len(image_bytes)} bytes)")
        return output_path

    # ============================================================
    # 第一策略：Hugging Face Spaces (主力，挂载 LoRA)
    # ============================================================

    def _build_lora_prompt(self, user_prompt: str) -> str:
        """
        构建 LoRA 注入的提示词

        在用户描述前强制前置 LoRA 触发词与权重。
        """
        if LORA_TRIGGER_WORD and LORA_FILE_NAME:
            # LoRA 触发词 + 权重 + 质量标签 + 用户描述
            lora_tag = f"<lora:{LORA_FILE_NAME}:1.0>"
            return f"{lora_tag}, {LORA_TRIGGER_WORD}, (best quality, masterpiece), {user_prompt}"
        return user_prompt

    async def _generate_hf_space(
        self,
        prompt: str,
        width: int,
        height: int,
    ) -> Optional[bytes]:
        """Hugging Face Spaces — 主力路由，挂载专属 LoRA"""
        if not HF_SPACE_API_URL:
            raise ValueError("HF_SPACE_API_URL 未配置")

        # 注入 LoRA
        full_prompt = self._build_lora_prompt(prompt)

        # 使用较长超时应对冷启动
        client = _get_http_client()

        payload = {
            "data": [full_prompt, width, height],
        }

        logger.info(f"[ImageGen] 调用 HF Spaces: {HF_SPACE_API_URL}")
        logger.info(f"[ImageGen] LoRA Prompt: {full_prompt[:100]}...")

        response = await client.post(
            f"{HF_SPACE_API_URL}/api/predict",
            json=payload,
        )

        if response.status_code == 429:
            raise RuntimeError("HF Spaces 限流 (429)")
        if response.status_code >= 500:
            raise RuntimeError(f"HF Spaces 服务错误 ({response.status_code})")
        response.raise_for_status()

        data = response.json()

        # 解析返回 — HF Spaces 可能返回不同格式
        image_url = None

        # 格式1: {"data": [{"url": "..."}]} 或 {"data": ["url"]}
        if "data" in data:
            data_field = data["data"]
            if isinstance(data_field, list) and len(data_field) > 0:
                first = data_field[0]
                if isinstance(first, str):
                    image_url = first
                elif isinstance(first, dict) and "url" in first:
                    image_url = first["url"]
                elif isinstance(first, dict) and "path" in first:
                    # 相对路径，拼接为完整 URL
                    image_url = f"{HF_SPACE_API_URL}/file={first['path']}"

        # 格式2: {"url": "..."}
        if not image_url and "url" in data:
            image_url = data["url"]

        if not image_url:
            logger.error(f"[ImageGen] HF Spaces 返回格式无法解析: {list(data.keys())}")
            raise ValueError("无法解析 HF Spaces 返回的图片 URL")

        # 使用 httpx 下载图片二进制流
        img_response = await client.get(image_url)
        img_response.raise_for_status()

        return img_response.content

    # ============================================================
    # 第二策略：SiliconFlow SDXL (兜底)
    # ============================================================

    async def _generate_siliconflow(
        self,
        prompt: str,
        width: int,
        height: int,
    ) -> Optional[bytes]:
        """SiliconFlow SDXL — 兜底路由（LoRA 未生效）"""
        if not SILICONFLOW_API_KEY:
            raise ValueError("SILICONFLOW_API_KEY 未配置")

        client = _get_http_client()
        payload = {
            "model": SILICONFLOW_IMAGE_MODEL,
            "prompt": prompt,
            "width": width,
            "height": height,
            "n": 1,
        }
        headers = {
            "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
            "Content-Type": "application/json",
        }

        logger.warning("[ImageGen] ⚠️ SiliconFlow 兜底 — LoRA 未生效")

        response = await client.post(
            f"{SILICONFLOW_API_BASE}/images/generations",
            json=payload,
            headers=headers,
        )

        if response.status_code == 429:
            raise RuntimeError("SiliconFlow 限流 (429)")
        response.raise_for_status()

        data = response.json()

        if "data" in data and len(data["data"]) > 0:
            image_data = data["data"][0]

            if "url" in image_data:
                img_response = await client.get(image_data["url"])
                img_response.raise_for_status()
                return img_response.content
            elif "b64_json" in image_data:
                import base64
                return base64.b64decode(image_data["b64_json"])

        raise ValueError("SiliconFlow 返回无图片数据")

    # ============================================================
    # 第三策略：OpenRouter SD3 (备选)
    # ============================================================

    async def _generate_openrouter(
        self,
        prompt: str,
        width: int,
        height: int,
    ) -> Optional[bytes]:
        """OpenRouter SD3 — 备选路由（LoRA 未生效）"""
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY 未配置")

        client = _get_http_client()
        payload = {
            "model": OPENROUTER_IMAGE_MODEL,
            "prompt": prompt,
            "width": width,
            "height": height,
            "n": 1,
        }
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": PROJECT_GITHUB,
            "X-Title": PROJECT_NAME,
        }

        logger.warning("[ImageGen] ⚠️ OpenRouter 兜底 — LoRA 未生效")

        response = await client.post(
            f"{OPENROUTER_API_BASE}/images/generations",
            json=payload,
            headers=headers,
        )

        if response.status_code == 429:
            raise RuntimeError("OpenRouter 限流 (429)")
        response.raise_for_status()

        data = response.json()

        if "data" in data and len(data["data"]) > 0:
            image_data = data["data"][0]

            if "url" in image_data:
                img_response = await client.get(image_data["url"])
                img_response.raise_for_status()
                return img_response.content
            elif "b64_json" in image_data:
                import base64
                return base64.b64decode(image_data["b64_json"])

        raise ValueError("OpenRouter 返回无图片数据")

    # ============================================================
    # 工具方法
    # ============================================================

    def _get_cache_path(self, provider: str = "img") -> str:
        """生成缓存文件路径"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"img_{provider}_{timestamp}.png"
        return os.path.join(IMAGE_CACHE_DIR, filename)


# ============================================================
# 意图检测（保留原有功能）
# ============================================================

import re

VISUAL_INTENT_KEYWORDS = [
    r"想看.*你在.*干嘛",
    r"发张.*照片",
    r"发.*自拍",
    r"让我看看.*你",
    r"看看.*样子",
    r"想看.*照片",
    r"给我.*图片",
    r"发个.*照",
    r"看看.*在干嘛",
    r"你在哪",
    r"你在干什么",
    r"想看.*表情",
]

SCENE_PROMPTS = {
    "daily_life": "A cute anime girl in casual clothes, doing daily activities at home, warm lighting, cozy atmosphere, high quality, detailed",
    "cooking": "A cute anime girl in an apron, cooking in a kitchen, delicious food on the counter, warm kitchen lighting, detailed",
    "farming": "A cute anime girl in a sun hat, working in a beautiful farm field with crops and flowers, sunny day, pastoral scenery",
    "relaxing": "A cute anime girl relaxing on a sofa, reading a book or using phone, cozy living room, soft lighting",
    "outdoor": "A cute anime girl walking in a beautiful park or garden, cherry blossoms, spring atmosphere, detailed background",
    "selfie": "A cute anime girl taking a selfie, phone in hand, making a sweet expression, soft lighting, close-up",
    "default": "A cute anime girl with a warm smile, beautiful detailed eyes, soft lighting, high quality anime style illustration",
}


def detect_visual_intent(message: str) -> Tuple[bool, str]:
    """检测消息中的视觉意图"""
    message = message.lower().strip()
    for pattern in VISUAL_INTENT_KEYWORDS:
        if re.search(pattern, message):
            if any(kw in message for kw in ["做饭", "煮", "cook"]):
                return True, "cooking"
            elif any(kw in message for kw in ["农场", "种", "farm"]):
                return True, "farming"
            elif any(kw in message for kw in ["自拍", "selfie"]):
                return True, "selfie"
            elif any(kw in message for kw in ["休息", "躺", "relax"]):
                return True, "relaxing"
            elif any(kw in message for kw in ["外面", "公园", "outdoor"]):
                return True, "outdoor"
            else:
                return True, "daily_life"
    return False, ""


def generate_prompt_from_context(
    chat_history: List[Dict[str, Any]],
    scene: str = "default",
) -> str:
    """根据对话上下文生成图像提示词"""
    base_prompt = SCENE_PROMPTS.get(scene, SCENE_PROMPTS["default"])
    context_hints = []
    for msg in chat_history[-5:]:
        content = msg.get("content", "").lower()
        if any(kw in content for kw in ["开心", "高兴", "happy", "喜欢"]):
            context_hints.append("happy expression, smiling")
        elif any(kw in content for kw in ["难过", "伤心", "sad"]):
            context_hints.append("slightly sad expression")
        if any(kw in content for kw in ["做饭", "煮"]):
            context_hints.append("cooking")
        elif any(kw in content for kw in ["看书", "读书"]):
            context_hints.append("reading a book")
    if context_hints:
        return f"{base_prompt}, {', '.join(context_hints[-2:])}"
    return base_prompt


# ============================================================
# 全局单例 + 便捷函数
# ============================================================

_image_service: Optional[ImageGenerationService] = None


def get_image_service() -> ImageGenerationService:
    """获取全局图像生成服务实例"""
    global _image_service
    if _image_service is None:
        _image_service = ImageGenerationService()
    return _image_service


async def generate_image_from_context(
    chat_history: List[Dict[str, Any]],
    user_message: str = "",
) -> Optional[str]:
    """根据对话上下文生成图片（便捷函数）"""
    has_intent, scene = detect_visual_intent(user_message)
    if not has_intent:
        return None

    prompt = generate_prompt_from_context(chat_history, scene)
    logger.info(f"[ImageGen] 检测到视觉意图，场景: {scene}")

    svc = get_image_service()
    return await svc.generate_and_save(prompt)


async def send_image_to_telegram(
    bot,
    chat_id: int,
    image_path: str,
    caption: str = "",
) -> bool:
    """发送图片到 Telegram"""
    if not os.path.exists(image_path):
        logger.error(f"[ImageGen] 图片不存在: {image_path}")
        return False
    try:
        await bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        with open(image_path, "rb") as f:
            await bot.send_photo(chat_id=chat_id, photo=f, caption=caption or None, message_thread_id=CHAT_TOPIC_THREAD_ID)
        logger.info(f"[ImageGen] 图片发送成功: chat_id={chat_id}")
        return True
    except Exception as e:
        logger.error(f"[ImageGen] 发送图片失败: {e}")
        return False


# ============================================================
# 测试
# ============================================================

async def test_image_service():
    """测试图像生成服务"""
    svc = ImageGenerationService()

    # 测试 LoRA Prompt 构建
    prompt = svc._build_lora_prompt("a girl smiling")
    print(f"LoRA Prompt: {prompt}")

    # 测试意图检测
    for msg in ["想看看你在干嘛", "发张照片", "你好"]:
        has_intent, scene = detect_visual_intent(msg)
        print(f"'{msg}' -> 意图: {has_intent}, 场景: {scene}")

    await svc.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_image_service())
