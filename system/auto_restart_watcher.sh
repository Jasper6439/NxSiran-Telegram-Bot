#!/bin/bash
# ============================================================
# 宿主机自动重启监控脚本
# 监听容器内的重启请求文件，自动重建并重启 Docker 容器
# 
# v1.4.8 修复: 使用 up -d --build 代替 restart，确保新代码生效
#
# 使用方法:
# 1. 将此脚本放在项目目录
# 2. 添加执行权限: chmod +x auto_restart_watcher.sh
# 3. 在后台运行: nohup ./auto_restart_watcher.sh &
# 或创建 systemd 服务（见 nxsiran-watcher.service）
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$PROJECT_DIR/data"
RESTART_FLAG="$DATA_DIR/.needs_restart"
LOG_FILE="$DATA_DIR/logs/restart_watcher.log"

# 确保日志目录存在
mkdir -p "$(dirname "$LOG_FILE")"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== 自动重启监控启动 ==="
log "项目目录: $PROJECT_DIR"
log "监控文件: $RESTART_FLAG"

# 主循环
while true; do
    if [ -f "$RESTART_FLAG" ]; then
        log "检测到重启请求文件，开始重建容器..."
        
        # 读取请求时间
        REQUEST_TIME=$(cat "$RESTART_FLAG")
        log "请求时间: $REQUEST_TIME"
        
        # 删除标记文件（先删，防止重复触发）
        rm -f "$RESTART_FLAG"
        
        # 执行重建并重启
        cd "$PROJECT_DIR"
        log "执行: docker compose up -d --build"
        docker compose up -d --build 2>&1 | tee -a "$LOG_FILE"
        
        if [ $? -eq 0 ]; then
            log "✅ 容器重建并重启成功"
        else
            log "❌ 容器重建失败，尝试 restart..."
            docker compose restart 2>&1 | tee -a "$LOG_FILE"
            if [ $? -eq 0 ]; then
                log "✅ 容器 restart 成功（未重建）"
            else
                log "❌ 容器 restart 也失败了"
            fi
        fi
    fi
    
    # 每5秒检查一次
    sleep 5
done
