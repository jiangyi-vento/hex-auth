#!/usr/bin/env bash
# Docker Compose 部署下的 MySQL 备份脚本
#
# 用法：./deploy/backup-docker.sh [备份目录] [保留天数]
# 建议 crontab：
#   17 3 * * * /opt/hex-auth/deploy/backup-docker.sh /var/backups/hex-auth 14 >> /var/log/hex-auth-backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${1:-/var/backups/hex-auth}"
RETENTION_DAYS="${2:-14}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$BACKUP_DIR"
cd "$PROJECT_DIR"

STAMP=$(date +%F_%H%M%S)
FILE="$BACKUP_DIR/hex_auth_${STAMP}.sql.gz"

# 容器内的 MYSQL_PASSWORD 由 compose 注入，无需在宿主机暴露密码
docker compose exec -T mysql sh -c \
  'exec mysqldump -uhexauth -p"$MYSQL_PASSWORD" --single-transaction --no-tablespaces hex_auth' \
  | gzip > "$FILE"

find "$BACKUP_DIR" -name 'hex_auth_*.sql.gz' -type f -mtime +"$RETENTION_DAYS" -delete

echo "备份完成: $FILE"
