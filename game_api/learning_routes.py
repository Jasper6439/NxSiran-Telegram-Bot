"""
角色学习进化 API
v1.6.4.1 — 触发角色自我学习，更新 persona/memories
"""

import logging
from aiohttp import web
from game_api.auth import authenticate_request
from characters.character_learning import evolve_character, get_learning

logger = logging.getLogger(__name__)


async def api_character_evolve(request):
    """触发角色完整学习进化流程

    POST /api/characters/evolve
    Body: { "character_id": "chayewoon" }  # 可选，默认当前角色

    执行：
    1. 从 novel.txt 学习 → 更新 persona.md
    2. 从聊天记录学习 → 更新 memories.md（用户画像）
    3. 从 Qdrant 记忆学习 → 更新 memories.md（关键记忆）
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        character_id = data.get('character_id', 'chayewoon')

        logger.info(f"[Learning API] 用户 {user_id} 触发角色 {character_id} 进化")

        result = await evolve_character(character_id, user_id)

        return web.json_response({
            'success': True,
            'result': result
        })

    except Exception as e:
        logger.error(f"[Learning API] 进化失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_character_learn_novel(request):
    """从小说知识库学习

    POST /api/characters/learn/novel
    Body: { "character_id": "chayewoon", "topic": "家庭背景" }  # topic 可选
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        character_id = data.get('character_id', 'chayewoon')
        topic = data.get('topic')

        learning = get_learning(character_id)
        result = await learning.learn_from_novel(topic)

        return web.json_response({
            'success': result.get('success', False),
            'result': result
        })

    except Exception as e:
        logger.error(f"[Learning API] 小说学习失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_character_learn_chat(request):
    """从聊天记录学习用户偏好

    POST /api/characters/learn/chat
    Body: { "character_id": "chayewoon" }
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        character_id = data.get('character_id', 'chayewoon')

        learning = get_learning(character_id)
        result = await learning.learn_from_chat_history(user_id)

        return web.json_response({
            'success': result.get('success', False),
            'result': result
        })

    except Exception as e:
        logger.error(f"[Learning API] 聊天记录学习失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_character_learn_qdrant(request):
    """从 Qdrant 记忆库学习

    POST /api/characters/learn/qdrant
    Body: { "character_id": "chayewoon" }
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        character_id = data.get('character_id', 'chayewoon')

        learning = get_learning(character_id)
        result = await learning.learn_from_qdrant_memories(user_id)

        return web.json_response({
            'success': result.get('success', False),
            'result': result
        })

    except Exception as e:
        logger.error(f"[Learning API] Qdrant 学习失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_character_learning_status(request):
    """获取角色学习状态

    GET /api/characters/learning/status?character_id=chayewoon
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        character_id = request.query.get('character_id', 'chayewoon')

        # 检查各学习源状态
        from characters.novel_knowledge import is_knowledge_ready
        from characters.qdrant_memory import get_memory_stats

        novel_ready = is_knowledge_ready(character_id)
        qdrant_stats = get_memory_stats(character_id)

        return web.json_response({
            'success': True,
            'character_id': character_id,
            'learning_status': {
                'novel_knowledge': {
                    'ready': novel_ready,
                    'source_file': f'characters/{character_id}/novel.txt'
                },
                'qdrant_memory': qdrant_stats,
                'persona_file': f'characters/{character_id}/persona.md',
                'memories_file': f'characters/{character_id}/memories.md',
            }
        })

    except Exception as e:
        logger.error(f"[Learning API] 获取状态失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})
