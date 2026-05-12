#!/bin/bash
# ============================================================
# NxSiran Bot - Cloudflare Tunnel 一键部署脚本
# v1.4.8.2
#
# 使用方法:
#   chmod +x setup-cloudflare.sh
#   sudo ./setup-cloudflare.sh
#
# 前提条件:
#   1. 已有 Cloudflare 账号
#   2. 已有域名（或使用 trycloudflare.com 免费域名）
# ============================================================

set -e

echo "=========================================="
echo "  NxSiran Bot - Cloudflare Tunnel 部署"
echo "=========================================="

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. 检查 cloudflared 是否安装
echo ""
echo -e "${YELLOW}[1/5] 检查 cloudflared...${NC}"
if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}cloudflared 未安装，正在安装...${NC}"
    # Debian/Ubuntu
    if command -v apt-get &> /dev/null; then
        curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
        dpkg -i /tmp/cloudflared.deb
        rm /tmp/cloudflared.deb
    # CentOS/RHEL
    elif command -v yum &> /dev/null; then
        curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.rpm -o /tmp/cloudflared.rpm
        yum install -y /tmp/cloudflared.rpm
        rm /tmp/cloudflared.rpm
    else
        echo -e "${RED}无法自动安装，请手动安装: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ cloudflared 安装成功${NC}"
else
    echo -e "${GREEN}✅ cloudflared 已安装: $(cloudflared --version)${NC}"
fi

# 2. 登录 Cloudflare
echo ""
echo -e "${YELLOW}[2/5] 登录 Cloudflare...${NC}"
if [ ! -f /root/.cloudflared/cert.pem ]; then
    echo "请在浏览器中完成授权..."
    cloudflared tunnel login
    echo -e "${GREEN}✅ 登录成功${NC}"
else
    echo -e "${GREEN}✅ 已登录${NC}"
fi

# 3. 创建 Tunnel
echo ""
echo -e "${YELLOW}[3/5] 创建 Tunnel...${NC}"
TUNNEL_NAME="nxsiran-bot"

# 检查是否已存在
EXISTING=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" || true)
if [ -n "$EXISTING" ]; then
    echo -e "${GREEN}✅ Tunnel '$TUNNEL_NAME' 已存在${NC}"
    TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}')
else
    cloudflared tunnel create "$TUNNEL_NAME"
    TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}')
    echo -e "${GREEN}✅ Tunnel 创建成功: $TUNNEL_ID${NC}"
fi

# 4. 配置 Tunnel
echo ""
echo -e "${YELLOW}[4/5] 配置 Tunnel...${NC}"
read -p "请输入你的域名 (例如: bot.example.com): " DOMAIN

if [ -z "$DOMAIN" ]; then
    echo -e "${RED}域名不能为空${NC}"
    exit 1
fi

# 生成配置文件
mkdir -p /root/.cloudflared
cat > /root/.cloudflared/config.yml << EOF
tunnel: ${TUNNEL_ID}
credentials-file: /root/.cloudflared/${TUNNEL_ID}.json

loglevel: info
logfile: /var/log/cloudflared.log

ingress:
  # Bot Web 界面 (主服务)
  - hostname: ${DOMAIN}
    service: http://localhost:8080

  # Webhook (GitHub 自动部署)
  - hostname: ${DOMAIN}
    path: /webhook/*
    service: http://localhost:8082

  # Bridge (SOLO 远程命令)
  - hostname: ${DOMAIN}
    path: /bridge/*
    service: http://localhost:8081

  # 兜底
  - service: http_status:404
EOF

echo -e "${GREEN}✅ 配置文件已生成: /root/.cloudflared/config.yml${NC}"

# 5. 创建 DNS 记录并启动服务
echo ""
echo -e "${YELLOW}[5/5] 配置 DNS 并启动服务...${NC}"

# 创建 DNS 路由
cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN"
echo -e "${GREEN}✅ DNS 记录已创建: ${DOMAIN} -> ${TUNNEL_ID}${NC}"

# 安装 systemd 服务
cloudflared service install
echo -e "${GREEN}✅ Cloudflare Tunnel 服务已安装${NC}"

# 启动服务
systemctl start cloudflared
systemctl enable cloudflared
echo -e "${GREEN}✅ Cloudflare Tunnel 已启动${NC}"

# 完成
echo ""
echo "=========================================="
echo -e "${GREEN}  🎉 部署完成！${NC}"
echo "=========================================="
echo ""
echo "  Bot Web:    https://${DOMAIN}"
echo "  Webhook:    https://${DOMAIN}/webhook/github"
echo "  Bridge:     https://${DOMAIN}/bridge/"
echo ""
echo "  请在 GitHub Webhook 设置中更新 URL:"
echo "  https://${DOMAIN}/webhook/github"
echo ""
echo "  查看状态: systemctl status cloudflared"
echo "  查看日志: journalctl -u cloudflared -f"
echo "=========================================="
