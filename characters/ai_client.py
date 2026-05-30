"""
AI 调用统一模块
整合 bot.py 和 chat_engine.py 中重复的 AI API 调用逻辑，
提供统一的模型列表、fallback机制和异步HTTP调用。
"""
import os
import re
import json
import logging
import random
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable

import httpx
import aiohttp

logger = logging.getLogger(__name__)

# 从 config 模块导入配置（统一管理）
from system.config import AI_API_BASE, AI_API_KEY, AI_MODEL, AI_MODELS, DATA_DIR, MAX_CONTEXT_TOKENS
from .token_utils import truncate_messages_for_api

# ── Reusable httpx client singleton ─────────────────────────
_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    """Lazily create and reuse a single httpx.AsyncClient."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=httpx.Timeout(DEFAULT_TIMEOUT))
    return _http_client


async def close_http_client():
    """Close the shared httpx client. Call on application shutdown."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None

# ── 统一的模型列表（从 config 导入） ──────────────────────────
FALLBACK_MODELS: List[str] = AI_MODELS

# ── 默认参数 ─────────────────────────────────────────────────
DEFAULT_TEMPERATURE = 0.85
DEFAULT_MAX_TOKENS = 300
DEFAULT_TIMEOUT = 60.0
MAX_HISTORY_MESSAGES = 20
MAX_RETRIES = 3
STREAM_CHUNK_SIZE = 1024


def _load_api_config() -> tuple:
    """从环境变量和配置文件中读取 API 配置。

    Returns:
        (api_key, api_base) 元组
    """
    # 优先使用 config 模块的值（已从环境变量和 config.json 加载）
    api_key = AI_API_KEY
    api_base = AI_API_BASE

    # 动态读取最新配置（兼容 DATA_DIR 下 config.json）
    try:
        config_path = os.path.join(DATA_DIR, 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                cfg = json.load(f)
            # 优先使用 config.json 中的值
            if cfg.get('ai_api_key'):
                api_key = cfg['ai_api_key']
            if cfg.get('ai_api_base'):
                api_base = cfg['ai_api_base']
    except Exception as e:
        logger.warning(f"Failed to load config.json: {e}")

    return api_key, api_base


async def call_ai(
    system_prompt: str,
    user_message: str,
    chat_history: Optional[List[Dict]] = None,
    model: Optional[str] = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = DEFAULT_TIMEOUT,
    response_format: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """统一的 AI API 调用函数，支持 fallback 机制。

    Args:
        system_prompt: 系统提示词
        user_message: 用户消息
        chat_history: 对话历史列表（每项为 {"role": ..., "content": ...}）
        model: 指定使用的模型，为 None 时按 FALLBACK_MODELS 顺序尝试
        temperature: 生成温度
        max_tokens: 最大生成 token 数
        timeout: HTTP 请求超时秒数
        response_format: 可选的响应格式（如 {"type": "json_object"}）
        tools: 可选的工具列表（用于 function calling）

    Returns:
        AI 回复文本

    Raises:
        ValueError: API Key 未配置
        RuntimeError: 所有模型均调用失败
    """
    # 构建 messages 列表
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    if chat_history:
        messages.extend(chat_history[-MAX_HISTORY_MESSAGES:])

    messages.append({"role": "user", "content": user_message})

    # 确定要尝试的模型列表
    if model:
        models_to_try = [model]
    else:
        models_to_try = [AI_MODEL] + [m for m in FALLBACK_MODELS if m != AI_MODEL]

    api_key, api_base = _load_api_config()

    if not api_key:
        raise ValueError("AI_API_KEY not set")

    last_error: Optional[str] = None

    for current_model in models_to_try:
        for attempt in range(MAX_RETRIES):
            try:
                response_text = await _make_api_request(
                    api_base=api_base,
                    api_key=api_key,
                    model=current_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    response_format=response_format,
                    tools=tools,
                )
                if response_text:
                    if current_model != models_to_try[0]:
                        logger.info(f"Fallback model {current_model} succeeded")
                    # 过滤掉 AI 思考过程
                    return _strip_thinking_content(response_text).strip()

            except asyncio.TimeoutError:
                logger.warning(f"Model {current_model} timed out (attempt {attempt + 1}/{MAX_RETRIES})")
                last_error = "timeout"
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1 * (attempt + 1))  # 指数退避
                continue
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                logger.warning(f"Model {current_model} HTTP error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                last_error = f"HTTP {status}"
                if attempt < MAX_RETRIES - 1:
                    # 429 限流用更长退避
                    delay = (5 * (attempt + 1)) if status == 429 else (1 * (attempt + 1))
                    await asyncio.sleep(delay)
                continue
            except Exception as e:
                logger.warning(f"Model {current_model} failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                last_error = str(e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                continue
        # 当前模型所有重试失败，尝试下一个模型（429限流时加长间隔）
        logger.warning(f"Model {current_model} all {MAX_RETRIES} retries exhausted, trying next")
        if "429" in str(last_error):
            await asyncio.sleep(3)

    logger.error(f"All AI models failed. Last error: {last_error}")
    raise RuntimeError(f"All AI models failed. Last error: {last_error}")


async def _make_api_request(
    api_base: str,
    api_key: str,
    model: str,
    messages: List[Dict],
    temperature: float,
    max_tokens: int,
    timeout: float,
    response_format: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """发送 API 请求到 OpenRouter 兼容接口。"""
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    if response_format:
        payload["response_format"] = response_format
    if tools:
        payload["tools"] = tools

    client = _get_http_client()
    response = await client.post(
        f"{api_base}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    response.raise_for_status()
    data = response.json()

    if "choices" not in data or not data["choices"]:
        logger.warning(f"Model {model} returned empty choices")
        return None

    content = data["choices"][0].get("message", {}).get("content", "")
    # SenseNova 等模型可能返回 reasoning_content（思考 token）
    if not content.strip():
        reasoning = data["choices"][0].get("message", {}).get("reasoning_content", "")
        if reasoning.strip():
            logger.info(f"Model {model} returned reasoning_content instead of content")
            content = reasoning
    if not content.strip():
        logger.warning(f"Model {model} returned empty content")
        return None

    return content


# ============================================================
# 图像生成功能（v1.9.3 新增）
# ============================================================

async def generate_image(
    prompt: str,
    model: str = "black-forest-labs/flux-1-schnell:free",
    width: int = 512,
    height: int = 512,
    timeout: float = 60.0,
) -> Optional[str]:
    """
    调用图像生成模型生成图片
    
    Args:
        prompt: 图像提示词
        model: 图像生成模型
        width: 图片宽度
        height: 图片高度
        timeout: 请求超时
    
    Returns:
        图片的 base64 编码，失败返回 None
    """
    import base64
    
    api_key, api_base = _load_api_config()
    
    if not api_key:
        raise ValueError("AI_API_KEY not set")
    
    payload = {
        "model": model,
        "prompt": prompt,
        "width": width,
        "height": height,
        "n": 1,
    }

    client = _get_http_client()
    try:
        response = await client.post(
            f"{api_base}/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        if "data" in data and len(data["data"]) > 0:
            image_data = data["data"][0]

            # 可能是 base64 或 URL
            if "b64_json" in image_data:
                return image_data["b64_json"]
            elif "url" in image_data:
                # 下载图片并转为 base64
                img_resp = await client.get(image_data["url"])
                img_data = img_resp.content
                return base64.b64encode(img_data).decode('utf-8')
            else:
                logger.warning(f"Unknown image response format: {image_data.keys()}")
                return None
        else:
            logger.warning(f"Image generation returned no data: {data}")
            return None

    except httpx.HTTPStatusError as e:
        logger.error(f"Image generation HTTP error: {e}")
        return None
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return None


async def generate_image_from_context(
    chat_history: List[Dict],
    user_message: str,
) -> Optional[str]:
    """
    根据对话上下文生成图片（意图驱动）
    
    Args:
        chat_history: 对话历史
        user_message: 用户消息
    
    Returns:
        图片的 base64 编码，如果用户没有视觉意图则返回 None
    """
    # 检测视觉意图
    visual_keywords = [
        "想看", "发张", "照片", "自拍", "看看", 
        "你在干嘛", "你在干什么", "让我看看",
    ]
    
    has_intent = any(kw in user_message.lower() for kw in visual_keywords)
    
    if not has_intent:
        return None
    
    # 根据上下文生成提示词
    # 默认场景
    base_prompt = "A cute anime girl with a warm smile, beautiful detailed eyes, soft lighting, high quality anime style illustration"
    
    # 根据关键词判断场景
    if any(kw in user_message for kw in ["做饭", "煮", "cook"]):
        base_prompt = "A cute anime girl in an apron, cooking in a kitchen, delicious food on the counter, warm kitchen lighting"
    elif any(kw in user_message for kw in ["自拍", "selfie"]):
        base_prompt = "A cute anime girl taking a selfie, phone in hand, making a sweet expression, soft lighting, close-up"
    elif any(kw in user_message for kw in ["休息", "躺"]):
        base_prompt = "A cute anime girl relaxing on a sofa, reading a book, cozy living room, soft lighting"
    
    logger.info(f"[Image] Generating image with prompt: {base_prompt}")
    
    return await generate_image(base_prompt)


async def stream_chat_completion(
    system_prompt: str,
    user_message: str,
    chat_history: Optional[List[Dict]] = None,
    model: Optional[str] = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = DEFAULT_TIMEOUT,
    response_format: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    on_chunk: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> str:
    """流式 AI API 调用函数，支持打字机效果输出。

    Args:
        system_prompt: 系统提示词
        user_message: 用户消息
        chat_history: 对话历史列表（每项为 {"role": ..., "content": ...}）
        model: 指定使用的模型，为 None 时按 FALLBACK_MODELS 顺序尝试
        temperature: 生成温度
        max_tokens: 最大生成 token 数
        timeout: HTTP 请求超时秒数
        response_format: 可选的响应格式（如 {"type": "json_object"}）
        tools: 可选的工具列表（用于 function calling）
        on_chunk: 回调函数，每当收到新 chunk 时调用，参数为当前完整文本
        should_stop: 可选的停止检查函数，返回 True 时中断流式输出

    Returns:
        完整的 AI 回复文本

    Raises:
        ValueError: API Key 未配置
        RuntimeError: 所有模型均调用失败
    """
    # 构建 messages 列表
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    if chat_history:
        messages.extend(chat_history[-MAX_HISTORY_MESSAGES:])

    messages.append({"role": "user", "content": user_message})

    # 确定要尝试的模型列表
    if model:
        models_to_try = [model]
    else:
        models_to_try = [AI_MODEL] + [m for m in FALLBACK_MODELS if m != AI_MODEL]

    api_key, api_base = _load_api_config()

    if not api_key:
        raise ValueError("AI_API_KEY not set")

    last_error: Optional[str] = None

    for current_model in models_to_try:
        for attempt in range(MAX_RETRIES):
            try:
                full_content = await _make_stream_request(
                    api_base=api_base,
                    api_key=api_key,
                    model=current_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    response_format=response_format,
                    tools=tools,
                    on_chunk=on_chunk,
                    should_stop=should_stop,
                )
                if full_content:
                    if current_model != models_to_try[0]:
                        logger.info(f"Fallback model {current_model} succeeded")
                    # 过滤掉 AI 思考过程
                    return _strip_thinking_content(full_content).strip()

            except asyncio.TimeoutError:
                logger.warning(f"Model {current_model} stream timed out (attempt {attempt + 1}/{MAX_RETRIES})")
                last_error = "timeout"
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1 * (attempt + 1))  # 指数退避
                continue
            except aiohttp.ClientError as e:
                logger.warning(f"Model {current_model} stream client error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                last_error = f"Client error: {e}"
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                continue
            except Exception as e:
                logger.warning(f"Model {current_model} stream failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                last_error = str(e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                continue
        # 当前模型所有重试失败，尝试下一个模型
        logger.warning(f"Model {current_model} all {MAX_RETRIES} retries exhausted, trying next")

    logger.error(f"All AI models failed in stream mode. Last error: {last_error}")
    raise RuntimeError(f"All AI models failed in stream mode. Last error: {last_error}")


async def stream_chat_completion_generator(
    system_prompt: str,
    user_message: str,
    chat_history: Optional[List[Dict]] = None,
    model: Optional[str] = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = DEFAULT_TIMEOUT,
) -> AsyncGenerator[str, None]:
    """真正的逐 token 流式生成器，用于 SSE。

    与 stream_chat_completion 不同，这个函数是异步生成器，
    每当收到新的 token 时立即 yield，实现真正的实时流式输出。

    Args:
        system_prompt: 系统提示词
        user_message: 用户消息
        chat_history: 对话历史列表
        model: 指定使用的模型
        temperature: 生成温度
        max_tokens: 最大生成 token 数
        timeout: HTTP 请求超时秒数

    Yields:
        每个 token（字符串片段）

    Raises:
        ValueError: API Key 未配置
        RuntimeError: 所有模型均调用失败
    """
    # 构建 messages 列表
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    if chat_history:
        messages.extend(chat_history[-MAX_HISTORY_MESSAGES:])

    messages.append({"role": "user", "content": user_message})

    # 确定要尝试的模型列表
    if model:
        models_to_try = [model]
    else:
        models_to_try = [AI_MODEL] + [m for m in FALLBACK_MODELS if m != AI_MODEL]

    api_key, api_base = _load_api_config()

    if not api_key:
        raise ValueError("AI_API_KEY not set")

    last_error: Optional[str] = None

    for current_model in models_to_try:
        for attempt in range(MAX_RETRIES):
            try:
                payload: Dict[str, Any] = {
                    "model": current_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                }

                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                    async with session.post(
                        f"{api_base}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    ) as response:
                        response.raise_for_status()

                        async for line in response.content:
                            line = line.decode('utf-8').strip()

                            # SSE 格式: data: {...}
                            if not line.startswith('data: '):
                                continue

                            data = line[6:]  # 去掉 'data: ' 前缀

                            # 流结束标记
                            if data == '[DONE]':
                                return

                            try:
                                chunk = json.loads(data)

                                # 检查 choices 是否存在
                                if "choices" not in chunk or not chunk["choices"]:
                                    continue

                                delta = chunk["choices"][0].get("delta", {})
                                content = delta.get("content", "")

                                if content:
                                    yield content

                            except json.JSONDecodeError:
                                continue
                            except Exception as e:
                                logger.warning(f"Error processing SSE chunk: {e}")
                                continue

                # 如果成功完成，直接返回
                return

            except asyncio.TimeoutError:
                logger.warning(f"Model {current_model} generator timed out (attempt {attempt + 1}/{MAX_RETRIES})")
                last_error = "timeout"
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                continue
            except aiohttp.ClientError as e:
                logger.warning(f"Model {current_model} generator client error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                last_error = f"Client error: {e}"
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                continue
            except Exception as e:
                logger.warning(f"Model {current_model} generator failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                last_error = str(e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                continue

        logger.warning(f"Model {current_model} generator all {MAX_RETRIES} retries exhausted, trying next")

    logger.error(f"All AI models failed in generator mode. Last error: {last_error}")
    raise RuntimeError(f"All AI models failed in generator mode. Last error: {last_error}")


async def _make_stream_request(
    api_base: str,
    api_key: str,
    model: str,
    messages: List[Dict],
    temperature: float,
    max_tokens: int,
    timeout: float,
    response_format: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    on_chunk: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Optional[str]:
    """发送流式 API 请求到 OpenRouter 兼容接口。

    Returns:
        完整的 AI 回复文本，失败时返回 None
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,  # 启用流式输出
    }

    if response_format:
        payload["response_format"] = response_format
    if tools:
        payload["tools"] = tools

    full_content = ""

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        async with session.post(
            f"{api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
            response.raise_for_status()

            async for line in response.content:
                # 检查是否需要停止
                if should_stop and should_stop():
                    logger.info("Stream interrupted by stop signal")
                    break

                line = line.decode('utf-8').strip()

                # SSE 格式: data: {...}
                if not line.startswith('data: '):
                    continue

                data = line[6:]  # 去掉 'data: ' 前缀

                # 流结束标记
                if data == '[DONE]':
                    break

                try:
                    chunk = json.loads(data)

                    # 检查 choices 是否存在
                    if "choices" not in chunk or not chunk["choices"]:
                        continue

                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")

                    if content:
                        full_content += content

                        # 调用回调函数
                        if on_chunk:
                            try:
                                on_chunk(full_content)
                            except Exception as e:
                                logger.warning(f"on_chunk callback error: {e}")

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse SSE chunk: {data}")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing SSE chunk: {e}")
                    continue

    if not full_content.strip():
        logger.warning(f"Model {model} returned empty content in stream mode")
        return None

    return full_content


def _strip_thinking_content(content: str) -> str:
    """去除 AI 模型返回的思考过程内容。

    某些模型（如 Minimax、DeepSeek 等 reasoning 模型）会在响应中包含
    思考过程，需要用 <think>、<think> 等标签包裹，或者直接以自然语言
    输出分析过程。这些内容不应该展示给用户。

    Args:
        content: AI 原始响应内容

    Returns:
        过滤后的最终回复内容
    """
    # 1. 移除标签包裹的思考过程
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'"reasoning"\s*:\s*".*?"', '', content, flags=re.DOTALL)
    
    # 2. 检测非标签形式的自然语言思考过程
    thinking_keywords = [
        '嗯，用户', '用户发了', '根据设定', '参考之前的',
        '回复要很短', '我需要按照', '她可能会说', '她害怕',
        '当用户表达', '听起来像是', '车如云看到', '可能会有点',
        '直接沉默', '不超过', '结合以上', '考虑到', '分析',
        '我应该', '让我想想', 'Let me think', 'I need to',
        '我需要按', '按照车如云', '按照', '好的，我', '好的，现在',
        '好的，用户', '根据之前的示例', '首先，回复', '当学长说',
        '学长说', '车如云可能', '车如云会', '参考之前的示例',
        # English reasoning model patterns
        'The user says', 'According to character', 'According to the character',
        'Thus ', 'should respond', 'Possible:', 'Given the instruction',
        'the user is', 'They should not', 'Perhaps:', 'Maybe:',
        'But need to keep', 'Thus Cha', 'they\'d likely',
        'the system says', 'the instruction:', 'they are currently',
        'minimal words', 'under 20 chars', 'with ... and',
        'Actually the user', 'meaning they',
    ]
    
    has_thinking = any(kw in content for kw in thinking_keywords)
    
    if has_thinking:
        # 策略A: 按空行分段，取最后一段短的（最常见情况）
        parts = re.split(r'\n\s*\n', content)
        if len(parts) > 1:
            for part in reversed(parts):
                part = part.strip()
                if part and len(part) < 80:
                    return part
        
        # 策略B: 找以 ... 或 （ 开头的行（排除纯标点）
        lines = content.split('\n')
        for line in reversed(lines):
            stripped = line.strip()
            if stripped and len(stripped) < 80 and (
                stripped.startswith('...') or stripped.startswith('（') or 
                stripped.startswith('(') or stripped.startswith('…')
            ):
                # 排除纯标点符号（如 "......" "..." "……"）
                text_content = stripped.lstrip('.').lstrip('…').lstrip('（').lstrip('(').rstrip('）').rstrip(')').strip()
                if len(text_content) >= 2:  # 至少要有2个有效字符
                    return stripped
        
        # 策略C: 找最后一个句号/问号/感叹号后的短句
        # 思考过程通常以分析结尾，回复通常是独立短句
        sentences = re.split(r'(?<=[。！？\n])', content)
        if len(sentences) > 2:
            # 取最后 1-2 个短句
            last = ''.join(sentences[-2:]).strip()
            if len(last) < 80 and not any(kw in last for kw in thinking_keywords):
                return last
        
        # 策略D: 如果整个内容很长且包含思考，尝试找引号中的回复
        if len(content) > 150:
            quotes = re.findall(r'[""](.+?)[""]', content)
            if quotes:
                for q in reversed(quotes):
                    q = q.strip()
                    if 2 <= len(q) <= 50 and (q.startswith('...') or '(' in q or '。' in q or '…' in q or '学长' in q):
                        return q
        
        # 策略E: 找 "回复" / "说" / "可能" 后面跟着的示例回复
        reply_patterns = [
            r'回复[：:]\s*[""]?(.*?)[""]?$',
            r'可能(?:会)?说[：:]\s*[""]?(.*?)[""]?$',
            r'比如[：:]\s*[""]?(.*?)[""]?$',
            r'例如[：:]\s*[""]?(.*?)[""]?$',
            r'最合适(?:的回复)?[：:]\s*[""]?(.*?)[""]?$',
            # English patterns
            r'Perhaps[:\s]+(.+?)[\.\n]',
            r'Possible[:\s]+(.+?)[\.\n]',
            r'Maybe[:\s]+(.+?)[\.\n]',
        ]
        for pattern in reply_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            for match in reversed(matches):
                match = match.strip().strip('"').strip('"').strip()
                if 2 <= len(match) <= 60 and ('学长' in match or match.startswith(('...', '（', '…', '('))):
                    return match
        
        # 策略F: 如果内容非常长（>200字符），从最后往前找第一个角色回复风格的段落
        if len(content) > 200:
            lines = content.split('\n')
            candidate = []
            for line in reversed(lines):
                stripped = line.strip()
                if not stripped:
                    if candidate:
                        break
                    continue
                # 角色回复通常以 ...、（、或简短对话开头
                if stripped.startswith(('...', '（', '…', '学长', '嗯')):
                    candidate.insert(0, stripped)
                    if len('\n'.join(candidate)) > 60:
                        break
            if candidate:
                result = '\n'.join(candidate)
                if len(result) <= 80:
                    return result
        
        # 策略G: 整个内容都是思考过程，没有最终回复，返回默认 fallback
        # 防止整段 reasoning 被原样发给用户
        logger.warning(f"[_strip_thinking] 无法提取有效回复，使用fallback。原始内容: {content[:200]}...")
        fallbacks = ['...（沉默）', '...嗯。', '...我在。']
        result = random.choice(fallbacks)
        logger.info(f"[_strip_thinking] fallback结果: {result}")
        return result
    
    return content
