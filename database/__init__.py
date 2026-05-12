# 恋爱至上主义区域 (Love Supremacy Zone)
"""
NxSiRan Game Database Package
SQLite 数据库操作模块 - 支持农场经营 + 角色互动游戏

通过 Mixin 模式按业务域拆分：
- base: 基类 + 连接管理 + 用户管理
- farm: 农场系统
- relationship: 关系/亲密度 + 情感值 + 觉醒事件
- cooking: 料理系统 + 每日奖励
- events: 心级事件 + 游戏事件日志 + 角色日程
- inventory: 背包系统
- chat: 聊天记录 + 记忆系统
- player: 玩家位置
- maps: 多地图系统 (v1.4.10.2)
"""

from database.base import (
    GameDatabase as _Base,
    DB_PATH,
    SCHEMA_PATH,
    KR_TZ,
    _get_thread_db,
    get_db as _get_db_func,
    init_game_db as _init_game_db_func,
)
from database.farm import FarmMixin
from database.relationship import RelationshipMixin
from database.cooking import CookingMixin
from database.events import EventsMixin
from database.inventory import InventoryMixin
from database.chat import ChatMixin
from database.player import PlayerMixin
from database.maps import MapMixin


class GameDatabase(MapMixin, FarmMixin, RelationshipMixin, CookingMixin, EventsMixin, InventoryMixin, ChatMixin, PlayerMixin, _Base):
    """游戏数据库管理类（组合所有业务域 Mixin）"""
    pass


def get_db(user_id=None):
    """获取数据库实例（优先线程本地，其次全局）"""
    return _get_thread_db(user_id)


def init_game_db():
    """初始化游戏数据库"""
    return _init_game_db_func()


__all__ = [
    'GameDatabase',
    'get_db',
    'init_game_db',
    'DB_PATH',
    'SCHEMA_PATH',
    'KR_TZ',
]
