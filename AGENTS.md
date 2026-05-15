# 🛡️ NxSiran Bot - AI Agent 宪法 (AGENTS.md)

> **核心指令**：本文件是最高行为准则。所有代码生成、修改和审查必须无条件遵守以下规则。

---

## 🚨 生存红线 (Survival First)

**目标环境**：Google Compute Engine e2-micro (1 vCPU, 1 GB RAM)

- **内存铁律**：工作集必须严格控制在 **512MB RSS** 以内。严禁任何可能导致内存溢出（OOM）的操作。
- **依赖洁癖**：严禁引入未经 `design.md` 批准的重型库（如 PyTorch, TensorFlow, 本地 Qdrant Server）。优先选择 stdlib 或轻量级单用途包。
- **异步强制**：所有网络 I/O 操作必须使用 `async/await`。严禁在异步上下文中使用阻塞 I/O。

---

## 📜 通用行为准则 (General Directives)

- **极简主义 (YAGNI)**：只实现明确需求的功能。严禁过度设计（如 Factory/Strategy 模式），除非显式要求。
- **变更最小化**：每次提交只包含与需求直接相关的变更。不要顺手格式化无关代码或修改注释。
- **绝对导入**：使用 `from system.config import X` 格式。禁止 `from . import` 除非在包内部。
- **配置中心化**：所有配置（路径、Token、阈值）必须写在 `system/config.py` 或环境变量中，严禁硬编码。

---

## 🔄 工作流协议 (Workflow Protocol)

### 1. 任务前检查 (Pre-Task)

1. **复盘记忆（最高优先级）**：**必须先阅读 `memory.md` 的顶部记录**。了解最近的变更历史、已踩过的坑以及用户最新的偏好，严禁重复犯错或违背最近的架构调整。
2. **阅读文档**：阅读 `design.md` (技术蓝图) 和 `PROJECT_CONTEXT.md` (业务背景)，确保不偏离整体架构。
3. **目录侦察**：阅读项目根目录及所有涉及子目录的 `README.md`，理解模块概要和接口定义。
4. **歧义暂停**：如果需求有歧义（>=2种解释），必须停下来列举选项，等待用户决策。

### 2. 任务后检查 (Post-Task)

1. **README 更新**：如果在某个目录创建了新文件，必须更新该目录 `README.md` 的模块表。
2. **语法验证**：使用 `python -m py_compile <file>` 验证语法。
3. **原子提交**：单次任务对应单次提交，使用 Conventional Commits 前缀 (`feat:`, `fix:`, `refactor:`)。
4. **验证方案**：必须提供验证步骤（如 "发送 /test 命令，观察日志"）。
5. **🧠 记忆固化 (Memory Update)**：**每次代码更新完成后，你必须自觉总结本次变更的核心逻辑、架构影响和关键代码片段，并以 Trae 的身份更新到 `memory.md` 的顶部。严禁只改代码不更新记忆。**

---

## 🛠️ 错误处理与回滚

- **回滚机制**：在进行大规模重构前，必须创建 Git Tag 和 Backup 分支，并告知用户回滚命令。
- **冲突处理**：如果用户需求与 `design.md` 架构冲突，必须优先遵守 `design.md` 并提示用户，或者要求用户修改 `design.md` 后再执行。

---

## 📐 代码规范 (Code Standards)

- **导入精度**：禁止 `from xxx import *`，必须显式命名导入符号。
- **根目录不变量**：`bot.py` 是唯一允许在项目根目录的 Python 文件。所有其他模块必须放在职责划分的包内（`characters/`, `system/`, `game_api/`, `database/`, `packages/`, `tools/`）。
- **算法上限**：热路径操作算法复杂度上限 O(n log n)，禁止 O(n²)。
- **进程模型**：单进程、单线程事件循环（python-telegram-bot + aiohttp）。Fork/Thread 仅限于隔离任务。

---

## 🎯 变更控制 (Change Control)

- **变更隔离**：每个提交必须只包含单一需求相关的变更。禁止无关重构、格式化、注释清理。
- **遗留保护**：不要删除、重述、重格式化与当前需求无关的现有注释、日志或逻辑。
- **Diff 可追溯**：每一行新增/修改/删除必须映射到具体需求条款。

---

*最后更新：2026-05-15 v1.6.5-hotfix*
