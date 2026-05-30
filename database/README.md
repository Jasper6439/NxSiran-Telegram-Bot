# database/

SQLite 数据库操作模块 — Mixin 模式按业务域拆分，支持农场经营 + 角色互动游戏。

## 模块索引

| 模块 | 职责 | 主要导出 |
|------|------|----------|
| `__init__.py` | 包入口, LoveSupremacyGameDB 类聚合所有 Mixin | `LoveSupremacyGameDB`, `get_db` |
| `base.py` | 基类, SQLite 连接管理, 用户注册/查询, 表初始化 | `LoveSupremacyGameDBBase`, `get_db` |
| `auth.py` | API Token 管理 | `AuthMixin` |
| `chat.py` | 聊天记录持久化, 记忆系统读写 | `ChatMixin` |
| `cooking.py` | 料理配方/烹饪记录, 每日奖励 | `CookingMixin` |
| `events.py` | 心级事件, 游戏事件日志, 角色日程 | `EventsMixin` |
| `farm.py` | 农场 CRUD, 作物种植/浇水/收获 | `FarmMixin` |
| `inventory.py` | 背包物品增删查 | `InventoryMixin` |
| `maps.py` | 多地图系统（home/school/cafe/park/rooftop/beach）, 地图解锁 | `MapsMixin`, `MAPS` |
| `player.py` | 玩家位置存取 | `PlayerMixin` |
| `relationship.py` | 关系/亲密度, 情感值, 觉醒事件 | `RelationshipMixin` |
| `world.py` | 世界系统 | `WorldMixin` |

## 架构

- `LoveSupremacyGameDB` 继承 `LoveSupremacyGameDBBase` + 所有 Mixin
- 全局单例 `get_db()` 返回聚合实例
- 线程安全：`threading.Lock` + `contextmanager` 连接管理
- 异步包装：`system/database.py:AsyncGameDatabase` 用于 FastAPI
- DDL: `data/game_schema.sql`
- 迁移: `data/migration_v18_world.sql`, `migration_v19_api_tokens.sql`, `migration_v20_evolution.sql`
- 数据库文件: `data/game.db`

## 注

`evolution_service.py` 使用独立数据库路径 `DATA_DIR/game.db`（与主数据库 `database/data/game.db` 分开）。
