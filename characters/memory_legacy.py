"""
旧版 JSON 记忆系统
==================
从 bot.py 提取的记忆相关函数：
  - 长期记忆（JSON 文件存储）
  - 语义记忆（关键词匹配 + jieba 分词）
  - 自我改进（纠正记录）
  - 文本人性化处理
"""

import re
import os
import logging
from datetime import datetime

from config import (
    DATA_DIR, YOUR_CHAT_ID,
    SEMANTIC_MEMORY_FILE, get_default_tz,
    get_user_memory_file, save_json, load_json, _migrate_user_data,
)
from prompts import AI_PATTERN_REPLACEMENTS, MEMORY_CATEGORIES

# ============================================================
# [Skill: self-improving] 自我改进系统
# ============================================================

# 纠正记录文件
CORRECTIONS_FILE = os.path.join(DATA_DIR, "corrections.json")

# 纠正检测关键词
CORRECTION_KEYWORDS = [
    "不对", "不是", "别说", "不要这样", "你应该",
    "叫你", "跟你说过", "错了", "笨", "才不是", "我不是",
    "不是这样的", "你搞错了", "说过了", "别这样",
    "你能不能", "都说了", "跟你讲过", "怎么又",
]


def humanize_text(text: str) -> str:
    """对 AI 回复进行人性化后处理，去除机械感"""
    if not text:
        return text

    result = text

    # 逐条应用替换规则
    for pattern, replacement in AI_PATTERN_REPLACEMENTS:
        result = re.sub(pattern, replacement, result)

    # 清理多余空格和空行
    result = re.sub(r'  +', ' ', result)           # 多个空格变一个
    result = re.sub(r'\n{3,}', '\n\n', result)      # 多个空行变两个
    result = re.sub(r'[ \t]+\n', '\n', result)      # 行尾空格去掉

    # 去掉开头/结尾的空白
    result = result.strip()

    # 如果处理后为空，返回默认回复
    if not result:
        return "..."

    return result


def detect_correction(user_text: str) -> bool:
    """检测用户消息是否包含纠正内容"""
    if not user_text:
        return False
    return any(kw in user_text for kw in CORRECTION_KEYWORDS)


def learn_from_correction(user_text: str, bot_response: str):
    """将纠正记录保存到文件，用于后续改进"""
    corrections = load_json(CORRECTIONS_FILE, [])
    entry = {
        "user_said": user_text,
        "bot_said": bot_response,
        "timestamp": datetime.now(get_default_tz()).isoformat(),
    }
    corrections.append(entry)
    # 只保留最近 100 条纠正记录
    if len(corrections) > 100:
        corrections = corrections[-100:]
    save_json(CORRECTIONS_FILE, corrections)
    logging.info(f"[自我改进] 记录纠正: {user_text[:30]}...")


def get_learned_count() -> int:
    """获取已学习的纠正数量"""
    return len(load_json(CORRECTIONS_FILE, []))


# ============================================================
# [Skill: semantic-memory] 语义记忆系统
# ============================================================

def save_semantic_memory(key: str, value: str, category: str = "personal"):
    """保存语义记忆条目"""
    memories = load_json(SEMANTIC_MEMORY_FILE, [])
    # 检查是否已存在相同 key 的记忆，如果存在则更新
    for m in memories:
        if m.get("key") == key:
            m["value"] = value
            m["category"] = category
            m["timestamp"] = datetime.now(get_default_tz()).isoformat()
            m["access_count"] = m.get("access_count", 0) + 1
            save_json(SEMANTIC_MEMORY_FILE, memories)
            logging.info(f"[语义记忆] 更新记忆: {key} = {value}")
            return
    # 新增记忆
    entry = {
        "key": key,
        "value": value,
        "category": category,
        "timestamp": datetime.now(get_default_tz()).isoformat(),
        "access_count": 0,
    }
    memories.append(entry)
    # 最多保留 200 条
    if len(memories) > 200:
        memories = memories[-200:]
    save_json(SEMANTIC_MEMORY_FILE, memories)
    logging.info(f"[语义记忆] 保存新记忆: {key} = {value}")


def search_semantic_memory(query: str, topk: int = 5) -> list:
    """搜索语义记忆，使用关键词匹配 + jieba 分词（如果可用）"""
    memories = load_json(SEMANTIC_MEMORY_FILE, [])
    if not memories or not query:
        return []

    # 尝试使用 jieba 分词
    query_tokens = set()
    try:
        import jieba
        query_tokens = set(jieba.cut(query))
        query_tokens.discard(" ")
        query_tokens = {t for t in query_tokens if len(t) > 1}
    except ImportError:
        # jieba 不可用，直接用字符匹配
        query_tokens = set()
        for i in range(len(query)):
            for j in range(i + 2, min(i + 5, len(query) + 1)):
                query_tokens.add(query[i:j])

    # 计算每条记忆的相关度分数
    scored = []
    for m in memories:
        key = m.get("key", "")
        value = m.get("value", "")
        combined = f"{key} {value}"
        score = 0

        # 关键词匹配
        for token in query_tokens:
            if token in key:
                score += 3  # key 匹配权重更高
            if token in value:
                score += 1
            if token in combined:
                score += 0.5

        # 完整查询字符串匹配
        if query in key:
            score += 5
        if query in value:
            score += 2

        if score > 0:
            scored.append((m, score))

    # 按分数排序
    scored.sort(key=lambda x: x[1], reverse=True)

    # 更新 access_count
    results = []
    for m, score in scored[:topk]:
        m["access_count"] = m.get("access_count", 0) + 1
        results.append(m)

    # 保存更新后的 access_count
    if results:
        save_json(SEMANTIC_MEMORY_FILE, memories)

    return results


def delete_semantic_memory(keyword: str) -> int:
    """删除包含关键词的语义记忆，返回删除数量"""
    memories = load_json(SEMANTIC_MEMORY_FILE, [])
    original_count = len(memories)
    memories = [m for m in memories if keyword not in m.get("key", "") and keyword not in m.get("value", "")]
    deleted = original_count - len(memories)
    if deleted > 0:
        save_json(SEMANTIC_MEMORY_FILE, memories)
        logging.info(f"[语义记忆] 删除了 {deleted} 条包含 '{keyword}' 的记忆")
    return deleted


def get_semantic_memory_context() -> str:
    """获取语义记忆上下文，用于注入系统提示词"""
    memories = load_json(SEMANTIC_MEMORY_FILE, [])
    if not memories:
        return ""

    # 按分类整理
    categories = {}
    for m in memories:
        cat = m.get("category", "其他")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f"{m['key']}: {m['value']}")

    parts = []
    for cat, items in categories.items():
        if items:
            parts.append(f"[{cat}] " + "；".join(items[-10:]))

    return "\n".join(parts)


def parse_memory_tags(text: str) -> list:
    """从 AI 回复中解析 [MEMORY:key:value] 标记"""
    pattern = r'\[MEMORY:([^:]+):([^\]]+)\]'
    matches = re.findall(pattern, text)
    return matches  # 返回 [(key, value), ...]


# ============================================================
# [Skill: 增强记忆] 记忆分类系统
# ============================================================

def categorize_memory(text: str) -> str:
    """为记忆条目分类"""
    for category, keywords in MEMORY_CATEGORIES.items():
        if any(kw in text for kw in keywords):
            return category
    return "其他"


def get_categorized_memory(user_id=None) -> str:
    """获取分类后的记忆文本"""
    if user_id is None:
        user_id = YOUR_CHAT_ID or 1
    _migrate_user_data(user_id)
    memories = load_json(get_user_memory_file(user_id), [])
    if not memories:
        return ""

    categorized = {}
    for m in memories:
        cat = categorize_memory(m)
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(m)

    parts = []
    for cat, items in categorized.items():
        if items:
            parts.append(f"[{cat}] " + "；".join(items[-10:]))  # 每类最多10条

    return "\n".join(parts)


def get_long_term_memory(user_id=None) -> str:
    """获取分类后的长期记忆"""
    return get_categorized_memory(user_id)


def save_memory_entry(entry: str, user_id=None):
    """保存一条长期记忆"""
    if user_id is None:
        user_id = YOUR_CHAT_ID or 1
    _migrate_user_data(user_id)
    memories = load_json(get_user_memory_file(user_id), [])
    if entry not in memories:
        memories.append(entry)
        if len(memories) > 50:
            memories = memories[-50:]
        save_json(get_user_memory_file(user_id), memories)
        logging.info(f"长期记忆已保存: {entry[:30]}...")
