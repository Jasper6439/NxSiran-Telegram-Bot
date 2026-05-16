#!/bin/bash
#
# server_setup.sh - 服务器首次设置脚本
# ================================
# 在服务器上执行此脚本完成首次部署
#
# 使用方法:
#   curl -fsSL https://raw.githubusercontent.com/Jasper6439/NxSiran-Telegram-Bot/master/server_setup.sh | sudo bash
#   或下载后执行: sudo ./server_setup.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="/opt/LoveSupremacy-Telegram-Bot"
REPO_URL="https://github.com/Jasper6439/NxSiran-Telegram-Bot.git"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  LoveSupremacy Bot 服务器首次设置${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 sudo 运行${NC}"
    exit 1
fi

# 1. 安装依赖
echo -e "${YELLOW}[1/4] 安装系统依赖...${NC}"
apt-get update -qq
apt-get install -y -qq git python3 python3-pip redis-server
echo -e "${GREEN}  ✓ 系统依赖安装完成${NC}"

# 2. 启动 Redis
echo -e "${YELLOW}[2/4] 启动 Redis...${NC}"
systemctl enable redis-server
systemctl start redis-server
redis-cli ping && echo -e "${GREEN}  ✓ Redis 启动成功${NC}" || echo -e "${YELLOW}  ! Redis 可能未启动${NC}"

# 3. 克隆项目
echo -e "${YELLOW}[3/4] 克隆项目...${NC}"
if [ ! -d "$PROJECT_DIR" ]; then
    mkdir -p /opt
    git clone "$REPO_URL" "$PROJECT_DIR"
    echo -e "${GREEN}  ✓ 项目克隆完成${NC}"
else
    echo -e "${YELLOW}  项目已存在，跳过克隆${NC}"
fi

# 4. 执行部署脚本
echo -e "${YELLOW}[4/4] 执行部署脚本...${NC}"
cd "$PROJECT_DIR"
bash deploy.sh

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  服务器设置完成！${NC}"
echo -e "${GREEN}========================================${NC}"
