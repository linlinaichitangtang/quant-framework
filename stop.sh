#!/bin/bash

# OpenClaw 一键停止脚本
# 功能：停止所有服务（保留数据）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  OpenClaw 量化交易框架 - 停止服务"
echo "=========================================="
echo ""

docker-compose stop

echo ""
echo -e "${GREEN}服务已停止，数据已保留${NC}"
echo "下次启动: ./start.sh"