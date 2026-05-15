# PROJECT_CONTEXT.md — NxSiran Telegram Bot

> **Mandatory:** All AI agents MUST read this file before starting any task.

## Project Identity

- **Name:** 恋爱至上主义区域 (Love Supremacy Zone)
- **Type:** Telegram Bot + Web Game — 恋爱模拟 RPG
- **Current Version:** v1.6.5
- **Repository:** `Jasper6439/NxSiran-Telegram-Bot`
- **Language:** Python 3.11+

## Architecture

```
bot.py                          # 唯一入口，python-telegram-bot Application
├── system/                     # 系统级模块
│   ├── config.py               # 全局配置、环境变量、版本号、路径
│   ├── prompts.py              # 系统提示词、模板、文本处理函数
│   ├── auth.py                 # 用户认证（邮箱注册、session/api token、角色绑定）
│   ├── scheduler.py            # APScheduler 后台定时任务
│   ├── email_sender.py         # Gmail SMTP 邮件发送
│   ├── webhook_server.py       # 独立 Webhook + Bridge 服务 (aiohttp:8082)
│   └── *.service / *.sh        # systemd 服务文件和运维脚本
├── characters/                 # 角色系统
│   ├── __init__.py             # 角色注册表、动态加载
│   ├── base.py                 # CharacterBase 抽象基类、CharacterConfig
│   ├── chayewoon.py            # 车如云角色实现（当前唯一角色）
│   ├── ai_client.py            # AI API 统一调用层（模型 fallback）
│   ├── ai_core.py              # call_ai + summarize_and_save_memory
│   ├── ai_compete.py           # 多模型并行竞争选优
│   ├── chat_engine.py          # Web/Telegram 统一对话引擎
│   ├── chat_history.py         # 聊天历史持久化
│   ├── emotion.py              # 情绪识别、表情反应、亲密度
│   ├── emotion_analyzer.py     # 关键词情感分析
│   ├── image_gen.py            # 图片生成（自拍/场景/贴纸）
│   ├── memory_legacy.py        # JSON 文件长期记忆
│   ├── qdrant_memory.py        # Qdrant Cloud 向量记忆
│   ├── tts_engine.py           # TTS 语音合成（Edge TTS / SoVITS / Fish Speech）
│   ├── weather.py              # 首尔天气查询
│   ├── music_skill.py          # YouTube Music 搜索
│   ├── novel_knowledge.py      # LightRAG 小说知识库
│   ├── anniversary.py          # 纪念日系统
│   └── stats.py                # 统计、额度、报告
├── game_api/                   # 游戏 HTTP API（aiohttp 路由）
│   ├── auth.py                 # 统一认证中间件
│   ├── farm_routes.py          # 农场种植/收获/浇水/售卖
│   ├── character_routes.py     # 角色互动/送礼/同步
│   ├── map_routes.py           # 多地图系统（6地图）
│   ├── sync_routes.py          # 游戏事件同步 + SSE 实时推送 + 增量 diff
│   ├── game_state.py           # 状态序列化 + 版本号管理 + 变更通知
│   ├── cooking_routes.py       # 烹饪 + 每日签到
│   ├── heart_routes.py         # 心级事件
│   ├── media_routes.py         # 自拍/贴纸/场景图生成 API
│   └── awakening_detector.py   # 觉醒阶段检测
├── database/                   # SQLite 数据库（Mixin 模式）
│   ├── base.py                 # 连接管理、用户管理、Schema 初始化
│   ├── farm.py                 # 农场 CRUD
│   ├── maps.py                 # 6 地图定义
│   ├── inventory.py            # 背包系统
│   ├── cooking.py              # 料理 + 每日奖励
│   ├── chat.py                 # 聊天记录 + 记忆
│   ├── relationship.py         # 关系/亲密度/情感值/觉醒事件
│   ├── player.py               # 玩家位置
│   └── events.py               # 心级事件/事件日志/角色日程
├── packages/                   # Telegram Bot 子包
│   ├── handlers/               # Update 分发（text/photo/callback/voice）
│   ├── commands/               # Bot 命令（basic/skills/extra/quota 等）
│   ├── web/                    # Web HTTP API 路由注册
│   ├── bridge/                 # VM 远程命令/文件桥接
│   ├── analysis/               # 聊天记录统计分析
│   └── importers/              # 外部数据导入（视频/聊天记录）
├── tools/                      # 工具脚本
│   ├── bridge_client.py        # VM 端桥接客户端
│   ├── create_character.py     # 新角色模板生成
│   ├── version_manager.py      # 角色版本备份/回滚
│   ├── init_admin.py           # 管理员初始化
│   └── _archive/               # 归档文件（bot_instance/manager 等）
├── web-v2/                     # React + TypeScript + Vite 前端
├── characters/chayewoon/       # 角色数据（车如云）
│   ├── config.json             # 角色配置
│   ├── persona.md              # 角色详细设定
│   ├── memories.md             # 共同记忆
│   └── novel.txt               # 原著小说（角色学习素材）
├── static/                     # 静态资源
├── templates/                  # HTML 模板
└── data/                       # 运行时数据（JSON/图片/音频）
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Bot Framework | python-telegram-bot (async) |
| Web Server | aiohttp |
| Database | SQLite (stdlib) |
| Frontend | React + TypeScript + Vite + Tailwind + Zustand + Phaser.js |
| AI | OpenRouter API (多模型 fallback) |
| Memory | Qdrant Cloud (向量) + JSON 文件 (长期) |
| TTS | Edge TTS / GPT-SoVITS / Fish Speech |
| Deployment | GCP e2-micro (1GB RAM), systemd, Cloudflare Tunnel |

## Deployment

- **VM:** GCP e2-micro, IP: `35.212.211.245`, OS: Debian
- **Project Dir:** `/root/NxSiran-Telegram-Bot/`
- **systemd Services:**
  - `nxsiran-bot.service` — Telegram Bot 主进程
  - `nxsiran-webhook.service` — Webhook + Bridge (port 8082)
  - `nxsiran-watcher.service` — 进程监控守护
  - `cloudflared-quick.service` — Cloudflare Tunnel
- **CI/CD:** GitHub Push → Webhook (8082) → `git pull` + `systemctl restart nxsiran-bot`
- **Auto-merge:** `.github/workflows/auto-merge.yml` — 版本号排序自动合并，冲突时创建 PR

## Import Convention

- **Absolute imports only:** `from system.config import X`, `from characters.ai_client import Y`
- **Relative imports only within-package:** `from .sibling import Z` (inside characters/, database/, etc.)
- **No re-export shims:** All imports resolve to canonical module location
- **Root directory:** Only `bot.py` is permitted at project root

## Database

- **Engine:** SQLite, file at `DATA_DIR/game.db`
- **Schema:** `database/data/game_schema.sql`
- **Pattern:** Mixin — `NxSiRanDB` class inherits from `BaseMixin`, `FarmMixin`, `RelationshipMixin`, etc.
- **Access:** `get_db()` returns thread-local instance

## Future Roadmap

| Version | Feature | Status |
|---------|---------|--------|
| v1.6.3 | Front-end/back-end game state sync | Done |
| v1.6.4 | Multi-character support | Done |
| v1.6.5 | Mobile touch controls | Done |

## Key Design Decisions

1. **Multi-character framework** — `characters/` 目录下每个子目录（含 `config.json`）自动发现并加载为独立角色。当前已实现：车如云。新增角色只需创建目录 + config.json + 可选的 `{char_id}.py`。`database._ensure_relationships()` 自动为所有已注册角色创建关系记录。
2. **Dual prompt system** — `system/prompts.py` has legacy `SYSTEM_PROMPT`; `characters/chayewoon.py` has `get_system_prompt()` with awakening/world-level awareness. The chayewoon version is authoritative.
3. **Web + Telegram dual interface** — `chat_engine.py` provides unified chat processing for both web and Telegram.
4. **Qdrant for semantic memory** — Replaces ChromaDB. Remote Qdrant Cloud with LRU cache (500 entries).
5. **Config-driven** — All paths, tokens, model lists in `system/config.py` via environment variables.
