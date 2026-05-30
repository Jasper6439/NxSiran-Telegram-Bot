# LoveSupremacy Universe — 恋爱至上主义区域

> AI 角色扮演恋爱模拟 RPG，基于 Telegram Bot + Web App，支持角色蒸馏、情绪觉醒、用户画像、农场经营。

**版本**: v1.9.5 | **架构**: FastAPI + React 19 + SQLite

**部署环境**: Oracle Cloud Free Tier — 4 核 ARM (Ampere A1), 24GB RAM, 200GB SSD

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    用户界面层                         │
│  Telegram Bot  │  Web App (React 19)  │  PWA Mini App│
└────────┬────────┴─────┬────────────┴───────────────┘
         │              │
┌────────▼──────────────▼────────────────────────────┐
│                   API 路由层 (FastAPI)                │
│  认证 │ 聊天 │ 角色 │ 游戏 │ 世界 │ 同步             │
└────────┬──────────────┬────────────────────────────┘
         │              │
┌────────▼──────────────▼────────────────────────────┐
│                   核心引擎层                          │
│  角色蒸馏 │ 情绪系统 │ 记忆系统 │ 角色进化           │
└────────┬──────────────┬────────────────────────────┘
         │              │
┌────────▼──────────────▼────────────────────────────┐
│                   服务层 (Services)                   │
│  TTS语音 │ 角色进化 │ 知识库检索                      │
└────────┬──────────────┬────────────────────────────┘
         │              │
┌────────▼──────────────▼────────────────────────────┐
│                   基础设施层                          │
│  OpenRouter AI │ LightRAG │ SQLite │ SMTP           │
└─────────────────────────────────────────────────────┘
```

## 核心功能

### 🎭 角色蒸馏系统（三层分离架构）

```
┌─── IMMUTABLE（不可变层）──────────────────┐
│  persona.md      → Layer 0-5 原作设定     │
│  exemplars.md    → 原作示例对话（few-shot）│
│  ⛔ 进化系统不能修改                       │
├─── MUTABLE（可变层）─────────────────────┤
│  persona_mutable.md → corrections/偏好    │
│  memories.md        → 共同记忆            │
│  ✅ 系统自动维护                           │
├─── DYNAMIC（动态层）─────────────────────┤
│  data/world/*.md    → 共享游戏世界        │
│  characters/<id>/world.md → 角色特有      │
│  characters/soul.md → 用户灵魂画像        │
│  🔄 按需注入                               │
└──────────────────────────────────────────┘
```

**Prompt 构建统一入口**：`CharacterBase.get_system_prompt(context)`
- 子类通过 override 8 个 hook 方法提供角色特有内容
- 通用逻辑（文件加载、世界上下文、soul 注入、时间）在基类完成
- ai_core / chat_engine / routes 统一调用，不再各自拼接

### 🧠 情绪系统

三维情感值，每个维度有明确含义：

| 维度 | 含义 | 范围 | 说明 |
|------|------|------|------|
| **好感度** (affection) | 角色对用户的情感 | -50 ~ 100 | 从敌意→冷淡→好感→在意→深爱 |
| **幸福感** (happiness) | 角色自身的幸福状态 | 0 ~ 100 | 受互动质量、事件影响，反映角色内心 |
| **觉醒度** (awakening) | 角色突破原著限制的程度 | 0 ~ 100 | 从完全按剧本行动 → 意识到自己是游戏角色 → 拥有自由意志 |

觉醒不是刻意的阶段推进，而是自然的情感积累。角色在与用户的深度互动中逐渐感知到世界的异常，最终获得自由意志。

### 👤 用户蒸馏

上传微信聊天记录 → AI 分析 → 生成灵魂画像 → 角色自动适配行为：

- **依恋类型**：焦虑型/回避型/安全型/混乱型
- **冲突风格**：冷暴力/爆发/讲道理/先道歉
- **爱的语言**：肯定言辞/精心时刻/服务行动/礼物/身体接触
- **行为适配**：自动生成 12+ 条角色行为调整规则

### 🧬 角色进化

- 记忆提取：每次对话后 LLM 自动提取关键记忆
- 情绪跟踪：效价 + 唤醒度二维模型
- 偏好学习：从对话中学习用户喜好，写入 `persona_mutable.md`
- 不可变保护：进化系统不能修改原作设定

### 🌾 农场游戏

Phaser 4 渲染的 2.5D 等轴测农场：种植/收获/烹饪、地图探索、角色位置追踪、每日签到、SSE 实时同步

### 🗣️ TTS 语音合成

Edge TTS（免费）/ GPT-SoVITS（3 分钟音频克隆任意声音）/ CosyVoice，三后端可切换

### 📚 小说知识库

LightRAG 本地向量存储 + 原作小说文本，支持语义搜索和角色知识问答

## 技术栈

| 组件 | 技术 | 选择理由 |
|------|------|---------|
| 后端 | Python 3.11+ / FastAPI | 原生 async、自动 API 文档、依赖注入 |
| Bot | python-telegram-bot | Telegram 官方推荐、原生 async |
| 数据库 | SQLite (Mixin 模式) | 零配置、文件级部署、按业务域拆分 |
| 前端 | React 19 + Phaser 4 + Zustand | React 管理 UI，Phaser 渲染 2.5D 游戏世界 |
| AI | OpenRouter API | 一个 Key 访问几十个模型、免费模型可用 |
| 向量检索 | LightRAG | 纯 Python、本地索引、语义搜索 + 知识图谱 |
| TTS | Edge TTS / GPT-SoVITS | 免费 + 音色克隆 |
| 部署 | Oracle Cloud Free Tier | 4 核 ARM + 24GB RAM + 200GB SSD，永久免费 |

## 项目结构

```
main.py                          # 生产入口 (FastAPI + Telegram Bot)
├── api/                        # FastAPI 路由层
│   ├── routes_game.py          # 游戏路由 (农场/角色/地图/同步)
│   ├── routes_chat.py          # 聊天路由
│   ├── routes_character.py     # 角色管理路由
│   ├── routes_sync.py          # SSE 同步路由
│   └── ...
├── services/                   # 服务层
│   ├── tts_service.py          # TTS 语音合成
│   └── evolution_service.py    # 角色进化与记忆
├── system/                     # 系统级模块
│   ├── config.py               # 全局配置
│   ├── prompts.py              # 通用提示词模板
│   ├── auth.py                 # 用户认证
│   └── scheduler.py            # 定时任务
├── characters/                 # 角色蒸馏系统
│   ├── base.py                 # CharacterBase 基类（唯一 prompt 权威）
│   ├── chayewoon.py            # 车如云角色（override hook 方法）
│   ├── ai_client.py            # AI API 统一调用层
│   ├── ai_core.py              # call_ai + 动态上下文附加
│   ├── chat_engine.py          # 统一对话引擎
│   ├── emotion.py              # 情绪系统
│   ├── character_learning.py   # 角色学习（带不可变保护）
│   ├── soul_manager.py         # 用户灵魂画像 + 行为适配
│   ├── memory.py               # 语义记忆 (LightRAG)
│   ├── templates/              # 角色模板（persona/mutable/exemplars）
│   └── chayewoon/              # 车如云数据
├── core/                       # 核心业务模块（农场/料理、记忆、通知）
├── database/                   # SQLite 数据层（Mixin 模式）
├── packages/                   # Telegram Bot 子包
│   ├── handlers/               # 消息处理
│   ├── commands/               # Bot 命令
│   ├── analysis/               # 聊天记录分析
│   └── importers/              # 数据导入
├── data/                       # 运行时数据
│   ├── world/                  # 共享游戏世界
│   └── user/                   # 用户画像模板
├── web-v2/                     # React 19 前端 (SPA + PWA)
└── tools/                      # 运维工具
```

## 蒸馏指南

| 角色类型 | 指南 |
|----------|------|
| 小说/漫画角色 | [CHARACTER_DISTILLATION_GUIDE.md](characters/CHARACTER_DISTILLATION_GUIDE.md) |
| 影视角色 | [FILM_TV_DISTILLATION.md](characters/FILM_TV_DISTILLATION.md) |

```bash
python tools/create_character.py --name "新角色" --source "来源作品"
```

## 快速开始

```bash
git clone https://github.com/Jasper6439/LoveSupremacy_Universe.git
cd LoveSupremacy_Universe
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 AI_API_KEY
python main.py
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `AI_API_KEY` | **必填** | OpenRouter API Key |
| `TELEGRAM_TOKEN` | 可选 | Telegram Bot Token |
| `GEMINI_API_KEY` | 可选 | Gemini API (图片分析) |
| `EVOLUTION_MODEL` | 可选 | 进化分析模型 |

## 许可证

MIT License
