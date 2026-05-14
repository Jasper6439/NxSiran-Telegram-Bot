"""
AI 调用统一模块
整合 bot.py 和 chat_engine.py 中重复的 AI API 调用逻辑，
提供统一的模型列表、fallback 机制和异步 HTTP 调用。
"""
import os
import re
import json
import logging
import random
from typing import Dict, List, Optional, Any

import httpx

logger = logging.getLogger(__name__)

# 从 config 模块导入配置（统一管理）
from system.config import AI_API_BASE, AI_API_KEY, AI_MODEL, AI_MODELS, DATA_DIR

# ── 统一的模型列表（从 config 导入） ──────────────────────────
FALLBACK_MODELS: List[str] = AI_MODELS

# ── 默认参数 ─────────────────────────────────────────────────
DEFAULT_TEMPERATURE = 0.85
DEFAULT_MAX_TOKENS = 300
DEFAULT_TIMEOUT = 60.0
MAX_HISTORY_MESSAGES = 20


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
            if cfg.get('ai_api_key'):
                api_key = cfg['ai_api_key']
            if cfg.get('ai_api_base'):
                api_base = cfg['ai_api_base']
    except Exception:
        pass

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
    """统一的 AI API 调用函数，支持模型 fallback。

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
        try:
            result = await _make_api_request(
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
            if result:
                if current_model != models_to_try[0]:
                    logger.info(f"Fallback model {current_model} succeeded")
                return result

        except httpx.TimeoutException:
            logger.warning(f"Model {current_model} timed out, trying next")
            last_error = "timeout"
            continue
        except httpx.HTTPStatusError as e:
            logger.warning(f"Model {current_model} returned HTTP {e.response.status_code}, trying next")
            last_error = f"HTTP {e.response.status_code}"
            continue
        except Exception as e:
            logger.warning(f"Model {current_model} failed: {e}, trying next")
            last_error = str(e)
            continue

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
    response_format: Optional[Dict] = None,
    tools: Optional[List[Dict]] = None,
) -> Optional[str]:
    """发送单次 API 请求到 OpenRouter 兼容接口。

    Returns:
        AI 回复文本，失败时返回 None
    """
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

    async with httpx.AsyncClient(timeout=timeout) as client:
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
            logger.warning(f"Model {model} returned no choices")
            return None

        content = data["choices"][0]["message"]["content"]
        if not content or not content.strip():
            logger.warning(f"Model {model} returned empty content")
            return None

        # 过滤掉 AI 思考过程（<think> 标签、<think> 标签等）
        content = _strip_thinking_content(content)

        return content.strip()


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
    
    content = content.strip()
    if not content:
        return content
    
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
            r'回复[：:]\s*[""]?(.+?)[""]?$',
            r'可能(?:会)?说[：:]\s*[""]?(.+?)[""]?$',
            r'比如[：:]\s*[""]?(.+?)[""]?$',
            r'例如[：:]\s*[""]?(.+?)[""]?$',
            r'最合适(?:的回复)?[：:]\s*[""]?(.+?)[""]?$',
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
