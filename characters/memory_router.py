"""
统一记忆路由层 (MemoryRouter)
============================
将项目中 4 套异构记忆系统统一为单一入口：

  1. legacy JSON 记忆  (memory_legacy.py)   — 关键词匹配，轻量快速
  2. LightRAG 语义记忆 (memory.py)          — 向量语义搜索，深度检索
  3. 角色进化记忆      (character_learning.py) — 用户偏好 / 情感模式
  4. 数据库记忆        (database/chat.py)   — 结构化 key-value 存储

路由策略：
  - 按记忆类别（category）决定写入哪些 store
  - 按查询长度决定搜索优先级（短查询先查 legacy，长查询先查 LightRAG）
  - 所有 store 独立容错，任一失败不影响其余 store

本模块仅作路由层，不重新实现底层逻辑。
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 记忆类别定义
# ============================================================

class MemoryCategory(str, Enum):
    """记忆类别及其路由目标"""
    DIALOGUE = "dialogue"       # 对话交换 → LightRAG + legacy JSON
    PREFERENCE = "preference"   # 用户偏好 → evolution service + DB
    EVENT = "event"             # 重要事件 → legacy JSON + LightRAG
    EMOTION = "emotion"         # 情感瞬间 → evolution service + DB
    FACT = "fact"               # 事实信息 → LightRAG
    OTHER = "other"             # 未分类   → legacy JSON


# 短查询阈值（字符数）
SHORT_QUERY_THRESHOLD = 50


# ============================================================
# 搜索结果数据类
# ============================================================

@dataclass
class MemoryResult:
    """统一的记忆搜索结果"""
    content: str
    source: str          # 来源: "legacy" | "lightrag" | "evolution" | "database"
    score: float = 0.0   # 相关度分数（越高越相关）
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        preview = self.content[:40].replace("\n", " ")
        return f"MemoryResult({self.source}: {preview}... score={self.score:.2f})"


# ============================================================
# 路由配置：每个类别 → 应写入 / 查询的 store 列表
# ============================================================

_CATEGORY_ROUTES: Dict[MemoryCategory, Dict[str, List[str]]] = {
    MemoryCategory.DIALOGUE: {
        "write": ["lightrag", "legacy"],
        "query": ["lightrag", "legacy"],
    },
    MemoryCategory.PREFERENCE: {
        "write": ["evolution", "database"],
        "query": ["evolution", "database"],
    },
    MemoryCategory.EVENT: {
        "write": ["legacy", "lightrag"],
        "query": ["legacy", "lightrag"],
    },
    MemoryCategory.EMOTION: {
        "write": ["evolution", "database"],
        "query": ["evolution", "database"],
    },
    MemoryCategory.FACT: {
        "write": ["lightrag"],
        "query": ["lightrag"],
    },
    MemoryCategory.OTHER: {
        "write": ["legacy"],
        "query": ["legacy"],
    },
}


# ============================================================
# MemoryRouter
# ============================================================

class MemoryRouter:
    """统一记忆路由器。

    通过组合 legacy JSON、LightRAG、角色进化、数据库四套记忆系统，
    提供统一的 add / search / context 接口。

    Args:
        character_id: 角色标识符，默认 'chayewoon'
    """

    def __init__(self, character_id: str = "chayewoon"):
        self.character_id = character_id
        self._legacy = None
        self._lightrag = None
        self._evolution = None
        self._db = None
        self._initialized = False

    # ----------------------------------------------------------
    # 延迟加载各 store
    # ----------------------------------------------------------

    def _init_stores(self) -> None:
        """惰性初始化各记忆 store（仅导入，不做重 I/O）"""
        if self._initialized:
            return

        # 1) Legacy JSON 记忆
        try:
            from characters.memory_legacy import (
                save_semantic_memory,
                search_semantic_memory,
                save_memory_entry,
                get_long_term_memory,
                get_semantic_memory_context,
            )
            self._legacy = {
                "save": save_semantic_memory,
                "search": search_semantic_memory,
                "save_entry": save_memory_entry,
                "get_long_term": get_long_term_memory,
                "get_context": get_semantic_memory_context,
            }
            logger.debug("[MemoryRouter] legacy store loaded")
        except Exception as e:
            logger.warning(f"[MemoryRouter] legacy store unavailable: {e}")

        # 2) LightRAG 语义记忆
        try:
            from characters.memory import get_memory
            self._lightrag = get_memory(self.character_id)
            logger.debug("[MemoryRouter] lightrag store loaded")
        except Exception as e:
            logger.warning(f"[MemoryRouter] lightrag store unavailable: {e}")

        # 3) 角色进化记忆
        try:
            from characters.character_learning import get_learning
            self._evolution = get_learning(self.character_id)
            logger.debug("[MemoryRouter] evolution store loaded")
        except Exception as e:
            logger.warning(f"[MemoryRouter] evolution store unavailable: {e}")

        # 4) 数据库记忆
        try:
            from database import get_db
            self._db = get_db()
            logger.debug("[MemoryRouter] database store loaded")
        except Exception as e:
            logger.warning(f"[MemoryRouter] database store unavailable: {e}")

        self._initialized = True

    # ----------------------------------------------------------
    # 1. add_memory — 写入记忆
    # ----------------------------------------------------------

    async def add_memory(
        self,
        content: str,
        category: str = "other",
        user_id: int = 0,
    ) -> Dict[str, bool]:
        """将记忆路由到对应的 store。

        Args:
            content:   记忆内容
            category:  记忆类别（dialogue / preference / event / emotion / fact / other）
            user_id:   用户 ID

        Returns:
            各 store 写入结果 ``{"legacy": True, "lightrag": False, ...}``
        """
        self._init_stores()

        cat = self._resolve_category(category)
        routes = _CATEGORY_ROUTES.get(cat, _CATEGORY_ROUTES[MemoryCategory.OTHER])
        targets = routes["write"]

        results: Dict[str, bool] = {}

        for store_name in targets:
            try:
                ok = await self._write_to_store(store_name, content, cat, user_id)
                results[store_name] = ok
            except Exception as e:
                logger.error(f"[MemoryRouter] write to {store_name} failed: {e}")
                results[store_name] = False

        return results

    async def _write_to_store(
        self,
        store_name: str,
        content: str,
        category: MemoryCategory,
        user_id: int,
    ) -> bool:
        """写入单个 store（内部路由）"""

        if store_name == "legacy" and self._legacy:
            self._legacy["save"](content, content, category.value)
            self._legacy["save_entry"](content, user_id)
            return True

        if store_name == "lightrag" and self._lightrag:
            return await self._lightrag.add_memory(
                user_id, content, metadata={"category": category.value}
            )

        if store_name == "evolution" and self._evolution:
            # 进化系统主要从聊天记录学习，此处将内容写入 memories.md
            try:
                lines = [f"- {content}"]
                self._evolution._update_memories_key_events.__func__  # type-check
            except Exception:
                pass
            # 使用写文件方式追加到角色 memories.md
            try:
                mem_path = os.path.join(self._evolution.char_dir, "memories.md")
                existing = ""
                if os.path.exists(mem_path):
                    with open(mem_path, "r", encoding="utf-8") as f:
                        existing = f.read()
                if content not in existing:
                    with open(mem_path, "a", encoding="utf-8") as f:
                        f.write(f"\n- {content}")
                return True
            except Exception as e:
                logger.error(f"[MemoryRouter] evolution write failed: {e}")
                return False

        if store_name == "database" and self._db:
            key = f"{category.value}_{abs(hash(content)) % 10**8}"
            self._db.save_memory(user_id, self.character_id, key, content, category.value)
            return True

        return False

    # ----------------------------------------------------------
    # 2. search_memories — 搜索记忆
    # ----------------------------------------------------------

    async def search_memories(
        self,
        query: str,
        user_id: int = 0,
        limit: int = 10,
    ) -> List[MemoryResult]:
        """搜索所有相关 store，返回按相关度排序的结果。

        短查询（< 50 字符）优先查 legacy；长查询优先查 LightRAG。
        进化记忆始终作为补充结果附加。

        Args:
            query:   搜索关键词
            user_id: 用户 ID
            limit:   最大返回条数

        Returns:
            按 score 降序排列的 MemoryResult 列表
        """
        self._init_stores()

        all_results: List[MemoryResult] = []
        is_short = len(query) < SHORT_QUERY_THRESHOLD

        # 确定搜索顺序
        if is_short:
            primary, secondary = "legacy", "lightrag"
        else:
            primary, secondary = "lightrag", "legacy"

        # 主搜索
        all_results.extend(await self._search_store(primary, query, user_id, limit))
        # 次搜索
        all_results.extend(await self._search_store(secondary, query, user_id, limit))
        # 补充：进化记忆
        all_results.extend(await self._search_store("evolution", query, user_id, limit))
        # 补充：数据库
        all_results.extend(await self._search_store("database", query, user_id, limit))

        # 去重（基于内容前 100 字符）
        seen = set()
        unique: List[MemoryResult] = []
        for r in all_results:
            key = r.content[:100].strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(r)

        # 按 score 降序
        unique.sort(key=lambda x: x.score, reverse=True)
        return unique[:limit]

    async def _search_store(
        self,
        store_name: str,
        query: str,
        user_id: int,
        limit: int,
    ) -> List[MemoryResult]:
        """搜索单个 store，异常时返回空列表"""
        try:
            if store_name == "legacy" and self._legacy:
                raw = self._legacy["search"](query, topk=limit)
                return [
                    MemoryResult(
                        content=f"{m.get('key', '')}: {m.get('value', '')}",
                        source="legacy",
                        score=float(m.get("access_count", 0)) + 1.0,
                        metadata={"category": m.get("category", "")},
                    )
                    for m in raw
                ]

            if store_name == "lightrag" and self._lightrag:
                raw = await self._lightrag.search_memories(query, user_id, n_results=limit)
                return [
                    MemoryResult(
                        content=m.get("content", ""),
                        source="lightrag",
                        score=1.0 - m.get("distance", 0.5),
                        metadata=m.get("metadata", {}),
                    )
                    for m in raw
                ]

            if store_name == "evolution" and self._evolution:
                # 读取 memories.md 中与查询相关的行
                mem_path = os.path.join(self._evolution.char_dir, "memories.md")
                if os.path.exists(mem_path):
                    with open(mem_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    results = []
                    query_lower = query.lower()
                    for line in lines:
                        line_s = line.strip()
                        if line_s and len(line_s) > 3:
                            # 简单关键词匹配
                            overlap = len(set(query_lower) & set(line_s.lower()))
                            score = overlap / max(len(set(query_lower)), 1)
                            if score > 0.1:
                                results.append(MemoryResult(
                                    content=line_s,
                                    source="evolution",
                                    score=score,
                                    metadata={"file": "memories.md"},
                                ))
                    results.sort(key=lambda x: x.score, reverse=True)
                    return results[:limit]

            if store_name == "database" and self._db:
                raw = self._db.get_memories(user_id, self.character_id)
                results = []
                query_lower = query.lower()
                for m in raw:
                    val = m.get("memory_value", "")
                    key = m.get("memory_key", "")
                    combined = f"{key} {val}".lower()
                    overlap = len(set(query_lower) & set(combined))
                    score = overlap / max(len(set(query_lower)), 1)
                    if score > 0.1:
                        results.append(MemoryResult(
                            content=val,
                            source="database",
                            score=score,
                            metadata={"key": key, "category": m.get("category", "")},
                        ))
                results.sort(key=lambda x: x.score, reverse=True)
                return results[:limit]

        except Exception as e:
            logger.warning(f"[MemoryRouter] search {store_name} failed: {e}")

        return []

    # ----------------------------------------------------------
    # 3. get_recent_memories — 获取最近记忆
    # ----------------------------------------------------------

    async def get_recent_memories(
        self,
        user_id: int = 0,
        limit: int = 10,
    ) -> List[MemoryResult]:
        """从所有 store 获取最近的记忆。

        Args:
            user_id: 用户 ID
            limit:   每个 store 最多返回条数

        Returns:
            按时间倒序的 MemoryResult 列表（最新在前）
        """
        self._init_stores()

        all_results: List[MemoryResult] = []

        # Legacy — 最近的长期记忆
        try:
            if self._legacy:
                raw_text = self._legacy["get_long_term"](user_id)
                if raw_text:
                    for line in raw_text.split("\n"):
                        line = line.strip()
                        if line:
                            all_results.append(MemoryResult(
                                content=line,
                                source="legacy",
                                score=1.0,
                            ))
        except Exception as e:
            logger.warning(f"[MemoryRouter] recent legacy failed: {e}")

        # LightRAG — 最近插入
        try:
            if self._lightrag:
                raw = self._lightrag.get_recent_memories(user_id, limit=limit)
                for m in raw:
                    all_results.append(MemoryResult(
                        content=m.get("content", ""),
                        source="lightrag",
                        score=1.0,
                        metadata=m.get("metadata", {}),
                    ))
        except Exception as e:
            logger.warning(f"[MemoryRouter] recent lightrag failed: {e}")

        # Database — 最近记忆
        try:
            if self._db:
                raw = self._db.get_memories(user_id, self.character_id)
                for m in raw[:limit]:
                    all_results.append(MemoryResult(
                        content=m.get("memory_value", ""),
                        source="database",
                        score=1.0,
                        metadata={"key": m.get("memory_key", ""), "category": m.get("category", "")},
                    ))
        except Exception as e:
            logger.warning(f"[MemoryRouter] recent database failed: {e}")

        # Evolution — memories.md 全文（最后 N 行非空行）
        try:
            if self._evolution:
                mem_path = os.path.join(self._evolution.char_dir, "memories.md")
                if os.path.exists(mem_path):
                    with open(mem_path, "r", encoding="utf-8") as f:
                        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
                    for line in lines[-limit:]:
                        all_results.append(MemoryResult(
                            content=line,
                            source="evolution",
                            score=0.5,
                            metadata={"file": "memories.md"},
                        ))
        except Exception as e:
            logger.warning(f"[MemoryRouter] recent evolution failed: {e}")

        return all_results[:limit * 2]  # 合并后限制总量

    # ----------------------------------------------------------
    # 4. get_context_for_prompt — 生成 prompt 上下文
    # ----------------------------------------------------------

    async def get_context_for_prompt(
        self,
        query: str,
        user_id: int = 0,
    ) -> str:
        """根据查询生成格式化的记忆上下文字符串，用于注入 system prompt。

        综合搜索结果 + 最近记忆，生成如下格式：
            [相关记忆]
            - ...
            [最近记忆]
            - ...
            [角色记忆]
            ...

        Args:
            query:   当前用户查询
            user_id: 用户 ID

        Returns:
            格式化的上下文字符串（可直接拼入 system prompt）
        """
        self._init_stores()

        sections: List[str] = []

        # --- 相关记忆（语义搜索） ---
        try:
            search_results = await self.search_memories(query, user_id, limit=5)
            if search_results:
                lines = []
                for r in search_results:
                    prefix = f"[{r.source}]"
                    lines.append(f"  - {prefix} {r.content[:200]}")
                sections.append("[相关记忆]\n" + "\n".join(lines))
        except Exception as e:
            logger.warning(f"[MemoryRouter] context search failed: {e}")

        # --- 最近记忆 ---
        try:
            recent = await self.get_recent_memories(user_id, limit=3)
            if recent:
                lines = [f"  - {r.content[:150]}" for r in recent[:3]]
                sections.append("[最近记忆]\n" + "\n".join(lines))
        except Exception as e:
            logger.warning(f"[MemoryRouter] context recent failed: {e}")

        # --- Legacy 语义记忆上下文 ---
        try:
            if self._legacy:
                ctx = self._legacy["get_context"]()
                if ctx:
                    sections.append(f"[语义记忆]\n  {ctx[:500]}")
        except Exception as e:
            logger.warning(f"[MemoryRouter] context legacy failed: {e}")

        # --- 角色进化记忆 (memories.md) ---
        try:
            if self._evolution:
                mem_path = os.path.join(self._evolution.char_dir, "memories.md")
                if os.path.exists(mem_path):
                    with open(mem_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # 取前 800 字符作为角色记忆摘要
                    if content:
                        sections.append(f"[角色记忆]\n  {content[:800]}")
        except Exception as e:
            logger.warning(f"[MemoryRouter] context evolution failed: {e}")

        if not sections:
            return ""

        return "\n\n".join(sections)

    # ----------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------

    @staticmethod
    def _resolve_category(category: str) -> MemoryCategory:
        """将字符串解析为 MemoryCategory 枚举"""
        try:
            return MemoryCategory(category.lower())
        except (ValueError, AttributeError):
            return MemoryCategory.OTHER

    def get_stats(self) -> Dict[str, Any]:
        """获取各 store 状态摘要"""
        self._init_stores()

        stats: Dict[str, Any] = {"character_id": self.character_id}

        stats["legacy"] = "available" if self._legacy else "unavailable"
        stats["lightrag"] = "available" if self._lightrag else "unavailable"
        stats["evolution"] = "available" if self._evolution else "unavailable"
        stats["database"] = "available" if self._db else "unavailable"

        # LightRAG stats
        if self._lightrag:
            try:
                rag_stats = self._lightrag.get_stats()
                stats["lightrag_detail"] = rag_stats
            except Exception:
                pass

        return stats


# ============================================================
# 便捷单例
# ============================================================

_router_instances: Dict[str, MemoryRouter] = {}


def get_router(character_id: str = "chayewoon") -> MemoryRouter:
    """获取 MemoryRouter 单例（按角色隔离）"""
    if character_id not in _router_instances:
        _router_instances[character_id] = MemoryRouter(character_id)
    return _router_instances[character_id]
