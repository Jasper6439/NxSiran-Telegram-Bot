#!/bin/bash
# LoveSupremacy e2-micro 内存优化脚本
# 在 GCP VM 上以 root 或 sudo 执行

set -e

echo "========================================="
echo "  LoveSupremacy e2-micro 内存优化"
echo "========================================="

# 1. 检查当前内存状态
echo ""
echo "【当前内存状态】"
free -m
echo ""

# 2. 创建 2GB swap 文件
if [ -f /swapfile ]; then
    echo "【跳过】/swapfile 已存在"
    SWAP_SIZE=$(du -m /swapfile | cut -f1)
    echo "  当前 swap 大小: ${SWAP_SIZE}MB"
else
    echo "【创建 2GB swap 文件】"
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo "  ✅ swap 文件创建成功"
fi

# 3. 持久化 swap
if grep -q '/swapfile' /etc/fstab; then
    echo "【跳过】swap 已在 fstab 中"
else
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "  ✅ swap 持久化到 fstab"
fi

# 4. 设置 swappiness
echo "【设置 swappiness = 60】"
sysctl vm.swappiness=60
if grep -q 'vm.swappiness' /etc/sysctl.conf; then
    sed -i 's/vm.swappiness=.*/vm.swappiness=60/' /etc/sysctl.conf
else
    echo 'vm.swappiness=60' >> /etc/sysctl.conf
fi
echo "  ✅ swappiness 已设置"

# 5. 优化 systemd 服务内存控制
echo ""
echo "【配置 systemd 内存控制】"

# Bot 主进程：优先物理内存
BOT_SERVICE="nxsiran-bot.service"
if [ -f "/etc/systemd/system/${BOT_SERVICE}" ]; then
    echo "  配置 ${BOT_SERVICE}..."
    # 检查是否已有 MemoryMin
    if ! grep -q 'MemoryMin' /etc/systemd/system/${BOT_SERVICE}; then
        # 在 [Service] 段后添加内存控制
        sed -i '/^\[Service\]/a MemoryMin=100M\nMemoryLow=200M' /etc/systemd/system/${BOT_SERVICE}
        echo "    ✅ 添加 MemoryMin=100M, MemoryLow=200M"
    else
        echo "    ⏭️ 已有内存配置"
    fi
    systemctl daemon-reload
else
    echo "  ⚠️ 未找到 ${BOT_SERVICE}，跳过"
    echo "    请手动确认服务文件名："
    echo "    ls /etc/systemd/system/*.service"
fi

# Qdrant（已弃用，如仍运行则配置）
QDRANT_SERVICE="qdrant.service"
if [ -f "/etc/systemd/system/${QDRANT_SERVICE}" ]; then
    echo "  配置 ${QDRANT_SERVICE}..."
    if ! grep -q 'MemoryMax' /etc/systemd/system/${QDRANT_SERVICE}; then
        sed -i '/^\[Service\]/a MemoryMax=300M\nMemorySwapMax=500M' /etc/systemd/system/${QDRANT_SERVICE}
        echo "    已添加 MemoryMax=300M, MemorySwapMax=500M"
    else
        echo "    已有内存配置"
    fi
    systemctl daemon-reload
else
    echo "  未找到 ${QDRANT_SERVICE}（已弃用，改用 LightRAG 本地存储）"
    echo "    如果用 Docker，可以配置 docker-compose.yml："
    echo "    deploy:"
    echo "      resources:"
    echo "        limits:"
    echo "          memory: 300M"
fi

# 6. 最终状态
echo ""
echo "========================================="
echo "  优化完成！"
echo "========================================="
echo ""
echo "【优化后内存状态】"
free -m
echo ""
echo "【swap 状态】"
swapon --show
echo ""
echo "【swappiness】"
cat /proc/sys/vm/swappiness
echo ""
echo "如需重启服务使配置生效："
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl restart nxsiran-bot"
