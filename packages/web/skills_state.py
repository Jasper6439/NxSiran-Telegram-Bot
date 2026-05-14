"""
Skills 状态管理模块
包含 skills 持久化状态加载/保存、角色技能覆盖、技能启用/禁用等功能。
"""

import os
import logging

from system.config import SKILLS_REGISTRY, SKILLS_STATE_FILE, load_json, save_json


def _load_skills_state():
    """Load skills persistent state from disk."""
    global SKILLS_REGISTRY
    if os.path.exists(SKILLS_STATE_FILE):
        try:
            state = load_json(SKILLS_STATE_FILE, {})
            for sid, sdata in state.get('skills', {}).items():
                if sid in SKILLS_REGISTRY:
                    SKILLS_REGISTRY[sid].update(sdata)
                else:
                    SKILLS_REGISTRY[sid] = sdata
        except Exception as e:
            logging.error(f"[skills-manager] 加载 skills 状态失败: {e}")

def _save_skills_state():
    """Save skills persistent state to disk."""
    try:
        state = {'skills': {sid: dict(sdata) for sid, sdata in SKILLS_REGISTRY.items()}}
        save_json(SKILLS_STATE_FILE, state)
    except Exception as e:
        logging.error(f"[skills-manager] 保存 skills 状态失败: {e}")

def is_skill_enabled_for_character(skill_id, character_id=None):
    """Check if a skill is enabled for a specific character."""
    if skill_id not in SKILLS_REGISTRY:
        return False
    return SKILLS_REGISTRY[skill_id].get('enabled', True)

def set_skill_for_character(skill_id, character_id, enabled):
    """Enable/disable a skill for a specific character."""
    if skill_id in SKILLS_REGISTRY:
        SKILLS_REGISTRY[skill_id]['enabled'] = enabled
        _save_skills_state()

# 启动时加载 skills 持久化状态
_load_skills_state()
