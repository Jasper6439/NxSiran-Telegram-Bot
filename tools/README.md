# tools/

运维与开发工具 — Bridge 客户端、角色生成、版本管理、管理员初始化。

## 模块索引

| 模块 | 职责 | 主要导出 |
|------|------|----------|
| `bridge_client.py` | VM 端 Bridge 客户端, 轮询 webhook_server 执行命令并回传结果 | `main`（CLI 入口） |
| `create_character.py` | 角色模板生成工具, 从模板创建新角色目录结构 | `main`（CLI, `--name`/`--source`/`--id`） |
| `version_manager.py` | 角色文件版本存档与回滚, 适配蒸馏标准 | `main`（CLI, `--action` list/backup/rollback/cleanup） |
| `init_admin.py` | 管理员账号初始化（密码命令行输入） | `main`（CLI） |

## 配置与脚本

| 文件 | 职责 |
|------|------|
| `nxsiran-bridge-client.service` | systemd service: Bridge 客户端守护进程 |
| `optimize_e2micro.sh` | e2micro 优化脚本 |

## `_archive/`

已归档的旧版工具（bot_instance.py, bot_manager.py, bots_config.json），不再维护。
