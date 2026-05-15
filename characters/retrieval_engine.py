"""
BM25 + LightRAG 混合检索引擎
双路混合检索：先 BM25（关键词匹配），未命中则 LightRAG（语义理解）
"""

import os
import re
import time
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果统一格式"""
    content: str
    score: float
    source: str  # 'bm25' 或 'lightrag'
    metadata: Optional[Dict[str, Any]] = None


class BaseRetriever(ABC):
    """检索器基类"""
    
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """
        执行检索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            检索结果列表
        """
        pass
    
    @abstractmethod
    def is_ready(self) -> bool:
        """检查检索器是否就绪"""
        pass


class BM25Retriever(BaseRetriever):
    """
    BM25 检索器 - 基于关键词匹配的快速检索
    目标响应时间: < 10ms
    """
    
    def __init__(self, character_id: str = 'chayewoon'):
        self.character_id = character_id
        self._corpus: List[str] = []
        self._tokenized_corpus: List[List[str]] = []
        self._bm25 = None
        self._initialized = False
        
        # 每个角色的知识文件路径
        self._knowledge_file = os.path.join(
            os.path.dirname(__file__), 
            character_id, 
            'novel.txt'
        )
    
    def _tokenize(self, text: str) -> List[str]:
        """
        中文分词（简化版）
        使用字符级分词 + 停用词过滤
        """
        # 移除标点符号和特殊字符
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text)
        
        # 中文按字符分词，英文按单词分词
        tokens = []
        for token in text.lower().split():
            if re.match(r'^[\u4e00-\u9fa5]+$', token):
                # 纯中文，按字符拆分
                tokens.extend(list(token))
            else:
                # 英文或混合
                tokens.append(token)
        
        # 简单停用词过滤
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', 
                     '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
                     '你', '会', '着', '没有', '看', '好', '自己', '这'}
        tokens = [t for t in tokens if t not in stopwords and len(t) > 0]
        
        return tokens
    
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """
        将长文本分块
        
        Args:
            text: 原始文本
            chunk_size: 每块大小（字符数）
            overlap: 块之间重叠大小
            
        Returns:
            文本块列表
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # 尽量在句子边界处截断
            if end < len(text):
                # 查找最近的句号、问号或感叹号
                for punct in ['。', '？', '！', '.', '?', '!']:
                    last_punct = chunk.rfind(punct)
                    if last_punct > chunk_size // 2:  # 至少保留一半内容
                        chunk = chunk[:last_punct + 1]
                        break
            
            chunks.append(chunk.strip())
            start += chunk_size - overlap
        
        return chunks
    
    def initialize(self) -> bool:
        """
        初始化 BM25 检索器
        加载知识文件并构建索引
        """
        try:
            from rank_bm25 import BM25Okapi
            
            if not os.path.exists(self._knowledge_file):
                logger.error(f"[BM25] 知识文件不存在: {self._knowledge_file}")
                return False
            
            # 读取知识文件
            with open(self._knowledge_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                logger.error(f"[BM25] 知识文件为空: {self._knowledge_file}")
                return False
            
            # 分块处理
            self._corpus = self._chunk_text(content, chunk_size=500, overlap=100)
            
            # 分词
            self._tokenized_corpus = [self._tokenize(doc) for doc in self._corpus]
            
            # 构建 BM25 索引
            self._bm25 = BM25Okapi(self._tokenized_corpus)
            
            self._initialized = True
            logger.info(f"[BM25] 初始化成功，共索引 {len(self._corpus)} 个文档块")
            return True
            
        except ImportError:
            logger.error("[BM25] 未安装 rank_bm25 库，请运行: pip install rank-bm25")
            return False
        except Exception as e:
            logger.error(f"[BM25] 初始化失败: {e}")
            return False
    
    def is_ready(self) -> bool:
        """检查是否就绪"""
        return self._initialized and self._bm25 is not None
    
    async def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """
        执行 BM25 检索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            检索结果列表
        """
        if not self.is_ready():
            # 尝试初始化
            if not self.initialize():
                return []
        
        try:
            start_time = time.time()
            
            # 查询分词
            tokenized_query = self._tokenize(query)
            
            if not tokenized_query:
                return []
            
            # 计算 BM25 分数
            scores = self._bm25.get_scores(tokenized_query)
            
            # 获取 top_k 结果的索引
            top_indices = np.argsort(scores)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                score = float(scores[idx])
                # 过滤低分结果
                if score < 0.1:
                    continue
                    
                results.append(RetrievalResult(
                    content=self._corpus[idx],
                    score=score,
                    source='bm25',
                    metadata={'index': int(idx)}
                ))
            
            elapsed = (time.time() - start_time) * 1000
            logger.debug(f"[BM25] 检索完成，找到 {len(results)} 个结果，耗时 {elapsed:.2f}ms")
            
            return results
            
        except Exception as e:
            logger.error(f"[BM25] 检索失败: {e}")
            return []


class LightRAGRetriever(BaseRetriever):
    """
    LightRAG 检索器 - 基于语义理解和关系推理
    目标响应时间: < 200ms
    """
    
    def __init__(self, character_id: str = 'chayewoon'):
        self.character_id = character_id
        self._novel_knowledge = None
        self._initialized = False
    
    def _get_knowledge(self):
        """获取 NovelKnowledge 实例（懒加载）"""
        if self._novel_knowledge is None:
            from characters.novel_knowledge import get_knowledge
            self._novel_knowledge = get_knowledge(self.character_id)
        return self._novel_knowledge
    
    def is_ready(self) -> bool:
        """检查是否就绪"""
        if not self._initialized:
            return False
        knowledge = self._get_knowledge()
        return knowledge.is_ready()
    
    async def initialize(self) -> bool:
        """
        初始化 LightRAG 检索器
        异步加载知识库
        """
        try:
            from characters.novel_knowledge import init_novel_knowledge
            
            success = await init_novel_knowledge(self.character_id)
            if success:
                self._initialized = True
                logger.info("[LightRAG] 初始化成功")
            return success
            
        except Exception as e:
            logger.error(f"[LightRAG] 初始化失败: {e}")
            return False
    
    async def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """
        执行 LightRAG 检索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量（LightRAG 返回的是生成文本，这里包装为结果）
            
        Returns:
            检索结果列表
        """
        if not self._initialized:
            if not await self.initialize():
                return []
        
        try:
            start_time = time.time()
            
            from characters.novel_knowledge import query_novel
            
            # LightRAG 返回的是生成的回答文本
            response = await query_novel(query, self.character_id)
            
            elapsed = (time.time() - start_time) * 1000
            logger.debug(f"[LightRAG] 检索完成，耗时 {elapsed:.2f}ms")
            
            # 将 LightRAG 的生成结果包装为 RetrievalResult
            # 由于 LightRAG 不直接返回相似度分数，使用固定置信度
            return [RetrievalResult(
                content=response,
                score=0.8,  # LightRAG 默认置信度
                source='lightrag',
                metadata={'mode': 'hybrid', 'elapsed_ms': elapsed}
            )]
            
        except Exception as e:
            logger.error(f"[LightRAG] 检索失败: {e}")
            return []


class HybridRetriever(BaseRetriever):
    """
    混合检索引擎 - BM25 + LightRAG
    
    检索策略：
    1. 首先使用 BM25 进行快速关键词匹配（< 10ms）
    2. 如果 BM25 未命中（无结果或分数过低），则使用 LightRAG（< 200ms）
    3. 返回统一格式的结果列表
    """
    
    # 默认阈值配置
    BM25_SCORE_THRESHOLD = 1.0  # BM25 最低分数阈值
    BM25_TIMEOUT_MS = 10  # BM25 超时时间（毫秒）
    LIGHTRAG_TIMEOUT_MS = 200  # LightRAG 超时时间（毫秒）
    
    def __init__(
        self,
        character_id: str = 'chayewoon',
        bm25_threshold: float = BM25_SCORE_THRESHOLD,
        use_lightrag_fallback: bool = True
    ):
        """
        初始化混合检索引擎
        
        Args:
            character_id: 角色 ID
            bm25_threshold: BM25 分数阈值，低于此值触发 LightRAG
            use_lightrag_fallback: 是否启用 LightRAG 作为后备
        """
        self.character_id = character_id
        self.bm25_threshold = bm25_threshold
        self.use_lightrag_fallback = use_lightrag_fallback
        
        # 初始化子检索器
        self._bm25_retriever = BM25Retriever(character_id)
        self._lightrag_retriever = LightRAGRetriever(character_id)
        
        # 延迟初始化标志
        self._bm25_initialized = False
        self._lightrag_initialized = False
    
    def initialize(self) -> bool:
        """
        同步初始化（主要用于 BM25）
        LightRAG 需要异步初始化
        """
        if not self._bm25_initialized:
            self._bm25_initialized = self._bm25_retriever.initialize()
        return self._bm25_initialized
    
    async def initialize_async(self) -> bool:
        """
        异步初始化（同时初始化 BM25 和 LightRAG）
        """
        # 初始化 BM25
        if not self._bm25_initialized:
            self._bm25_initialized = self._bm25_retriever.initialize()
        
        # 初始化 LightRAG
        if not self._lightrag_initialized and self.use_lightrag_fallback:
            self._lightrag_initialized = await self._lightrag_retriever.initialize()
        
        return self._bm25_initialized or self._lightrag_initialized
    
    def is_ready(self) -> bool:
        """检查是否就绪（至少有一个检索器就绪）"""
        return self._bm25_retriever.is_ready() or self._lightrag_retriever.is_ready()
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        force_mode: Optional[str] = None
    ) -> List[RetrievalResult]:
        """
        执行混合检索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            force_mode: 强制使用指定模式 ('bm25', 'lightrag', None 表示自动)
            
        Returns:
            检索结果列表
        """
        if not query or not query.strip():
            return []
        
        query = query.strip()
        results = []
        
        # 模式 1: 强制使用 BM25
        if force_mode == 'bm25':
            return await self._bm25_retriever.retrieve(query, top_k)
        
        # 模式 2: 强制使用 LightRAG
        if force_mode == 'lightrag':
            return await self._lightrag_retriever.retrieve(query, top_k)
        
        # 模式 3: 自动混合检索
        # 步骤 1: 尝试 BM25 快速检索
        try:
            bm25_results = await self._bm25_retriever.retrieve(query, top_k)
            
            # 检查 BM25 结果质量
            if bm25_results:
                # 获取最高分数
                max_score = max(r.score for r in bm25_results)
                
                # 如果分数超过阈值，直接返回 BM25 结果
                if max_score >= self.bm25_threshold:
                    logger.debug(f"[Hybrid] BM25 命中（分数 {max_score:.2f}），直接返回")
                    return bm25_results
                else:
                    # 分数较低，保留结果作为备选
                    results = bm25_results
                    logger.debug(f"[Hybrid] BM25 分数较低（{max_score:.2f}），尝试 LightRAG")
            else:
                logger.debug("[Hybrid] BM25 无结果，尝试 LightRAG")
                
        except Exception as e:
            logger.warning(f"[Hybrid] BM25 检索异常: {e}")
        
        # 步骤 2: BM25 未命中或分数低，使用 LightRAG
        if self.use_lightrag_fallback:
            try:
                lightrag_results = await self._lightrag_retriever.retrieve(query, top_k)
                
                if lightrag_results:
                    # 合并结果（去重并排序）
                    combined = self._merge_results(results, lightrag_results, top_k)
                    logger.debug(f"[Hybrid] LightRAG 返回 {len(lightrag_results)} 个结果")
                    return combined
                    
            except Exception as e:
                logger.error(f"[Hybrid] LightRAG 检索异常: {e}")
        
        # 如果 LightRAG 也失败，返回 BM25 的结果（如果有）
        return results
    
    def _merge_results(
        self,
        bm25_results: List[RetrievalResult],
        lightrag_results: List[RetrievalResult],
        top_k: int
    ) -> List[RetrievalResult]:
        """
        合并 BM25 和 LightRAG 的结果
        
        策略：
        - LightRAG 结果优先（语义理解更深层）
        - BM25 结果作为补充
        """
        combined = []
        seen_content = set()
        
        # 首先添加 LightRAG 结果
        for result in lightrag_results:
            content_hash = hash(result.content[:100])  # 使用前100字符去重
            if content_hash not in seen_content:
                combined.append(result)
                seen_content.add(content_hash)
        
        # 然后添加 BM25 结果（去重）
        for result in bm25_results:
            content_hash = hash(result.content[:100])
            if content_hash not in seen_content:
                combined.append(result)
                seen_content.add(content_hash)
        
        # 按分数排序并截断
        combined.sort(key=lambda x: x.score, reverse=True)
        return combined[:top_k]
    
    async def query_with_context(
        self,
        query: str,
        top_k: int = 3,
        max_context_length: int = 2000
    ) -> Dict[str, Any]:
        """
        检索并生成上下文
        
        Args:
            query: 查询文本
            top_k: 检索结果数量
            max_context_length: 最大上下文长度
            
        Returns:
            包含检索结果和格式化上下文的字典
        """
        results = await self.retrieve(query, top_k)
        
        if not results:
            return {
                'results': [],
                'context': '',
                'sources': [],
                'has_knowledge': False
            }
        
        # 格式化上下文
        context_parts = []
        sources = []
        
        for i, result in enumerate(results, 1):
            # 截断过长的内容
            content = result.content
            if len(content) > max_context_length // top_k:
                content = content[:max_context_length // top_k] + '...'
            
            context_parts.append(f"[{i}] {content}")
            sources.append({
                'index': i,
                'source': result.source,
                'score': result.score,
                'metadata': result.metadata
            })
        
        context = '\n\n'.join(context_parts)
        
        return {
            'results': results,
            'context': context,
            'sources': sources,
            'has_knowledge': True
        }


# ===== 便捷函数 =====

# 全局实例字典（每个角色独立）
_hybrid_retriever_instances: Dict[str, HybridRetriever] = {}


def get_hybrid_retriever(character_id: str = 'chayewoon') -> HybridRetriever:
    """获取指定角色的混合检索器实例（懒加载）"""
    if character_id not in _hybrid_retriever_instances:
        retriever = HybridRetriever(character_id)
        retriever.initialize()  # 同步初始化 BM25
        _hybrid_retriever_instances[character_id] = retriever
    return _hybrid_retriever_instances[character_id]


async def retrieve_knowledge(
    query: str,
    character_id: str = 'chayewoon',
    top_k: int = 5,
    force_mode: Optional[str] = None
) -> List[RetrievalResult]:
    """
    便捷函数：检索知识
    
    Args:
        query: 查询文本
        character_id: 角色 ID
        top_k: 返回结果数量
        force_mode: 强制模式 ('bm25', 'lightrag', None)
        
    Returns:
        检索结果列表
    """
    retriever = get_hybrid_retriever(character_id)
    return await retriever.retrieve(query, top_k, force_mode)


async def get_knowledge_context(
    query: str,
    character_id: str = 'chayewoon',
    top_k: int = 3
) -> Dict[str, Any]:
    """
    便捷函数：获取知识上下文
    
    Args:
        query: 查询文本
        character_id: 角色 ID
        top_k: 检索结果数量
        
    Returns:
        包含上下文和元数据的字典
    """
    retriever = get_hybrid_retriever(character_id)
    return await retriever.query_with_context(query, top_k)


# 清理函数（用于测试或重新加载）
def clear_retriever_cache(character_id: Optional[str] = None):
    """
    清除检索器缓存
    
    Args:
        character_id: 指定角色 ID，None 表示清除所有
    """
    global _hybrid_retriever_instances
    
    if character_id is None:
        _hybrid_retriever_instances.clear()
        logger.info("[HybridRetriever] 已清除所有缓存")
    elif character_id in _hybrid_retriever_instances:
        del _hybrid_retriever_instances[character_id]
        logger.info(f"[HybridRetriever] 已清除角色 {character_id} 的缓存")
