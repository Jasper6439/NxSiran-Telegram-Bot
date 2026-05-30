# system/

系统级模块 — 全局配置、认证鉴权、提示词/模板、定时调度、邮件发送、Webhook 服务。

## Python 模块

| 模块 | 职责 | 主要导出 |
|------|------|----------|
| `config.py` | 全局配置常量、环境变量、路径定义、版本号 | `BOT_VERSION`, `TELEGRAM_TOKEN`, `init_config` |
| `prompts.py` | 通用提示词模板、AI 文本替换规则、情绪识别数据 | `AI_PATTERN_REPLACEMENTS`, `EMOTION_RESPONSE_GUIDE` |
| `auth.py` | 用户认证, 邮箱注册, session/api token 管理 | `register_user`, `login_user`, `validate_session_token` |
| `scheduler.py` | 后台定时任务调度（纪念日提醒、早安/晚安、主动消息） | `scheduler` |
| `email_sender.py` | Gmail SMTP 邮件发送（验证码等） | `send_email` |
| `database.py` | 异步数据库包装层（ThreadPoolExecutor） | `AsyncGameDatabase`, `run_in_threadpool` |
| `webhook_server.py` | 独立 Webhook + Bridge 服务（GitHub 自动部署 + VM 远程命令执行） | `run_server` |

## 运维脚本

| 文件 | 职责 |
|------|------|
| `auto_restart_watcher.sh` | 进程监控, 异常自动重启 |

## systemd Service 文件

| 文件 | 服务 |
|------|------|
| `nxsiran-bot.service` | Telegram Bot 主进程 |
| `nxsiran-bridge.service` | Bridge 桥接服务 |
| `nxsiran-webhook.service` | Webhook 接收服务 |
| `nxsiran-watcher.service` | 进程监控守护 |
