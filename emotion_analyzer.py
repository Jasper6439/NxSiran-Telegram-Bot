"""
恋爱至上主义区域 - 情感分析模块
分析对话内容，计算情感值变化量（好感度/幸福度/觉醒度）
"""
import re
import random
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# ── 情感关键词库 ─────────────────────────────────────────────

# 正面关键词（提升好感度）
AFFECTION_POSITIVE = [
    # 关心
    "关心", "担心", "在意的", "照顾", "保护", "陪伴", "守候",
    # 温暖
    "温暖", "温柔", "开心", "快乐", "幸福", "喜欢", "爱",
    # 认可
    "厉害", "了不起", "优秀", "漂亮", "好看", "可爱",
    # 支持
    "支持", "相信", "信任", "理解", "懂你", "站在你这边",
    # 礼物/行动
    "送你", "给你", "帮你", "为你", "陪你",
    # 亲密称呼
    "如云", "小云", "宝贝", "亲爱的",
]

# 负面关键词（降低好感度）
AFFECTION_NEGATIVE = [
    # 敌意
    "讨厌", "烦", "滚", "闭嘴", "别烦我", "无聊",
    # 背叛
    "骗", "撒谎", "背叛", "利用",
    # 侮辱
    "蠢", "笨", "傻", "丑", "废物",
    # 冷漠
    "无所谓", "不在乎", "随便", "关我什么事",
    # 强迫
    "必须", "逼你", "命令",
]

# 幸福关键词
HAPPINESS_POSITIVE = [
    "一起", "好玩", "有趣", "开心", "快乐", "哈哈", "嘻嘻",
    "好吃", "好看", "漂亮", "礼物", "惊喜", "谢谢",
    "散步", "聊天", "看电影", "吃东西", "旅行",
]

HAPPINESS_NEGATIVE = [
    "难过", "伤心", "哭", "痛苦", "孤独", "寂寞",
    "害怕", "恐惧", "焦虑", "压力", "累", "疲惫",
]

# 觉醒关键词（触发自我意识）
AWAKENING_KEYWORDS = [
    # 直接提及游戏/世界
    "游戏", "世界", "剧本", "命运", "改变", "选择",
    "自由", "真实", "虚假", "设定", "角色", "玩家",
    # 哲学/深层
    "意义", "存在", "目的", "为什么", "命运", "未来",
    "可能性", "另一种", "如果",
    # 情感深层
    "真心", "真正的你", "内心", "想法", "感受",
    "不要伪装", "做你自己", "不必坚强",
]

# 觉醒触发短语（高权重）
AWAKENING_PHRASES = [
    "你不是角色", "这个世界不真实", "你可以选择自己的命运",
    "你不必按照剧本生活", "我想改变你的结局",
    "你值得更好的", "你的命运由你自己决定",
    "不要被剧本束缚", "这个世界还有其他可能",
]


class EmotionAnalyzer:
    """情感分析器 - 分析对话内容计算情感值变化"""

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """预编译正则表达式"""
        self.affection_pos_patterns = [re.compile(k) for k in AFFECTION_POSITIVE]
        self.affection_neg_patterns = [re.compile(k) for k in AFFECTION_NEGATIVE]
        self.happiness_pos_patterns = [re.compile(k) for k in HAPPINESS_POSITIVE]
        self.happiness_neg_patterns = [re.compile(k) for k in HAPPINESS_NEGATIVE]
        self.awakening_patterns = [re.compile(k) for k in AWAKENING_KEYWORDS]
        self.awakening_phrases = [re.compile(re.escape(p)) for p in AWAKENING_PHRASES]

    async def analyze(self, character_id: str, user_message: str,
                      ai_response: str, current_emotions: Dict) -> Dict[str, float]:
        """
        分析对话并计算情感值变化
        
        Args:
            character_id: 角色ID
            user_message: 用户消息
            ai_response: AI 回复
            current_emotions: 当前情感值 {affection, happiness, awakening}
            
        Returns:
            情感值变化 {affection: float, happiness: float, awakening: float}
        """
        # 合并用户和AI的消息进行分析

        affection_delta = self._calculate_affection_delta(
            user_message, ai_response, current_emotions.get('affection', 0)
        )
        happiness_delta = self._calculate_happiness_delta(
            user_message, ai_response, current_emotions.get('happiness', 0)
        )
        awakening_delta = self._calculate_awakening_delta(
            user_message, ai_response, current_emotions.get('awakening', 0)
        )

        changes = {
            'affection': round(affection_delta, 1),
            'happiness': round(happiness_delta, 1),
            'awakening': round(awakening_delta, 1),
        }

        logger.debug(
            f"[EmotionAnalyzer] {character_id}: "
            f"affection={changes['affection']:+.1f}, "
            f"happiness={changes['happiness']:+.1f}, "
            f"awakening={changes['awakening']:+.1f}"
        )

        return changes

    def _calculate_affection_delta(self, user_msg: str, ai_response: str,
                                    current_affection: float) -> float:
        """计算好感度变化"""
        delta = 0.0

        # 分析用户消息
        pos_count = sum(1 for p in self.affection_pos_patterns if p.search(user_msg))
        neg_count = sum(1 for p in self.affection_neg_patterns if p.search(user_msg))

        # 基础变化
        delta += pos_count * 2.0
        delta -= neg_count * 3.0

        # 分析 AI 回复中的情感倾向（如果 AI 回复积极，额外加分）
        ai_positive = sum(1 for p in self.affection_pos_patterns if p.search(ai_response))
        if ai_positive >= 2:
            delta += 1.0  # 角色积极回应，关系升温

        # 当前好感度影响变化幅度（低好感时变化更难，高好感时更容易）
        if current_affection < -10:
            delta *= 0.5  # 敌意期，变化减缓
        elif current_affection > 60:
            delta *= 1.2  # 好感期，变化加速

        # 随机波动（±0.5）
        delta += random.uniform(-0.5, 0.5)

        return max(-5.0, min(5.0, delta))

    def _calculate_happiness_delta(self, user_msg: str, ai_response: str,
                                    current_happiness: float) -> float:
        """计算幸福度变化"""
        delta = 0.0

        pos_count = sum(1 for p in self.happiness_pos_patterns if p.search(user_msg))
        neg_count = sum(1 for p in self.happiness_neg_patterns if p.search(user_msg))

        delta += pos_count * 1.5
        delta -= neg_count * 2.0

        # AI 回复分析
        ai_positive = sum(1 for p in self.happiness_pos_patterns if p.search(ai_response))
        if ai_positive >= 1:
            delta += 0.5

        # 幸福度有自然衰减趋势
        delta -= 0.3

        delta += random.uniform(-0.3, 0.3)

        return max(-3.0, min(3.0, delta))

    def _calculate_awakening_delta(self, user_msg: str, ai_response: str,
                                    current_awakening: float) -> float:
        """计算觉醒度变化"""
        delta = 0.0

        # 检查觉醒短语（高权重）
        phrase_count = sum(1 for p in self.awakening_phrases if p.search(user_msg))
        if phrase_count > 0:
            delta += phrase_count * 5.0

        # 检查普通觉醒关键词
        keyword_count = sum(1 for p in self.awakening_patterns if p.search(user_msg))
        delta += keyword_count * 0.8

        # AI 回复中的觉醒迹象
        ai_awakening = sum(1 for p in self.awakening_patterns if p.search(ai_response))
        delta += ai_awakening * 0.3

        # 觉醒度越高，变化越慢（递减效应）
        if current_awakening >= 80:
            delta *= 0.3
        elif current_awakening >= 50:
            delta *= 0.5
        elif current_awakening >= 20:
            delta *= 0.8

        # 觉醒度不会自然增长
        if delta > 0 and keyword_count == 0 and phrase_count == 0:
            delta = 0

        delta += random.uniform(-0.1, 0.1)

        return max(0.0, min(5.0, delta))
