#!/bin/bash
# Скрипт для правильного перезапуска приложения с перезагрузкой .env

set -e

echo "========================================="
echo "  SOP LLM Service - Restart"
echo "========================================="
echo ""

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Проверка .env
echo -e "${YELLOW}[1/4] Checking .env file...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env file not found!${NC}"
    echo "Please create .env file from .env.example:"
    echo "  cp .env.example .env"
    exit 1
fi

# Проверка ANTHROPIC_API_KEY
if grep -q "^ANTHROPIC_API_KEY=sk-" .env; then
    echo -e "${GREEN}✓ ANTHROPIC_API_KEY found in .env${NC}"
else
    echo -e "${YELLOW}⚠ ANTHROPIC_API_KEY not set or empty in .env${NC}"
    echo "Claude provider will not be available"
fi

echo ""

# Остановка контейнеров
echo -e "${YELLOW}[2/4] Stopping containers...${NC}"
docker compose down
echo -e "${GREEN}✓ Containers stopped${NC}"
echo ""

# Пересборка (опционально)
if [ "$1" = "--build" ]; then
    echo -e "${YELLOW}[3/4] Rebuilding images...${NC}"
    docker compose build --no-cache
    echo -e "${GREEN}✓ Images rebuilt${NC}"
else
    echo -e "${YELLOW}[3/4] Skipping rebuild (use --build to rebuild)${NC}"
fi
echo ""

# Запуск
echo -e "${YELLOW}[4/4] Starting containers...${NC}"
docker compose up -d
echo -e "${GREEN}✓ Containers started${NC}"
echo ""

# Ожидание запуска
echo "Waiting for application to start..."
sleep 5

# Проверка переменных в контейнере
echo ""
echo "Checking environment variables in container:"
echo "---"
docker compose exec app env | grep -E "(ANTHROPIC|REDIS|APP_)" || echo "Variables not found"
echo "---"
echo ""

# Проверка логов
echo "Recent logs:"
echo "---"
docker compose logs --tail=20 app
echo "---"
echo ""

# Проверка health
echo "Checking health endpoint..."
sleep 2
curl -s http://localhost:8023/api/v1/health | python3 -m json.tool 2>/dev/null || echo "Health check failed (app might still be starting)"
echo ""

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  Restart complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "  - Check logs:      docker compose logs -f app"
echo "  - Check health:    curl http://localhost:8023/api/v1/health"
echo "  - Check providers: curl http://localhost:8023/api/v1/providers"
echo "  - Swagger UI:      http://localhost:8023/docs"
echo ""
