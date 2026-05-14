# system/

系统级模块 — 全局配置、认证鉴权、提示词/模板、定时调度、邮件发送、Webhook 服务、运维部署脚本。

## Python 模块

| 模块 | 职责 | 主要导出 |
|------|------|----------|
| `__init__.py` | 包标识 | — |
| `config.py` | 全局配置常量、环境变量、路径定义、版本号 | `BOT_VERSION`, `TELEGRAM_TOKEN`, `init_config`, `load_config` |
| `prompts.py` | 系统提示词、AI 文本替换规则、自拍/场景/表情包模板、情绪识别数据、亲密度等级、生活事件、记忆分类、文本处理函数 | `SYSTEM_PROMPT`, `AI_PATTERN_REPLACEMENTS`, `SELFIE_PROMPTS`, `detect_sticker_mood`, `analyze_dialogue_patterns` |
| `auth.py` | 用户认证, 邮箱注册, session/api token 管理, 角色绑定 Telegram Chat ID | `register_user`, `login_user`, `validate_session_token`, `validate_api_token`, `hash_password` |
| `scheduler.py` | 后台定时任务调度（纪念日提醒、早安/晚安、主动消息） | `scheduler` |
| `email_sender.py` | Gmail SMTP 邮件发送（验证码等） | `send_email`, `get_smtp_config` |
| `webhook_server.py` | 独立 Webhook + Bridge 服务（GitHub 自动部署 + VM 远程命令执行） | `run_server` |

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

- `config.py` → 环境变量, `.env` 文件
- `prompts.py` → `config.py`, `characters.*`（延迟 import）
- `auth.py` → `config.py`（USERS_FILE, load_config）
- `scheduler.py` → `config.py`, `prompts.py`, `characters.*`
- `email_sender.py` → `config.py`, `smtplib`
- `webhook_server.py` → `config.py`（BOT_VERSION）
