# system/

系统级模块 — 认证鉴权、定时调度、邮件发送、运维部署脚本。

## Python 模块

| 模块 | 职责 | 主要导出 |
|------|------|----------|
| `__init__.py` | 包标识 | — |
| `auth.py` | 用户认证, 邮箱注册, session/api token 管理, 角色绑定 Telegram Chat ID | `register_user`, `login_user`, `validate_session_token`, `validate_api_token`, `hash_password` |
| `scheduler.py` | 后台定时任务调度（纪念日提醒、早安/晚安、主动消息） | `scheduler` |
| `email_sender.py` | Gmail SMTP 邮件发送（验证码等） | `send_email`, `get_smtp_config` |

## 运维脚本

| 文件 | 职责 |
|------|------|
| `auto_restart_watcher.sh` | 进程监控, 异常自动重启 |
| `start-tunnel.sh` | Cloudflare Tunnel 启动 |
| `update-tunnel-url.sh` | Tunnel URL 动态更新 |

## systemd Service 文件

| 文件 | 服务 |
|------|------|
| `nxsiran-bot.service` | Telegram Bot 主进程 |
| `nxsiran-bridge.service` | Bridge 桥接服务 |
| `nxsiran-webhook.service` | Webhook 接收服务 |
| `nxsiran-watcher.service` | 进程监控守护 |
| `cloudflared-quick.service` | Cloudflare Tunnel |

## 依赖关系

- `auth.py` → `config.py`（USERS_FILE, load_config）
- `scheduler.py` → `config.py`, `characters.*`
- `email_sender.py` → `smtplib`, Gmail SMTP
