#!/bin/bash
# ============================================================
# OpenClaw 数据库自动备份脚本
# 支持全量/增量备份、自动压缩、保留策略、备份验证
# ============================================================

set -euo pipefail

# ========== 配置 ==========
BACKUP_DIR="${BACKUP_DIR:-/var/backups/openclaw}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
LOG_FILE="${LOG_FILE:-/var/log/openclaw/backup.log}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-openclaw}"
DB_PASS="${DB_PASS:-}"
DB_NAME="${DB_NAME:-openclaw}"
COMPRESS="${COMPRESS:-true}"
VERIFY="${VERIFY:-true}"

# ========== 初始化 ==========
mkdir -p "${BACKUP_DIR}"
mkdir -p "$(dirname "${LOG_FILE}")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

error_exit() {
    log "ERROR: $*"
    exit 1
}

# ========== 参数解析 ==========
BACKUP_TYPE="full"
while [[ $# -gt 0 ]]; do
    case $1 in
        --full)       BACKUP_TYPE="full" ;;
        --incremental) BACKUP_TYPE="incremental" ;;
        --dir)        BACKUP_DIR="$2"; shift ;;
        --retention)  RETENTION_DAYS="$2"; shift ;;
        *)            echo "用法: $0 [--full|--incremental] [--dir <目录>] [--retention <天数>]"; exit 1 ;;
    esac
    shift
done

log "========== 开始${BACKUP_TYPE}备份 =========="
log "备份目录: ${BACKUP_DIR}"
log "数据库: ${DB_HOST}:${DB_PORT}/${DB_NAME}"

# ========== 执行备份 ==========
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${BACKUP_TYPE}_${TIMESTAMP}.sql"

if [ "${BACKUP_TYPE}" = "full" ]; then
    log "执行全量备份..."
    START_TIME=$(date +%s)

    if command -v mysqldump &> /dev/null; then
        # MySQL 全量备份
        mysqldump \
            -h "${DB_HOST}" -P "${DB_PORT}" \
            -u "${DB_USER}" \
            ${DB_PASS:+-p"${DB_PASS}"} \
            --single-transaction \
            --routines \
            --triggers \
            --events \
            --set-gtid-purged=OFF \
            "${DB_NAME}" > "${BACKUP_FILE}" 2>> "${LOG_FILE}" || error_exit "mysqldump 执行失败"
    else
        # SQLite 备份（简单复制）
        DB_PATH="${DATABASE_URL:-sqlite:///./quant_trade.db}"
        DB_PATH="${DB_PATH#sqlite:///}"
        if [ -f "${DB_PATH}" ]; then
            cp "${DB_PATH}" "${BACKUP_FILE}"
        else
            error_exit "数据库文件不存在: ${DB_PATH}"
        fi
    fi
else
    log "执行增量备份..."
    START_TIME=$(date +%s)

    # 增量备份：使用 mysqlbinlog 或 xtrabackup
    if command -v mysqlbinlog &> /dev/null; then
        # MySQL 增量备份（基于 binlog）
        BINLOG_DIR="${BACKUP_DIR}/binlog"
        mkdir -p "${BINLOG_DIR}"
        mysqlbinlog \
            -h "${DB_HOST}" -P "${DB_PORT}" \
            -u "${DB_USER}" \
            ${DB_PASS:+-p"${DB_PASS}"} \
            --read-from-remote-server \
            --raw \
            --stop-never \
            "${BINLOG_DIR}" 2>> "${LOG_FILE}" || log "WARNING: mysqlbinlog 执行失败，回退到全量备份"

        # 如果增量失败，回退到全量
        if [ $? -ne 0 ]; then
            log "增量备份失败，回退到全量备份"
            BACKUP_TYPE="full"
            mysqldump -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" ${DB_PASS:+-p"${DB_PASS}"} --single-transaction "${DB_NAME}" > "${BACKUP_FILE}" 2>> "${LOG_FILE}"
        fi
    else
        log "不支持增量备份，回退到全量备份"
        BACKUP_TYPE="full"
        DB_PATH="${DATABASE_URL:-sqlite:///./quant_trade.db}"
        DB_PATH="${DB_PATH#sqlite:///}"
        cp "${DB_PATH}" "${BACKUP_FILE}"
    fi
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# ========== 压缩 ==========
if [ "${COMPRESS}" = "true" ] && [ -f "${BACKUP_FILE}" ]; then
    log "压缩备份文件..."
    gzip -f "${BACKUP_FILE}"
    BACKUP_FILE="${BACKUP_FILE}.gz"
fi

# ========== 备份验证 ==========
if [ "${VERIFY}" = "true" ] && [ -f "${BACKUP_FILE}" ]; then
    log "验证备份文件..."
    FILE_SIZE=$(stat -f%z "${BACKUP_FILE}" 2>/dev/null || stat -c%s "${BACKUP_FILE}" 2>/dev/null || echo 0)

    if [ "${FILE_SIZE}" -eq 0 ]; then
        error_exit "备份文件为空，验证失败"
    fi

    # 检查文件完整性（gzip 检查）
    if [[ "${BACKUP_FILE}" == *.gz ]]; then
        gzip -t "${BACKUP_FILE}" 2>> "${LOG_FILE}" || error_exit "gzip 完整性检查失败"
    fi

    log "备份验证通过，文件大小: ${FILE_SIZE} bytes"
fi

# ========== 保留策略 ==========
log "清理过期备份（保留 ${RETENTION_DAYS} 天）..."
DELETED_COUNT=0
if [ -d "${BACKUP_DIR}" ]; then
    while IFS= read -r -d '' old_file; do
        rm -f "${old_file}"
        log "已删除过期备份: $(basename "${old_file}")"
        DELETED_COUNT=$((DELETED_COUNT + 1))
    done < <(find "${BACKUP_DIR}" -name "*.sql.gz" -o -name "*.sql" | while read -r f; do
        file_age=$(( (END_TIME - $(stat -f%m "${f}" 2>/dev/null || stat -c%Y "${f}" 2>/dev/null)) / 86400 ))
        if [ "${file_age}" -gt "${RETENTION_DAYS}" ]; then
            echo "${f}"
        fi
    done)
fi

# ========== 完成 ==========
log "备份完成: $(basename "${BACKUP_FILE}")"
log "耗时: ${DURATION} 秒"
log "删除过期备份: ${DELETED_COUNT} 个"
log "========== 备份结束 =========="
