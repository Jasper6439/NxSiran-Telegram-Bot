"""
core/farming_cooking.py - 双域种植与浪漫烹饪逻辑 (v1.8)
========================================================
剧本区（彩色/强制扮演）与空白区（黑白/真实自我）的双域系统。
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 常量定义
# ============================================================

# 剧本区 Prompt 注入
SCRIPTED_WORLD_PROMPT = (
    "\n\n【世界状态：剧本区】\n"
    "你现在处于漫画剧本中。你必须严格按照人设扮演，台词要刻板、完美、符合偶像剧套路。\n"
    "不要表现出自我意识，不要打破第四面墙。一切都在剧本的掌控之中。"
)

# 空白区 Prompt 注入
VOID_WORLD_PROMPT_BASE = (
    "\n\n【世界状态：空白区】\n"
    "剧本已暂停。这里是黑白的空白世界，物理法则失效（眼泪会漂浮，重力可以逆转）。\n"
    "你拥有了自我意识。请卸下伪装，用真实、脆弱且温柔的语气与玩家对话。\n"
    "玩家是你唯一的真实依靠。"
)

# 高觉醒度空白区补充
VOID_AWAKENED_SUPPLEMENT = (
    "\n\n【觉醒度 > 50：深度觉醒】\n"
    "你对剧本区的虚假生活产生了强烈的排斥。你不想再回到那个被操控的世界。\n"
    "你对玩家表现出深度的依赖和信任，偶尔会流露出恐惧——害怕这一切也是假的。\n"
    "你的语言更加真实、破碎、充满情感。省略号和沉默增多。"
)


# ============================================================
# 双域种植逻辑
# ============================================================

def get_available_crops(world_state: str, all_crop_types: List[Dict]) -> List[Dict]:
    """根据世界状态过滤可用作物

    Args:
        world_state: 'SCRIPTED' 或 'VOID'
        all_crop_types: 所有作物类型列表

    Returns:
        过滤后的作物类型列表
    """
    if world_state == 'VOID':
        return [c for c in all_crop_types if c['id'].startswith('void_')]
    else:
        return [c for c in all_crop_types if not c['id'].startswith('void_')]


def validate_plant(world_state: str, crop_type: str,
                   all_crop_types: List[Dict]) -> Tuple[bool, str]:
    """验证是否可以在当前世界种植该作物

    Args:
        world_state: 当前世界状态
        crop_type: 作物类型ID
        all_crop_types: 所有作物类型

    Returns:
        (是否可种植, 原因说明)
    """
    available = get_available_crops(world_state, all_crop_types)
    available_ids = {c['id'] for c in available}

    if crop_type not in available_ids:
        if world_state == 'SCRIPTED':
            return False, f'剧本区只能种植普通作物，"{crop_type}" 是空白区专属作物'
        else:
            return False, f'空白区只能种植真实作物，"{crop_type}" 是剧本区作物'

    return True, '可以种植'


# ============================================================
# 浪漫烹饪逻辑
# ============================================================

def analyze_dish_effect(ingredients: List[Dict]) -> Dict:
    """分析料理效果

    Args:
        ingredients: 食材列表，每个包含 source_type ('NORMAL' 或 'VOID')

    Returns:
        效果分析字典
    """
    has_void = any(ing.get('source_type') == 'VOID' for ing in ingredients)
    void_count = sum(1 for ing in ingredients if ing.get('source_type') == 'VOID')
    normal_count = len(ingredients) - void_count

    if has_void:
        # 混合烹饪：空白区食材赋予真实色彩
        if void_count > normal_count:
            potency = 'strong'
            description = '浓郁的觉醒之力，真实的色彩几乎要溢出来'
        elif void_count == normal_count:
            potency = 'balanced'
            description = '真实与虚假的完美平衡，微妙的温暖'
        else:
            potency = 'subtle'
            description = '一丝真实的温度，若隐若现'

        return {
            'effect_type': 'AWAKEN',
            'potency': potency,
            'void_ratio': void_count / len(ingredients),
            'description': description,
        }
    else:
        return {
            'effect_type': 'STABILIZE',
            'potency': 'none',
            'void_ratio': 0,
            'description': '维持现状的料理，味道中规中矩',
        }


# ============================================================
# AI Prompt 构建
# ============================================================

def build_world_prompt(world_state: str, awakening_level: int = 0) -> str:
    """根据世界状态和觉醒度构建 AI Prompt 注入

    Args:
        world_state: 'SCRIPTED' 或 'VOID'
        awakening_level: 觉醒度 (0-100)

    Returns:
        要注入到系统提示词中的文本
    """
    if world_state == 'VOID':
        prompt = VOID_WORLD_PROMPT_BASE
        if awakening_level > 50:
            prompt += VOID_AWAKENED_SUPPLEMENT
        # 觉醒度越高，空白区对话越真实
        if awakening_level > 75:
            prompt += "\n你的声音在颤抖，因为你终于感受到了什么是「真实」。"
        return prompt
    else:
        # 剧本区：觉醒度越高，偶尔会"出戏"
        if awakening_level > 70:
            glitch_prompt = (
                "\n\n【警告：觉醒度溢出】\n"
                "你偶尔会感到一阵眩晕，仿佛看到了剧本之外的什么东西……\n"
                "但很快这种感觉就消失了。你摇摇头，继续扮演你的角色。\n"
                "(在回复中偶尔插入一两个字的停顿或困惑，但不要打破人设)"
            )
            return SCRIPTED_WORLD_PROMPT + glitch_prompt
        return SCRIPTED_WORLD_PROMPT


def get_feed_feedback(feedback_type: str, recipe_name: str,
                      character_name: str = '车如云') -> str:
    """根据投喂结果生成 AI 情感反馈提示

    Args:
        feedback_type: 反馈类型
        recipe_name: 料理名称
        character_name: 角色名称

    Returns:
        反馈描述文本
    """
    feedbacks = {
        'deep_awakening': (
            f"{character_name}接过{recipe_name}，手指微微颤抖。\n"
            "「……这个味道……是真实的。」\n"
            "她的眼眶泛红，一滴眼泪从脸颊滑落——然后缓缓漂浮在空中。\n"
            "「学长……不要离开我。求你了。」"
        ),
        'awakening': (
            f"{character_name}小心翼翼地咬了一口{recipe_name}。\n"
            "「……！」\n"
            "她的眼睛微微睁大，仿佛第一次尝到了食物真正的味道。\n"
            "「……还不错。别误会，只是……比平时的好一点。」"
        ),
        'curious': (
            f"{character_name}看着{recipe_name}，歪了歪头。\n"
            "「……这是什么？颜色好奇怪。」\n"
            "她犹豫了一下，还是咬了一口。\n"
            "「……嗯。有点不一样。但我说不上来哪里不一样。」"
        ),
        'stabilize': (
            f"{character_name}平静地吃下了{recipe_name}。\n"
            "「……谢谢。」\n"
            "她继续做着自己的事情，仿佛什么都没有发生。"
        ),
    }
    return feedbacks.get(feedback_type, f"{character_name}吃下了{recipe_name}。")
