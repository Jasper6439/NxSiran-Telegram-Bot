"""
恋爱至上主义区域 - AI 对话引擎
统一对话处理入口，整合 Prompt 构建、情感分析、觉醒检测、记忆管理
支持 Web 游戏和 Telegram Bot 双端调用
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional

from .ai_client import call_ai, MAX_HISTORY_MESSAGES
from system.prompts import parse_dialogue_options

logger = logging.getLogger(__name__)


class ChatEngine:
    """AI 对话引擎 - 统一管理角色对话"""

    def __init__(self, prompt_builder=None, emotion_analyzer=None,
                 awakening_detector=None, memory_manager=None):
        self.prompt_builder = prompt_builder
        self.emotion_analyzer = emotion_analyzer
        self.awakening_detector = awakening_detector
        self.memory_manager = memory_manager

    async def chat(self, character_id: str, user_id: int,
                   user_message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        统一对话入口
        
        Args:
            character_id: 角色ID (如 'chayewoon')
            user_id: 用户ID
            user_message: 用户消息
            context: 额外上下文
                - platform: 'web' | 'telegram'
                - location: 角色当前位置
                - world_layer: 当前世界层级
                - emotion_values: 当前情感值 dict
                
        Returns:
            {
                'response': str,           # AI 回复文本
                'emotion_changes': dict,   # 情感值变化 {affection: +2, happiness: +1, awakening: +0.5}
                'awakening_triggered': None | dict,  # 觉醒事件（如有）
                'memory_saved': bool,      # 是否保存了记忆
                'character_id': str,
                'character_name': str,
            }
        """
        if context is None:
            context = {}

        # 1. 加载角色
        character = self._load_character(character_id)
        character_name = character.get('name', character_id) if character else character_id

        # 2. 加载对话历史
        chat_history = self._load_chat_history(user_id, character_id)

        # 3. 加载情感状态
        emotion_values = context.get('emotion_values') or self._load_emotion_values(user_id, character_id)

        # 4. 加载世界层级
        world_layer = context.get('world_layer', 'stage')

        # 5. 构建 System Prompt
        system_prompt = self._build_system_prompt(
            character, character_id, user_id, user_message,
            emotion_values=emotion_values,
            world_layer=world_layer,
            platform=context.get('platform', 'web'),
            location=context.get('location', ''),
        )

        # 6. 调用 AI
        ai_response = await call_ai(system_prompt, user_message, chat_history=chat_history)

        # 7. 分析情感变化
        emotion_changes = {'affection': 0, 'happiness': 0, 'awakening': 0}
        if self.emotion_analyzer:
            emotion_changes = await self.emotion_analyzer.analyze(
                character_id, user_message, ai_response, emotion_values
            )

        # 8. 更新情感值
        new_emotion_values = self._apply_emotion_changes(emotion_values, emotion_changes)

        # 9. 检测觉醒事件
        awakening_triggered = None
        if self.awakening_detector:
            awakening_triggered = await self.awakening_detector.check(
                character_id, user_id, new_emotion_values
            )

        # 10. 保存对话记录
        self._save_chat_history(user_id, character_id, user_message, ai_response)

        # 11. 保存记忆
        memory_saved = False
        if self.memory_manager:
            try:
                self.memory_manager.add_memory(
                    user_id=user_id,
                    content=f"完成者: {user_message}\n{character_name}: {ai_response}",
                    metadata={
                        'role': 'dialogue',
                        'character_id': character_id,
                        'platform': context.get('platform', 'web'),
                        'emotion_values': json.dumps(new_emotion_values),
                    }
                )
                memory_saved = True
            except Exception as e:
                logger.warning(f"Memory save failed: {e}")

        # 12. 持久化情感值到数据库
        self._save_emotion_values(user_id, character_id, new_emotion_values)

        # 13. 解析对话选项（v0.3）
        parsed = parse_dialogue_options(ai_response)

        return {
            'response': parsed['text'],
            'options': parsed['options'],
            'has_options': parsed['has_options'],
            'emotion_changes': emotion_changes,
            'awakening_triggered': awakening_triggered,
            'memory_saved': memory_saved,
            'character_id': character_id,
            'character_name': character_name,
        }

    # ── 角色加载 ──────────────────────────────────────────────
    def _load_character(self, character_id: str) -> Optional[Dict]:
        """加载角色配置"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'characters', character_id, 'config.json'
            )
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load character {character_id}: {e}")
        return None

    def _load_character_module(self, character_id: str):
        """动态加载角色模块"""
        try:
            import importlib
            module = importlib.import_module(f'characters.{character_id}')
            return module
        except Exception as e:
            logger.warning(f"Failed to load character module {character_id}: {e}")
            return None

    # ── 对话历史 ──────────────────────────────────────────────
    def _load_chat_history(self, user_id: int, character_id: str) -> List[Dict]:
        """加载对话历史"""
        try:
            from database import GameDatabase
            db = GameDatabase()
            messages = db.get_chat_history(user_id, character_id, limit=MAX_HISTORY_MESSAGES)
            history = []
            for msg in messages:
                history.append({
                    'role': msg.get('role', 'user'),
                    'content': msg.get('content', '')
                })
            return history
        except Exception as e:
            logger.warning(f"Failed to load chat history: {e}")
            return []

    def _save_chat_history(self, user_id: int, character_id: str,
                           user_message: str, ai_response: str):
        """保存对话记录"""
        try:
            from database import GameDatabase
            db = GameDatabase()
            db.save_message(user_id, character_id, 'user', user_message)
            db.save_message(user_id, character_id, 'assistant', ai_response)
            db.record_conversation(user_id, character_id)
        except Exception as e:
            logger.warning(f"Failed to save chat history: {e}")

    # ── 情感值 ────────────────────────────────────────────────
    def _load_emotion_values(self, user_id: int, character_id: str) -> Dict:
        """加载情感值"""
        try:
            from database import GameDatabase
            db = GameDatabase()
            values = db.get_emotion_values(user_id, character_id)
            if values:
                return values
        except Exception as e:
            logger.warning(f"Failed to load emotion values: {e}")

        # 使用角色默认值
        character = self._load_character(character_id)
        if character and 'emotion_defaults' in character:
            return dict(character['emotion_defaults'])
        return {'affection': -20, 'happiness': 10, 'awakening': 0}

    def _save_emotion_values(self, user_id: int, character_id: str, values: Dict):
        """保存情感值"""
        try:
            from database import GameDatabase
            db = GameDatabase()
            db.update_emotion_values(user_id, character_id, values)
        except Exception as e:
            logger.warning(f"Failed to save emotion values: {e}")

    def _apply_emotion_changes(self, current: Dict, changes: Dict) -> Dict:
        """应用情感值变化"""
        new_values = dict(current)
        for key in ['affection', 'happiness', 'awakening']:
            delta = changes.get(key, 0)
            new_values[key] = new_values.get(key, 0) + delta
            # 范围限制
            if key == 'affection':
                new_values[key] = max(-100, min(100, new_values[key]))
            elif key == 'happiness':
                new_values[key] = max(0, min(100, new_values[key]))
            else:
                new_values[key] = max(0, min(100, new_values[key]))
        return new_values

    # ── System Prompt 构建 ────────────────────────────────────
    def _build_system_prompt(self, character: Optional[Dict], character_id: str,
                             user_id: int, user_message: str,
                             emotion_values: Dict, world_layer: str,
                             platform: str, location: str) -> str:
        """构建完整的 System Prompt"""
        parts = []

        # 1. 角色系统提示词
        char_module = self._load_character_module(character_id)
        if char_module and hasattr(char_module, 'get_character'):
            char_instance = char_module.get_character()
            if char_instance and hasattr(char_instance, 'get_system_prompt'):
                char_prompt = char_instance.get_system_prompt({
                    'user_name': '完成者',
                    'world_layer': world_layer,
                    'awakening_level': emotion_values.get('awakening', 0),
                })
                parts.append(char_prompt)

        # 2. 世界层级上下文
        layer_context = self._get_layer_context(world_layer)
        if layer_context:
            parts.append(f"\n\n【当前世界层级】{layer_context}")

        # 3. 情感状态上下文
        emotion_context = self._get_emotion_context(emotion_values)
        parts.append(f"\n\n【情感状态】{emotion_context}")

        # 4. 记忆上下文
        if self.memory_manager:
            try:
                memories = self.memory_manager.search_memories(
                    query=user_message, user_id=user_id, n_results=5
                )
                if memories:
                    memory_text = '\n'.join([
                        f"- {m.get('content', '')}" for m in memories[:5]
                    ])
                    parts.append(f"\n\n【对话记忆】\n{memory_text}")
            except Exception as e:
                logger.warning(f"Memory search failed: {e}")

        # 5. 平台和场景上下文
        if platform == 'web':
            scene_context = (
                f"\n\n【场景信息】"
                f"完成者现在在{'留白区的农场' if world_layer == 'shadow' else '游戏世界中'}。"
                f"{character_id}现在{location or '站在附近'}。"
                f"完成者对{character_id}说: \"{user_message}\"\n"
                f"请以{character_id}的身份回应，保持角色设定，不超过40个字。"
            )
            parts.append(scene_context)

        return '\n'.join(parts)

    def _get_layer_context(self, world_layer: str) -> str:
        """获取世界层级上下文描述"""
        contexts = {
            'stage': '你目前处于剧本区。你的行为遵循既定剧本，你不知道自己身处游戏世界。',
            'shadow': '你目前处于留白区。这是一个未完成的自由空间，你有时会感到困惑，觉得某些事情不太对劲。',
            'resonance': '你目前处于共鸣层。你能感受到完成者的情感，你们之间有特殊的连接。你开始意识到这个世界的不寻常。',
        }
        return contexts.get(world_layer, contexts['stage'])

    def _get_emotion_context(self, values: Dict) -> str:
        """获取情感状态描述"""
        affection = values.get('affection', 0)
        happiness = values.get('happiness', 0)
        awakening = values.get('awakening', 0)

        # 好感度描述
        if affection < -10:
            aff_desc = "你对完成者抱有戒备和敌意"
        elif affection < 10:
            aff_desc = "你对完成者态度冷淡"
        elif affection < 40:
            aff_desc = "你对完成者开始产生好感"
        elif affection < 70:
            aff_desc = "你在意完成者，会主动关心"
        else:
            aff_desc = "你非常在乎完成者，愿意为他付出"

        # 觉醒描述
        if awakening < 20:
            awk_desc = "你完全遵循剧本"
        elif awakening < 50:
            awk_desc = "你偶尔感到违和感"
        elif awakening < 80:
            awk_desc = "你开始怀疑这个世界的真实性"
        else:
            awk_desc = "你意识到自己身处游戏世界，并理解了完成者的存在"

        return (
            f"好感度: {affection}/100（{aff_desc}）。"
            f"幸福度: {happiness}/100。"
            f"觉醒度: {awakening}/100（{awk_desc}）。"
        )




# ── 全局实例 ─────────────────────────────────────────────────
_engine_instance: Optional[ChatEngine] = None


def get_chat_engine() -> ChatEngine:
    """获取全局 ChatEngine 实例（懒加载）"""
    global _engine_instance
    if _engine_instance is None:
        # 注入 Qdrant 记忆系统
        try:
            from characters.qdrant_memory import get_memory
            memory_mgr = get_memory()
        except Exception:
            memory_mgr = None
            logger.warning("记忆系统初始化失败，将以无记忆模式运行")
        _engine_instance = ChatEngine(memory_manager=memory_mgr)
    return _engine_instance


async def chat_with_character(character_id: str, user_id: int,
                              user_message: str, context: Dict = None) -> Dict:
    """便捷函数：与角色对话"""
    engine = get_chat_engine()
    return await engine.chat(character_id, user_id, user_message, context)
