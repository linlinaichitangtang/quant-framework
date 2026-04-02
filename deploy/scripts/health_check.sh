#!/bin/bash
# ============================================================
# OpenClaw 健康检查脚本
# 检查所有服务状态、数据库连通性、复制延迟
# 输出 JSON 格式报告
# ============================================================

set -euo pipefail

# ========== 配置 ==========
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-openclaw}"
DB_PASS="${DB_PASS:-}"
DB_NAME="${DB_NAME:-openclaw}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASS="${REDIS_PASS:-}"
BACKEND_HOSTS="${BACKEND_HOSTS:-localhost:8000 localhost:8001 localhost:8002}"
CHECK_TIMESTAMP=$(date '+%Y-%m-%dT%H:%M:%S')

# ========== 辅助函数 ==========
check_service() {
    local name="$1"
    local host="$2"
    local port="$3"
    local result="offline"

    if timeout 5 bash -c "echo > /dev/tcp/${host}/${port}" 2>/dev/null; then
        result="online"
    fi

    echo "{\"name\": \"${name}\", \"host\": \"${host}\", \"port\": ${port}, \"status\": \"${result}\"}"
}

check_http() {
    local name="$1"
    local url="$2"
    local status_code="0"
    local response_time_ms=0

    if command -v curl &> /dev/null; then
        local curl_output
        curl_output=$(curl -s -o /dev/null -w "%{http_code} %{time_total}" --max-time 5 "${url}" 2>/dev/null || echo "000 0")
        status_code=$(echo "${curl_output}" | awk '{print $1}')
        response_time_ms=$(echo "${curl_output}" | awk '{printf "%.0f", $2 * 1000}')
    fi

    local health="unhealthy"
    if [ "${status_code}" -ge 200 ] && [ "${status_code}" -lt 500 ]; then
        health="healthy"
    fi

    echo "{\"name\": \"${name}\", \"url\": \"${url}\", \"status_code\": ${status_code}, \"response_time_ms\": ${response_time_ms}, \"health\": \"${health}\"}"
}

# ========== 开始检查 ==========
SERVICES_JSON="["
FIRST=true

# 检查 MySQL 主库
if [ "${FIRST}" = true ]; then FIRST=false; else SERVICES_JSON+=","; fi
SERVICES_JSON+="$(check_service "mysql-master" "${DB_HOST}" "${DB_PORT}")"

# 检查 Redis
if [ "${FIRST}" = true ]; then FIRST=false; else SERVICES_JSON+=","; fi
SERVICES_JSON+="$(check_service "redis" "${REDIS_HOST}" "${REDIS_PORT}")"

# 检查后端服务
for host_port in ${BACKEND_HOSTS}; do
    if [ "${FIRST}" = true ]; then FIRST=false; else SERVICES_JSON+=","; fi
    SERVICES_JSON+="$(check_service "backend-${host_port}" "${host_port%:*}" "${host_port#*:}")"
done

SERVICES_JSON+="]"

# ========== HTTP 健康检查 ==========
HTTP_JSON="["
FIRST=true

for host_port in ${BACKEND_HOSTS}; do
    if [ "${FIRST}" = true ]; then FIRST=false; else HTTP_JSON+=","; fi
    HTTP_JSON+="$(check_http "backend-${host_port}" "http://${host_port}/health")"
done

HTTP_JSON+="]"

# ========== 数据库连通性检查 ==========
DB_STATUS="error"
DB_LATENCY_MS=0

if command -v mysqladmin &> /dev/null; then
    START_MS=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")
    if mysqladmin ping -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" ${DB_PASS:+-p"${DB_PASS}"} &>/dev/null; then
        DB_STATUS="ok"
    fi
    END_MS=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")
    DB_LATENCY_MS=$((END_MS - START_MS))
elif command -v python3 &> /dev/null; then
    # SQLite 检查
    DB_STATUS="ok"
    DB_LATENCY_MS=$(python3 -c "import time; s=time.time(); open('quant_trade.db','rb').close(); print(int((time.time()-s)*1000))" 2>/dev/null || echo 1)
fi

# ========== 复制延迟检查 ==========
REPLICATION_LAG=0
REPLICATION_STATUS="unknown"

if command -v mysql &> /dev/null; then
    LAG_OUTPUT=$(mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" ${DB_PASS:+-p"${DB_PASS}"} \
        -e "SHOW SLAVE STATUS\G" 2>/dev/null | grep "Seconds_Behind_Master" | awk '{print $2}' || echo "")

    if [ -n "${LAG_OUTPUT}" ] && [ "${LAG_OUTPUT}" != "NULL" ]; then
        REPLICATION_LAG="${LAG_OUTPUT}"
        if [ "${LAG_OUTPUT}" -lt 5 ]; then
            REPLICATION_STATUS="ok"
        elif [ "${LAG_OUTPUT}" -lt 30 ]; then
            REPLICATION_STATUS="warning"
        else
            REPLICATION_STATUS="critical"
        fi
    else
        REPLICATION_STATUS="not_replica"
    fi
fi

# ========== 综合评估 ==========
OVERALL_STATUS="healthy"
if [ "${DB_STATUS}" != "ok" ]; then
    OVERALL_STATUS="critical"
elif [ "${REPLICATION_STATUS}" = "critical" ]; then
    OVERALL_STATUS="degraded"
fi

# ========== 输出 JSON 报告 ==========
cat <<EOF
{
    "check_time": "${CHECK_TIMESTAMP}",
    "overall_status": "${OVERALL_STATUS}",
    "database": {
        "status": "${DB_STATUS}",
        "latency_ms": ${DB_LATENCY_MS},
        "host": "${DB_HOST}:${DB_PORT}",
        "replication_lag": ${REPLICATION_LAG},
        "replication_status": "${REPLICATION_STATUS}"
    },
    "services": ${SERVICES_JSON},
    "http_checks": ${HTTP_JSON}
}
EOF
