#!/bin/bash

# OpenClaw 重置环境脚本
# 功能：停止服务 -> 删除数据 -> 重新启动

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  OpenClaw 量化交易框架 - 重置环境"
echo "=========================================="
echo ""

read -p "此操作将删除所有数据（包括数据库和日志），是否继续？ (y/N): " confirm

if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "停止服务 ... "
docker-compose down

echo ""
echo "删除数据卷（数据库和日志）... "
docker volume rm quant-framework_mysql_data 2>/dev/null || true
rm -rf ./logs/* 2>/dev/null || true

echo ""
echo -e "${GREEN}数据已清除${NC}"
echo ""
echo "正在重新启动 ... "
./start.sh