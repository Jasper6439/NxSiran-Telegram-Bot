"""
AI Core Functions - AI 调用核心逻辑
=====================================
从 bot.py 提取，降低多 SOLO 并行开发时的 Git 冲突。

包含：
  - call_ai: 统一 AI 调用，组装系统提示词
  - call_ai_stream: 流式 AI 调用，支持打字机效果
  - summarize_and_save_memory: 记忆提取与保存
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, Callable

import httpx

# ============================================================
# Core imports (from bot.py's import block)
# ============================================================

from .ai_client import call_ai as ai_client_call_ai, stream_chat_completion
from system.config import (
    get_default_tz,
    get_user_memory_file,
    load_json,
    AI_API_BASE,
    AI_API_KEY,
    AI_MODEL,
    YOUR_CHAT_ID,
)
from system.prompts import EMOTION_RESPONSE_GUIDE
from .memory_legacy import (
    get_long_term_memory,
    get_semantic_memory_context,
    save_memory_entry,
    humanize_text,
)
from .chat_history import get_history
from .emotion import get_intimacy_context
from .stats import load_stats
from .weather import get_seoul_weather, get_weather_context
from .anniversary import get_upcoming_anniversary
from characters import get_current_character
from packages.analysis.chatlog import get_all_imported_relationships
from packages.importers.video import get_video_analysis_context
from packages.commands.misc import call_gemini, web_search
from .token_utils import truncate_chat_history
from system.config import MAX_CONTEXT_TOKENS


# ============================================================
# AI Core Functions
# ============================================================


def _build_system_prompt(use_memory: bool = True, emotion: str = "") -> str:
    """构建系统提示词。

    Args:
        use_memory: 是否使用记忆
        emotion: 情绪状态

    Returns:
        完整的系统提示词
    """
    now = datetime.now(get_default_tz())
    weekdays = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日']
    period = '凌晨' if now.hour < 6 else '上午' if now.hour < 12 else '下午' if now.hour < 18 else '晚上'
    time_info = f"当前时间：{now.strftime('%Y年%m月%d日 %H:%M')}，{period}，{weekdays[now.weekday()]}（韩国时间）"

    # [角色系统] 使用蒸馏角色的系统提示词
    character = get_current_character()
    if character:
        system_content = character.get_system_prompt({'user_name': '学长'})
    else:
        system_content = ""
    system_content += f"\n\n【实时信息】{time_info}"

    # [Skill: 亲密度系统] 注入关系状态
    stats = load_stats()
    stats["memories_count"] = len(load_json(get_user_memory_file(YOUR_CHAT_ID or 1), []))
    stats["selfies_sent"] = stats.get("selfies_sent", 0)
    stats["photos_received"] = stats.get("photos_received", 0)
    intimacy_ctx = get_intimacy_context(stats)
    system_content += intimacy_ctx

    # [Skill: 增强记忆] 注入分类记忆
    if use_memory:
        memory = get_long_term_memory()
        if memory:
            system_content += f"\n\n【你对学长的记忆】\n{memory}"

    # [Skill: semantic-memory] 注入语义记忆
    semantic_ctx = get_semantic_memory_context()
    if semantic_ctx:
        system_content += f"\n\n【你记住的关于学长的重要信息（语义记忆）】\n{semantic_ctx}"

    # [Skill: semantic-memory] 添加记忆提取提示
    system_content += "\n\n【记忆规则】如果学长提到了重要的个人信息（如生日、喜好、家人、工作、住址、重要约定等），请在回复末尾用 [MEMORY:关键词:具体内容] 标记。例如：如果学长说「我生日是3月15日」，你回复末尾加上 [MEMORY:学长的生日:3月15日]。只标记真正重要的信息，不要滥用。标记格式严格为 [MEMORY:key:value]，不要加多余空格。"

    # [Skill: 情绪识别] 注入情绪反应指引
    if emotion and emotion in EMOTION_RESPONSE_GUIDE:
        system_content += f"\n\n【当前情绪感知】{EMOTION_RESPONSE_GUIDE[emotion]}"

    # [Skill: 纪念日] 检查是否有即将到来的纪念日
    upcoming = get_upcoming_anniversary(3)
    if upcoming:
        ann_info = "，".join([f"{a['name']}还有{a['days_until']}天" for a in upcoming])
        system_content += f"\n\n【即将到来的纪念日】{ann_info}。如果合适的话，可以提起这件事。"

    # [Skill: 微信聊天记录导入] 注入已了解的人际关系
    imported_relationships = get_all_imported_relationships()
    if imported_relationships:
        system_content += f"\n\n【你了解学长的人际关系（从聊天记录分析得出）】{imported_relationships}\n\n在对话中，你可以自然地提及这些人，表现出你对学长生活的了解。比如当学长提到相关话题时，你可以说「你妈妈不是...」或「上次你提到...」"

    # [Skill: 视频分析] 注入从视频中学到的角色特点
    video_context = get_video_analysis_context()
    if video_context:
        system_content += f"\n\n{video_context}\n\n请尽量模仿上述说话风格和口头禅，让角色更加真实。"

    return system_content


async def _build_user_message_with_search(user_message: str) -> str:
    """构建用户消息，包含联网搜索结果（如果需要）。"""
    search_keywords = ["几点", "时间", "天气", "今天", "新闻", "最近", "现在", "多少度", "热搜", "发生了什么", "怎么了"]
    need_search = any(kw in user_message for kw in search_keywords)

    if need_search:
        search_result = await web_search(user_message)
        if search_result:
            search_context = f"\n\n【联网搜索结果】\n{search_result}\n\n请结合以上搜索结果回答，如果搜索结果不相关就忽略。"
            return user_message + search_context

    return user_message


async def call_ai(user_message: str, chat_history: list = None, use_memory: bool = True, emotion: str = "") -> str:
    """统一 AI 调用，组装系统提示词（非流式）。"""
    system_content = _build_system_prompt(use_memory, emotion)

    # [Skill: 天气] 注入天气信息
    weather = await get_seoul_weather()
    weather_ctx = get_weather_context(weather)
    if weather_ctx:
        system_content += weather_ctx

    final_user_message = await _build_user_message_with_search(user_message)

    # [上下文截断] 防止 KV Cache 溢出
    truncated_history, truncate_info = truncate_chat_history(
        chat_history=chat_history,
        system_prompt=system_content,
        user_message=final_user_message,
        max_tokens=MAX_CONTEXT_TOKENS,
        preserve_system=True,
    )
    if truncate_info['was_truncated']:
        logging.info(
            f"[AI] 上下文已截断: 从 {truncate_info['original_count']} 条 -> "
            f"{truncate_info['truncated_count']} 条, "
            f"tokens: {truncate_info['original_tokens']} -> {truncate_info['final_tokens']}"
        )

    # [AI竞争] 多模型竞争生成最佳回复
    try:
        from characters.ai_compete import compete_reply
        content = await compete_reply(
            system_prompt=system_content,
            user_message=final_user_message,
            chat_history=truncated_history,
        )
        content = humanize_text(content)
        return content
    except Exception as e:
        logging.warning(f"[AI] 竞争模式失败，fallback 单模型: {e}")

    # fallback: 使用统一的 AI 调用模块
    try:
        content = await ai_client_call_ai(
            system_prompt=system_content,
            user_message=final_user_message,
            chat_history=truncated_history,
        )
        content = humanize_text(content)
        return content
    except Exception as e:
        logging.error(f"[AI] OpenRouter 调用失败: {type(e).__name__}: {e}")

    logging.error("[AI] 所有OpenRouter模型都失败了")

    # [Skill: gemini] 所有OpenRouter模型失败时，fallback到Gemini
    logging.info("[Skill: gemini] 尝试使用Gemini作为fallback...")
    try:
        gemini_result = await call_gemini(user_message)
        if gemini_result:
            gemini_result = humanize_text(gemini_result)
            logging.info("[Skill: gemini] Gemini fallback成功")
                return gemini_result
        except Exception as e:
            logging.error(f"[Skill: gemini] Gemini fallback失败: {e}")

    return "...（低头不说话）"


async def call_ai_stream(
    user_message: str,
    chat_history: list = None,
    use_memory: bool = True,
    emotion: str = "",
    on_chunk: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> str:
    """流式 AI 调用，支持打字机效果输出。

    Args:
        user_message: 用户消息
        chat_history: 对话历史
        use_memory: 是否使用记忆
        emotion: 情绪状态
        on_chunk: 回调函数，每当收到新 chunk 时调用，参数为当前完整文本
        should_stop: 可选的停止检查函数，返回 True 时中断流式输出

    Returns:
        完整的 AI 回复文本
    """
    system_content = _build_system_prompt(use_memory, emotion)

    # [Skill: 天气] 注入天气信息
    weather = await get_seoul_weather()
    weather_ctx = get_weather_context(weather)
    if weather_ctx:
        system_content += weather_ctx

    final_user_message = await _build_user_message_with_search(user_message)

    # [上下文截断] 防止 KV Cache 溢出
    truncated_history, truncate_info = truncate_chat_history(
        chat_history=chat_history,
        system_prompt=system_content,
        user_message=final_user_message,
        max_tokens=MAX_CONTEXT_TOKENS,
        preserve_system=True,
    )
    if truncate_info['was_truncated']:
        logging.info(
            f"[AI Stream] 上下文已截断: 从 {truncate_info['original_count']} 条 -> "
            f"{truncate_info['truncated_count']} 条"
        )

    # 使用流式 API 调用
    try:
        content = await stream_chat_completion(
            system_prompt=system_content,
            user_message=final_user_message,
            chat_history=truncated_history,
            on_chunk=on_chunk,
            should_stop=should_stop,
        )
        content = humanize_text(content)
        return content
    except Exception as e:
        logging.error(f"[AI] 流式调用失败: {type(e).__name__}: {e}")
        # fallback 到非流式调用
        logging.info("[AI] 流式调用失败，fallback 到非流式调用")
        return await call_ai(user_message, chat_history, use_memory, emotion)


async def summarize_and_save_memory(chat_id: int):
    history = get_history(chat_id)
    if len(history) < 4:
        return

    recent = history[-10:]
    conversation_text = "\n".join([f"{'明' if m['role']=='user' else '车如云'}: {m['content']}" for m in recent])

    prompt = f"""请从以下对话中提取1-2条值得长期记住的关键信息，用简短的句子描述。
只提取关于学长的偏好、重要事件、情感变化、约定等信息。
如果没有值得记住的信息，回复"无"。

对话：
{conversation_text}

请直接输出记忆内容，每条一行，不要加序号或其他格式："""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是记忆提取助手，只提取关键信息，保持简洁。"},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 100,
                    "temperature": 0.3,
                },
            )
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()

            if content and content != "无":
                for line in content.split("\n"):
                    line = line.strip().lstrip("-•· ").strip()
                    if line and len(line) > 3:
                        save_memory_entry(line)
    except Exception as e:
        logging.error(f"记忆提取失败: {e}")
