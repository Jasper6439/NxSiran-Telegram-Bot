"""
LightRAG 知识库技能 - 小说知识查询
让车如云拥有原作剧情知识，能回答关于小说内容的问题
"""

import os
import logging
from typing import List, Dict

# LightRAG
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

logger = logging.getLogger(__name__)

# 数据存储路径
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), 'knowledge')
NOVEL_FILE = os.path.join(KNOWLEDGE_DIR, 'novel.txt')
LIGHTRAG_DIR = os.path.join(DATA_DIR, 'lightrag_db')


class NovelKnowledge:
    """小说知识库系统 - 支持多角色独立知识库"""
    
    def __init__(self, character_id: str = 'chayewoon'):
        self.character_id = character_id
        self.rag = None
        self._initialized = False
        self._novel_loaded = False
        
        # 每个角色独立的路径
        self._novel_file = os.path.join(KNOWLEDGE_DIR, character_id, 'novel.txt')
        self._lightrag_dir = os.path.join(DATA_DIR, 'lightrag_db', character_id)
    
    def _get_llm_model_func(self):
        """获取 LLM 模型函数"""
        from system.config import AI_API_BASE, AI_API_KEY, AI_MODELS
        
        async def llm_model_func(prompt, system_prompt="", history_messages=[], **kwargs) -> str:
            """调用 OpenRouter API"""
            import httpx
            
            headers = {
                "Authorization": f"Bearer {AI_API_KEY}",
                "Content-Type": "application/json"
            }
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            for msg in history_messages:
                messages.append(msg)
            messages.append({"role": "user", "content": prompt})
            
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{AI_API_BASE}/chat/completions",
                    headers=headers,
                    json={
                        "model": AI_MODELS[0],
                        "messages": messages,
                        "max_tokens": 1000,
                        "temperature": 0.3,
                    }
                )
                if resp.status_code == 200:
                    return resp.json()['choices'][0]['message']['content']
                else:
                    raise Exception(f"API error: {resp.status_code}")
        
        return llm_model_func
    
    def _get_embedding_func(self):
        """获取嵌入函数（简化版，使用伪嵌入）"""
        import hashlib
        import numpy as np
        
        async def embedding_func(texts: List[str]) -> np.ndarray:
            """简化的嵌入函数 - 使用哈希作为伪嵌入"""
            embeddings = []
            for text in texts:
                h = hashlib.md5(text.encode()).hexdigest()
                np.random.seed(int(h[:8], 16))
                emb = np.random.randn(768)
                embeddings.append(emb)
            return np.array(embeddings)
        
        return EmbeddingFunc(
            embedding_dim=768,
            max_token_size=8192,
            func=embedding_func,
        )
    
    def _ensure_init(self) -> bool:
        """延迟初始化"""
        if self._initialized:
            return True
        
        try:
            # 确保目录存在
            os.makedirs(self._lightrag_dir, exist_ok=True)
            
            # 初始化 LightRAG
            # 注意：这里使用简化配置，实际生产环境需要配置正确的 LLM 和嵌入模型
            self.rag = LightRAG(
                working_dir=self._lightrag_dir,
                llm_model_func=self._get_llm_model_func(),
                embedding_func=self._get_embedding_func(),
            )
            
            self._initialized = True
            logger.info("[LightRAG] 初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"[LightRAG] 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def load_novel(self) -> bool:
        """加载小说文件"""
        if not self._ensure_init():
            return False
        
        if self._novel_loaded:
            return True
        
        try:
            if not os.path.exists(self._novel_file):
                logger.error(f"[LightRAG] 小说文件不存在: {self._novel_file}")
                return False
            
            # 读取小说内容
            with open(self._novel_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"[LightRAG] 开始加载小说，共 {len(content)} 字符...")
            
            # 分块插入（避免一次性插入太多）
            chunk_size = 5000
            chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
            
            for i, chunk in enumerate(chunks):
                try:
                    await self.rag.ainsert(chunk)
                    logger.info(f"[LightRAG] 已加载 {i+1}/{len(chunks)} 块")
                except Exception as e:
                    logger.warning(f"[LightRAG] 加载块 {i+1} 失败: {e}")
                    continue
            
            self._novel_loaded = True
            logger.info("[LightRAG] 小说加载完成")
            return True
            
        except Exception as e:
            logger.error(f"[LightRAG] 加载小说失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def query(self, question: str, mode: str = "hybrid") -> str:
        """
        查询知识库
        
        Args:
            question: 问题
            mode: 查询模式 (naive, local, global, hybrid)
        
        Returns:
            回答
        """
        if not self._ensure_init():
            return "知识库未初始化"
        
        if not self._novel_loaded:
            # 尝试加载小说
            await self.load_novel()
        
        try:
            # 执行查询
            result = await self.rag.aquery(question, param=QueryParam(mode=mode))
            return result
        except Exception as e:
            logger.error(f"[LightRAG] 查询失败: {e}")
            return f"查询失败: {str(e)}"
    
    def is_ready(self) -> bool:
        """检查是否就绪"""
        return self._initialized and self._novel_loaded


# ===== 多角色知识库管理 =====

# 全局实例字典（每个角色独立）
_knowledge_instances: Dict[str, NovelKnowledge] = {}


def get_knowledge(character_id: str = 'chayewoon') -> NovelKnowledge:
    """获取指定角色的知识库实例（懒加载）"""
    if character_id not in _knowledge_instances:
        _knowledge_instances[character_id] = NovelKnowledge(character_id)
    return _knowledge_instances[character_id]


# ===== 便捷函数（默认使用车如云） =====

async def query_novel(question: str, character_id: str = 'chayewoon') -> str:
    """查询小说知识"""
    kg = get_knowledge(character_id)
    return await kg.query(question)


async def init_novel_knowledge(character_id: str = 'chayewoon') -> bool:
    """初始化并加载小说"""
    kg = get_knowledge(character_id)
    return await kg.load_novel()


def is_knowledge_ready(character_id: str = 'chayewoon') -> bool:
    """检查知识库是否就绪"""
    kg = get_knowledge(character_id)
    return kg.is_ready()
