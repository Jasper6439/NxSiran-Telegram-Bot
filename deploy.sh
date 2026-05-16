#!/bin/bash
#
# deploy.sh - LoveSupremacy Bot 部署脚本
# ======================================
# 一键部署 Systemd 服务
#
# 使用方法:
#   chmod +x deploy.sh
#   sudo ./deploy.sh
#

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SERVICE_NAME="nx_siran"
PROJECT_DIR="/opt/LoveSupremacy-Telegram-Bot"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  LoveSupremacy Bot 部署脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 sudo 运行${NC}"
    exit 1
fi

# 1. 克隆或更新项目代码
echo -e "${YELLOW}[1/8] 检查项目目录...${NC}"
if [ ! -d "${PROJECT_DIR}" ]; then
    echo -e "${YELLOW}  项目目录不存在，正在克隆...${NC}"
    git clone https://github.com/Jasper6439/NxSiran-Telegram-Bot.git "${PROJECT_DIR}"
    echo -e "${GREEN}  ✓ 项目克隆完成${NC}"
fi

cd "${PROJECT_DIR}"

# 配置 git pull 策略（解决分支分叉问题）
git config pull.rebase false

echo -e "${YELLOW}[2/8] 拉取最新代码...${NC}"
# 丢弃本地更改，强制同步远程
git fetch origin
git reset --hard origin/master

echo -e "${GREEN}  ✓ 代码已同步到最新版本${NC}"

# 3. 复制 service 文件
echo -e "${YELLOW}[3/8] 复制 Systemd 服务文件...${NC}"
cp "${PROJECT_DIR}/nx_siran.service" /etc/systemd/system/
chmod 644 /etc/systemd/system/nx_siran.service
echo -e "${GREEN}  ✓ 已复制到 /etc/systemd/system/${NC}"

# 4. 配置 journal 限制（防止磁盘撑爆）
echo -e "${YELLOW}[4/8] 配置 Journal 日志限制...${NC}"
mkdir -p /etc/systemd/journald.conf.d/
cp "${PROJECT_DIR}/journald.conf" /etc/systemd/journald.conf.d/nx-siran.conf
chmod 644 /etc/systemd/journald.conf.d/nx-siran.conf
echo -e "${GREEN}  ✓ Journal 配置已更新${NC}"

# 5. 安装/更新依赖
echo -e "${YELLOW}[5/8] 安装 Python 依赖...${NC}"
pip install -r "${PROJECT_DIR}/requirements.txt" --break-system-packages -q
echo -e "${GREEN}  ✓ 依赖安装完成${NC}"

# 6. 重载 Systemd
echo -e "${YELLOW}[6/8] 重载 Systemd...${NC}"
systemctl daemon-reload
echo -e "${GREEN}  ✓ daemon-reload 完成${NC}"

# 7. 设置开机自启
echo -e "${YELLOW}[7/8] 设置开机自启...${NC}"
systemctl enable ${SERVICE_NAME}.service
echo -e "${GREEN}  ✓ 开机自启已启用${NC}"

# 8. 启动服务
echo -e "${YELLOW}[8/8] 启动服务...${NC}"
systemctl restart ${SERVICE_NAME}.service
sleep 2

# 检查状态
if [ "$(systemctl is-active ${SERVICE_NAME}.service)" = "active" ]; then
    echo -e "${GREEN}  ✓ 服务启动成功${NC}"
else
    echo -e "${RED}  ✗ 服务启动失败${NC}"
    systemctl status ${SERVICE_NAME}.service --no-pager | head -20
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "服务状态:"
systemctl status ${SERVICE_NAME}.service --no-pager | head -12
echo ""
