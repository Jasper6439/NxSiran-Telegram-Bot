"""
ChromaDB 记忆技能 - 向量数据库存储和语义搜索记忆
让车如云能记住并搜索聊天内容
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# ChromaDB
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

# 数据存储路径
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
CHROMA_DIR = os.path.join(DATA_DIR, 'chroma_db')


class ChromaDBMemory:
    """ChromaDB 向量记忆系统 - 支持多角色独立集合"""
    
    def __init__(self, character_id: str = 'chayewoon'):
        self.character_id = character_id
        self.client = None
        self.collection = None
        self._initialized = False
    
    def _ensure_init(self):
        """延迟初始化"""
        if self._initialized:
            return True
        
        try:
            # 确保目录存在
            os.makedirs(CHROMA_DIR, exist_ok=True)
            
            # 初始化 ChromaDB 客户端（持久化存储）
            self.client = chromadb.PersistentClient(path=CHROMA_DIR)
            
            # 获取或创建集合（每个角色独立）
            self.collection = self.client.get_or_create_collection(
                name=f"{self.character_id}_memories",
                metadata={"description": f"{self.character_id} 的记忆向量数据库"}
            )
            
            self._initialized = True
            logger.info(f"[ChromaDB] 初始化成功，当前记忆数: {self.collection.count()}")
            return True
            
        except Exception as e:
            logger.error(f"[ChromaDB] 初始化失败: {e}")
            return False
    
    def add_memory(self, user_id: int, content: str, metadata: Dict = None) -> bool:
        """
        添加记忆
        
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
            # 生成唯一ID
            timestamp = datetime.now().isoformat()
            memory_id = f"mem_{user_id}_{timestamp}"
            
            # 默认元数据
            if metadata is None:
                metadata = {}
            
            metadata.update({
                "user_id": str(user_id),
                "timestamp": timestamp,
                "content_preview": content[:100] if len(content) > 100 else content
            })
            
            # 添加到集合
            self.collection.add(
                documents=[content],
                metadatas=[metadata],
                ids=[memory_id]
            )
            
            logger.info(f"[ChromaDB] 添加记忆: {content[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"[ChromaDB] 添加记忆失败: {e}")
            return False
    
    def search_memories(self, query: str, user_id: int = None, n_results: int = 5) -> List[Dict]:
        """
        语义搜索记忆
        
        Args:
            query: 搜索查询
            user_id: 可选，限制为特定用户的记忆
            n_results: 返回结果数量
        
        Returns:
            匹配的记忆列表
        """
        if not self._ensure_init():
            return []
        
        try:
            # 构建过滤条件
            where_filter = None
            if user_id:
                where_filter = {"user_id": str(user_id)}
            
            # 搜索
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
            
            # 整理结果
            memories = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    memories.append({
                        "content": doc,
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else 0
                    })
            
            logger.info(f"[ChromaDB] 搜索 '{query[:30]}...' 找到 {len(memories)} 条记忆")
            return memories
            
        except Exception as e:
            logger.error(f"[ChromaDB] 搜索失败: {e}")
            return []
    
    def get_recent_memories(self, user_id: int = None, limit: int = 10) -> List[Dict]:
        """
        获取最近的记忆
        
        Args:
            user_id: 可选，限制为特定用户
            limit: 返回数量
        
        Returns:
            最近的记忆列表
        """
        if not self._ensure_init():
            return []
        
        try:
            # 构建过滤条件
            where_filter = None
            if user_id:
                where_filter = {"user_id": str(user_id)}
            
            # 获取所有匹配的记忆
            results = self.collection.get(
                where=where_filter,
                limit=limit,
                include=["documents", "metadatas"]
            )
            
            # 整理结果
            memories = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents']):
                    memories.append({
                        "content": doc,
                        "metadata": results['metadatas'][i] if results['metadatas'] else {}
                    })
            
            return memories
            
        except Exception as e:
            logger.error(f"[ChromaDB] 获取最近记忆失败: {e}")
            return []
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除特定记忆"""
        if not self._ensure_init():
            return False
        
        try:
            self.collection.delete(ids=[memory_id])
            logger.info(f"[ChromaDB] 删除记忆: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"[ChromaDB] 删除失败: {e}")
            return False
    
    def clear_user_memories(self, user_id: int) -> bool:
        """清空特定用户的所有记忆"""
        if not self._ensure_init():
            return False
        
        try:
            # 获取该用户的所有记忆ID
            results = self.collection.get(
                where={"user_id": str(user_id)},
                include=[]
            )
            
            if results and results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"[ChromaDB] 清空用户 {user_id} 的 {len(results['ids'])} 条记忆")
            
            return True
        except Exception as e:
            logger.error(f"[ChromaDB] 清空失败: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        if not self._ensure_init():
            return {"total": 0, "status": "not_initialized"}
        
        return {
            "total": self.collection.count(),
            "status": "ready"
        }


# ===== 多角色记忆管理 =====

# 全局实例字典（每个角色独立）
_memory_instances: Dict[str, ChromaDBMemory] = {}


def get_memory(character_id: str = 'chayewoon') -> ChromaDBMemory:
    """获取指定角色的记忆实例（懒加载）"""
    if character_id not in _memory_instances:
        _memory_instances[character_id] = ChromaDBMemory(character_id)
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
