#!/bin/bash
set -e # 如果任何命令失敗，腳本將退出

# 等待資料庫可用 (可選但建議)
# 這需要 netcat (nc)，你可能需要在 Dockerfile 中安裝它 (apt-get install -y netcat-traditional)
# while ! nc -z db 5432; do
#   echo "Waiting for postgres..."
#   sleep 1
# done
# echo "PostgreSQL started"

# 執行 Alembic 遷移
echo "Running database migrations..."
alembic upgrade head

# 執行傳遞給此腳本的命令 (即 docker-compose.yml 中的 CMD 或 command)
echo "Starting application server..."
exec "$@"
