#!/bin/bash
set -e

# OpenClaw 一键启动脚本
# 功能：检测环境 -> 启动所有服务 -> 等待健康 -> 显示访问地址

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  OpenClaw 量化交易框架 - 一键启动"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Docker 是否安装
check_docker() {
    echo -n "检查 Docker ... "
    if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
        echo -e "${GREEN}已安装${NC}"
        docker --version
        docker-compose --version
        return 0
    else
        echo -e "${RED}未安装${NC}"
        echo -e "${YELLOW}请先安装 Docker 和 docker-compose${NC}"
        echo "  macOS: https://docs.docker.com/docker-for-mac/install/"
        echo "  Ubuntu: sudo apt install docker.io docker-compose"
        exit 1
    fi
}

# 检查端口占用
check_ports() {
    echo ""
    echo "检查端口占用 ... "
    PORTS=(3306 8000 80)
    for PORT in "${PORTS[@]}"; do
        if lsof -i:$PORT &> /dev/null || netstat -an | grep -q ":$PORT " ; then
            echo -e "  端口 $PORT: ${YELLOW}已被占用${NC}"
            lsof -i:$PORT 2>/dev/null || echo "    (可能是其他进程)"
        else
            echo -e "  端口 $PORT: ${GREEN}可用${NC}"
        fi
    done
}

# 初始化环境变量文件
init_env() {
    echo ""
    echo "初始化环境配置 ... "
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            echo -e "  ${GREEN}已创建 .env 文件${NC}"
            echo -e "  ${YELLOW}请编辑 .env 配置您的 API Key${NC}"
        else
            cat > .env << 'EOF'
# 数据库配置
MYSQL_ROOT_PASSWORD=quant123456
MYSQL_DATABASE=quant_trade
MYSQL_USER=quant
MYSQL_PASSWORD=quant123456

# 调试模式
DEBUG=false

# 数据源 Token（可选）
AK_SHARE_TOKEN=
TUSHARE_TOKEN=

# FMZ 发明者量化 API（可选）
FMZ_API_KEY=
FMZ_SECRET_KEY=
FMZ_CID=0

# CORS 配置
CORS_ORIGIN=http://localhost
EOF
            echo -e "  ${GREEN}已创建 .env 文件（使用默认配置）${NC}"
        fi
    else
        echo -e "  .env 文件已存在，跳过"
    fi
}

# 启动服务
start_services() {
    echo ""
    echo "启动服务 ... "
    docker-compose up -d --build
    echo -e "  ${GREEN}服务已在后台启动${NC}"
}

# 等待服务健康
wait_for_health() {
    echo ""
    echo "等待服务健康检查 ... "
    echo "(这可能需要 1-2 分钟)"

    local max_wait=180
    local waited=0
    local interval=5

    while [ $waited -lt $max_wait ]; do
        # 检查后端健康
        if curl -sf http://localhost:8000/health &> /dev/null; then
            echo -e "  后端 API: ${GREEN}健康${NC}"
            break
        fi
        echo -ne "  等待后端启动 ... ${waited}s/${max_wait}s\r"
        sleep $interval
        waited=$((waited + interval))
    done

    if [ $waited -ge $max_wait ]; then
        echo -e "\n  ${RED}后端启动超时，请检查日志: docker-compose logs backend${NC}"
        exit 1
    fi

    # 检查前端
    if curl -sf http://localhost:80 &> /dev/null; then
        echo -e "  前端界面: ${GREEN}就绪${NC}"
    fi

    # 检查数据库
    if docker-compose exec -T db mysqladmin ping -h localhost -u root -p${MYSQL_ROOT_PASSWORD:-quant123456} &> /dev/null; then
        echo -e "  数据库: ${GREEN}连接正常${NC}"
    fi
}

# 显示访问信息
show_access_info() {
    echo ""
    echo "=========================================="
    echo -e "${GREEN}  启动成功！${NC}"
    echo "=========================================="
    echo ""
    echo "  访问地址："
    echo -e "    前端界面: ${GREEN}http://localhost${NC}"
    echo -e "    API 文档: ${GREEN}http://localhost:8000/docs${NC}"
    echo -e "    API 健康: ${GREEN}http://localhost:8000/health${NC}"
    echo ""
    echo "  快捷命令："
    echo "    查看日志: docker-compose logs -f"
    echo "    停止服务: ./stop.sh"
    echo "    重置环境: ./reset.sh"
    echo ""
    echo -e "${YELLOW}  首次使用请先阅读 QUICKSTART.md${NC}"
    echo "=========================================="
}

# 主流程
main() {
    check_docker
    check_ports
    init_env
    start_services
    wait_for_health
    show_access_info
}

main "$@"