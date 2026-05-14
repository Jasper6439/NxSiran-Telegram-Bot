# database/

SQLite 数据库操作模块 — Mixin 模式按业务域拆分，支持农场经营 + 角色互动游戏。

## 模块索引

| 模块 | 职责 | 主要导出 |
|------|------|----------|
| `__init__.py` | 包入口, NxSiranGameDB 类聚合所有 Mixin | `NxSiranGameDB`, `get_db` |
| `base.py` | 基类, SQLite 连接管理, 用户注册/查询, 表初始化 | `NxSiranGameDBBase`, `get_db` |
| `player.py` | 玩家位置存取 | `PlayerMixin` |
| `chat.py` | 聊天记录持久化, 记忆系统读写 | `ChatMixin` |
| `cooking.py` | 料理配方/烹饪记录, 每日奖励 | `CookingMixin` |
| `events.py` | 心级事件, 游戏事件日志, 角色日程 | `EventsMixin` |
| `farm.py` | 农场 CRUD, 作物种植/浇水/收获 | `FarmMixin` |
| `inventory.py` | 背包物品增删查 | `InventoryMixin` |
| `relationship.py` | 关系/亲密度, 情感值, 觉醒事件 | `RelationshipMixin` |
| `maps.py` | 多地图系统（home/school/cafe/park/rooftop/beach）, 地图解锁 | `MapsMixin`, `MAPS` |

## 架构

- `NxSiranGameDB`（`__init__.py`）继承 `NxSiranGameDBBase` + 所有 Mixin
- 全局单例 `get_db()` 返回聚合实例
- 线程安全：`threading.Lock` + `contextmanager` 连接管理
- DDL: `data/game_schema.sql`

## 依赖关系

- 所有 Mixin → `config.get_default_tz`
- `base.py` → `sqlite3`, `config.py`
