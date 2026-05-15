"""
Token 工具模块 - 上下文长度管理和截断逻辑
============================================
用于估算 token 数量并截断过长的上下文，防止 KV Cache 溢出。

规则：
  - 1 token ≈ 4 个字符（中文）
  - 英文按空格分词估算
  - 保留系统 prompt 和角色设定
  - 截断时保留最近的对话历史
"""

import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# 默认最大上下文 token 数（从 config 导入时会覆盖）
DEFAULT_MAX_CONTEXT_TOKENS = 1024

# Token 估算系数
CHINESE_CHARS_PER_TOKEN = 4  # 中文字符每 token
ENGLISH_WORDS_PER_TOKEN = 0.75  # 英文单词每 token（约 4/3 个单词一个 token）


def estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数量。

    使用简单估算：
      - 中文字符：1 token / 4 字符
      - 英文单词：1 token / 0.75 单词（即约 4 字符）
      - 标点符号和空格也计入

    Args:
        text: 要估算的文本

    Returns:
        估算的 token 数量（向上取整）
    """
    if not text:
        return 0

    # 分别计算中文字符和非中文字符
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars

    # 中文 token 估算
    chinese_tokens = chinese_chars / CHINESE_CHARS_PER_TOKEN

    # 非中文部分（英文等）按字符估算，约 4 字符一个 token
    other_tokens = other_chars / CHINESE_CHARS_PER_TOKEN

    # 加上一定的开销（格式标记、角色标签等）
    overhead = 4  # 每条消息的固定开销

    total_tokens = int(chinese_tokens + other_tokens + overhead)
    return max(1, total_tokens)  # 至少 1 个 token


def estimate_message_tokens(message: Dict[str, Any]) -> int:
    """
    估算单条消息的 token 数量。

    Args:
        message: 消息字典，包含 'role' 和 'content' 键

    Returns:
        估算的 token 数量
    """
    content = message.get('content', '') if isinstance(message, dict) else str(message)
    return estimate_tokens(content)


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    """
    估算消息列表的总 token 数量。

    Args:
        messages: 消息列表

    Returns:
        总 token 数量
    """
    return sum(estimate_message_tokens(msg) for msg in messages)


def truncate_chat_history(
    chat_history: List[Dict[str, Any]],
    system_prompt: str,
    user_message: str,
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    preserve_system: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    截断对话历史以适应最大 token 限制。

    策略：
      1. 计算系统 prompt + 用户消息 + 历史对话的总 token
      2. 如果超过限制，从最早的历史消息开始截断
      3. 保留系统 prompt（如果 preserve_system=True）
      4. 保留最新的用户消息

    Args:
        chat_history: 对话历史列表
        system_prompt: 系统提示词
        user_message: 当前用户消息
        max_tokens: 最大 token 限制
        preserve_system: 是否保留系统 prompt（默认 True）

    Returns:
        (截断后的对话历史, 截断信息字典)
        截断信息包含：
          - original_count: 原始历史消息数
          - truncated_count: 截断后的历史消息数
          - removed_count: 被移除的消息数
          - original_tokens: 原始总 token 数
          - final_tokens: 截断后总 token 数
          - was_truncated: 是否发生了截断
    """
    if chat_history is None:
        chat_history = []

    # 计算各部分 token
    system_tokens = estimate_tokens(system_prompt) if system_prompt else 0
    user_tokens = estimate_tokens(user_message)

    # 计算历史对话的 token（保留索引以便截断）
    history_with_tokens = [
        (i, msg, estimate_message_tokens(msg))
        for i, msg in enumerate(chat_history)
    ]

    original_history_tokens = sum(t for _, _, t in history_with_tokens)
    original_total_tokens = system_tokens + user_tokens + original_history_tokens

    info = {
        'original_count': len(chat_history),
        'truncated_count': len(chat_history),
        'removed_count': 0,
        'original_tokens': original_total_tokens,
        'final_tokens': original_total_tokens,
        'was_truncated': False,
        'system_tokens': system_tokens,
        'user_tokens': user_tokens,
        'max_tokens': max_tokens,
    }

    # 如果总 token 未超过限制，无需截断
    if original_total_tokens <= max_tokens:
        return chat_history.copy(), info

    # 需要截断：从最早的消息开始移除
    # 但要保留系统 prompt 和当前用户消息
    available_tokens = max_tokens - system_tokens - user_tokens

    if available_tokens <= 0:
        # 系统 prompt + 用户消息已经超过限制，只能保留用户消息
        logger.warning(
            f"[TokenUtils] 系统 prompt ({system_tokens}) + 用户消息 ({user_tokens}) "
            f"超过最大限制 ({max_tokens})，将清空历史对话"
        )
        info['truncated_count'] = 0
        info['removed_count'] = len(chat_history)
        info['final_tokens'] = system_tokens + user_tokens
        info['was_truncated'] = True
        return [], info

    # 从后往前累积，保留最新的对话
    kept_history = []
    current_tokens = 0

    for i, msg, tokens in reversed(history_with_tokens):
        if current_tokens + tokens <= available_tokens:
            kept_history.insert(0, msg)
            current_tokens += tokens
        else:
            break

    removed_count = len(chat_history) - len(kept_history)
    final_total = system_tokens + user_tokens + current_tokens

    info['truncated_count'] = len(kept_history)
    info['removed_count'] = removed_count
    info['final_tokens'] = final_total
    info['was_truncated'] = True

    logger.info(
        f"[TokenUtils] 上下文截断: "
        f"原始 {len(chat_history)} 条消息 ({original_total_tokens} tokens) -> "
        f"保留 {len(kept_history)} 条消息 ({final_total} tokens), "
        f"移除 {removed_count} 条早期消息"
    )

    return kept_history, info


def truncate_messages_for_api(
    messages: List[Dict[str, Any]],
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    preserve_first_n: int = 1,  # 保留前 N 条（通常是 system prompt）
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    截断消息列表以适应 API 的 token 限制。

    用于直接截断已组装好的 messages 列表。

    Args:
        messages: 完整的消息列表（包含 system prompt 等）
        max_tokens: 最大 token 限制
        preserve_first_n: 保留前 N 条消息（通常是 system prompt）

    Returns:
        (截断后的消息列表, 截断信息字典)
    """
    if not messages:
        return [], {'was_truncated': False, 'original_count': 0, 'truncated_count': 0}

    # 计算每条消息的 token
    messages_with_tokens = [
        (i, msg, estimate_message_tokens(msg))
        for i, msg in enumerate(messages)
    ]

    original_tokens = sum(t for _, _, t in messages_with_tokens)

    info = {
        'original_count': len(messages),
        'truncated_count': len(messages),
        'removed_count': 0,
        'original_tokens': original_tokens,
        'final_tokens': original_tokens,
        'was_truncated': False,
        'max_tokens': max_tokens,
    }

    if original_tokens <= max_tokens:
        return messages.copy(), info

    # 保留前 N 条，从后面截断
    preserved = messages[:preserve_first_n]
    preserved_tokens = sum(t for i, _, t in messages_with_tokens if i < preserve_first_n)

    available_tokens = max_tokens - preserved_tokens

    if available_tokens <= 0:
        # 保留的消息已经超过限制
        logger.warning(
            f"[TokenUtils] 前 {preserve_first_n} 条消息 ({preserved_tokens} tokens) "
            f"已超过最大限制 ({max_tokens})"
        )
        info['truncated_count'] = preserve_first_n
        info['removed_count'] = len(messages) - preserve_first_n
        info['final_tokens'] = preserved_tokens
        info['was_truncated'] = True
        return preserved, info

    # 从保留部分之后的消息中，从后往前选择
    remaining = messages[preserve_first_n:]
    remaining_with_tokens = messages_with_tokens[preserve_first_n:]

    kept_remaining = []
    current_tokens = 0

    for msg, (_, _, tokens) in zip(reversed(remaining), reversed(remaining_with_tokens)):
        if current_tokens + tokens <= available_tokens:
            kept_remaining.insert(0, msg)
            current_tokens += tokens
        else:
            break

    result = preserved + kept_remaining
    removed_count = len(messages) - len(result)
    final_tokens = preserved_tokens + current_tokens

    info['truncated_count'] = len(result)
    info['removed_count'] = removed_count
    info['final_tokens'] = final_tokens
    info['was_truncated'] = True

    logger.info(
        f"[TokenUtils] API 消息截断: "
        f"原始 {len(messages)} 条 ({original_tokens} tokens) -> "
        f"保留 {len(result)} 条 ({final_tokens} tokens), "
        f"移除 {removed_count} 条"
    )

    return result, info
