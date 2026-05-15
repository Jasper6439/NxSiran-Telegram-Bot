# 🏗️ NxSiran Bot - 技术设计蓝图 (design.md)

> **核心目标**：在 1GB RAM 环境下，通过混合检索技术实现低延迟的角色扮演聊天。

---

## 1. 🗺️ 系统架构概览

我们采用 **"核心本地化 + 边缘云端化"** 的混合架构。

### 1.1 目录结构与职责

| 目录/文件 | 职责概要 | 关键技术/约束 |
|:----------|:---------|:--------------|
| **Root** | 入口与根配置 | `bot.py` (唯一入口), `README.md` (项目总览) |
| **system/** | 核心框架与配置 | `config.py` (全局配置), `webhook_server.py` (部署钩子) |
| **characters/** | 角色逻辑与记忆 | `novel_knowledge.py` (LightRAG), `retrieval_engine.py` (混合检索) |
| **game_api/** | 小游戏接口 | 农场/烹饪逻辑，独立路由，SSE 推送 |
| **packages/** | 第三方封装 | `web/` (HTTP 路由), `bridge/` (远程命令) |
| **tools/** | 运维脚本 | `memory_monitor.py` (熔断监控), `optimize_memory.sh` (系统优化) |
| **web-v2/** | 前端应用 | React + TypeScript + Vite + Phaser 4 (2.5D 等轴测) |

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

### 2.2 内存阈值

| 阈值 | 动作 |
|:-----|:-----|
| > 85% | 自动清理临时文件、缓存 |
| > 95% | Telegram 告警 + 服务自愈重启 |

### 2.3 环境变量

| 变量 | 说明 | 示例 |
|:-----|:-----|:-----|
| `TELEGRAM_TOKEN` | Bot Token | `123456:ABC...` |
| `OPENROUTER_API_KEY` | LLM API | `sk-or-...` |
| `GEMINI_API_KEY` | 图像生成 | `AIza...` |
| `MEMORY_SAFE_MODE` | 内存安全模式 | `true` |
| `MAX_CONTEXT_TOKENS` | 上下文限制 | `1024` |

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

- **框架**：React 18 + TypeScript + Vite
- **状态管理**：Zustand
- **游戏引擎**：Phaser 4 (2.5D 等轴测)
- **样式**：Tailwind CSS

### 4.2 游戏功能

- 农场种植/收获/浇水
- 6 地图漫游
- 角色互动/送礼
- 烹饪系统
- 觉醒阶段

---

## 5. 📡 API 路由

| 路径 | 模块 | 说明 |
|:-----|:-----|:-----|
| `/api/farm/*` | `game_api/farm_routes.py` | 农场操作 |
| `/api/character/*` | `game_api/character_routes.py` | 角色互动 |
| `/api/sync/*` | `game_api/sync_routes.py` | SSE 实时推送 |
| `/api/version` | `packages/web/routes.py` | 版本信息 |
| `/api/user/*` | `packages/web/auth_routes.py` | 用户认证 |

---

## 6. ⚠️ 禁止事项

- ❌ 本地运行 Qdrant Server（使用 Qdrant Cloud）
- ❌ 本地加载 LLM 权重（使用 OpenRouter API）
- ❌ 本地运行 Stable Diffusion（使用 Gemini API）
- ❌ 引入 PyTorch/TensorFlow 等重型框架
- ❌ 阻塞 I/O 在异步上下文中

---

*最后更新：2026-05-15 v1.6.5-hotfix*
