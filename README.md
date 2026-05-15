# NxSiran — 恋爱至上主义区域

> AI 角色扮演恋爱模拟 RPG，基于 Telegram Bot + Web，支持多模型竞争、语义记忆、情绪系统、农场经营。

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    用户界面层                         │
│  Telegram Bot  │  Web App (React)  │  Mini App      │
└────────┬────────┴─────┬────────────┴───────────────┘
         │              │
┌────────▼──────────────▼────────────────────────────┐
│                   API 路由层                          │
│  认证 │ 聊天 │ 角色 │ 媒体 │ 游戏 │ 技能 │ 分析      │
└────────┬──────────────┬────────────────────────────┘
         │              │
┌────────▼──────────────▼────────────────────────────┐
│                   核心引擎层                          │
│  AI竞争 │ 角色系统 │ 情绪系统 │ 记忆系统 │ TTS      │
└────────┬──────────────┬────────────────────────────┘
         │              │
┌────────▼──────────────▼────────────────────────────┐
│                   基础设施层                          │
│  OpenRouter AI │ Qdrant Cloud │ SQLite │ Gmail SMTP │
└─────────────────────────────────────────────────────┘
```

## 核心功能

### AI 多模型竞争

4 个免费 AI 模型轮换竞争，规则引擎 + 按需互评选出最佳回复：

```
用户发言 → Qdrant缓存 → 3模型并行生成 → 规则引擎评分 → 按需互评 → 返回最佳
```

- **规则引擎**（<1ms）：角色专属规则，一票否决 + 扣分制
- **轮换评委**：4 模型轮换参赛/评委，公平竞争
- **权重系统**：获胜 +0.1，失败 -0.05，持久化存储
- **Qdrant 缓存**：语义相似度 > 0.92 直接返回，毫秒级响应
- **超时熔断**：总链路 60s，自动降级

### 角色系统

可扩展的多角色框架，每个角色独立配置：

| 配置项 | 说明 |
|--------|------|
| `persona.md` | 分层角色设定（世界观→硬规则→身份→风格→情感→关系） |
| `config.json` | 角色属性、情绪默认值、觉醒条件、AI 规则 |
| `memories.md` | 共同记忆、关系时间线、偏好习惯 |
| `ai_rules` | 规则引擎配置（长度、格式、语言、禁用词等） |

已实现角色：**车如云**（恋爱至上主义区域）

### 记忆系统

- **长期记忆**：JSON 持久化，支持搜索/删除/导出
- **语义记忆**：Qdrant Cloud 向量数据库，语义相似度搜索
- **自我改进**：用户纠正 → 学习 → 更新行为模式
- **小说知识库**：LightRAG + 原作小说文本

### 情绪系统

- 三维情感值：好感度（affection）、幸福感（happiness）、觉醒度（awakening）
- 觉醒条件系统：满足最低情感值 + 触发关键事件
- 世界层级：stage → shadow → resonance

### 多媒体

- **AI 换脸**：Gemini 2.5 Flash，用户上传照片 → AI 生成角色自拍
- **表情包生成**：Pollinations AI
- **TTS 语音合成**：Edge TTS / GPT-SoVITS / Fish Speech
- **图片分析**：Gemini Vision
- **OCR**：文档文字识别

### 农场游戏

Phaser.js 渲染的农场经营小游戏，与角色互动：

- 种植/收获/烹饪系统
- 6 地图探索（好感度解锁）
- 角色位置追踪
- 觉醒事件触发
- 每日签到
- SSE 实时状态同步 + 增量 diff

### Bridge 远程命令执行

通过 Webhook 服务的 Bridge 功能，可从外部向 VM 发送命令：

```
外部 (SOLO) → POST /bridge/send → VM 端轮询客户端 → 执行 → 回传结果
```

- **统一端口 8082**：与 Webhook 服务共用
- **安全认证**：Token 验证，仅授权请求可执行

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.11+ / python-telegram-bot / aiohttp |
| AI | OpenRouter（多模型）/ Gemini 2.5 Flash |
| 向量数据库 | Qdrant Cloud |
| 关系数据库 | SQLite |
| 前端 | React + TypeScript + Vite + Tailwind + Zustand + Phaser.js |
| 部署 | GCP e2-micro / systemd / Cloudflare Tunnel |
| CI/CD | GitHub Webhook → git pull + systemctl restart |

## 项目结构

```
bot.py                          # 唯一入口
├── system/                     # 系统级模块
│   ├── config.py               # 全局配置、环境变量、版本号
│   ├── prompts.py              # 系统提示词、模板、文本处理
│   ├── auth.py                 # 用户认证
│   ├── scheduler.py            # 后台定时任务
│   ├── email_sender.py         # Gmail SMTP
│   ├── webhook_server.py       # Webhook + Bridge 服务 (port 8082)
│   └── *.service / *.sh        # systemd 服务 + 运维脚本
├── characters/                 # 角色系统
│   ├── base.py                 # CharacterBase 抽象基类
│   ├── chayewoon.py            # 车如云角色
│   ├── ai_client.py            # AI API 统一调用层
│   ├── ai_core.py              # call_ai + 记忆提取
│   ├── ai_compete.py           # 多模型竞争选优
│   ├── chat_engine.py          # 统一对话引擎
│   ├── chat_history.py         # 聊天历史
│   ├── emotion.py              # 情绪系统
│   ├── image_gen.py            # 图片生成
│   ├── memory_legacy.py        # JSON 长期记忆
│   ├── qdrant_memory.py        # Qdrant 向量记忆
│   ├── tts_engine.py           # TTS 语音合成
│   └── ...                     # weather, music, novel, anniversary, stats
├── game_api/                   # 游戏 HTTP API
│   ├── farm_routes.py          # 农场种植/收获
│   ├── map_routes.py           # 多地图系统
│   ├── character_routes.py     # 角色互动
│   ├── sync_routes.py          # 游戏同步
│   └── ...                     # cooking, heart, media, auth, awakening
├── database/                   # SQLite（Mixin 模式）
│   ├── base.py                 # 连接管理 + Schema
│   ├── farm.py                 # 农场 CRUD
│   ├── relationship.py         # 关系/情感/觉醒
│   └── ...                     # maps, inventory, cooking, chat, player, events
├── packages/                   # Telegram Bot 子包
│   ├── handlers/               # 消息处理（text/photo/callback/voice）
│   ├── commands/               # Bot 命令
│   ├── web/                    # Web HTTP API 路由
│   ├── bridge/                 # VM 桥接
│   ├── analysis/               # 聊天记录分析
│   └── importers/              # 数据导入
├── web-v2/                     # React 前端
├── tools/                      # 工具脚本
├── knowledge/                  # LightRAG 知识库
└── data/                       # 运行时数据
```

## 快速开始

### 环境要求

- Python 3.10+
- Telegram Bot Token（从 [@BotFather](https://t.me/BotFather) 获取）
- OpenRouter API Key（从 [openrouter.ai](https://openrouter.ai) 获取，免费）

### 安装

```bash
git clone https://github.com/Jasper6439/NxSiran-Telegram-Bot.git
cd NxSiran-Telegram-Bot
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 TELEGRAM_TOKEN, AI_API_KEY 等
python bot.py
```

### Docker 部署

```bash
docker-compose up -d
```

### e2-micro (1GB RAM) 优化

```bash
sudo bash tools/optimize_e2micro.sh
```

- 2GB Swap + swappiness=60 + systemd 内存控制

## Telegram 命令

| 命令 | 说明 |
|------|------|
| `/start` | 开始对话 |
| `/reset` | 重置对话 |
| `/selfie` | 查看自拍相册 |
| `/genface` | AI 换脸生成 |
| `/memory` | 查看记忆 |
| `/stats` | 统计数据 |
| `/analyze` | 对话模式分析 |
| `/sticker` | 表情包生成 |
| `/tts` | 语音合成 |
| `/novel` | 小说知识查询 |
| `/version` | 版本信息 |

## Web API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/register` | POST | 用户注册 |
| `/api/login` | POST | 用户登录 |
| `/api/chat` | POST | 发送聊天消息 |
| `/api/characters` | GET | 角色列表 |
| `/api/characters/switch` | POST | 切换角色 |
| `/api/game/state/sse` | GET | SSE 实时状态推送 |
| `/api/game/state/diff` | GET | 增量状态差异 |
| `/api/mobile/dpad` | POST | 移动端方向键移动 |
| `/api/mobile/tap` | POST | 移动端点击交互 |
| `/api/mobile/swipe` | POST | 移动端滑动手势 |
| `/api/characters/evolve` | POST | 角色学习进化（一键） |
| `/api/characters/learn/novel` | POST | 从小说学习 |
| `/api/characters/learn/chat` | POST | 从聊天记录学习 |
| `/api/characters/learning/status` | GET | 学习状态查询 |
| `/api/upload-selfies` | POST | 上传照片 |
| `/api/generate-face` | POST | AI 换脸 |

### Bridge API（端口 8082）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/bridge/send` | POST | 发送命令到 VM |
| `/bridge/poll` | POST | VM 轮询获取命令 |
| `/bridge/result/{id}` | GET | 查询命令执行结果 |
| `/deploy` | GET/POST | 手动触发部署 |
| `/health` | GET | 健康检查 |

## 许可证

MIT License
