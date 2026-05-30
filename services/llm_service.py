"""
LLM 对话路由服务 — 免费三级降级策略
=====================================
零成本高可用的多模型对话路由，严格规避付费。

三级路由:
  1. OpenRouter 免费池 (主力) — openrouter/auto / deepseek-chat
  2. 国内极速池 (硅基流动 & 商汤) — DeepSeek-V3 / Qwen2.5 / SenseChat-Turbo
  3. 国际兜底池 (Google Gemini) — gemini-2.5-flash (严格限流保护)

用法:
    from services.llm_service import LLMRouterService, get_llm_service

    llm = get_llm_service()
    result = await llm.chat(messages)
    # {"role": "assistant", "content": "...", "source": "openrouter/deepseek-chat"}
"""

import os
import logging
from typing import Optional, List, Dict, Any


from characters.ai_client import _get_http_client

logger = logging.getLogger(__name__)

# ============================================================
# 配置 — 从环境变量读取
# ============================================================

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/auto")

SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
SILICONFLOW_API_BASE = "https://api.siliconflow.cn/v1"
SILICONFLOW_MODEL = os.environ.get("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V3")

SENSENOVA_API_KEY = os.environ.get("SENSENOVA_API_KEY", "")
SENSENOVA_API_BASE = "https://api.sensenova.cn/v1"
SENSENOVA_MODEL = os.environ.get("SENSENOVA_MODEL", "SenseChat-Turbo")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.5-flash"  # 硬编码，严禁使用 Pro 模型

# 项目信息（用于 OpenRouter 请求头）
PROJECT_GITHUB = "https://github.com/Jasper6439/LoveSupremacy_Universe"
PROJECT_NAME = "LoveSupremacy Universe"

# 超时配置
LLM_TIMEOUT = 15.0  # 秒
GEMINI_TIMEOUT = 10.0  # 更短，避免阻塞


class LLMRouterService:
    """
    免费三级 LLM 对话路由服务

    策略模式：按优先级尝试每个路由，首个成功即返回。
    所有请求使用 httpx 异步 HTTP 客户端。
    """
    # ============================================================
    # 统一入口
    # ============================================================

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, str]:
        """
        三级降级对话，返回统一格式

        Args:
            messages: 对话历史 [{"role": "user", "content": "..."}]
            temperature: 采样温度
            max_tokens: 最大 token 数

        Returns:
            {"role": "assistant", "content": "回复内容", "source": "模型来源标识"}
        """
        # 按优先级尝试
        routes = [
            ("openrouter", self._chat_openrouter),
            ("siliconflow", self._chat_siliconflow),
            ("sensenova", self._chat_sensenova),
            ("gemini", self._chat_gemini),
        ]

        last_error = None
        for source, handler in routes:
            try:
                result = await handler(messages, temperature, max_tokens)
                if result and result.get("content"):
                    logger.info(f"[LLM] ✅ 成功调用 {source}")
                    return result
            except Exception as e:
                last_error = e
                logger.warning(f"[LLM] ⚠️ {source} 失败: {e}")

        # 全部失败
        logger.error(f"[LLM] ❌ 所有路由均失败，最后错误: {last_error}")
        return {
            "role": "assistant",
            "content": "（所有 AI 服务暂时不可用，请稍后再试）",
            "source": "none",
        }

    # ============================================================
    # 第一梯队：OpenRouter 免费池
    # ============================================================

    async def _chat_openrouter(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Optional[Dict[str, str]]:
        """OpenRouter 免费池 — 主力路由"""
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY 未配置")

        client = _get_http_client()
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            # 规避风控的必需请求头
            "HTTP-Referer": PROJECT_GITHUB,
            "X-Title": PROJECT_NAME,
        }

        response = await client.post(
            f"{OPENROUTER_API_BASE}/chat/completions",
            json=payload,
            headers=headers,
        )
        # 降级条件
        if response.status_code == 429:
            raise RuntimeError("OpenRouter 限流 (429)")
        if response.status_code in (502, 503):
            raise RuntimeError(f"OpenRouter 服务不可用 ({response.status_code})")
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        model_used = data.get("model", OPENROUTER_MODEL)

        return {
            "role": "assistant",
            "content": content,
            "source": f"openrouter/{model_used}",
        }

    # ============================================================
    # 第二梯队：国内极速池
    # ============================================================

    async def _chat_siliconflow(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Optional[Dict[str, str]]:
        """硅基流动 — DeepSeek-V3 / Qwen2.5"""
        if not SILICONFLOW_API_KEY:
            raise ValueError("SILICONFLOW_API_KEY 未配置")

        client = _get_http_client()
        payload = {
            "model": SILICONFLOW_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
            "Content-Type": "application/json",
        }

        response = await client.post(
            f"{SILICONFLOW_API_BASE}/chat/completions",
            json=payload,
            headers=headers,
        )
        if response.status_code == 429:
            raise RuntimeError("SiliconFlow 限流 (429)")
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        return {
            "role": "assistant",
            "content": content,
            "source": f"siliconflow/{SILICONFLOW_MODEL}",
        }

    async def _chat_sensenova(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Optional[Dict[str, str]]:
        """商汤日日新 — SenseChat-Turbo"""
        if not SENSENOVA_API_KEY:
            raise ValueError("SENSENOVA_API_KEY 未配置")

        client = _get_http_client()
        payload = {
            "model": SENSENOVA_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {SENSENOVA_API_KEY}",
            "Content-Type": "application/json",
        }

        response = await client.post(
            f"{SENSENOVA_API_BASE}/chat/completions",
            json=payload,
            headers=headers,
        )
        if response.status_code == 429:
            raise RuntimeError("SenseNova 限流 (429)")
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        return {
            "role": "assistant",
            "content": content,
            "source": f"sensenova/{SENSENOVA_MODEL}",
        }

    # ============================================================
    # 第三梯队：Google Gemini (严格限流保护)
    # ============================================================

    async def _chat_gemini(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Optional[Dict[str, str]]:
        """
        Google Gemini — 国际兜底池
        严格限制：仅使用 gemini-2.5-flash，严禁 Pro 模型
        熔断机制：429 不重试，直接跳过
        """
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY 未配置")

        # 使用更短的超时，防止阻塞
        client = _get_http_client()

        # 转换消息格式：OpenAI → Gemini
        gemini_contents = []
        system_instruction = None
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                gemini_contents.append({
                    "role": "user" if msg["role"] == "user" else "model",
                    "parts": [{"text": msg["content"]}],
                })

        payload: Dict[str, Any] = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}],
            }

        url = (
            f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent"
            f"?key={GEMINI_API_KEY}"
        )

        response = await client.post(url, json=payload)

        # 熔断：429 不重试，直接跳过
        if response.status_code == 429:
            raise RuntimeError("Gemini 限流 (429)，熔断跳过")

        response.raise_for_status()

        data = response.json()
        content = data["candidates"][0]["content"]["parts"][0]["text"]

        return {
            "role": "assistant",
            "content": content,
            "source": f"gemini/{GEMINI_MODEL}",
        }


# ============================================================
# 全局单例
# ============================================================

_llm_service: Optional[LLMRouterService] = None


def get_llm_service() -> LLMRouterService:
    """获取全局 LLM 路由服务实例"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMRouterService()
    return _llm_service


# ============================================================
# 便捷函数
# ============================================================

async def llm_chat(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> Dict[str, str]:
    """
    三级降级对话（便捷函数）

    Args:
        messages: 对话历史
        temperature: 采样温度
        max_tokens: 最大 token 数

    Returns:
        {"role": "assistant", "content": "...", "source": "模型来源"}
    """
    service = get_llm_service()
    return await service.chat(messages, temperature, max_tokens)


# ============================================================
# 测试
# ============================================================

async def test_llm_service():
    """测试 LLM 路由服务"""
    service = LLMRouterService()

    messages = [{"role": "user", "content": "你好，请用一句话介绍自己"}]

    print("测试三级 LLM 路由...")
    result = await service.chat(messages)

    print(f"来源: {result['source']}")
    print(f"回复: {result['content']}")

    await service.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_llm_service())
