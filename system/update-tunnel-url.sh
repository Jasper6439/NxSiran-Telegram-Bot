#!/bin/bash
# ============================================================
# Cloudflare 快速隧道 - 自动获取 URL 并更新 Bot 配置
# v1.4.8.2
#
# 用法: 添加到 crontab，每分钟检查一次
#   crontab -e
#   * * * * * /opt/NxSiran/NxSiran-Telegram-Bot/update-tunnel-url.sh
# ============================================================

LOG_FILE="/opt/NxSiran/data/logs/tunnel.log"
CONFIG_FILE="/opt/NxSiran/data/config.json"

mkdir -p "$(dirname "$LOG_FILE")"

# 从日志中提取最新的 trycloudflare.com URL
TUNNEL_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_FILE" 2>/dev/null | tail -1 || true)

if [ -z "$TUNNEL_URL" ]; then
    exit 0
fi

# 读取当前配置的 URL
CURRENT_URL=""
if [ -f "$CONFIG_FILE" ]; then
    CURRENT_URL=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('public_url',''))" 2>/dev/null || true)
fi

# 如果 URL 没变，跳过
if [ "$TUNNEL_URL" = "$CURRENT_URL" ]; then
    exit 0
fi

# 更新配置
python3 -c "
import json
with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)
old = config.get('public_url', '')
config['public_url'] = '$TUNNEL_URL'
with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print(f'URL updated: {old} -> $TUNNEL_URL')
" >> "$LOG_FILE" 2>&1

# 重启 bot 使新 URL 生效
systemctl restart nxsiran-bot.service
echo "[$(date)] Bot restarted with new URL: $TUNNEL_URL" >> "$LOG_FILE"
