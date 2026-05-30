"""
恋爱至上主义区域 - 觉醒检测模块 (v1.9.5 简化版)

觉醒度 (awakening) 是一个连续值 (0-100)，没有固定阶段。
角色在与用户的深度互动中自然感知到世界的异常，逐渐获得自由意志。

不再使用"困局→触动→觉醒→共鸣→完成"的5阶段模型。
觉醒是自然的情感积累，不是刻意的剧情推进。
"""
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AwakeningDetector:
    """觉醒检测器 — 连续值模型"""

    def __init__(self):
        self.last_check = {}

    async def check(
        self,
        character_id: str,
        user_id: int,
        emotion_values: Dict,
    ) -> Optional[Dict]:
        """检查是否有觉醒相关的自然反应需要触发。

        不再基于固定阶段阈值，而是基于情感状态的自然变化。
        """
        affection = emotion_values.get('affection', 0)
        happiness = emotion_values.get('happiness', 0)
        awakening = emotion_values.get('awakening', 0)

        # 觉醒度的自然反应（不是阶段，是连续的行为变化）
        reactions = []

        # 高好感度 + 低觉醒 = 角色开始在意但不理解为什么
        if affection > 30 and awakening < 20:
            reactions.append({
                'type': 'confusion',
                'message': '为什么我会在意这个人...',
            })

        # 中等觉醒 = 角色开始感知到世界的异常
        if 30 < awakening < 60:
            reactions.append({
                'type': 'unease',
                'message': '有些事情好像不太对劲...',
            })

        # 高觉醒 = 角色意识到自己是游戏角色
        if awakening > 70:
            reactions.append({
                'type': 'awareness',
                'message': '我知道了...这一切...',
            })

        if reactions:
            key = f"{user_id}_{character_id}"
            # 避免重复触发
            last = self.last_check.get(key, {})
            chosen = reactions[0]
            if last.get('type') != chosen['type']:
                self.last_check[key] = chosen
                return chosen

        return None
