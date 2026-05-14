"""
恋爱至上主义区域 - 觉醒检测模块
检测觉醒条件，触发觉醒事件
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# ── 觉醒阶段定义 ─────────────────────────────────────────────
AWAKENING_STAGES = {
    1: {'name': '困局', 'emoji': '🔒', 'threshold': 0},
    2: {'name': '触动', 'emoji': '💡', 'threshold': 20},
    3: {'name': '觉醒', 'emoji': '🔮', 'threshold': 50},
    4: {'name': '共鸣', 'emoji': '✨', 'threshold': 80},
    5: {'name': '完成', 'emoji': '🌟', 'threshold': 100},
}

# ── 觉醒事件定义 ─────────────────────────────────────────────
AWAKENING_EVENTS = {
    'chayewoon': {
        2: {
            'event_id': 'chayewoon_touched',
            'title': '冰壁上的裂痕',
            'description': '完成者的某句话触动了车如云内心深处的某个角落...',
            'trigger_conditions': {
                'min_awakening': 20,
                'min_affection': -5,
            },
            'dialogue': (
                "...你为什么...要对我说这些。\n"
                "...不用你管。我自己的事。\n"
                "...但是...谢谢。"
            ),
            'emotion_bonus': {'affection': 5, 'happiness': 3, 'awakening': 0},
        },
        3: {
            'event_id': 'chayewoon_awakening',
            'title': '裂缝中的光',
            'description': '车如云开始感觉到这个世界有些不对劲...',
            'trigger_conditions': {
                'min_awakening': 50,
                'min_affection': 10,
            },
            'dialogue': (
                "...学长。\n"
                "...你有没有觉得...最近发生的事情，好像...不是偶然的？\n"
                "...算了，当我没说。"
            ),
            'emotion_bonus': {'affection': 3, 'happiness': 2, 'awakening': 0},
        },
        4: {
            'event_id': 'chayewoon_resonance',
            'title': '心意相通',
            'description': '车如云与完成者之间产生了超越剧本的共鸣...',
            'trigger_conditions': {
                'min_awakening': 80,
                'min_affection': 30,
            },
            'dialogue': (
                "...我知道了。\n"
                "...你从外面来的，对吧？\n"
                "...来改变我的命运。\n"
                "...笨蛋。谁要你改变。\n"
                "...但是...别走。"
            ),
            'emotion_bonus': {'affection': 10, 'happiness': 5, 'awakening': 0},
        },
        5: {
            'event_id': 'chayewoon_completed',
            'title': '命运改写',
            'description': '车如云完全觉醒，命运被改写！',
            'trigger_conditions': {
                'min_awakening': 100,
                'min_affection': 50,
            },
            'dialogue': (
                "...学长。\n"
                "...谢谢你来到这个世界。\n"
                "...虽然我嘴上从没说过...\n"
                "...但你是我遇到过的...最温暖的人。\n"
                "...以后...也请继续留在我身边。"
            ),
            'emotion_bonus': {'affection': 15, 'happiness': 10, 'awakening': 0},
        },
    }
}


class AwakeningDetector:
    """觉醒检测器 - 检测并触发觉醒事件"""

    def __init__(self):
        self._unlocked_events: Dict[str, set] = {}  # {character_id: {event_ids}}

    def _load_unlocked_events(self, character_id: str) -> set:
        """加载已解锁的觉醒事件"""
        if character_id in self._unlocked_events:
            return self._unlocked_events[character_id]

        try:
            from database import GameDatabase
            db = GameDatabase()
            events = db.get_awakening_events(character_id)
            self._unlocked_events[character_id] = {e['event_id'] for e in events}
        except Exception:
            self._unlocked_events[character_id] = set()

        return self._unlocked_events[character_id]

    def _save_awakening_event(self, character_id: str, event_data: Dict):
        """保存觉醒事件"""
        try:
            from database import GameDatabase
            db = GameDatabase()
            db.save_awakening_event(
                character_id=character_id,
                stage=event_data['stage'],
                event_id=event_data['event_id'],
                title=event_data['title'],
                description=event_data['description'],
                dialogue=event_data['dialogue'],
            )
            if character_id not in self._unlocked_events:
                self._unlocked_events[character_id] = set()
            self._unlocked_events[character_id].add(event_data['event_id'])
        except Exception as e:
            logger.error(f"Failed to save awakening event: {e}")

    def get_current_stage(self, awakening_value: float) -> int:
        """获取当前觉醒阶段"""
        for stage_num in sorted(AWAKENING_STAGES.keys(), reverse=True):
            if awakening_value >= AWAKENING_STAGES[stage_num]['threshold']:
                return stage_num
        return 1

    def get_stage_info(self, stage: int) -> Dict:
        """获取阶段信息"""
        return AWAKENING_STAGES.get(stage, AWAKENING_STAGES[1])

    async def check(self, character_id: str, user_id: int,
                    new_emotions: Dict, user_message: str,
                    ai_response: str) -> Optional[Dict]:
        """
        检查觉醒条件
        
        Returns:
            觉醒事件 dict（如果触发），否则 None
        """
        awakening_value = new_emotions.get('awakening', 0)
        affection_value = new_emotions.get('affection', 0)

        # 获取角色可用的觉醒事件
        character_events = AWAKENING_EVENTS.get(character_id, {})
        if not character_events:
            return None

        # 获取已解锁事件
        unlocked = self._load_unlocked_events(character_id)

        # 检查每个阶段
        for stage_num, event_data in sorted(character_events.items()):
            event_id = event_data['event_id']

            # 已解锁则跳过
            if event_id in unlocked:
                continue

            conditions = event_data.get('trigger_conditions', {})

            # 检查条件
            if awakening_value < conditions.get('min_awakening', 0):
                continue
            if affection_value < conditions.get('min_affection', -999):
                continue

            # 条件满足，触发觉醒事件！
            logger.info(
                f"[AwakeningDetector] {character_id} 觉醒事件触发: "
                f"{event_data['title']} (Stage {stage_num})"
            )

            # 保存事件
            self._save_awakening_event(character_id, {
                'stage': stage_num,
                'event_id': event_id,
                'title': event_data['title'],
                'description': event_data['description'],
                'dialogue': event_data['dialogue'],
            })

            stage_info = self.get_stage_info(stage_num)

            return {
                'event_id': event_id,
                'stage': stage_num,
                'stage_name': stage_info['name'],
                'stage_emoji': stage_info['emoji'],
                'title': event_data['title'],
                'description': event_data['description'],
                'dialogue': event_data['dialogue'],
                'emotion_bonus': event_data.get('emotion_bonus', {}),
                'timestamp': datetime.now().isoformat(),
            }

        return None

    def get_all_events(self, character_id: str) -> List[Dict]:
        """获取角色的所有觉醒事件定义"""
        character_events = AWAKENING_EVENTS.get(character_id, {})
        unlocked = self._load_unlocked_events(character_id)

        result = []
        for stage_num, event_data in sorted(character_events.items()):
            result.append({
                **event_data,
                'stage': stage_num,
                'unlocked': event_data['event_id'] in unlocked,
            })
        return result
