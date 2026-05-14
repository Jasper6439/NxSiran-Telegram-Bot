"""
角色系统 - 支持多蒸馏角色动态加载
v1.6.4 — 多角色系统：自动发现并加载 characters/ 下的角色目录
"""
import os
import json
import logging
from typing import Dict, List, Optional
from .base import CharacterBase, CharacterConfig

logger = logging.getLogger(__name__)

# 角色注册表
_CHARACTERS: Dict[str, CharacterBase] = {}
_CURRENT_CHARACTER: Optional[str] = None


def register_character(character: CharacterBase):
    """注册角色"""
    _CHARACTERS[character.config.id] = character
    logger.info(f"[Characters] 注册角色: {character.config.name} ({character.config.id})")


def get_character(character_id: str) -> Optional[CharacterBase]:
    """获取角色"""
    return _CHARACTERS.get(character_id)


def get_current_character() -> Optional[CharacterBase]:
    """获取当前激活的角色"""
    if _CURRENT_CHARACTER and _CURRENT_CHARACTER in _CHARACTERS:
        return _CHARACTERS[_CURRENT_CHARACTER]
    # 返回第一个注册的角色
    if _CHARACTERS:
        return list(_CHARACTERS.values())[0]
    return None


def set_current_character(character_id: str) -> bool:
    """设置当前角色"""
    global _CURRENT_CHARACTER
    if character_id in _CHARACTERS:
        _CURRENT_CHARACTER = character_id
        logger.info(f"[Characters] 切换到角色: {character_id}")
        return True
    logger.warning(f"[Characters] 角色不存在: {character_id}")
    return False


def list_characters() -> List[dict]:
    """列出所有角色"""
    return [c.to_dict() for c in _CHARACTERS.values()]


def get_character_count() -> int:
    """获取角色数量"""
    return len(_CHARACTERS)


def get_all_character_ids() -> List[str]:
    """获取所有已注册角色 ID"""
    return list(_CHARACTERS.keys())


def load_character_from_dir(char_id: str, char_path: str) -> Optional[CharacterBase]:
    """从目录加载单个角色

    目录结构:
    characters/{char_id}/
    ├── config.json      # 角色配置（必须）
    ├── persona.md       # 角色详细设定（可选）
    ├── memories.md      # 共同记忆（可选）
    └── {char_id}.py     # 角色类实现（可选，默认使用 chayewoon 模板）
    """
    config_file = os.path.join(char_path, "config.json")
    if not os.path.exists(config_file):
        logger.warning(f"[Characters] 角色配置文件不存在: {config_file}")
        return None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # 尝试导入角色专属类
        try:
            import importlib
            module = importlib.import_module(f"characters.{char_id}")
            CharacterClass = getattr(module, 'Character')
            logger.debug(f"[Characters] 使用角色专属类: characters.{char_id}.Character")
        except (ImportError, AttributeError):
            # 使用默认角色类（chayewoon 模板）
            from .chayewoon import Character as CharacterClass
            logger.debug(f"[Characters] 使用默认角色类: chayewoon.Character")

        config = CharacterConfig.from_dict(config_data, char_id, char_path)
        character = CharacterClass(config)
        return character

    except Exception as e:
        logger.error(f"[Characters] 加载角色失败 {char_id}: {e}")
        return None


def load_characters_from_dir(base_dir: str):
    """从 characters/ 目录自动发现并加载所有角色

    扫描 base_dir/characters/ 下的每个子目录，
    如果子目录包含 config.json，则视为一个角色目录并加载。
    """
    characters_dir = os.path.join(base_dir, "characters")
    if not os.path.exists(characters_dir):
        logger.info(f"[Characters] 角色目录不存在: {characters_dir}")
        return

    loaded = 0
    for name in sorted(os.listdir(characters_dir)):
        if name.startswith('__') or name.startswith('_') or name.startswith('.'):
            continue  # 跳过 __pycache__, _archive, .git 等
        char_path = os.path.join(characters_dir, name)
        if not os.path.isdir(char_path):
            continue

        # 检查是否有 config.json
        config_file = os.path.join(char_path, "config.json")
        if not os.path.exists(config_file):
            continue

        character = load_character_from_dir(name, char_path)
        if character:
            register_character(character)
            loaded += 1

    logger.info(f"[Characters] 从目录加载了 {loaded} 个角色")
