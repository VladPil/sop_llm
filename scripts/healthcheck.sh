#!/bin/sh
# Healthcheck script для Docker контейнера
# Проверяет доступность API и основных компонентов

set -e

# Параметры
API_HOST="${API_HOST:-localhost}"
API_PORT="${API_PORT:-8000}"
HEALTH_ENDPOINT="${HEALTH_ENDPOINT:-/api/v1/health}"
TIMEOUT="${HEALTHCHECK_TIMEOUT:-5}"

# Цвета для вывода (опционально, работает в терминале)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для логирования
log() {
    echo "[HEALTHCHECK] $1"
}

# Проверяем доступность HTTP endpoint
check_http() {
    URL="http://${API_HOST}:${API_PORT}${HEALTH_ENDPOINT}"

    log "Checking HTTP endpoint: $URL"

    # Используем curl для проверки
    RESPONSE=$(curl -s -f -m "${TIMEOUT}" "${URL}" || echo "FAILED")

    if [ "$RESPONSE" = "FAILED" ]; then
        log "ERROR: HTTP endpoint not responding"
        return 1
    fi

    # Проверяем что ответ содержит JSON со статусом
    STATUS=$(echo "$RESPONSE" | grep -o '"status"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)

    if [ -z "$STATUS" ]; then
        log "ERROR: Invalid response format"
        return 1
    fi

    log "Health status: $STATUS"

    # Проверяем статус
    case "$STATUS" in
        "healthy")
            log "✓ System is healthy"
            return 0
            ;;
        "warning"|"degraded")
            log "⚠ System is degraded but operational"
            # Degraded считается OK для healthcheck (сервис работает)
            return 0
            ;;
        "unhealthy")
            log "✗ System is unhealthy"
            return 1
            ;;
        *)
            log "⚠ Unknown status: $STATUS"
            return 1
            ;;
    esac
}

# Проверяем наличие провайдеров (дополнительная проверка)
check_providers() {
    URL="http://${API_HOST}:${API_PORT}/api/v1/providers"

    log "Checking providers endpoint: $URL"

    RESPONSE=$(curl -s -f -m "${TIMEOUT}" "${URL}" || echo "FAILED")

    if [ "$RESPONSE" = "FAILED" ]; then
        log "WARNING: Providers endpoint not responding"
        # Не критично для healthcheck
        return 0
    fi

    # Проверяем что есть хотя бы один провайдер
    TOTAL=$(echo "$RESPONSE" | grep -o '"total"[[:space:]]*:[[:space:]]*[0-9]*' | grep -o '[0-9]*')

    if [ -z "$TOTAL" ] || [ "$TOTAL" -eq 0 ]; then
        log "WARNING: No providers available"
        # Не критично для healthcheck
        return 0
    fi

    log "✓ Providers available: $TOTAL"
    return 0
}

# Основная логика
main() {
    log "Starting healthcheck..."

    # Проверка HTTP endpoint (обязательно)
    if ! check_http; then
        log "FAILED: HTTP health check failed"
        exit 1
    fi

    # Проверка провайдеров (опционально)
    check_providers || true

    log "PASSED: All checks completed successfully"
    exit 0
}

# Запуск
main
