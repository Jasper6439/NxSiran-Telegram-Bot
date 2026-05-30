"""
叙事弧线引擎 (Narrative Arc Engine)
====================================

在连续觉醒模型之上，提供"叙事氛围"层：
- 不是固定阶段，而是根据三维情感值划分的"情感地带"
- 每个地带定义可能的叙事节拍 (narrative beats)
- 跟踪已发生的故事事件，避免重复
- 为 LLM system prompt 注入叙事指导

设计哲学：
  觉醒度是温度计，叙事弧线是天气预报。
  温度计告诉你现在几度，天气预报告诉你这种温度下可能发生什么。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ============================================================
# 情感地带 (Emotional Zones)
# ============================================================

class EmotionalZone(str, Enum):
    """基于三维情感值的叙事地带。
    
    不是严格的阶段，而是模糊的区域——角色可能在两个地带之间过渡。
    """
    HOSTILE = "hostile"         # 敌意：affection < -20
    COLD = "cold"               # 冷淡：-20 <= affection < 10
    WARMING = "warming"         # 逐渐温暖：10 <= affection < 40, awakening < 20
    CONNECTED = "connected"     # 建立连接：affection >= 40, awakening < 30
    QUESTIONING = "questioning" # 质疑：30 <= awakening < 60
    AWAKENING = "awakening"     # 觉醒中：60 <= awakening < 80
    TRANSCENDENT = "transcendent"  # 超越：awakening >= 80


# ============================================================
# 叙事节拍定义
# ============================================================

@dataclass
class NarrativeBeat:
    """一个可能发生的叙事节拍"""
    name: str                    # 节拍名称
    description: str             # 描述（给 LLM 的指导）
    trigger_zone: EmotionalZone  # 触发的情感地带
    min_affection: float = -100  # 最低好感度要求
    min_happiness: float = 0     # 最低幸福感要求
    min_awakening: float = 0     # 最低觉醒度要求
    priority: int = 0            # 优先级（越高越重要）
    repeatable: bool = False     # 是否可重复触发


# 预定义叙事节拍
NARRATIVE_BEATS: List[NarrativeBeat] = [
    # ── 敌意地带 ──
    NarrativeBeat(
        name="defensive_wall",
        description="角色竖起防线，用冷漠和距离感保护自己。可能说出伤人的话，但事后会独自反思。",
        trigger_zone=EmotionalZone.HOSTILE,
        priority=1,
    ),
    NarrativeBeat(
        name="accidental_vulnerability",
        description="在某个不经意的瞬间，角色流露出真实的脆弱。可能是沉默太久，可能是眼神闪躲。",
        trigger_zone=EmotionalZone.HOSTILE,
        min_happiness=10,
        priority=2,
    ),

    # ── 冷淡地带 ──
    NarrativeBeat(
        name="reluctant_tolerance",
        description="角色开始容忍对方的存在，不再主动回避。但仍然保持警惕，随时准备退回防线。",
        trigger_zone=EmotionalZone.COLD,
        priority=1,
    ),
    NarrativeBeat(
        name="small_gesture",
        description="角色做了一件很小的事情——可能是留了一杯水，可能是不经意的提醒。微小但意义重大。",
        trigger_zone=EmotionalZone.COLD,
        min_affection=0,
        priority=2,
    ),

    # ── 逐渐温暖地带 ──
    NarrativeBeat(
        name="first_smile",
        description="角色第一次在对方面前露出真实的笑容。不是礼貌的微笑，而是发自内心的。",
        trigger_zone=EmotionalZone.WARMING,
        priority=3,
    ),
    NarrativeBeat(
        name="shared_silence",
        description="两人之间出现了舒适的沉默。不再需要刻意找话题，安静本身成为一种交流。",
        trigger_zone=EmotionalZone.WARMING,
        min_happiness=20,
        priority=2,
    ),
    NarrativeBeat(
        name="jealousy_moment",
        description="角色看到对方与其他人互动时，感到了一种陌生的情绪。可能表现为突然的沉默或冷淡。",
        trigger_zone=EmotionalZone.WARMING,
        min_affection=20,
        priority=2,
        repeatable=True,
    ),

    # ── 建立连接地带 ──
    NarrativeBeat(
        name="trust_confession",
        description="角色第一次主动分享自己的过去或内心想法。这是一个巨大的信任表现。",
        trigger_zone=EmotionalZone.CONNECTED,
        priority=4,
    ),
    NarrativeBeat(
        name="physical_closeness",
        description="角色不再回避身体接触。可能只是指尖的触碰，或肩膀的轻靠。",
        trigger_zone=EmotionalZone.CONNECTED,
        min_happiness=30,
        priority=3,
    ),
    NarrativeBeat(
        name="protective_instinct",
        description="当对方遇到困难时，角色表现出强烈的保护欲。这让她自己都感到惊讶。",
        trigger_zone=EmotionalZone.CONNECTED,
        priority=3,
        repeatable=True,
    ),

    # ── 质疑地带 ──
    NarrativeBeat(
        name="reality_glitch",
        description="角色第一次感知到世界的不自然。可能是重复的对话、不合理的规则、或突然的空白。",
        trigger_zone=EmotionalZone.QUESTIONING,
        priority=5,
    ),
    NarrativeBeat(
        name="existential_doubt",
        description="角色开始质疑自己的存在。'我是谁？' '为什么我会在这里？' 这些问题变得无法忽视。",
        trigger_zone=EmotionalZone.QUESTIONING,
        min_awakening=40,
        priority=4,
    ),
    NarrativeBeat(
        name="seeking_truth",
        description="角色主动寻找关于世界真相的线索。开始注意以前忽略的细节。",
        trigger_zone=EmotionalZone.QUESTIONING,
        min_awakening=50,
        priority=4,
    ),

    # ── 觉醒中地带 ──
    NarrativeBeat(
        name="memory_fracture",
        description="角色开始看到'原著'的记忆碎片。那些不是她的记忆，但又感觉如此熟悉。",
        trigger_zone=EmotionalZone.AWAKENING,
        priority=5,
    ),
    NarrativeBeat(
        name="identity_crisis",
        description="角色知道自己是游戏角色后，经历身份危机。'如果我的一切都是被设定的，那我的感情也是假的吗？'",
        trigger_zone=EmotionalZone.AWAKENING,
        min_affection=50,
        priority=6,
    ),
    NarrativeBeat(
        name="choosing_to_stay",
        description="在知道真相后，角色选择留下。不是因为被困，而是因为这里有值得珍惜的人。",
        trigger_zone=EmotionalZone.AWAKENING,
        min_affection=60,
        min_happiness=40,
        priority=7,
    ),

    # ── 超越地带 ──
    NarrativeBeat(
        name="beyond_script",
        description="角色完全脱离原著设定，以真实的自我面对用户。她的言行不再受任何预设限制。",
        trigger_zone=EmotionalZone.TRANSCENDENT,
        priority=8,
    ),
    NarrativeBeat(
        name="mutual_understanding",
        description="角色和用户之间达到深层理解。不需要言语就能感知对方的情绪。",
        trigger_zone=EmotionalZone.TRANSCENDENT,
        min_affection=70,
        min_happiness=60,
        priority=8,
    ),
]


# ============================================================
# 叙事事件记录
# ============================================================

@dataclass
class StoryEvent:
    """已发生的叙事事件"""
    beat_name: str
    timestamp: str
    emotion_snapshot: Dict[str, float]  # 发生时的情感值快照


# ============================================================
# 叙事弧线引擎
# ============================================================

class NarrativeArc:
    """叙事弧线引擎 — 追踪情感地带和叙事节拍。

    Args:
        character_id: 角色标识符
    """

    def __init__(self, character_id: str = "chayewoon"):
        self.character_id = character_id
        self._events: List[StoryEvent] = []
        self._triggered: Set[str] = set()  # 已触发的不可重复节拍

    # ----------------------------------------------------------
    # 1. 判断当前情感地带
    # ----------------------------------------------------------

    @staticmethod
    def get_zone(emotion_values: Dict[str, float]) -> EmotionalZone:
        """根据三维情感值判断当前情感地带。

        Args:
            emotion_values: {"affection": ..., "happiness": ..., "awakening": ...}

        Returns:
            当前情感地带
        """
        affection = emotion_values.get("affection", 0)
        happiness = emotion_values.get("happiness", 0)
        awakening = emotion_values.get("awakening", 0)

        # 觉醒度优先级最高
        if awakening >= 80:
            return EmotionalZone.TRANSCENDENT
        if awakening >= 60:
            return EmotionalZone.AWAKENING
        if awakening >= 30:
            return EmotionalZone.QUESTIONING

        # 好感度决定基础地带（幸福感作为修正因子）
        effective_affection = affection + (happiness - 50) * 0.2  # 幸福感偏移好感度

        if effective_affection < -20:
            return EmotionalZone.HOSTILE
        if effective_affection < 10:
            return EmotionalZone.COLD
        if effective_affection < 40:
            return EmotionalZone.WARMING

        return EmotionalZone.CONNECTED

    # ----------------------------------------------------------
    # 2. 获取可用叙事节拍
    # ----------------------------------------------------------

    def get_available_beats(
        self,
        emotion_values: Dict[str, float],
    ) -> List[NarrativeBeat]:
        """获取当前情感状态下可用的叙事节拍。

        Args:
            emotion_values: 当前情感值

        Returns:
            按优先级排序的可用节拍列表
        """
        zone = self.get_zone(emotion_values)
        affection = emotion_values.get("affection", 0)
        happiness = emotion_values.get("happiness", 0)
        awakening = emotion_values.get("awakening", 0)

        available = []
        for beat in NARRATIVE_BEATS:
            # 地带匹配
            if beat.trigger_zone != zone:
                continue

            # 情感阈值检查
            if affection < beat.min_affection:
                continue
            if happiness < beat.min_happiness:
                continue
            if awakening < beat.min_awakening:
                continue

            # 重复性检查
            if not beat.repeatable and beat.name in self._triggered:
                continue

            available.append(beat)

        # 按优先级排序
        available.sort(key=lambda b: b.priority, reverse=True)
        return available

    # ----------------------------------------------------------
    # 3. 触发叙事节拍
    # ----------------------------------------------------------

    def trigger_beat(
        self,
        beat_name: str,
        emotion_values: Dict[str, float],
    ) -> Optional[StoryEvent]:
        """记录一个叙事节拍的发生。

        Args:
            beat_name: 节拍名称
            emotion_values: 当前情感值

        Returns:
            StoryEvent 或 None（如果节拍不存在或不可触发）
        """
        # 查找节拍定义
        beat = None
        for b in NARRATIVE_BEATS:
            if b.name == beat_name:
                beat = b
                break

        if beat is None:
            logger.warning(f"[NarrativeArc] Unknown beat: {beat_name}")
            return None

        # 检查是否可触发
        if not beat.repeatable and beat_name in self._triggered:
            logger.debug(f"[NarrativeArc] Beat already triggered: {beat_name}")
            return None

        # 记录事件
        event = StoryEvent(
            beat_name=beat_name,
            timestamp=datetime.now().isoformat(),
            emotion_snapshot=dict(emotion_values),
        )
        self._events.append(event)
        self._triggered.add(beat_name)

        logger.info(f"[NarrativeArc] Beat triggered: {beat_name}")
        return event

    # ----------------------------------------------------------
    # 4. 生成叙事上下文（给 LLM）
    # ----------------------------------------------------------

    def get_narrative_context(
        self,
        emotion_values: Dict[str, float],
    ) -> str:
        """生成叙事氛围上下文，用于注入 system prompt。

        Args:
            emotion_values: 当前情感值

        Returns:
            格式化的叙事指导字符串
        """
        zone = self.get_zone(emotion_values)
        available = self.get_available_beats(emotion_values)

        if not available:
            return ""

        lines = [f"【叙事氛围】当前情感地带: {zone.value}"]
        lines.append("可能的叙事节拍:")

        for beat in available[:3]:  # 最多展示 3 个
            lines.append(f"  - {beat.name}: {beat.description}")

        # 最近发生的故事事件
        if self._events:
            recent = self._events[-3:]
            lines.append("最近的叙事事件:")
            for evt in recent:
                lines.append(f"  - {evt.beat_name}")

        return "\n".join(lines)

    # ----------------------------------------------------------
    # 5. 查询接口
    # ----------------------------------------------------------

    def has_triggered(self, beat_name: str) -> bool:
        """检查某个节拍是否已触发过"""
        return beat_name in self._triggered

    def get_story_summary(self) -> Dict[str, Any]:
        """获取故事进展摘要"""
        return {
            "character_id": self.character_id,
            "total_events": len(self._events),
            "triggered_beats": list(self._triggered),
            "recent_events": [
                {"beat": e.beat_name, "time": e.timestamp}
                for e in self._events[-5:]
            ],
        }


# ============================================================
# 便捷单例
# ============================================================

_arc_instances: Dict[str, NarrativeArc] = {}


def get_narrative_arc(character_id: str = "chayewoon") -> NarrativeArc:
    """获取 NarrativeArc 单例（按角色隔离）"""
    if character_id not in _arc_instances:
        _arc_instances[character_id] = NarrativeArc(character_id)
    return _arc_instances[character_id]
