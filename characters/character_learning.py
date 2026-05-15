"""
角色自我学习进化系统
v1.6.4.1 — 实现完整的自我进化链条：
用户上传资料 → 角色学习 → 更新 persona/memories → 下次对话自动使用

核心功能：
1. 从 novel.txt 提取知识并更新角色设定
2. 从聊天记录学习用户偏好，更新 memories.md
3. 从 Qdrant 记忆提取高频话题，补充到角色知识
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from system.config import get_default_tz

logger = logging.getLogger(__name__)


class CharacterLearning:
    """角色学习进化引擎"""

    def __init__(self, character_id: str):
        self.character_id = character_id
        self.char_dir = os.path.join(
            os.path.dirname(__file__), character_id
        )
        self._ensure_dir()

    def _ensure_dir(self):
        """确保角色目录存在"""
        os.makedirs(self.char_dir, exist_ok=True)

    def _read_file(self, filename: str) -> str:
        """读取角色文件"""
        path = os.path.join(self.char_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def _write_file(self, filename: str, content: str):
        """写入角色文件"""
        path = os.path.join(self.char_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    # ============================================================
    # 1. 从 novel.txt 学习（LightRAG 知识提取）
    # ============================================================

    async def learn_from_novel(self, topic: str = None) -> Dict:
        """从小说知识库学习，提取与 topic 相关的知识更新到 persona

        Args:
            topic: 学习主题（如"家庭背景""田径训练"），None 则自动选择

        Returns:
            学习结果统计
        """
        from .novel_knowledge import get_knowledge

        kg = get_knowledge(self.character_id)

        # 如果没有指定主题，查询几个核心主题
        if not topic:
            topics = [
                "车如云的家庭背景和父母情况",
                "车如云的田径训练和比赛成绩",
                "车如云的性格特点和行为习惯",
                "车如云和完成者的关系发展",
            ]
        else:
            topics = [topic]

        learned_facts = []
        for t in topics:
            try:
                result = await kg.query(t, mode="hybrid")
                if result and len(result) > 20:  # 过滤无效结果
                    learned_facts.append(f"【{t}】\n{result}")
            except Exception as e:
                logger.warning(f"[Learning] 查询主题失败 '{t}': {e}")

        if not learned_facts:
            return {"success": False, "error": "未能从知识库提取有效信息"}

        # 更新 persona.md 的学习记录部分
        await self._update_persona_learned(learned_facts)

        return {
            "success": True,
            "topics": topics,
            "facts_learned": len(learned_facts),
        }

    async def _update_persona_learned(self, facts: List[str]):
        """将学习到的知识追加到 persona.md"""
        persona = self._read_file("persona.md")

        # 找到或创建 【从原著学习】 部分
        learned_section = "\n\n## 【从原著学习】\n\n"
        learned_section += f"_最后更新: {datetime.now(get_default_tz()).strftime('%Y-%m-%d')}_\n\n"

        for i, fact in enumerate(facts, 1):
            learned_section += f"### 知识点 {i}\n{fact}\n\n"

        # 如果已有该部分，替换；否则追加
        marker = "## 【从原著学习】"
        if marker in persona:
            # 替换现有部分
            before = persona.split(marker)[0].rstrip()
            persona = before + learned_section
        else:
            # 追加到末尾
            persona = persona.rstrip() + learned_section

        self._write_file("persona.md", persona)
        logger.info(f"[Learning] 更新 persona.md，新增 {len(facts)} 个知识点")

    # ============================================================
    # 2. 从聊天记录学习用户偏好
    # ============================================================

    async def learn_from_chat_history(self, user_id: int) -> Dict:
        """分析用户聊天记录，提取偏好更新到 memories.md

        学习维度：
        - 用户喜欢的互动方式
        - 用户的称呼偏好
        - 用户常聊的话题
        - 用户的情绪反应模式
        """
        from database import get_db
        from .qdrant_memory import get_memory

        db = get_db()

        # 获取最近聊天记录（从数据库）
        recent_chats = db.get_recent_chat_history(user_id, self.character_id, limit=50)

        if not recent_chats:
            return {"success": False, "error": "没有足够的聊天记录"}

        # 分析用户偏好（简化版，实际可用 LLM 分析）
        user_patterns = self._analyze_user_patterns(recent_chats)

        # 更新 memories.md
        await self._update_memories_user_profile(user_id, user_patterns)

        return {
            "success": True,
            "chats_analyzed": len(recent_chats),
            "patterns_found": len(user_patterns),
        }

    def _analyze_user_patterns(self, chats: List[Dict]) -> Dict:
        """分析用户聊天模式"""
        patterns = {
            "greeting_style": [],
            "topics": {},
            "response_to_cold": [],
            "response_to_warm": [],
        }

        for chat in chats:
            user_msg = chat.get('user_message', '').lower()
            char_reply = chat.get('character_reply', '')

            # 统计话题
            topics = ["训练", "吃饭", "奶奶", "妈妈", "跑步", "学校", "冰淇淋"]
            for topic in topics:
                if topic in user_msg:
                    patterns["topics"][topic] = patterns["topics"].get(topic, 0) + 1

            # 记录用户对冷淡回复的反应
            if "……" in char_reply or len(char_reply) < 10:
                patterns["response_to_cold"].append(user_msg[:30])

        return patterns

    async def _update_memories_user_profile(self, user_id: int, patterns: Dict):
        """更新 memories.md 的用户画像部分"""
        memories = self._read_file("memories.md")

        # 构建用户画像
        profile_section = f"\n\n## 【用户 {user_id} 画像】\n\n"
        profile_section += f"_最后更新: {datetime.now(get_default_tz()).strftime('%Y-%m-%d')}_\n\n"

        if patterns.get("topics"):
            profile_section += "**常聊话题**: " + ", ".join(
                sorted(patterns["topics"].keys(),
                       key=lambda x: patterns["topics"][x],
                       reverse=True)[:5]
            ) + "\n\n"

        # 如果已有该用户画像，替换；否则追加
        marker = f"## 【用户 {user_id} 画像】"
        if marker in memories:
            before = memories.split(marker)[0].rstrip()
            memories = before + profile_section
        else:
            memories = memories.rstrip() + profile_section

        self._write_file("memories.md", memories)
        logger.info(f"[Learning] 更新 memories.md，添加用户 {user_id} 画像")

    # ============================================================
    # 3. 从 Qdrant 记忆提取高频话题
    # ============================================================

    async def learn_from_qdrant_memories(self, user_id: int = None) -> Dict:
        """从向量记忆库提取高频话题，更新到角色知识

        分析 Qdrant 中的记忆，找出用户反复提及的话题和情感模式，
        补充到 memories.md 的共同记忆部分。
        """
        from .qdrant_memory import get_memory

        memory = get_memory(self.character_id)

        # 获取最近记忆
        recent = memory.get_recent_memories(user_id=user_id, limit=20)

        if not recent:
            return {"success": False, "error": "Qdrant 记忆库为空"}

        # 提取关键词和情感（简化版）
        key_memories = []
        for mem in recent:
            content = mem.get("content", "")
            # 筛选重要记忆（长度适中，包含情感词）
            if len(content) > 10 and any(kw in content for kw in ["喜欢", "讨厌", "开心", "难过", "记得", "第一次"]):
                key_memories.append(content)

        if not key_memories:
            return {"success": False, "error": "未找到有价值的记忆"}

        # 更新 memories.md
        await self._update_memories_key_events(key_memories)

        return {
            "success": True,
            "memories_analyzed": len(recent),
            "key_memories": len(key_memories),
        }

    async def _update_memories_key_events(self, memories: List[str]):
        """更新 memories.md 的关键事件部分"""
        content = self._read_file("memories.md")

        events_section = "\n\n## 【从对话中提取的关键记忆】\n\n"
        events_section += f"_最后更新: {datetime.now(get_default_tz()).strftime('%Y-%m-%d')}_\n\n"

        for i, mem in enumerate(memories[:10], 1):  # 最多 10 条
            events_section += f"{i}. {mem}\n"

        marker = "## 【从对话中提取的关键记忆】"
        if marker in content:
            before = content.split(marker)[0].rstrip()
            content = before + events_section
        else:
            content = content.rstrip() + events_section

        self._write_file("memories.md", content)
        logger.info(f"[Learning] 更新 memories.md，添加 {len(memories)} 条关键记忆")

    # ============================================================
    # 4. 完整学习流程（一键进化）
    # ============================================================

    async def evolve(self, user_id: int = None) -> Dict:
        """执行完整的学习进化流程

        依次执行：
        1. 从 novel.txt 学习
        2. 从聊天记录学习
        3. 从 Qdrant 记忆学习

        Returns:
            各阶段学习结果
        """
        results = {
            "character_id": self.character_id,
            "timestamp": datetime.now(get_default_tz()).isoformat(),
            "stages": {},
        }

        # Stage 1: 从小说学习
        try:
            novel_result = await self.learn_from_novel()
            results["stages"]["novel_learning"] = novel_result
        except Exception as e:
            results["stages"]["novel_learning"] = {"success": False, "error": str(e)}

        # Stage 2: 从聊天记录学习（如果指定了用户）
        if user_id:
            try:
                chat_result = await self.learn_from_chat_history(user_id)
                results["stages"]["chat_learning"] = chat_result
            except Exception as e:
                results["stages"]["chat_learning"] = {"success": False, "error": str(e)}

        # Stage 3: 从 Qdrant 记忆学习
        try:
            qdrant_result = await self.learn_from_qdrant_memories(user_id)
            results["stages"]["qdrant_learning"] = qdrant_result
        except Exception as e:
            results["stages"]["qdrant_learning"] = {"success": False, "error": str(e)}

        # 总结
        success_count = sum(1 for s in results["stages"].values() if s.get("success"))
        results["summary"] = {
            "total_stages": len(results["stages"]),
            "successful_stages": success_count,
            "evolved": success_count > 0,
        }

        return results


# ===== 便捷函数 =====

_learning_instances: Dict[str, CharacterLearning] = {}


def get_learning(character_id: str = 'chayewoon') -> CharacterLearning:
    """获取角色学习实例"""
    if character_id not in _learning_instances:
        _learning_instances[character_id] = CharacterLearning(character_id)
    return _learning_instances[character_id]


async def evolve_character(character_id: str = 'chayewoon', user_id: int = None) -> Dict:
    """一键进化角色"""
    learning = get_learning(character_id)
    return await learning.evolve(user_id)
