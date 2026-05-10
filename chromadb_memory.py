"""
Qdrant Cloud 记忆技能 - 向量数据库存储和语义搜索记忆
让车如云能记住并搜索聊天内容

替代 ChromaDB，使用远程 Qdrant Cloud，本地零内存占用。
接口与原 ChromaDBMemory 完全一致，可直接替换。

环境变量：
  QDRANT_URL       - Qdrant Cloud 集群 URL
  QDRANT_API_KEY   - Qdrant Cloud API Key
  OPENROUTER_API_KEY - OpenRouter API Key（用于生成 embedding）
"""

import os
import logging
import hashlib
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct, VectorParams, Distance,
    Filter, FieldCondition, MatchValue,
    PayloadSchemaType,
)

logger = logging.getLogger(__name__)

# 配置
QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", os.environ.get("AI_API_KEY", ""))
EMBEDDING_API = os.environ.get("EMBEDDING_API", "https://openrouter.ai/api/v1/embeddings")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
VECTOR_DIMENSIONS = 768


# ===== Embedding 客户端 =====

class _EmbeddingClient:
    """调用 OpenRouter API 生成文本向量（带缓存）"""

    def __init__(self):
        self._cache: Dict[str, List[float]] = {}

    def embed(self, text: str) -> List[float]:
        if text in self._cache:
            return self._cache[text]

        if not OPENROUTER_API_KEY:
            logger.warning("[Qdrant] 未配置 OPENROUTER_API_KEY，使用零向量（记忆搜索将不生效）")
            return [0.0] * VECTOR_DIMENSIONS

        try:
            resp = requests.post(
                EMBEDDING_API,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"model": EMBEDDING_MODEL, "input": text},
                timeout=10,
            )
            resp.raise_for_status()
            vector = resp.json()["data"][0]["embedding"]

            # 截断/填充到目标维度
            if len(vector) > VECTOR_DIMENSIONS:
                vector = vector[:VECTOR_DIMENSIONS]
            elif len(vector) < VECTOR_DIMENSIONS:
                vector = vector + [0.0] * (VECTOR_DIMENSIONS - len(vector))

            self._cache[text] = vector
            return vector

        except Exception as e:
            logger.error(f"[Qdrant] Embedding 失败: {e}")
            return [0.0] * VECTOR_DIMENSIONS

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


_embedding_client = _EmbeddingClient()


# ===== Qdrant Cloud 记忆系统 =====

class QdrantMemory:
    """Qdrant Cloud 向量记忆系统 - 支持多角色独立集合"""

    def __init__(self, character_id: str = 'chayewoon'):
        self.character_id = character_id
        self.client: Optional[QdrantClient] = None
        self._initialized = False

    def _ensure_init(self) -> bool:
        """延迟初始化"""
        if self._initialized:
            return True

        if not QDRANT_URL or not QDRANT_API_KEY:
            logger.error("[Qdrant] 未配置 QDRANT_URL 和 QDRANT_API_KEY 环境变量")
            return False

        try:
            self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

            # 获取或创建集合（每个角色独立）
            collection_name = f"{self.character_id}_memories"
            try:
                self.client.get_collection(collection_name)
            except Exception:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=VECTOR_DIMENSIONS,
                        distance=Distance.COSINE,
                    ),
                )
                # 为 user_id 字段创建索引（过滤查询必需）
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="user_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )

            self._initialized = True
            count = self.client.get_collection(collection_name).points_count
            logger.info(f"[Qdrant] 初始化成功，当前记忆数: {count}")
            return True

        except Exception as e:
            logger.error(f"[Qdrant] 初始化失败: {e}")
            return False

    def _collection_name(self) -> str:
        return f"{self.character_id}_memories"

    def add_memory(self, user_id: int, content: str, metadata: Dict = None) -> bool:
        """
        添加记忆（接口与 ChromaDBMemory 完全一致）

        Args:
            user_id: 用户ID
            content: 记忆内容
            metadata: 额外元数据（如角色、情绪、时间等）

        Returns:
            是否成功
        """
        if not self._ensure_init():
            return False

        try:
            timestamp = datetime.now().isoformat()
            memory_id = f"mem_{user_id}_{timestamp}"
            # 用 MD5 生成 Qdrant 兼容的 UUID
            uuid = hashlib.md5(memory_id.encode()).hexdigest()

            if metadata is None:
                metadata = {}

            metadata.update({
                "user_id": str(user_id),
                "timestamp": timestamp,
                "content_preview": content[:100] if len(content) > 100 else content,
            })

            vector = _embedding_client.embed(content)

            self.client.upsert(
                collection_name=self._collection_name(),
                points=[PointStruct(id=uuid, vector=vector, payload=metadata)],
            )

            logger.info(f"[Qdrant] 添加记忆: {content[:50]}...")
            return True

        except Exception as e:
            logger.error(f"[Qdrant] 添加记忆失败: {e}")
            return False

    def search_memories(self, query: str, user_id: int = None, n_results: int = 5) -> List[Dict]:
        """
        语义搜索记忆（接口与 ChromaDBMemory 完全一致）

        Args:
            query: 搜索查询
            user_id: 可选，限制为特定用户的记忆
            n_results: 返回结果数量

        Returns:
            匹配的记忆列表（格式与 ChromaDB 版一致）
        """
        if not self._ensure_init():
            return []

        try:
            # 构建过滤条件
            conditions = []
            if user_id:
                conditions.append(FieldCondition(key="user_id", match=MatchValue(value=str(user_id))))
            query_filter = Filter(must=conditions) if conditions else None

            query_vector = _embedding_client.embed(query)

            # 使用 query_points API（兼容新版 qdrant-client）
            results = self.client.query_points(
                collection_name=self._collection_name(),
                query=query_vector,
                query_filter=query_filter,
                limit=n_results,
            ).points

            # 整理结果（格式与 ChromaDB 版一致）
            memories = []
            for r in results:
                memories.append({
                    "content": r.payload.get("content_preview", ""),
                    "metadata": {k: v for k, v in r.payload.items() if k != "content_preview"},
                    "distance": 1.0 - r.score,  # Qdrant score 越大越相似，转成 distance
                })

            logger.info(f"[Qdrant] 搜索 '{query[:30]}...' 找到 {len(memories)} 条记忆")
            return memories

        except Exception as e:
            logger.error(f"[Qdrant] 搜索失败: {e}")
            return []

    def get_recent_memories(self, user_id: int = None, limit: int = 10) -> List[Dict]:
        """
        获取最近的记忆（接口与 ChromaDBMemory 完全一致）

        Args:
            user_id: 可选，限制为特定用户
            limit: 返回数量

        Returns:
            最近的记忆列表
        """
        if not self._ensure_init():
            return []

        try:
            conditions = []
            if user_id:
                conditions.append(FieldCondition(key="user_id", match=MatchValue(value=str(user_id))))
            scroll_filter = Filter(must=conditions) if conditions else None

            results = self.client.scroll(
                collection_name=self._collection_name(),
                scroll_filter=scroll_filter,
                limit=limit,
                with_payload=True,
            )

            memories = []
            if results and results[0]:
                for point in results[0]:
                    payload = point.payload or {}
                    memories.append({
                        "content": payload.get("content_preview", ""),
                        "metadata": {k: v for k, v in payload.items() if k != "content_preview"},
                    })

            return memories

        except Exception as e:
            logger.error(f"[Qdrant] 获取最近记忆失败: {e}")
            return []

    def delete_memory(self, memory_id: str) -> bool:
        """删除特定记忆"""
        if not self._ensure_init():
            return False

        try:
            # 将 memory_id 转为 UUID
            uuid = hashlib.md5(memory_id.encode()).hexdigest()
            self.client.delete(
                collection_name=self._collection_name(),
                points_selector=[uuid],
            )
            logger.info(f"[Qdrant] 删除记忆: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"[Qdrant] 删除失败: {e}")
            return False

    def clear_user_memories(self, user_id: int) -> bool:
        """清空特定用户的所有记忆"""
        if not self._ensure_init():
            return False

        try:
            # 搜索该用户的所有记忆点
            conditions = [FieldCondition(key="user_id", match=MatchValue(value=str(user_id)))]
            results = self.client.scroll(
                collection_name=self._collection_name(),
                scroll_filter=Filter(must=conditions),
                limit=10000,
                with_payload=False,
            )

            if results and results[0]:
                ids = [point.id for point in results[0]]
                if ids:
                    self.client.delete(
                        collection_name=self._collection_name(),
                        points_selector=ids,
                    )
                    logger.info(f"[Qdrant] 清空用户 {user_id} 的 {len(ids)} 条记忆")

            return True
        except Exception as e:
            logger.error(f"[Qdrant] 清空失败: {e}")
            return False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        if not self._ensure_init():
            return {"total": 0, "status": "not_initialized"}

        try:
            count = self.client.get_collection(self._collection_name()).points_count
            return {"total": count, "status": "ready"}
        except Exception:
            return {"total": 0, "status": "error"}


# ===== 多角色记忆管理 =====

_memory_instances: Dict[str, QdrantMemory] = {}


def get_memory(character_id: str = 'chayewoon') -> QdrantMemory:
    """获取指定角色的记忆实例（懒加载）"""
    if character_id not in _memory_instances:
        _memory_instances[character_id] = QdrantMemory(character_id)
    return _memory_instances[character_id]


# ===== 便捷函数（默认使用当前角色） =====

def add_memory(user_id: int, content: str, metadata: Dict = None, character_id: str = 'chayewoon') -> bool:
    """添加记忆"""
    return get_memory(character_id).add_memory(user_id, content, metadata)


def search_memories(query: str, user_id: int = None, n_results: int = 5, character_id: str = 'chayewoon') -> List[Dict]:
    """搜索记忆"""
    return get_memory(character_id).search_memories(query, user_id, n_results)


def get_recent_memories(user_id: int = None, limit: int = 10, character_id: str = 'chayewoon') -> List[Dict]:
    """获取最近记忆"""
    return get_memory(character_id).get_recent_memories(user_id, limit)


def get_memory_stats(character_id: str = 'chayewoon') -> Dict:
    """获取记忆统计"""
    return get_memory(character_id).get_stats()
