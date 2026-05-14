"""
AI 竞争模块 - v1.4.12.13
规则引擎 + 按需互评 + Qdrant 缓存 + 超时熔断

流程：
1. Qdrant 缓存（命中直接返回）
2. 3个模型并行生成
3. 本地规则引擎评分（<1ms，角色扮演专属规则）
4. 只剩1个合规 → 直接用
   ≥2个合规 → 随机抽1个当评委二选一
   全部淘汰 → 按权重随机选（降级）
5. 更新权重 + 缓存
"""

import json
import logging
import os
import random
import re
import time
import asyncio
from typing import Dict, List, Optional, Tuple

from system.config import DATA_DIR, AI_MODELS

logger = logging.getLogger(__name__)

# 所有模型（从 config 导入，与全局保持同步）
ALL_MODELS = AI_MODELS

# 轮换计数器
_rotate_counter = 0

# 权重持久化文件
WEIGHTS_FILE = os.path.join(DATA_DIR, "ai_weights.json")

# 缓存配置
CACHE_SIMILARITY_THRESHOLD = 0.92

# 超时配置（秒）
MODEL_TIMEOUT = 30.0
JUDGE_TIMEOUT = 20.0
TOTAL_TIMEOUT = 60.0

# ============================================================
# 规则引擎（本地执行，从角色配置加载规则）
# ============================================================

# 提示词泄露关键词（全局一票否决，所有角色通用）
LEAK_KEYWORDS = [
    'respond as', 'following the style', 'we need to respond',
    'calling user', 'system prompt', 'you are a', 'as an ai',
    'i need to', 'i should respond', 'according to the',
]

# 默认规则（当角色没有配置 ai_rules 时使用）
DEFAULT_RULES = {
    "max_length": 100,
    "max_length_penalty": 25,
    "require_ellipsis": False,
    "require_action_parentheses": False,
    "disqualify_positive_emotions": False,
    "positive_emotions": [],
    "disallow_emoji": False,
    "max_punctuation_marks": 5,
    "min_cjk_ratio": 0.0,
    "languages": ["zh", "en"],
    "judge_prompt_extra": "",
}


def _load_character_rules() -> dict:
    """从当前角色的 config.json 加载 ai_rules"""
    try:
        from characters import get_current_character
        character = get_current_character()
        if character and hasattr(character, 'config') and character.config:
            rules = getattr(character.config, 'ai_rules', None)
            if rules and isinstance(rules, dict):
                return rules
    except Exception as e:
        logger.debug(f"[规则引擎] 加载角色规则失败: {e}")
    return DEFAULT_RULES


def _rule_engine_score(reply: str) -> Tuple[float, bool]:
    """
    本地规则引擎评分。从当前角色配置加载规则。
    返回 (分数, 是否被淘汰)。
    """
    if not reply:
        return 0, True

    rules = _load_character_rules()
    score = 100.0
    disqualified = False

    # --- 全局一票否决：提示词泄露 ---
    reply_lower = reply.lower()
    if any(kw in reply_lower for kw in LEAK_KEYWORDS):
        logger.debug("[规则引擎] 淘汰: 提示词泄露")
        return 0, True

    # --- 角色规则：正面情感一票否决 ---
    if rules.get("disqualify_positive_emotions"):
        positive_list = rules.get("positive_emotions", [])
        if any(expr in reply for expr in positive_list):
            logger.debug("[规则引擎] 淘汰: 直接正面情感")
            return 0, True

    # --- 扣分规则（大幅放宽，只淘汰最差回复） ---

    # 长度：仅对超长回复一票否决
    max_len = rules.get("max_length", 100)
    length = len(reply)
    if length > max_len * 2:
        logger.debug("[规则引擎] 淘汰: 回复过长")
        return 0, True
    elif length > max_len:
        score -= rules.get("max_length_penalty", 25)
    elif length < 3:
        score -= 10

    # 格式：省略号和括号动作（不淘汰，只影响分数）
    has_ellipsis = reply.strip().startswith('...')
    has_action = bool(re.search(r'[（(].+?[）)]', reply))
    require_ellipsis = rules.get("require_ellipsis", False)
    require_action = rules.get("require_action_parentheses", False)

    if require_ellipsis and not has_ellipsis:
        score -= 10
    if require_action and not has_action:
        score -= 5

    # CJK 占比（只淘汰完全无 CJK 的长回复）
    if length > 20:
        allowed_langs = rules.get("languages", ["zh", "en"])
        cjk_chars = 0
        if "zh" in allowed_langs:
            cjk_chars += sum(1 for c in reply if '\u4e00' <= c <= '\u9fff')
        if "ko" in allowed_langs:
            cjk_chars += sum(1 for c in reply if '\uAC00' <= c <= '\uD7AF' or '\u1100' <= c <= '\u11FF')
        if "ja" in allowed_langs:
            cjk_chars += sum(1 for c in reply if '\u3040' <= c <= '\u309F' or '\u30A0' <= c <= '\u30FF')

        min_ratio = rules.get("min_cjk_ratio", 0.0)
        if min_ratio > 0 and length > 30:
            cjk_ratio = cjk_chars / length
            if cjk_ratio < min_ratio * 0.5:  # 只在 CJK 极低时淘汰
                logger.debug(f"[规则引擎] 淘汰: CJK 占比过低 ({cjk_ratio:.2f})")
                return 0, True

    # Emoji（不淘汰，只扣分）
    if rules.get("disallow_emoji"):
        emoji_pattern = re.compile(
            '[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
            '\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0000FE00-\U0000FE0F'
            '\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
            '\U00002600-\U000026FF\U00002700-\U000027BF]'
        )
        emoji_count = len(emoji_pattern.findall(reply))
        if emoji_count > 0:
            score -= emoji_count * 3

    # 标点符号过少（不淘汰，但影响分数）
    punct_count = reply.count('！') + reply.count('?') + reply.count('！') + reply.count('？')
    max_punct = rules.get("max_punctuation_marks", 5)
    if punct_count > max_punct:
        score -= 10

    score = max(0, min(100, score))
    return score, False


# ============================================================
# 权重管理
# ============================================================

def _load_weights() -> Dict[str, float]:
    try:
        if os.path.exists(WEIGHTS_FILE):
            with open(WEIGHTS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"[AI竞争] 加载权重失败: {e}")
    return {model: 1.0 for model in ALL_MODELS}


def _save_weights(weights: Dict[str, float]):
    try:
        os.makedirs(os.path.dirname(WEIGHTS_FILE), exist_ok=True)
        with open(WEIGHTS_FILE, 'w') as f:
            json.dump(weights, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[AI竞争] 保存权重失败: {e}")


def update_model_weight(model: str, delta: float = 0.1):
    weights = _load_weights()
    weights[model] = max(0.1, weights.get(model, 1.0) + delta)
    _save_weights(weights)
    logger.info(f"[AI竞争] 权重更新: {model} -> {weights[model]:.2f}")


def get_model_weights() -> Dict[str, float]:
    return _load_weights()


# ============================================================
# 模型调用
# ============================================================

async def _call_single_model(model: str, system_prompt: str, user_message: str,
                              chat_history: Optional[List[Dict]] = None) -> Optional[str]:
    try:
        from characters.ai_client import call_ai
        response = await call_ai(
            system_prompt=system_prompt,
            user_message=user_message,
            chat_history=chat_history,
            model=model,
            temperature=0.85,
            max_tokens=300,
            timeout=MODEL_TIMEOUT,
        )
        return response
    except asyncio.TimeoutError:
        logger.warning(f"[AI竞争] {model} 超时")
        return None
    except Exception as e:
        logger.warning(f"[AI竞争] {model} 失败: {e}")
        return None


# ============================================================
# Qdrant 缓存
# ============================================================

async def _search_cache(user_message: str) -> Optional[str]:
    try:
        from characters.qdrant_memory import QdrantMemoryManager
        mgr = QdrantMemoryManager(collection_prefix="ai_cache")
        results = await mgr.search_memories(user_message, n_results=1)
        if results and results[0].get("distance", 1.0) < (1.0 - CACHE_SIMILARITY_THRESHOLD):
            cached = results[0].get("content", "")
            if cached:
                logger.info(f"[AI竞争] 缓存命中: 相似度 {1.0 - results[0]['distance']:.3f}")
                return cached
    except Exception as e:
        logger.debug(f"[AI竞争] 缓存搜索失败: {e}")
    return None


async def _save_to_cache(user_message: str, best_reply: str, winning_model: str):
    try:
        from characters.qdrant_memory import QdrantMemoryManager
        mgr = QdrantMemoryManager(collection_prefix="ai_cache")
        await mgr.add_memory(
            content=best_reply,
            metadata={
                "user_message_preview": user_message[:100],
                "model": winning_model,
                "type": "ai_competition_cache",
            }
        )
    except Exception as e:
        logger.debug(f"[AI竞争] 缓存保存失败: {e}")


# ============================================================
# 评委（按需触发，二选一）
# ============================================================

async def _judge_binary(user_message: str, reply_a: str, reply_b: str,
                        model_a: str, model_b: str,
                        judge_model: str) -> Optional[str]:
    """评委二选一，返回获胜模型名或 None"""
    rules = _load_character_rules()
    extra = rules.get("judge_prompt_extra", "")

    prompt = f"""你是一个评委，从两个AI回复中选一个更好的。
{extra}

用户说："{user_message[:200]}"

A: {reply_a}
B: {reply_b}

只回复A或B，不要其他内容。"""
    try:
        from characters.ai_client import call_ai
        result = await call_ai(
            system_prompt="你是一个客观的评委，只回复A或B。",
            user_message=prompt,
            model=judge_model,
            temperature=0.3,
            max_tokens=5,
            timeout=JUDGE_TIMEOUT,
        )
        choice = result.strip().upper()
        if choice == 'A':
            logger.info(f"[AI竞争] 评委选 A ({model_a})")
            return model_a
        elif choice == 'B':
            logger.info(f"[AI竞争] 评委选 B ({model_b})")
            return model_b
        else:
            logger.warning(f"[AI竞争] 评委结果无法解析: {choice}")
            return None
    except Exception as e:
        logger.warning(f"[AI竞争] 评比失败: {e}")
        return None


# ============================================================
# 主竞争入口
# ============================================================

async def compete_reply(system_prompt: str, user_message: str,
                        chat_history: Optional[List[Dict]] = None) -> str:
    """
    AI 竞争入口：规则引擎 + 按需互评 + 超时熔断
    """
    global _rotate_counter
    start_time = time.time()

    # 1. 缓存
    cached = await _search_cache(user_message)
    if cached:
        return cached

    # 2. 轮换决定评委
    judge_index = _rotate_counter % len(ALL_MODELS)
    judge_model = ALL_MODELS[judge_index]
    competitor_models = [m for i, m in enumerate(ALL_MODELS) if i != judge_index]
    _rotate_counter += 1

    logger.info(f"[AI竞争] 第{_rotate_counter}轮 | 评委: {judge_model.split('/')[1]} | 参赛: {[m.split('/')[1] for m in competitor_models]}")

    # 3. 并行调用 3 个参赛模型（带总超时熔断）
    try:
        tasks = {
            model: _call_single_model(model, system_prompt, user_message, chat_history)
            for model in competitor_models
        }
        results = await asyncio.wait_for(
            asyncio.gather(*tasks.values(), return_exceptions=True),
            timeout=TOTAL_TIMEOUT - 5  # 留 5 秒给后续流程
        )
    except asyncio.TimeoutError:
        logger.warning(f"[AI竞争] 总超时，使用已返回的结果")
        # 取已完成的
        results = []
        for model in competitor_models:
            try:
                r = await asyncio.wait_for(
                    _call_single_model(model, system_prompt, user_message, chat_history),
                    timeout=1.0
                )
                results.append(r)
            except Exception:
                results.append(None)
        # 如果还是全空，用最快返回的那个
        if not any(r for r in results if r):
            logger.error("[AI竞争] 全部超时")
            return ""

    # 收集回复
    raw_replies = {}
    for model, result in zip(competitor_models, results):
        if isinstance(result, Exception) or not result or len(result.strip()) == 0:
            continue
        raw_replies[model] = result.strip()

    if not raw_replies:
        logger.error("[AI竞争] 所有模型失败")
        return ""

    # 4. 规则引擎评分
    scored = {}  # model -> (score, disqualified, reply)
    for model, reply in raw_replies.items():
        score, disqualified = _rule_engine_score(reply)
        scored[model] = (score, disqualified, reply)
        status = "淘汰" if disqualified else f"{score}分"
        logger.info(f"[规则引擎] {model.split('/')[1]}: {status} | {reply[:40]}...")

    # 分离合格和淘汰的（只淘汰 disqualified=True 的）
    qualified = {m: v for m, v in scored.items() if not v[1]}
    disqualified = {m: v for m, v in scored.items() if v[1]}

    winning_model = None
    best_reply = ""

    if len(qualified) == 0:
        # 全部淘汰 → 降级：按权重从原始回复中随机选
        logger.warning(f"[AI竞争] 全部淘汰，降级选择")
        weights = _load_weights()
        weighted = []
        for model in raw_replies:
            w = weights.get(model, 1.0)
            weighted.extend([model] * max(1, int(w * 10)))
        winning_model = random.choice(weighted)
        best_reply = raw_replies[winning_model]

    elif len(qualified) == 1:
        # 只有1个合格 → 直接用
        winning_model = list(qualified.keys())[0]
        best_reply = qualified[winning_model][2]
        logger.info(f"[AI竞争] 唯一合格: {winning_model.split('/')[1]}")

    else:
        # ≥2个合格 → 按需互评
        # 先按分数排序，取前2个让评委二选一
        sorted_models = sorted(qualified.keys(), key=lambda m: qualified[m][0], reverse=True)
        top_a, top_b = sorted_models[0], sorted_models[1]

        # 检查是否还有时间
        elapsed = time.time() - start_time
        if elapsed < TOTAL_TIMEOUT - JUDGE_TIMEOUT - 2:
            judge_result = await _judge_binary(
                user_message, qualified[top_a][2], qualified[top_b][2],
                top_a, top_b, judge_model
            )
            if judge_result:
                winning_model = judge_result
                best_reply = raw_replies[judge_result]
            else:
                # 评委失败，选分数高的
                winning_model = top_a
                best_reply = qualified[top_a][2]
        else:
            # 时间不够，选分数高的
            logger.warning(f"[AI竞争] 时间不足，跳过互评")
            winning_model = top_a
            best_reply = qualified[top_a][2]

    # 5. 更新权重
    if winning_model:
        update_model_weight(winning_model, 0.1)
        for model in raw_replies:
            if model != winning_model:
                update_model_weight(model, -0.05)

    # 6. 缓存
    if best_reply:
        await _save_to_cache(user_message, best_reply, winning_model or "unknown")

    elapsed = time.time() - start_time
    logger.info(f"[AI竞争] 获胜: {winning_model} | 耗时: {elapsed:.1f}s | 回复: {best_reply[:50]}...")
    return best_reply
