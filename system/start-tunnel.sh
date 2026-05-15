#!/bin/bash
# ============================================================
# Cloudflare 快速隧道 + 自动更新 Bot URL
# v1.4.8.2
#
# 每次重启自动获取新的 trycloudflare.com 地址
# 并更新 bot 的 public_url 配置
#
# 使用方法:
#   chmod +x start-tunnel.sh
#   ./start-tunnel.sh
# ============================================================

set -e

PROJECT_DIR="/opt/NxSiran/NxSiran-Telegram-Bot"
CONFIG_FILE="/opt/NxSiran/data/config.json"
LOG_FILE="/opt/NxSiran/data/logs/tunnel.log"

mkdir -p "$(dirname "$LOG_FILE")"

echo "[$(date)] 启动 Cloudflare 快速隧道..." | tee -a "$LOG_FILE"

# 启动 cloudflared 并捕获 URL
TUNNEL_OUTPUT=$(cloudflared tunnel --url http://localhost:8080 2>&1 &)
TUNNEL_PID=$!

# 等待 URL 出现（最多30秒)
URL=""
for i in $(seq 1 30); do
    sleep 1
    # 从日志中提取 URL
    URL=$(curl -s http://localhost:8080 2>/dev/null && echo "" || true)
    # 尝试从 cloudflared 进程输出获取
    if [ -z "$URL" ]; then
        # cloudflared 输出格式: https://xxx-xxx-xxx.trycloudflare.com
        TUNNEL_URL=$(cat /proc/$TUNNEL_PID/fd/2 2>/dev/null | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || true)
        if [ -n "$TUNNEL_URL" ]; then
            URL="$TUNNEL_URL"
        fi
    fi
    if [ -n "$URL" ]; then
        break
    fi
done

# 更可靠的方式：用 timeout 运行 cloudflared 并捕获输出
kill $TUNNEL_PID 2>/dev/null || true
wait $TUNNEL_PID 2>/dev/null || true

# 重新启动并捕获 URL
TUNNEL_URL=$(timeout 15 cloudflared tunnel --url http://localhost:8080 2>&1 | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1 || true)

if [ -z "$TUNNEL_URL" ]; then
    echo "[$(date)] ❌ 无法获取隧道URL" | tee -a "$LOG_FILE"
    exit 1
fi

echo "[$(date)] 隧道地址: $TUNNEL_URL" | tee -a "$LOG_FILE"

# 更新 bot 的 public_url
if [ -f "$CONFIG_FILE" ]; then
    # 使用 python 更新 JSON
    python3 -c "
import json
with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)
config['public_url'] = '$TUNNEL_URL'
with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print('public_url 已更新')
"
else
    echo "[$(date)] ⚠️ config.json 不存在: $CONFIG_FILE" | tee -a "$LOG_FILE"
fi

# 后台启动隧道（保持运行）
nohup cloudflared tunnel --url http://localhost:8080 >> "$LOG_FILE" 2>&1 &
echo $! > /opt/NxSiran/data/tunnel.pid
echo "[$(date)] 隧道已在后台运行 (PID: $(cat /opt/NxSiran/data/tunnel.pid))" | tee -a "$LOG_FILE"

# 重启 bot 使新 URL 生效
systemctl restart nxsiran-bot.service
echo "[$(date)] Bot 已重启" | tee -a "$LOG_FILE"

echo ""
echo "=========================================="
echo "  ✅ 隧道已启动"
echo "  URL: $TUNNEL_URL"
echo "=========================================="
