# 🎮 LoveSupremacy Bot - 游戏系统全景文档

> **版本**: v1.6.5 | **更新日期**: 2026-05-15  
> **世界观**: 韩国小说《恋爱至上主义区域》(Love Supremacy Zone)  
> **部署环境**: GCP e2-micro (1 vCPU, 1 GB RAM)

---

## 一、系统架构

```
[Telegram Bot] ←→ [game_api/ (aiohttp)] ←→ [database/ (SQLite)]
                        ↕ SSE / REST
[web-v2/ (React + Phaser 4)] ←→ [Zustand Store]
```

| 层级 | 技术 |
|------|------|
| 后端框架 | Python aiohttp |
| 数据库 | SQLite (Mixin 模式) |
| 前端框架 | React 18 + TypeScript + Vite |
| 状态管理 | Zustand (persist 中间件) |
| 游戏引擎 | Phaser 4 (2.5D 等轴测) |
| 样式 | Tailwind CSS + Framer Motion |
| 实时通信 | SSE (Server-Sent Events) |

---

## 二、后端 API 路由总表

### 2.1 农场 API

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/game/farm` | GET | 获取完整农场数据，自动更新生长 |
| `/api/game/plant` | POST | 种植作物 |
| `/api/game/harvest` | POST | 收获作物 |
| `/api/game/bulk-harvest` | POST | 一键收获所有成熟作物 |
| `/api/game/water` | POST | 浇水 |
| `/api/game/sell` | POST | 出售作物获得金币 |
| `/api/game/buy-seed` | POST | 购买种子 |
| `/api/game/move` | POST | 保存玩家位置 |

### 2.2 角色互动 API

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/game/character/location` | GET | 角色位置 |
| `/api/game/character/interact` | POST | 角色互动 |
| `/api/game/gift` | POST | 送礼 |

### 2.3 烹饪 & 签到 API

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/game/recipes` | GET | 获取所有配方 |
| `/api/game/cook` | POST | 烹饪料理 |
| `/api/game/daily/check` | GET | 检查签到 |
| `/api/game/daily/claim` | POST | 领取签到奖励 |

### 2.4 事件 & 觉醒 API

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/game/events/heart` | GET | 心级事件检查 |
| `/api/game/events/trigger` | POST | 触发心级事件 |
| `/api/game/awakening/check` | GET | 检查觉醒条件 |
| `/api/game/awakening/trigger` | POST | 触发觉醒 |

### 2.5 地图 API

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/game/maps` | GET | 地图列表 |
| `/api/game/maps/switch` | POST | 切换地图 |
| `/api/game/maps/state` | GET | 地图状态 |
| `/api/game/maps/discover` | POST | 发现地图内容 |
| `/api/game/maps/discoveries` | GET | 发现列表 |

### 2.6 状态同步 API

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/game/state` | GET | 全量游戏状态 |
| `/api/game/state/sse` | GET | SSE 实时推送 |
| `/api/game/state/diff` | GET | 增量差异 |
| `/api/game/state/version` | GET | 状态版本号 |
| `/api/game/sync` | POST | 增量操作同步 |

### 2.7 多媒体 API

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/game/generate/selfie` | POST | AI 自拍生成 |
| `/api/game/generate/sticker` | POST | 表情包生成 |
| `/api/game/generate/scene` | POST | 场景图生成 |
| `/api/game/tts` | POST | 文本转语音 |

### 2.8 角色学习 API

| 路由 | 方法 | 功能 |
|------|------|------|
| `/api/characters/evolve` | POST | 角色进化（三阶段） |
| `/api/characters/learn/novel` | POST | 小说学习 |
| `/api/characters/learn/chat` | POST | 聊天记录学习 |
| `/api/characters/learn/memory` | POST | 向量记忆学习 |
| `/api/characters/learning/status` | GET | 学习状态 |

---

## 三、数据库 Schema

### 3.1 核心数据表

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `users` | 用户 | telegram_id, username, is_admin |
| `characters` | 角色 | name, personality, speaking_style, world_layer |
| `farms` | 农场 | user_id, level, experience, money(初始500) |
| `farm_tiles` | 地块 | farm_id, x, y, tile_type, is_unlocked |
| `crops` | 作物 | tile_x, tile_y, crop_type, growth_stage(0-3), water_level(0-3) |
| `crop_types` | 作物类型 | name, growth_time, sell_price, seed_price, tier(0-8) |
| `inventory` | 背包 | item_type, item_id, quantity, quality(1-3星) |
| `relationships` | 玩家-角色关系 | hearts(0-10), affection, happiness, awakening |
| `recipe_types` | 料理配方 | name, ingredients(JSON), sell_price, effect(JSON) |
| `character_schedules` | 角色日程 | day_of_week, start_hour, location, activity |
| `heart_events` | 心级事件 | required_hearts, trigger_location, dialogue(JSON) |
| `triggered_events` | 已触发事件 | user_id, event_id, triggered_at |
| `gift_history` | 礼物记录 | reaction(love/like/neutral/dislike/hate) |
| `game_events` | 游戏事件日志 | event_type, event_data(JSON), synced |
| `daily_rewards` | 每日奖励 | reward_date, reward_type, claimed |
| `awakening_events` | 觉醒事件 | required_affection/happiness/awakening |
| `memories` | 记忆 | memory_key, memory_value, category, importance |

### 3.2 数据库 Mixin 模块

| 文件 | 类名 | 职责 |
|------|------|------|
| `database/farm.py` | `FarmMixin` | 农场 CRUD、种植/收获/浇水、作物生长更新 |
| `database/cooking.py` | `CookingMixin` | 料理配方查询、材料检查、烹饪执行 |
| `database/inventory.py` | `InventoryMixin` | 背包物品增删查 |
| `database/relationship.py` | `RelationshipMixin` | 好感度/心级/情感值/觉醒/世界层级 |
| `database/player.py` | `PlayerMixin` | 玩家位置保存/读取 |
| `database/maps.py` | `MapMixin` | 多地图系统、解锁、切换、发现 |
| `database/events.py` | `EventsMixin` | 心级事件、游戏事件日志、角色日程 |

---

## 四、农场系统

### 4.1 作物生长机制

- 基于种植时间计算生长进度: `elapsed_minutes / growth_time`
- 浇水加速: 每级浇水减少 15% 生长时间，最高 3 级 = 45% 减少
- 生长阶段: 0(种子) → 1(发芽, 33%) → 2(生长中, 66%) → 3(成熟, 100%)
- 收获概率奖励: 15% 返还种子, 5% 双倍产量

### 4.2 作物类型（20种，8个层级）

| 作物 | 生长时间 | 种子价 | 售价 | 层级 | 季节 |
|------|----------|--------|------|------|------|
| 🥔 土豆 | 120分钟 | 10 | 30 | 0 | 春/秋 |
| 🍅 番茄 | 180分钟 | 20 | 50 | 0 | 春/夏 |
| 🥬 白菜 | 180分钟 | 15 | 40 | 0 | 秋/冬 |
| 🌽 玉米 | 240分钟 | 30 | 80 | 0 | 夏 |
| 🥕 胡萝卜 | 150分钟 | 15 | 35 | 0 | 春/秋 |
| 🍓 草莓 | 300分钟 | 50 | 120 | 0 | 春 |
| 🎃 南瓜 | 360分钟 | 40 | 150 | 0 | 秋 |
| 🍉 西瓜 | 420分钟 | 60 | 200 | 0 | 夏 |
| 🌻 向日葵 | 5分钟 | 5 | 15 | 1 | 春/夏 |
| 🌾 小麦 | 10分钟 | 8 | 20 | 1 | 秋 |
| 🫚 萝卜 | 20分钟 | 10 | 25 | 1 | 春/秋 |
| 🍚 水稻 | 60分钟 | 25 | 60 | 2 | 夏 |
| 🧅 洋葱 | 90分钟 | 30 | 70 | 2 | 春/冬 |
| 🍆 茄子 | 120分钟 | 40 | 90 | 3 | 夏 |
| 🌶️ 辣椒 | 150分钟 | 45 | 100 | 3 | 夏/秋 |
| 🥦 西兰花 | 240分钟 | 60 | 150 | 4 | 秋/冬 |
| 🥬 花椰菜 | 360分钟 | 70 | 180 | 5 | 冬 |
| 🌿 朝鲜蓟 | 480分钟 | 100 | 250 | 6 | 春 |
| 🌿 人参 | 720分钟 | 200 | 500 | 7 | 秋 |
| ✨ 金草莓 | 1440分钟 | 400 | 1000 | 8 | 夏 |

### 4.3 前端崩坏区作物（6种简化版）

| 作物 | 生长时间(秒) | 种子价 | 售价 | 崩坏外观 | 崩坏效果 |
|------|-------------|--------|------|----------|----------|
| 🍅 番茄 | 30 | 10 | 25 | 💗 | 送给角色+2好感 |
| 🥕 胡萝卜 | 20 | 5 | 15 | ✨ | 送给角色+2觉醒 |
| 🌽 玉米 | 40 | 15 | 40 | 🌈 | 可兑换特殊道具 |
| 🌾 小麦 | 25 | 8 | 20 | 📖 | 解锁角色回忆 |
| 🥔 土豆 | 35 | 12 | 30 | ⏰ | 加速作物生长 |
| 🍓 草莓 | 50 | 20 | 50 | 🔮 | 直接+5觉醒值 |

---

## 五、烹饪系统

### 5.1 料理配方（8种）

| 配方 | 材料 | 售价 | 角色喜好 | 效果 |
|------|------|------|----------|------|
| 🥗 番茄沙拉 | 番茄x2 | 120 | like | 能量+10 |
| 🍲 玉米浓汤 | 玉米x2 + 土豆x1 | 200 | love | 心级+2 |
| 🍰 草莓蛋糕 | 草莓x3 + 番茄x1 | 350 | love | 心级+5 |
| 🥧 南瓜派 | 南瓜x2 + 白菜x1 | 280 | like | 能量+20 |
| 🧃 西瓜汁 | 西瓜x2 | 180 | like | 能量+15 |
| 🍲 红豆粥 | 草莓x1 + 土豆x2 | 500 | love | 心级+8 |
| 🍚 蔬菜炒饭 | 胡萝卜x1 + 白菜x1 + 玉米x1 | 150 | neutral | 能量+25 |
| 🥔 烤土豆 | 土豆x3 | 100 | like | 能量+15 |

### 5.2 每日签到奖励池

随机抽取: 番茄种子x3 / 玉米种子x2 / 草莓种子x1 / 金币(50-200)

---

## 六、角色系统

### 6.1 可互动角色（4位）

| 角色 | 身份 | 初始觉醒 | 命运力 | 喜好 | 厌恶 | 闲逛区域 |
|------|------|----------|--------|------|------|----------|
| 🏃 车如云 | 田径部王牌 | 0 | 80 | 番茄、草莓 | 玉米 | 操场 |
| 📚 姜泰河 | 学生会会长 | 0 | 90 | 小麦、土豆 | 胡萝卜 | 图书馆 |
| 🎨 李素妍 | 漫画社成员 | 15 | 50 | 玉米、草莓 | 土豆 | 漫画社 |
| 👵 朴奶奶 | 小卖部老板 | 50 | 20 | 小麦、番茄 | 无 | 小卖部 |

### 6.2 对话系统

三种对话选项:
- **剧本** (script): 普通对话，无效果
- **真心** (heart): 增加心级和觉醒值
- **隐藏** (hidden): 需要觉醒值条件触发，大幅增加觉醒值

对话条件示例:
- 觉醒值 > 30: 解锁第一层隐藏对话
- 觉醒值 > 60: 解锁第二层隐藏对话
- 所有角色觉醒值 > 50: 解锁朴奶奶终极对话

### 6.3 好感度/关系系统

**关系状态**: stranger → acquaintance → friend → close → lover → awakened

**情感三维值**:
- `affection` (-100 ~ 100): 好感度
- `happiness` (0 ~ 100): 幸福度
- `awakening` (0 ~ 100): 觉醒度

**送礼机制**: 每个礼物 +5 好感度，角色有 likedGifts / dislikedGifts 偏好

### 6.4 心级事件系统（5个预设事件）

| 事件 | 需要心级 | 地点 | 时间 | 奖励 |
|------|----------|------|------|------|
| 初遇 | 0 | 田径场 | 7-8时 | hearts+1 |
| 屋顶夜景 | 3 | 天台 | 21-23时 | hearts+2, 解锁天台 |
| 雨天共伞 | 6 | 学校 | 15-18时 | hearts+3 |
| 冰淇淋 | 4 | 咖啡厅 | 14-16时 | hearts+2 |
| 奶奶的故事 | 8 | 宿舍 | 20-22时 | hearts+5 |

### 6.5 觉醒系统（5个阶段）

| 阶段 | 名称 | 觉醒阈值 | 事件标题 |
|------|------|----------|----------|
| 1 | 困局 | 0 | - |
| 2 | 触动 | 20 | 冰壁上的裂痕 |
| 3 | 觉醒 | 50 | 裂缝中的光 |
| 4 | 共鸣 | 80 | 心意相通 |
| 5 | 完成 | 100 | 命运改写 |

**觉醒条件**: 好感度≥80, 幸福度≥70, 觉醒度≥60, 心级≥8

### 6.6 角色日程系统（车如云）

| 时间 | 周一至周五 | 周六 | 周日 |
|------|-----------|------|------|
| 6-7 | 起床 | - | 睡懒觉 |
| 7-8 | 晨跑 | - | - |
| 8-12 | 上课 | 训练 | - |
| 12-13 | 午餐 | - | - |
| 13-17 | 上课 | - | - |
| 17-19 | 训练 | - | 轻松训练(晴天) |
| 19-21 | 休息 | 休息 | - |
| 21-23 | 天台看夜景(需3心级) | - | 天台看日落(晴天, 需4心级) |

---

## 七、多地图系统（6张地图）

| 地图 | 网格大小 | 默认解锁 | 解锁条件 | 背景色 | 活动 |
|------|----------|----------|----------|--------|------|
| 🏠 家 | 20x20 | 是 | - | #FFF8E7 | 休息/日记/烹饪 |
| 🏫 学校 | 30x30 | 是 | - | #F0F4FF | 学习/偶遇/社团 |
| ☕ 咖啡厅 | 20x20 | 是 | - | #F5E6D3 | 约会/对话/兼职 |
| 🌳 公园 | 30x30 | 否 | 好感度≥20 | #E8F5E9 | 散步/季节活动/野餐 |
| 🌃 天台 | 20x20 | 否 | 好感度≥50 | #1A1A2E | 特殊对话/观星/秘密 |
| 🏖️ 海边 | 30x30 | 否 | 好感度≥80 | #87CEEB | 约会/游泳/烟花 |

---

## 八、世界层级系统

| 层级 | 名称 | 解锁条件 | 描述 |
|------|------|----------|------|
| normal | 现实世界 | 默认 | 日常生活层 |
| dream | 梦境层 | 默认 | 潜意识世界 |
| memory | 记忆层 | 好感度≥50 | 过去的回忆 |
| truth | 真相层 | 有觉醒角色 | 隐藏的真相 |

---

## 九、崩坏系统

4 种崩坏事件（需 ≥10 能量）:

| 事件 | 描述 | 风险 | 效果 |
|------|------|------|------|
| ⏩ 时间加速 | 所有作物瞬间成熟 | 20% | 作物瞬间成熟 |
| 🌀 空间折叠 | - | 10% | 解锁隐藏种植格 |
| 💭 记忆涌现 | - | 30% | 解锁角色秘密 |
| 💗 情感共鸣 | - | 15% | 全角色心级+2 |

**能量获取**: 崩坏区收获作物 +3 能量，真心/隐藏对话按比例获得能量

---

## 十、2.5D 等轴测游戏引擎 (Phaser 4)

### 10.1 文件结构

| 文件 | 职责 |
|------|------|
| `hooks/usePhaser.ts` | React Hook，初始化 Phaser Game 实例 |
| `scenes/BootScene.ts` | 启动场景 |
| `scenes/PreloadScene.ts` | 资源预加载，创建粒子纹理 |
| `scenes/GameScene.ts` | 主游戏场景，2.5D 等轴测 RPG |
| `classes/Player.ts` | 玩家角色类，键盘/点击移动、Y-Sorting |
| `classes/MapLoader.ts` | 地图加载器，支持 Tiled JSON 和程序化生成 |
| `utils/IsometricUtils.ts` | 等轴测坐标转换工具 |

### 10.2 引擎特性

- **瓦片尺寸**: 64x32 (标准 2:1 等轴测)
- **坐标转换**: `gridToScreen()` / `screenToGrid()` 双向转换
- **深度排序**: Y-Sorting，`(gridX + gridY) * 10 + layer`
- **玩家**: 几何图形组合（阴影+身体+头部+眼睛），WASD/方向键+点击移动
- **地图**: 程序化生成等轴测菱形网格（草地纹理+高光效果）
- **相机**: 跟随玩家，带边界限制
- **粒子**: 星星(金色)、心形(珊瑚色)、泥土(棕色)、水滴(蓝色)

### 10.3 前端双模式

1. **漫游模式** (roam): DOM 渲染校园地图，WASD 移动，E 键互动
2. **管理模式** (manage): Phaser 2.5D 等轴测视图，底部工具栏

两种世界区域:
1. **剧本区** (script): 正常游戏世界，绿色渐变背景
2. **崩坏区** (collapse): 异变世界，紫色渐变背景，闪烁粒子特效

### 10.4 漫游模式校园区域（9个）

操场、天台、走廊、图书馆、漫画社、食堂、小卖部、校门、花坛(农田)

---

## 十一、状态同步机制

为适应 e2-micro 1GB RAM 约束，采用 **SSE + 版本号 + 增量差异** 方案:

```
[后端状态变更] → notify_state_change() → 版本号+1 → SSE 推送
                                                         |
[前端] ← SSE 收到通知 → GET /state/diff?version=N → 增量差异 → 局部更新
```

- **版本号**: 进程级内存存储，重启后重置
- **快照缓存**: TTL=300秒
- **SSE 推送**: 每用户最多 3 个订阅者，30秒心跳
- **全量回退**: 版本号差距>10 或无快照时自动全量拉取

---

## 十二、当前实现状态

### ✅ 已完成

| 系统 | 说明 |
|------|------|
| 农场后端 API | 种植/收获/浇水/买卖/批量收获，含概率奖励 |
| 烹饪后端 API | 8种配方，材料检查，每日签到 |
| 角色互动 API | 送礼、互动、位置查询 |
| 心级事件 | 5个预设事件，条件触发 |
| 觉醒系统 | 5阶段觉醒，条件检测 |
| 多地图后端 | 6地图，好感度解锁，发现系统 |
| 世界层级 | 4层级，条件解锁 |
| SSE 状态同步 | 版本号 + 增量差异 + 快照缓存 |
| 前端漫游模式 | DOM 渲染校园地图，角色对话 |
| 前端管理模式 UI | 商店/背包/工具栏 |
| 崩坏系统 | 4种崩坏事件，能量管理 |
| 角色学习进化 | 三阶段学习 API |
| 多媒体生成 | 自拍/表情包/场景/TTS |

### 🔨 进行中 / 部分完成

| 系统 | 说明 |
|------|------|
| Phaser 2.5D 引擎 | 等轴测网格+玩家移动已实现，NPC/作物渲染待实现 |
| 前后端数据打通 | 前端 Zustand 有本地状态，与后端 API 实时同步尚未完全接通 |

### 📋 待实现

| 功能 | 说明 |
|------|------|
| Tiled 地图文件 | MapLoader 支持加载但无实际地图文件 |
| NPC 在 Phaser 中渲染 | 当前仅有玩家角色 |
| 作物在 Phaser 中渲染 | 管理模式使用 Phaser 但作物由 DOM 渲染 |
| 碰撞检测 | MapLoader.isWalkable() 仅做边界检查 |
| 前端烹饪 UI | 后端 API 完整但前端无独立烹饪页面 |
| 前端地图切换 UI | 后端 API 完整但前端未集成 |

---

*最后更新：2026-05-15 v1.6.5*
