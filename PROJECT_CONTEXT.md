# PROJECT_CONTEXT.md — LoveSupremacy Telegram Bot

> **Mandatory:** All AI agents MUST read this file before starting any task.

## Project Identity

- **Name:** 恋爱至上主义区域 (Love Supremacy Zone)
- **Type:** Telegram Bot + Web Game — 恋爱模拟 RPG
- **Current Version:** v1.9.5
- **Repository:** `Jasper6439/LoveSupremacy_Universe`
- **Language:** Python 3.11+
- **Deployment:** Oracle Cloud Free Tier — 4 核 ARM (Ampere A1), 24GB RAM, 200GB SSD

## 三维情感值定义

| 维度 | 英文 | 含义 | 范围 |
|------|------|------|------|
| **好感度** | affection | 角色对用户的情感 | -50 ~ 100 |
| **幸福感** | happiness | 角色自身的幸福状态 | 0 ~ 100 |
| **觉醒度** | awakening | 角色突破原著限制的程度 | 0 ~ 100 |

- 好感度从敌意→冷淡→好感→在意→深爱
- 幸福感受互动质量、事件影响，反映角色内心
- 觉醒度是自然的情感积累，不是刻意的阶段推进

## Architecture (v1.9.5)

### Prompt 构建统一入口

`CharacterBase.get_system_prompt(context)` 是唯一的 prompt 构建权威。

### 角色蒸馏三层分离

```
IMMUTABLE:  persona.md + exemplars.md（原作设定，不可被进化修改）
MUTABLE:    persona_mutable.md + memories.md（系统自动维护）
DYNAMIC:    data/world/*.md + characters/<id>/world.md + soul.md（按需注入）
```

### 不可变文件保护

`IMMUTABLE_FILES` 列表：`persona.md`、`exemplars.md`、`config.json`

### 用户蒸馏

上传聊天记录 → `soul_manager.py` 生成 soul.md → 行为适配规则自动注入

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Bot Framework | python-telegram-bot (async) |
| Web Server | FastAPI |
| Database | SQLite (Mixin pattern) |
| Frontend | React 19 + TypeScript + Vite + Zustand + Phaser 4 |
| AI | OpenRouter API |
| Memory | LightRAG (local vectors) + JSON (long-term) |
| TTS | Edge TTS / GPT-SoVITS / CosyVoice |
| Deployment | Oracle Cloud Free Tier (4C ARM, 24GB RAM) |

## Key Design Decisions

1. **Single prompt authority** — `CharacterBase.get_system_prompt()` 唯一入口
2. **Three-layer distillation** — Immutable / Mutable / Dynamic
3. **Continuous awakening** — 觉醒度是连续值，不是阶段推进
4. **No multi-model competition** — 已移除，使用单一模型调用
5. **No multimedia generation** — 已移除图像生成/换脸/表情包
6. **Config-driven** — 所有配置在 `system/config.py` 或 `.env`
7. **FastAPI unification** — 单一 Web 框架
