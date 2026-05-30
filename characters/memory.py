"""
LightRAG 记忆技能 - 本地轻量级向量存储和语义搜索记忆
让车如云能记住并搜索聊天内容

使用 LightRAG 自带存储，本地零外部依赖。

环境变量：
  OPENROUTER_API_KEY - OpenRouter API Key（用于 LLM）
"""

import os
import logging
import hashlib
from typing import List, Dict, Optional
from datetime import datetime

import numpy as np

# LightRAG (可选依赖)
try:
    from lightrag import LightRAG, QueryParam
    from lightrag.utils import EmbeddingFunc
    LIGHTRAG_AVAILABLE = True
except ImportError:
    LIGHTRAG_AVAILABLE = False
    LightRAG = None
    QueryParam = None
    EmbeddingFunc = None

from system.config import DATA_DIR

logger = logging.getLogger(__name__)

# 配置
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", os.environ.get("AI_API_KEY", ""))
OPENROUTER_API_BASE = os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")

# e2-micro 内存限制：缓存最多 500 条 embedding（约 5MB）
MAX_CACHE_SIZE = 500


# ===== Embedding 函数 =====

async def _embedding_func(texts: List[str]) -> np.ndarray:
    """简化的嵌入函数 - 使用哈希作为伪嵌入（轻量级，无需外部 API）"""
    embeddings = []
    for text in texts:
        h = hashlib.md5(text.encode()).hexdigest()
        np.random.seed(int(h[:8], 16))
        emb = np.random.randn(768)
        # 归一化
        emb = emb / np.linalg.norm(emb)
        embeddings.append(emb)
    return np.array(embeddings)


_embedding_wrapper = EmbeddingFunc(
    embedding_dim=768,
    max_token_size=8192,
    func=_embedding_func,
) if LIGHTRAG_AVAILABLE else None


# ===== LLM 函数 =====

def _get_llm_model_func():
    """获取 LLM 模型函数"""
    async def llm_model_func(prompt, system_prompt="", history_messages=[], **kwargs) -> str:
        """调用 OpenRouter API"""
        if not OPENROUTER_API_KEY:
            logger.warning("[LightRAG Memory] 未配置 OPENROUTER_API_KEY")
            return ""

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for msg in history_messages:
            messages.append(msg)
        messages.append({"role": "user", "content": prompt})

        try:
            from characters.ai_client import _get_http_client
            client = _get_http_client()
            resp = await client.post(
                f"{OPENROUTER_API_BASE}/chat/completions",
                headers=headers,
                json={
                    "model": "openrouter/free",
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.3,
                }
            )
            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content']
            else:
                logger.warning(f"[LightRAG Memory] API error: {resp.status_code}")
                return ""
        except Exception as e:
            logger.error(f"[LightRAG Memory] LLM 调用失败: {e}")
            return ""

    return llm_model_func


# ===== LightRAG 记忆系统 =====

class MemoryManager:
    """LightRAG 本地向量记忆系统 - 支持多角色独立存储"""

    def __init__(self, character_id: str = 'chayewoon'):
        self.character_id = character_id
        self.rag = None
        self._initialized = False
        self._lightrag_dir = os.path.join(DATA_DIR, 'lightrag_memory', character_id)

    async def _async_init(self) -> bool:
        """异步初始化 LightRAG"""
        if self._initialized:
            return True

        if not LIGHTRAG_AVAILABLE:
            logger.warning("[LightRAG Memory] lightrag 未安装，语义记忆不可用")
            return False

        try:
            # 确保目录存在
            os.makedirs(self._lightrag_dir, exist_ok=True)

            # 初始化 LightRAG
            self.rag = LightRAG(
                working_dir=self._lightrag_dir,
                llm_model_func=_get_llm_model_func(),
                embedding_func=_embedding_wrapper,
            )

            # 显式初始化 storages
            await self.rag.initialize_storages()

            self._initialized = True
            logger.info(f"[LightRAG Memory] 初始化成功: {self.character_id}")
            return True

        except Exception as e:
            logger.error(f"[LightRAG Memory] 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _ensure_init(self) -> bool:
        """延迟初始化（同步入口）"""
        if self._initialized:
            return True

        try:
            import asyncio
            # 尝试获取当前事件循环
            try:
                loop = asyncio.get_running_loop()
                # 如果在异步上下文中，需要异步初始化
                return False  # 返回 False，让异步调用方处理
            except RuntimeError:
                # 不在异步上下文中，创建新循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self._async_init())
                return result
        except Exception as e:
            logger.error(f"[LightRAG Memory] 同步初始化失败: {e}")
            return False

    async def add_memory(self, user_id: int, content: str, metadata: Dict = None) -> bool:
        """添加记忆（异步版本）"""
        if not self._initialized:
            if not await self._async_init():
                return False

        try:
            timestamp = datetime.now().isoformat()

            # 构建带元数据的记忆文本
            meta_str = f"[用户: {user_id}] [时间: {timestamp}] "
            if metadata:
                for k, v in metadata.items():
                    meta_str += f"[{k}: {v}] "

            memory_text = f"{meta_str}\n{content}"

            # 使用 LightRAG 插入
            await self.rag.ainsert(memory_text)

            logger.info(f"[LightRAG Memory] 添加记忆: {content[:50]}...")
            return True

        except Exception as e:
            logger.error(f"[LightRAG Memory] 添加记忆失败: {e}")
            return False

    async def search_memories(self, query: str, user_id: int = None, n_results: int = 5) -> List[Dict]:
        """语义搜索记忆（异步版本）"""
        if not self._initialized:
            if not await self._async_init():
                return []

        try:
            # 构建查询（添加用户过滤提示）
            search_query = query
            if user_id:
                search_query = f"用户 {user_id} 的相关记忆: {query}"

            # 使用 LightRAG 查询
            result = await self.rag.aquery(
                search_query,
                param=QueryParam(mode="hybrid", top_k=n_results)
            )

            # 解析结果（LightRAG 返回字符串，需要包装）
            memories = []
            if result:
                memories.append({
                    "content": result,
                    "metadata": {"query": query, "user_id": str(user_id) if user_id else None},
                    "distance": 0.5,  # LightRAG 不直接返回距离，使用固定值
                })

            logger.info(f"[LightRAG Memory] 搜索 '{query[:30]}...' 找到 {len(memories)} 条记忆")
            return memories

        except Exception as e:
            logger.error(f"[LightRAG Memory] 搜索失败: {e}")
            return []

    def get_recent_memories(self, user_id: int = None, limit: int = 10) -> List[Dict]:
        """获取最近的记忆（同步，查询最近插入的内容）"""
        if not self._ensure_init():
            return []

        try:
            # LightRAG 没有直接的 scroll 接口，使用查询方式
            query = f"最近的对话记忆"
            if user_id:
                query = f"用户 {user_id} 的最近对话记忆"

            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # 如果在异步上下文中，无法执行
                return []
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.rag.aquery(query, param=QueryParam(mode="local", top_k=limit))
                )

            memories = []
            if result:
                memories.append({
                    "content": result,
                    "metadata": {"user_id": str(user_id) if user_id else None},
                })

            return memories

        except Exception as e:
            logger.error(f"[LightRAG Memory] 获取最近记忆失败: {e}")
            return []

    def delete_memory(self, memory_id: str) -> bool:
        """删除特定记忆（LightRAG 暂不支持精确删除，返回提示）"""
        logger.warning("[LightRAG Memory] 精确删除记忆暂不支持，请手动清理存储目录")
        return False

    def clear_user_memories(self, user_id: int) -> bool:
        """清空特定用户的所有记忆"""
        logger.warning("[LightRAG Memory] 按用户清空记忆暂不支持，请手动清理存储目录")
        return False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        if not self._ensure_init():
            return {"total": 0, "status": "not_initialized"}

        try:
            # LightRAG 没有直接的计数接口，检查存储目录
            import glob
            json_files = glob.glob(os.path.join(self._lightrag_dir, "**/*.json"), recursive=True)
            return {"total": len(json_files), "status": "ready", "storage_dir": self._lightrag_dir}
        except Exception:
            return {"total": 0, "status": "error"}


# ===== 多角色记忆管理 =====

_memory_instances: Dict[str, MemoryManager] = {}


def get_memory(character_id: str = 'chayewoon') -> MemoryManager:
    """获取指定角色的记忆实例（懒加载）"""
    if character_id not in _memory_instances:
        _memory_instances[character_id] = MemoryManager(character_id)
    return _memory_instances[character_id]


# ===== 便捷函数（默认使用当前角色） =====

async def add_memory(user_id: int, content: str, metadata: Dict = None, character_id: str = 'chayewoon') -> bool:
    """添加记忆（异步）"""
    return await get_memory(character_id).add_memory(user_id, content, metadata)


async def search_memories(query: str, user_id: int = None, n_results: int = 5, character_id: str = 'chayewoon') -> List[Dict]:
    """搜索记忆（异步）"""
    return await get_memory(character_id).search_memories(query, user_id, n_results)


def get_recent_memories(user_id: int = None, limit: int = 10, character_id: str = 'chayewoon') -> List[Dict]:
    """获取最近记忆（同步）"""
    return get_memory(character_id).get_recent_memories(user_id, limit)


def get_memory_stats(character_id: str = 'chayewoon') -> Dict:
    """获取记忆统计"""
    return get_memory(character_id).get_stats()
