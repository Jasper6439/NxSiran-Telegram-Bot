"""
本地模型适配器
==============

统一 Ollama / vLLM / llama.cpp 等本地推理引擎的调用接口。
与现有 ai_client.py 的远程 API 调用保持相同接口。

使用方式：
    from tools.local_model_adapter import get_local_client
    client = get_local_client("ollama")  # 或 "vllm"
    response = await client.chat(messages, model="llama3")

配置：
    在 config.json 中添加：
    {
        "local_model": {
            "provider": "ollama",       # ollama / vllm / llamacpp
            "base_url": "http://localhost:11434",  # Ollama 默认端口
            "model": "llama3:8b",
            "api_key": ""               # 本地通常不需要
        }
    }
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ============================================================
# 基类
# ============================================================

class LocalModelClient(ABC):
    """本地模型客户端基类"""

    def __init__(self, base_url: str, model: str = "", api_key: str = ""):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self, timeout: float = 120.0) -> httpx.AsyncClient:
        """Reuse a single httpx.AsyncClient per instance."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=timeout)
        return self._client

    async def close(self):
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.85,
        max_tokens: int = 300,
        **kwargs,
    ) -> str:
        """同步聊天调用（返回完整响应）"""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.85,
        max_tokens: int = 300,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式聊天调用"""
        ...

    @abstractmethod
    async def list_models(self) -> List[str]:
        """列出可用模型"""
        ...


# ============================================================
# Ollama 适配器
# ============================================================

class OllamaClient(LocalModelClient):
    """Ollama API 适配器

    Ollama API:
        POST /api/chat         — 聊天
        GET  /api/tags         — 列出模型
        POST /api/generate     — 文本生成
    """

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.85,
        max_tokens: int = 300,
        **kwargs,
    ) -> str:
        model = model or self.model or "llama3"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        client = self._get_client()
        resp = await client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.85,
        max_tokens: int = 300,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        model = model or self.model or "llama3"
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        client = self._get_client()
        async with client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    async def list_models(self) -> List[str]:
        client = self._get_client(timeout=10.0)
        resp = await client.get(f"{self.base_url}/api/tags")
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]


# ============================================================
# vLLM 适配器（OpenAI 兼容 API）
# ============================================================

class VLLMClient(LocalModelClient):
    """vLLM API 适配器

    vLLM 提供 OpenAI 兼容的 API：
        POST /v1/chat/completions  — 聊天
        GET  /v1/models            — 列出模型
    """

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.85,
        max_tokens: int = 300,
        **kwargs,
    ) -> str:
        model = model or self.model or "default"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        client = self._get_client()
        resp = await client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "",
        temperature: float = 0.85,
        max_tokens: int = 300,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        model = model or self.model or "default"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        client = self._get_client()
        async with client.stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line.strip() != "data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def list_models(self) -> List[str]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        client = self._get_client(timeout=10.0)
        resp = await client.get(
            f"{self.base_url}/v1/models",
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]


# ============================================================
# 工厂函数
# ============================================================

PROVIDERS = {
    "ollama": OllamaClient,
    "vllm": VLLMClient,
}


def get_local_client(
    provider: str = "ollama",
    base_url: str = "",
    model: str = "",
    api_key: str = "",
) -> LocalModelClient:
    """获取本地模型客户端。

    Args:
        provider: 提供商 (ollama / vllm)
        base_url: API 地址（空则用默认值）
        model: 模型名称
        api_key: API 密钥（本地通常不需要）

    Returns:
        LocalModelClient 实例
    """
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}. Supported: {list(PROVIDERS.keys())}")

    defaults = {
        "ollama": ("http://localhost:11434", "llama3"),
        "vllm": ("http://localhost:8000", "default"),
    }
    default_url, default_model = defaults.get(provider, ("http://localhost:8000", "default"))

    return PROVIDERS[provider](
        base_url=base_url or default_url,
        model=model or default_model,
        api_key=api_key,
    )


def load_local_config() -> Optional[Dict[str, str]]:
    """从 config.json 加载本地模型配置"""
    try:
        from system.config import DATA_DIR
        config_path = os.path.join(DATA_DIR, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                cfg = json.load(f)
            return cfg.get("local_model")
    except Exception:
        pass
    return None
