"""
角色进化服务模块 - 自我学习与记忆系统
=====================================
角色根据长期对话不断自我进化，记住用户喜好并改变性格/对话风格。

核心功能:
1. 从对话中提取关键记忆
2. 调整角色情绪状态
3. 积累进化点数，更新系统提示词
4. 后台异步任务处理

用法:
    from services.evolution_service import EvolutionService, analyze_and_evolve
    
    await analyze_and_evolve(user_id, character_id, chat_history)
"""

import os
import logging
import asyncio
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict

import aiohttp

from system.config import DATA_DIR, AI_API_BASE, AI_API_KEY

logger = logging.getLogger(__name__)

# ============================================================
# 配置区域
# ============================================================

# 进化分析使用的轻量级模型
EVOLUTION_MODEL = os.environ.get(
    "EVOLUTION_MODEL", 
    "deepseek/deepseek-r1:free"
)

# 进化阈值配置
EVOLUTION_CONFIG = {
    # 触发性格更新的进化点数阈值
    "personality_update_threshold": 100,
    # 触发情绪变化的进化点数阈值
    "emotion_update_threshold": 20,
    # 单次对话最大获得的进化点数
    "max_points_per_conversation": 15,
    # 记忆提取的最大条数
    "max_memories_per_analysis": 5,
    # 后台任务间隔（秒）
    "background_task_interval": 300,  # 5 分钟
}

# 情绪状态定义
EMOTION_STATES = {
    "neutral": {"valence": 0.0, "arousal": 0.0},
    "happy": {"valence": 0.8, "arousal": 0.5},
    "excited": {"valence": 0.9, "arousal": 0.8},
    "sad": {"valence": -0.6, "arousal": -0.3},
    "angry": {"valence": -0.7, "arousal": 0.7},
    "loving": {"valence": 0.9, "arousal": 0.3},
    "shy": {"valence": 0.3, "arousal": -0.2},
    "worried": {"valence": -0.4, "arousal": 0.2},
}


@dataclass
class CharacterMemory:
    """角色记忆数据结构"""
    id: Optional[int] = None
    user_id: int = 0
    character_id: str = "chayewoon"
    memory_content: str = ""
    memory_type: str = "preference"  # preference, event, emotion, fact
    importance: float = 0.5  # 0.0 - 1.0
    created_at: str = ""
    last_accessed: str = ""


@dataclass
class CharacterState:
    """角色状态数据结构"""
    id: Optional[int] = None
    user_id: int = 0
    character_id: str = "chayewoon"
    emotion_state: str = "neutral"
    emotion_valence: float = 0.0
    emotion_arousal: float = 0.0
    evolution_points: int = 0
    personality_traits: str = "{}"  # JSON
    system_prompt_additions: str = ""  # 额外的系统提示词
    updated_at: str = ""


class EvolutionService:
    """
    角色自我学习与进化服务
    
    功能:
    1. 对话复盘：提取关键记忆
    2. 情绪调整：根据对话氛围调整角色情绪
    3. 性格进化：积累点数后更新系统提示词
    4. 记忆检索：回复前拉取用户专属记忆
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(DATA_DIR, "game.db")
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_connection(self):
        """获取数据库连接（上下文管理器），复用 GameDatabase 的连接管理。"""
        from database.base import get_db
        db = get_db()
        return db.get_connection()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session
    
    # ============================================================
    # 记忆提取
    # ============================================================
    
    async def extract_memories(
        self, 
        chat_history: List[Dict[str, Any]]
    ) -> List[CharacterMemory]:
        """
        从对话中提取关键记忆
        
        Args:
            chat_history: 对话历史
        
        Returns:
            提取的记忆列表
        """
        if not chat_history:
            return []
        
        # 构建分析提示词
        conversation_text = self._format_conversation(chat_history)
        
        prompt = f"""请分析以下对话，提取用户的关键信息作为记忆点。

对话内容:
{conversation_text}

请提取以下类型的记忆（JSON 格式）:
1. preference: 用户喜好（如"喜欢吃草莓"）
2. fact: 用户事实（如"住在上海"）
3. event: 重要事件（如"明天要考试"）
4. emotion: 情感状态（如"最近心情不好"）

返回格式:
[
  {{"type": "preference", "content": "用户喜欢吃草莓", "importance": 0.8}},
  {{"type": "fact", "content": "用户住在上海", "importance": 0.6}}
]

只返回 JSON 数组，不要其他内容。"""

        try:
            session = await self._get_session()
            
            headers = {
                "Authorization": f"Bearer {AI_API_KEY}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": EVOLUTION_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500,
            }
            
            async with session.post(
                f"{AI_API_BASE}/chat/completions",
                headers=headers,
                json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    
                    # 解析 JSON
                    memories = self._parse_memory_response(content)
                    logger.info(f"[Evolution] 提取到 {len(memories)} 条记忆")
                    return memories
                else:
                    error_text = await resp.text()
                    logger.error(f"[Evolution] API 错误 {resp.status}: {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"[Evolution] 记忆提取失败: {e}")
            return []
    
    def _format_conversation(self, chat_history: List[Dict]) -> str:
        """格式化对话历史"""
        lines = []
        for msg in chat_history[-10:]:  # 最近 10 条
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)
    
    def _parse_memory_response(self, content: str) -> List[CharacterMemory]:
        """解析 LLM 返回的记忆 JSON"""
        try:
            # 提取 JSON 数组
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if not json_match:
                return []
            
            data = json.loads(json_match.group())
            
            memories = []
            for item in data[:EVOLUTION_CONFIG["max_memories_per_analysis"]]:
                memory = CharacterMemory(
                    memory_type=item.get("type", "fact"),
                    memory_content=item.get("content", ""),
                    importance=item.get("importance", 0.5),
                    created_at=datetime.now().isoformat(),
                )
                memories.append(memory)
            
            return memories
            
        except json.JSONDecodeError as e:
            logger.error(f"[Evolution] JSON 解析失败: {e}")
            return []
    
    # ============================================================
    # 情绪调整
    # ============================================================
    
    async def analyze_emotion(
        self, 
        chat_history: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        分析对话氛围，计算情绪变化
        
        Args:
            chat_history: 对话历史
        
        Returns:
            情绪变化 {"valence_delta": 0.1, "arousal_delta": 0.0}
        """
        # 简单的关键词分析
        positive_keywords = ["开心", "喜欢", "爱", "谢谢", "好的", "太棒了", "happy", "love"]
        negative_keywords = ["难过", "讨厌", "烦", "生气", "不好", "sad", "angry", "hate"]
        excited_keywords = ["太好了", "真的吗", "哇", "好期待", "amazing", "wow"]
        
        valence_delta = 0.0
        arousal_delta = 0.0
        
        for msg in chat_history[-5:]:
            content = msg.get("content", "").lower()
            
            for kw in positive_keywords:
                if kw in content:
                    valence_delta += 0.1
            
            for kw in negative_keywords:
                if kw in content:
                    valence_delta -= 0.1
            
            for kw in excited_keywords:
                if kw in content:
                    arousal_delta += 0.1
        
        # 限制范围
        valence_delta = max(-0.3, min(0.3, valence_delta))
        arousal_delta = max(-0.2, min(0.2, arousal_delta))
        
        return {"valence_delta": valence_delta, "arousal_delta": arousal_delta}
    
    def determine_emotion_state(self, valence: float, arousal: float) -> str:
        """根据效价和唤醒度确定情绪状态"""
        if valence > 0.6:
            if arousal > 0.5:
                return "excited"
            elif arousal > 0.2:
                return "loving"
            else:
                return "happy"
        elif valence > 0.2:
            if arousal < 0:
                return "shy"
            else:
                return "neutral"
        elif valence < -0.4:
            if arousal > 0.4:
                return "angry"
            else:
                return "sad"
        elif valence < -0.2:
            return "worried"
        else:
            return "neutral"
    
    # ============================================================
    # 进化点数计算
    # ============================================================
    
    def calculate_evolution_points(
        self, 
        chat_history: List[Dict[str, Any]],
        memories: List[CharacterMemory]
    ) -> int:
        """
        计算本次对话获得的进化点数
        
        Args:
            chat_history: 对话历史
            memories: 提取的记忆
        
        Returns:
            进化点数
        """
        points = 0
        
        # 基础点数：对话轮数
        points += min(len(chat_history), 5)
        
        # 记忆奖励
        points += len(memories) * 3
        
        # 高重要性记忆额外奖励
        for m in memories:
            if m.importance > 0.7:
                points += 2
        
        # 限制最大点数
        return min(points, EVOLUTION_CONFIG["max_points_per_conversation"])
    
    # ============================================================
    # 性格进化
    # ============================================================
    
    async def evolve_personality(
        self, 
        state: CharacterState,
        memories: List[CharacterMemory]
    ) -> str:
        """
        根据积累的记忆进化性格
        
        Args:
            state: 当前角色状态
            memories: 积累的记忆
        
        Returns:
            更新后的系统提示词补充
        """
        # 解析现有性格特征
        try:
            traits = json.loads(state.personality_traits)
        except:
            traits = {}
        
        # 根据记忆更新性格
        for memory in memories:
            content = memory.memory_content.lower()
            
            # 用户喜欢什么 -> 角色更倾向于提及
            if memory.memory_type == "preference":
                if "喜欢" in content:
                    # 提取喜欢的事物
                    import re
                    match = re.search(r"喜欢(.+)", content)
                    if match:
                        thing = match.group(1).strip()
                        traits[f"knows_user_likes_{thing}"] = True
            
            # 用户不喜欢什么 -> 角色避免提及
            if "讨厌" in content or "不喜欢" in content:
                match = re.search(r"(?:讨厌|不喜欢)(.+)", content)
                if match:
                    thing = match.group(1).strip()
                    traits[f"knows_user_dislikes_{thing}"] = True
        
        # 生成系统提示词补充
        additions = []
        
        for key, value in traits.items():
            if key.startswith("knows_user_likes_") and value:
                thing = key.replace("knows_user_likes_", "")
                additions.append(f"用户喜欢{thing}，可以主动提及或推荐相关内容。")
            elif key.startswith("knows_user_dislikes_") and value:
                thing = key.replace("knows_user_dislikes_", "")
                additions.append(f"用户不喜欢{thing}，避免提及相关话题。")
        
        # 将学习到的偏好写入 persona_mutable.md（可变层）
        await self._update_mutable_preferences(state.character_id, additions)
        
        return "\n".join(additions[:5])  # 最多 5 条

    async def _update_mutable_preferences(self, character_id: str, additions: list):
        """将学习到的用户偏好写入 persona_mutable.md"""
        import pathlib
        char_dir = pathlib.Path(__file__).parent.parent / "characters" / character_id
        mutable_path = char_dir / "persona_mutable.md"
        
        if not mutable_path.exists():
            return
        
        content = mutable_path.read_text(encoding='utf-8')
        
        # 替换"学习到的用户偏好"部分
        marker = "## 学习到的用户偏好"
        if marker not in content:
            return
        
        # 找到该段落的起止位置
        start = content.find(marker)
        end_marker = "\n## "
        end = content.find(end_marker, start + len(marker))
        if end < 0:
            end = len(content)
        
        # 构建新的偏好段落
        prefs_lines = [marker, "", "> 由进化系统从对话中自动提取", ""]
        if additions:
            for a in additions[:5]:
                prefs_lines.append(f"- {a}")
        else:
            prefs_lines.append("（暂无记录）")
        prefs_lines.append("")
        
        new_section = "\n".join(prefs_lines)
        content = content[:start] + new_section + content[end:]
        
        mutable_path.write_text(content, encoding='utf-8')
        logger.info(f"[Evolution] 更新 persona_mutable.md 偏好: {len(additions)} 条")
    
    # ============================================================
    # 数据库操作
    # ============================================================
    
    async def save_memory(self, memory: CharacterMemory) -> int:
        """保存记忆到数据库"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO character_memory 
                    (user_id, character_id, memory_content, memory_type, importance, created_at, last_accessed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    memory.user_id,
                    memory.character_id,
                    memory.memory_content,
                    memory.memory_type,
                    memory.importance,
                    memory.created_at,
                    memory.last_accessed or memory.created_at,
                ))

                memory_id = cursor.lastrowid
                logger.info(f"[Evolution] 保存记忆: {memory.memory_content[:30]}...")
                return memory_id

            except Exception as e:
                logger.error(f"[Evolution] 保存记忆失败: {e}")
                return 0
    
    async def get_user_memories(
        self, 
        user_id: int, 
        character_id: str,
        limit: int = 10
    ) -> List[CharacterMemory]:
        """获取用户的记忆"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    SELECT id, user_id, character_id, memory_content, memory_type, importance, created_at, last_accessed
                    FROM character_memory
                    WHERE user_id = ? AND character_id = ?
                    ORDER BY importance DESC, created_at DESC
                    LIMIT ?
                """, (user_id, character_id, limit))

                rows = cursor.fetchall()

                memories = []
                for row in rows:
                    memories.append(CharacterMemory(
                        id=row[0],
                        user_id=row[1],
                        character_id=row[2],
                        memory_content=row[3],
                        memory_type=row[4],
                        importance=row[5],
                        created_at=row[6],
                        last_accessed=row[7],
                    ))

                return memories

            except Exception as e:
                logger.error(f"[Evolution] 获取记忆失败: {e}")
                return []
    
    async def get_or_create_state(
        self, 
        user_id: int, 
        character_id: str
    ) -> CharacterState:
        """获取或创建角色状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    SELECT id, user_id, character_id, emotion_state, emotion_valence, emotion_arousal,
                           evolution_points, personality_traits, system_prompt_additions, updated_at
                    FROM character_state
                    WHERE user_id = ? AND character_id = ?
                """, (user_id, character_id))

                row = cursor.fetchone()

                if row:
                    return CharacterState(
                        id=row[0],
                        user_id=row[1],
                        character_id=row[2],
                        emotion_state=row[3],
                        emotion_valence=row[4],
                        emotion_arousal=row[5],
                        evolution_points=row[6],
                        personality_traits=row[7],
                        system_prompt_additions=row[8],
                        updated_at=row[9],
                    )
                else:
                    # 创建新状态
                    now = datetime.now().isoformat()
                    cursor.execute("""
                        INSERT INTO character_state 
                        (user_id, character_id, emotion_state, emotion_valence, emotion_arousal,
                         evolution_points, personality_traits, system_prompt_additions, updated_at)
                        VALUES (?, ?, 'neutral', 0.0, 0.0, 0, '{}', '', ?)
                    """, (user_id, character_id, now))

                    return CharacterState(
                        id=cursor.lastrowid,
                        user_id=user_id,
                        character_id=character_id,
                        emotion_state="neutral",
                        emotion_valence=0.0,
                        emotion_arousal=0.0,
                        evolution_points=0,
                        personality_traits="{}",
                        system_prompt_additions="",
                        updated_at=now,
                    )

            except Exception as e:
                logger.error(f"[Evolution] 获取角色状态失败: {e}")
                raise
    
    async def update_state(self, state: CharacterState):
        """更新角色状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    UPDATE character_state
                    SET emotion_state = ?, emotion_valence = ?, emotion_arousal = ?,
                        evolution_points = ?, personality_traits = ?, system_prompt_additions = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    state.emotion_state,
                    state.emotion_valence,
                    state.emotion_arousal,
                    state.evolution_points,
                    state.personality_traits,
                    state.system_prompt_additions,
                    datetime.now().isoformat(),
                    state.id,
                ))

            except Exception as e:
                logger.error(f"[Evolution] 更新角色状态失败: {e}")
                raise
    
    async def close(self):
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()


# ============================================================
# 便捷函数
# ============================================================

_evolution_service: Optional[EvolutionService] = None


def get_evolution_service() -> EvolutionService:
    """获取全局进化服务实例"""
    global _evolution_service
    if _evolution_service is None:
        _evolution_service = EvolutionService()
    return _evolution_service


async def analyze_and_evolve(
    user_id: int,
    character_id: str,
    chat_history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    分析对话并进化角色（便捷函数）
    
    Args:
        user_id: 用户 ID
        character_id: 角色 ID
        chat_history: 对话历史
    
    Returns:
        进化结果
    """
    service = get_evolution_service()
    
    # 1. 提取记忆
    memories = await service.extract_memories(chat_history)
    
    # 2. 保存记忆
    for memory in memories:
        memory.user_id = user_id
        memory.character_id = character_id
        await service.save_memory(memory)
    
    # 3. 获取当前状态
    state = await service.get_or_create_state(user_id, character_id)
    
    # 4. 分析情绪
    emotion_delta = await service.analyze_emotion(chat_history)
    state.emotion_valence += emotion_delta["valence_delta"]
    state.emotion_arousal += emotion_delta["arousal_delta"]
    
    # 限制范围
    state.emotion_valence = max(-1.0, min(1.0, state.emotion_valence))
    state.emotion_arousal = max(-1.0, min(1.0, state.emotion_arousal))
    state.emotion_state = service.determine_emotion_state(
        state.emotion_valence, state.emotion_arousal
    )
    
    # 5. 计算进化点数
    points = service.calculate_evolution_points(chat_history, memories)
    state.evolution_points += points
    
    # 6. 检查是否需要性格进化
    if state.evolution_points >= EVOLUTION_CONFIG["personality_update_threshold"]:
        all_memories = await service.get_user_memories(user_id, character_id, limit=20)
        state.system_prompt_additions = await service.evolve_personality(state, all_memories)
        state.evolution_points = 0  # 重置点数
        logger.info(f"[Evolution] 角色性格进化！新提示词: {state.system_prompt_additions[:50]}...")
    
    # 7. 更新状态
    await service.update_state(state)
    
    return {
        "memories_added": len(memories),
        "evolution_points": points,
        "total_points": state.evolution_points,
        "emotion_state": state.emotion_state,
        "personality_evolved": state.evolution_points == 0,
    }


async def get_context_for_reply(
    user_id: int,
    character_id: str
) -> Dict[str, Any]:
    """
    获取回复前的上下文（记忆 + 角色状态）
    
    Args:
        user_id: 用户 ID
        character_id: 角色 ID
    
    Returns:
        上下文信息
    """
    service = get_evolution_service()
    
    memories = await service.get_user_memories(user_id, character_id)
    state = await service.get_or_create_state(user_id, character_id)
    
    return {
        "memories": [m.memory_content for m in memories],
        "emotion_state": state.emotion_state,
        "system_prompt_additions": state.system_prompt_additions,
    }


# ============================================================
# 后台任务
# ============================================================

async def background_evolution_task():
    """
    后台进化任务（定期处理未分析的对话）
    可通过 asyncio.create_task() 启动
    """
    logger.info("[Evolution] 后台任务启动")
    
    while True:
        try:
            await asyncio.sleep(EVOLUTION_CONFIG["background_task_interval"])
            
            # TODO: 从数据库获取需要处理的对话
            # 这里可以添加批量处理逻辑
            
            logger.debug("[Evolution] 后台任务运行中...")
            
        except asyncio.CancelledError:
            logger.info("[Evolution] 后台任务停止")
            break
        except Exception as e:
            logger.error(f"[Evolution] 后台任务错误: {e}")


# ============================================================
# 测试
# ============================================================

async def test_evolution_service():
    """测试进化服务"""
    service = EvolutionService()
    
    # 测试对话
    chat_history = [
        {"role": "user", "content": "我今天心情很好，刚吃了一个很好吃的草莓蛋糕"},
        {"role": "assistant", "content": "哇，草莓蛋糕听起来很好吃呢！"},
        {"role": "user", "content": "我最喜欢草莓了"},
    ]
    
    # 提取记忆
    memories = await service.extract_memories(chat_history)
    print(f"提取到 {len(memories)} 条记忆:")
    for m in memories:
        print(f"  - [{m.memory_type}] {m.memory_content} (重要性: {m.importance})")
    
    # 分析情绪
    emotion_delta = await service.analyze_emotion(chat_history)
    print(f"\n情绪变化: {emotion_delta}")
    
    await service.close()


if __name__ == "__main__":
    asyncio.run(test_evolution_service())
