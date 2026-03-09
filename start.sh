#!/bin/bash
set -e

echo "=========================================="
echo "   AI MEDIA SERVICE — AUTO DEPLOY"
echo "=========================================="

# Проверяем зависимости
command -v docker >/dev/null 2>&1 || { echo "❌ Docker не установлен! https://docs.docker.com/get-docker/"; exit 1; }
command -v docker compose version >/dev/null 2>&1 || { echo "❌ Docker Compose не найден!"; exit 1; }

# Проверяем .env
if [ ! -f ".env" ]; then
  echo "❌ Файл .env не найден!"
  exit 1
fi
echo "✅ .env найден"

# Останавливаем старые контейнеры если есть
echo ""
echo "🔄 Останавливаем старые контейнеры..."
docker compose down --remove-orphans 2>/dev/null || true

# Строим и запускаем
echo ""
echo "🐳 Запускаем Docker контейнеры..."
docker compose up --build -d

# Ждём БД
echo ""
echo "⏳ Ждём готовности PostgreSQL..."
until docker exec agent_traffic_pg pg_isready -U agent -d agent_traffic >/dev/null 2>&1; do
  sleep 1
done
echo "✅ PostgreSQL готов"

# Ждём Redis
echo ""
echo "⏳ Ждём готовности Redis..."
until docker exec agent_traffic_redis redis-cli ping >/dev/null 2>&1; do
  sleep 1
done
echo "✅ Redis готов"

echo ""
echo "=========================================="
echo "✅ ДЕПЛОЙ ЗАВЕРШЁН!"
echo ""
echo "   Dashboard:  http://localhost:8000"
echo "   API docs:   http://localhost:8000/docs"
echo ""
echo "📋 Статус контейнеров:"
docker compose ps
echo "=========================================="
