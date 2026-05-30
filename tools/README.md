# tools/

运维与开发工具 — 角色生成、版本管理、Bridge 客户端、管理员初始化。

## 模块索引

| 模块 | 职责 | 主要导出 |
|------|------|----------|
| `create_character.py` | 角色模板生成工具，自动创建完整角色目录结构（persona/mutable/exemplars/world/memories） | CLI `--name`/`--source`/`--id` |
| `version_manager.py` | 角色文件版本存档与回滚 | CLI `--action` list/backup/rollback/cleanup |
| `bridge_client.py` | VM 端 Bridge 客户端，轮询 webhook_server 执行命令并回传结果 | `main`（CLI 入口） |
| `init_admin.py` | 管理员账号初始化（密码命令行输入） | `main`（CLI） |
| `memory_monitor.py` | 内存监控脚本 | — |
| `migrate_api_tokens_to_db.py` | API Token 迁移到数据库 | — |
| `reset_and_init.py` | 数据库重置与初始化 | — |

## 配置与脚本

| 文件 | 职责 |
|------|------|
| `nxsiran-bridge-client.service` | systemd service: Bridge 客户端守护进程 |
| `optimize_e2micro.sh` | e2micro 优化脚本（2GB Swap + swappiness） |

## 创建新角色

```bash
python tools/create_character.py --name "新角色" --source "来源作品"
```

自动生成：config.json + persona.md + persona_mutable.md + exemplars.md + memories.md
