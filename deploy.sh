#!/bin/bash
#
# deploy.sh - LoveSupremacy Bot 部署脚本 v1.9.2.1
# ======================================
# 一键部署 Systemd 服务（幂等 + 原子操作 + 回滚保护）
#
# 使用方法:
#   chmod +x deploy.sh
#   sudo ./deploy.sh
#

set -euo pipefail

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SERVICE_NAME="nx_siran"
PROJECT_DIR="/opt/LoveSupremacy-Telegram-Bot"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  LoveSupremacy Bot 部署脚本 v1.9.2.1${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 sudo 运行${NC}"
    exit 1
fi

# ============================================================
# 环境检查
# ============================================================

echo -e "${YELLOW}[0/9] 环境检查...${NC}"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}  ✗ python3 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ python3 $(python3 --version | awk '{print $2}')${NC}"

# 检查 pip
if ! command -v pip &> /dev/null; then
    echo -e "${RED}  ✗ pip 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ pip $(pip --version | awk '{print $2}')${NC}"

# 检查 systemd
if ! command -v systemctl &> /dev/null; then
    echo -e "${RED}  ✗ systemctl 不可用（非 systemd 环境）${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ systemd 可用${NC}"

# 检查 git
if ! command -v git &> /dev/null; then
    echo -e "${RED}  ✗ git 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ git $(git --version | awk '{print $3}')${NC}"

# ============================================================
# 1. 克隆或更新项目代码
# ============================================================

echo -e "${YELLOW}[1/9] 检查项目目录...${NC}"
if [ ! -d "${PROJECT_DIR}" ]; then
    echo -e "${YELLOW}  项目目录不存在，正在克隆...${NC}"
    mkdir -p "$(dirname "${PROJECT_DIR}")"
    if ! git clone https://github.com/Jasper6439/LoveSupremacy_Universe.git "${PROJECT_DIR}"; then
        echo -e "${RED}  ✗ git clone 失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ 项目克隆完成${NC}"
fi

cd "${PROJECT_DIR}"

# ============================================================
# 2. Git 原子操作
# ============================================================

echo -e "${YELLOW}[2/9] 拉取最新代码（原子操作）...${NC}"

# 记录当前版本（用于回滚）
PREV_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "none")
echo -e "${GREEN}  当前版本: ${PREV_COMMIT}${NC}"

# 原子操作: fetch + reset --hard
if ! git fetch origin; then
    echo -e "${RED}  ✗ git fetch 失败${NC}"
    exit 1
fi

NEW_COMMIT=$(git rev-parse --short origin/master 2>/dev/null || echo "none")

if [ "${PREV_COMMIT}" = "${NEW_COMMIT}" ]; then
    echo -e "${GREEN}  ✓ 已是最新版本 (${PREV_COMMIT})${NC}"
else
    if ! git reset --hard origin/master; then
        echo -e "${RED}  ✗ git reset 失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ 代码已更新: ${PREV_COMMIT} -> ${NEW_COMMIT}${NC}"
fi

# ============================================================
# 3. 复制 service 文件
# ============================================================

echo -e "${YELLOW}[3/9] 复制 Systemd 服务文件...${NC}"
if [ -f "${PROJECT_DIR}/nx_siran.service" ]; then
    cp "${PROJECT_DIR}/nx_siran.service" /etc/systemd/system/
    chmod 644 /etc/systemd/system/nx_siran.service
    echo -e "${GREEN}  ✓ nx_siran.service 已复制${NC}"
else
    echo -e "${YELLOW}  ⚠ nx_siran.service 不存在，跳过${NC}"
fi

# Webhook 服务
if [ -f "${PROJECT_DIR}/system/nxsiran-webhook.service" ]; then
    cp "${PROJECT_DIR}/system/nxsiran-webhook.service" /etc/systemd/system/
    chmod 644 /etc/systemd/system/nxsiran-webhook.service
    echo -e "${GREEN}  ✓ nxsiran-webhook.service 已复制${NC}"
fi

# ============================================================
# 4. 配置 Journal 日志限制
# ============================================================

echo -e "${YELLOW}[4/9] 配置 Journal 日志限制...${NC}"
if [ -f "${PROJECT_DIR}/journald.conf" ]; then
    mkdir -p /etc/systemd/journald.conf.d/
    cp "${PROJECT_DIR}/journald.conf" /etc/systemd/journald.conf.d/nx-siran.conf
    chmod 644 /etc/systemd/journald.conf.d/nx-siran.conf
    echo -e "${GREEN}  ✓ Journal 配置已更新${NC}"
else
    echo -e "${YELLOW}  ⚠ journald.conf 不存在，跳过${NC}"
fi

# ============================================================
# 5. 安装/更新依赖
# ============================================================

echo -e "${YELLOW}[5/9] 安装 Python 依赖...${NC}"
if ! pip install -r "${PROJECT_DIR}/requirements.txt" --break-system-packages -q; then
    echo -e "${RED}  ✗ 依赖安装失败，尝试回滚代码...${NC}"
    if [ "${PREV_COMMIT}" != "none" ]; then
        git reset --hard "${PREV_COMMIT}" 2>/dev/null || true
    fi
    exit 1
fi
echo -e "${GREEN}  ✓ 依赖安装完成${NC}"

# ============================================================
# 6. 重载 Systemd
# ============================================================

echo -e "${YELLOW}[6/9] 重载 Systemd...${NC}"
systemctl daemon-reload
echo -e "${GREEN}  ✓ daemon-reload 完成${NC}"

# ============================================================
# 7. 设置开机自启
# ============================================================

echo -e "${YELLOW}[7/9] 设置开机自启...${NC}"
systemctl enable ${SERVICE_NAME}.service 2>/dev/null || true
echo -e "${GREEN}  ✓ 开机自启已启用${NC}"

# ============================================================
# 8. 启动服务（带验证）
# ============================================================

echo -e "${YELLOW}[8/9] 启动服务...${NC}"

# 记录旧进程是否在运行
WAS_RUNNING=false
if [ "$(systemctl is-active ${SERVICE_NAME}.service 2>/dev/null)" = "active" ]; then
    WAS_RUNNING=true
fi

systemctl restart ${SERVICE_NAME}.service
sleep 3

# 验证服务状态
if [ "$(systemctl is-active ${SERVICE_NAME}.service)" = "active" ]; then
    echo -e "${GREEN}  ✓ 服务启动成功${NC}"
else
    echo -e "${RED}  ✗ 服务启动失败${NC}"
    systemctl status ${SERVICE_NAME}.service --no-pager | head -20

    # 尝试回滚代码
    if [ "${PREV_COMMIT}" != "none" ] && [ "${PREV_COMMIT}" != "${NEW_COMMIT}" ]; then
        echo -e "${YELLOW}  尝试回滚代码到 ${PREV_COMMIT}...${NC}"
        git reset --hard "${PREV_COMMIT}" 2>/dev/null || true
        systemctl restart ${SERVICE_NAME}.service
        sleep 3
        if [ "$(systemctl is-active ${SERVICE_NAME}.service)" = "active" ]; then
            echo -e "${GREEN}  ✓ 回滚成功，服务已恢复${NC}"
        else
            echo -e "${RED}  ✗ 回滚后服务仍无法启动${NC}"
        fi
    fi
    exit 1
fi

# ============================================================
# 9. 验证部署
# ============================================================

echo -e "${YELLOW}[9/9] 验证部署...${NC}"

# 检查 Web 端口
sleep 2
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>/dev/null | grep -q "200"; then
    echo -e "${GREEN}  ✓ Web 服务正常 (HTTP 200)${NC}"
else
    echo -e "${YELLOW}  ⚠ Web 服务未响应（可能需要更多启动时间）${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "服务状态:"
systemctl status ${SERVICE_NAME}.service --no-pager | head -12
echo ""
