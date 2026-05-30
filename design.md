# 🏗️ LoveSupremacy Universe - 技术设计蓝图 (DESIGN.md)

> **核心目标**：在 1GB RAM 环境下，提供角色扮演聊天 + 农场游戏 + Web 界面的一体化体验。

---

## 1. 🗺️ 系统架构概览

**统一入口**：`main.py`（FastAPI + python-telegram-bot 共享事件循环）
**回滚入口**：`bot.py`（aiohttp，仅紧急回滚使用）

### 1.1 目录结构与职责 (v1.9.5)

| 目录/文件 | 职责概要 | 关键技术/约束 |
|:----------|:---------|:--------------|
| **main.py** | 生产入口，FastAPI + Telegram 共享事件循环 | 无 TOKEN 时仅启动 Web |
| **api/** | FastAPI 路由层 | `create_app()` 工厂模式 |
| **services/** | 服务层 | TTS、图像生成、角色进化 |
| **system/** | 核心框架与配置 | `config.py`, `auth.py`, `scheduler.py` |
| **characters/** | 角色蒸馏系统（三层分离） | `base.py` 唯一 prompt 权威 |
| **core/** | 核心业务模块 | 农场/料理、记忆、通知 |
| **database/** | SQLite 数据库 | Mixin 模式，`get_db()` 单例 |
| **packages/** | Telegram Bot 子包 | handlers, commands, analysis, importers |
| **data/** | 运行时数据 | `world/` 共享游戏世界, `user/` 用户画像 |
| **web-v2/** | React 前端 | React 19 + Phaser 4 + PWA |
| **tools/** | 运维工具 | create_character, version_manager |

### 1.2 核心检索架构 (RAG)

为了解决 1GB 内存下的知识检索问题，采用 **双路混合检索** 策略。

```
用户提问
    │
    ▼
┌─────────────────┐
│  BM25 关键词    │  ← 本地内存，低延迟
└────────┬────────┘
         │ 未命中
         ▼
┌─────────────────┐
│  LightRAG 语义  │  ← 本地索引 + Qdrant Cloud
└────────┬────────┘
         │
         ▼
    组装 Prompt → OpenRouter API
```

| 检索路 | 位置 | 用途 | 延迟 |
|:-------|:-----|:-----|:-----|
| **BM25** | 本地内存 | 实体、术语精准匹配 | <10ms |
| **LightRAG** | 本地索引 + Qdrant Cloud | 语义理解、关系推理 | <200ms |

**决策逻辑**：先 BM25，命中则返回；未命中则调用 LightRAG。

### 1.3 入口启动流程

```
main.py 启动
    │
    ├─ init_config()          # 加载配置
    ├─ init_characters()      # 初始化角色系统
    ├─ 配置日志
    ├─ 配置 uvicorn (0.0.0.0:PORT)
    │
    ├─ 有 TELEGRAM_TOKEN？
    │   ├─ YES → 创建 Telegram Application
    │   │        → 注册 handlers
    │   │        → 后台加载小说知识库
    │   │        → asyncio.gather(uvicorn + telegram polling)
    │   │
    │   └─ NO  → 仅启动 Web 服务 (uvicorn)
    │            → Telegram Bot 跳过
    │
    └─ 等待关闭信号
```

---

## 2. 🚀 部署与运维

### 2.1 系统级优化

```bash
# 执行内存优化脚本
sudo bash tools/optimize_memory.sh
```

- **Swap 空间**：2GB Swap 文件，swappiness=60
- **进程限制**：`MemoryMin=100M`, `MemoryLow=200M`
- **熔断监控**：`tools/memory_monitor.py` 每分钟检测
- **OOM 自愈**：systemd `Restart=always`, `RestartSec=5`

### 2.2 内存阈值

| 阈值 | 动作 |
|:-----|:-----|
| > 85% | 自动清理临时文件、缓存 |
| > 95% | Telegram 告警 + 服务自愈重启 |

### 2.3 环境变量

| 变量 | 说明 | 必需 | 示例 |
|:-----|:-----|:-----|:-----|
| `PORT` | Web 服务端口 | 否 (默认 8080) | `8080` |
| `DATA_DIR` | 数据目录 | 否 (默认 /opt/...) | `/opt/LoveSupremacy-Telegram-Bot/data` |
| `TELEGRAM_TOKEN` | Bot Token | 否* | `123456:ABC...` |
| `OPENROUTER_API_KEY` | LLM API | 是** | `sk-or-...` |
| `GEMINI_API_KEY` | 图像生成 | 否 | `AIza...` |
| `MEMORY_SAFE_MODE` | 内存安全模式 | 否 (默认 true) | `true` |
| `MAX_CONTEXT_TOKENS` | 上下文限制 | 否 (默认 1024) | `1024` |

> *TELEGRAM_TOKEN 非必需。未配置时 Web 服务正常启动，Telegram Bot 功能跳过。
> **OPENROUTER_API_KEY 为 AI 对话功能所必需，用户首次使用时配置。

### 2.4 部署方式

```bash
# 一键部署
sudo ./deploy.sh

# 手动更新
cd /opt/LoveSupremacy-Telegram-Bot
git pull origin master
sudo systemctl restart nx_siran
```

---

## 3. 🧠 记忆系统

### 3.1 角色目录结构

```
characters/{character_id}/
├── config.json      # 角色配置
├── persona.md       # 详细设定
├── memories.md      # 共同记忆
└── novel.txt        # 原著素材（LightRAG 学习）
```

### 3.2 记忆流程

1. **用户上传资料** → 存入 `characters/{id}/novel.txt`
2. **LightRAG 索引** → 构建知识图谱
3. **对话时检索** → BM25 + LightRAG 混合查询
4. **更新记忆** → 写入 `memories.md`

---

## 4. 🎮 游戏系统

### 4.1 前端架构

- **框架**：React 19 + TypeScript + Vite
- **状态管理**：Zustand
- **游戏引擎**：Phaser 4 (2.5D 等轴测)
- **样式**：Tailwind CSS
- **PWA**：vite-plugin-pwa + Workbox

### 4.2 前端路由

| 路径 | 页面 | 说明 |
|:-----|:-----|:-----|
| `/` | HomePage | 首页：用户信息、快捷入口 |
| `/game` | GamePage | 农场：Phaser 2.5D 等轴测游戏 |
| `/chat` | ChatPage | 聊天：角色对话 |
| `/settings` | SettingsPage | 设置：账户、外观、通知 |

### 4.3 游戏功能

- 农场种植/收获/浇水
- 6 地图漫游
- 角色互动/送礼
- 烹饪系统
- 觉醒阶段

---

## 5. 📡 API 路由

### 5.1 FastAPI 路由 (api/)

| 路径 | 模块 | 说明 |
|:-----|:-----|:-----|
| `/api/user/*` | `routes_user.py` | 用户认证与管理 |
| `/api/chat/*` | `routes_chat.py` | 聊天接口 |
| `/api/game/*` | `routes_game.py` | 游戏数据 |
| `/api/character/*` | `routes_character.py` | 角色信息 |
| `/api/sync/*` | `routes_sync.py` | SSE 实时推送 |
| `/api/media/*` | `routes_media.py` | 媒体资源 |
| `/api/world/*` | `routes_world.py` | 世界系统 |
| `/*` | `routes_static.py` | 静态文件 + SPA Fallback |

### 5.2 认证机制 (api/deps.py)

三级认证链（按优先级）：
1. **Session Token** — Web 端登录会话
2. **API Token** — 数据库存储的 API Token（v1.9 迁移到 SQLite）
3. **Chat ID Fallback** — Telegram Chat ID 直接访问

---

## 6. 💾 数据库架构 (database/)

### 6.1 Mixin 模式

`GameDatabase` 通过多重继承聚合 10 个 Mixin：

| Mixin | 文件 | 职责 |
|:------|:-----|:-----|
| AuthMixin | auth.py | API Token 管理、金币事务 |
| WorldMixin | world.py | 世界系统 |
| MapMixin | maps.py | 多地图 |
| FarmMixin | farm.py | 农场 CRUD |
| RelationshipMixin | relationship.py | 关系/亲密度/觉醒 |
| CookingMixin | cooking.py | 料理 + 每日奖励 |
| EventsMixin | events.py | 心级事件 + 日程 |
| InventoryMixin | inventory.py | 背包 |
| ChatMixin | chat.py | 聊天记录 + 记忆 |
| PlayerMixin | player.py | 玩家位置 |

### 6.2 级联删除

所有用户相关表配置了 `ON DELETE CASCADE`，删除用户时自动清理关联数据。

---

## 7. ⚠️ 禁止事项

- ❌ 本地运行 Qdrant Server（使用 Qdrant Cloud）
- ❌ 本地加载 LLM 权重（使用 OpenRouter API）
- ❌ 本地运行 Stable Diffusion（使用 Gemini API）
- ❌ 引入 PyTorch/TensorFlow 等重型框架
- ❌ 阻塞 I/O 在异步上下文中
- ❌ Web 服务依赖 Telegram Token（两者独立启动）
- ❌ 直接操作 sqlite3 连接（必须通过 database/ 模块）

---

*最后更新：2026-05-16 v1.9.1*
