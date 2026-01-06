.PHONY: help install install-dev run run-dev up down restart ps logs logs-app logs-redis shell shell-redis build lint format type-check check test test-unit test-integration test-coverage clean clean-models clean-all

RESET := \033[0m
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
MAGENTA := \033[35m
CYAN := \033[36m
BOLD := \033[1m

# Автоопределение команды docker-compose (v1 или v2)
DOCKER_COMPOSE := $(shell which docker-compose 2>/dev/null)
ifeq ($(DOCKER_COMPOSE),)
    DOCKER_COMPOSE := docker compose
else
    DOCKER_COMPOSE := docker-compose
endif

# Выберите окружение через переменную ENV:
#   make ENV=local up    - локальная разработка (все в Docker с volumes для hot-reload)
#   make ENV=infra up    - только инфраструктура (Redis БЕЗ Backend)
#   make ENV=dev up      - dev окружение (stateless backend для Kubernetes)
#   make up              - по умолчанию: локальная разработка (local)

ENV ?= local

# Выбор файла docker-compose и .env в зависимости от окружения
ifeq ($(ENV),local)
    COMPOSE_FILE := .docker/docker-compose.local.yml
    ENV_FILE := .env
else ifeq ($(ENV),infra)
    COMPOSE_FILE := .docker/docker-compose.infra.yml
    ENV_FILE := .env
else ifeq ($(ENV),dev)
    COMPOSE_FILE := .docker/docker-compose.dev.yml
    ENV_FILE := .docker/configs/.env.dev
else
    COMPOSE_FILE := .docker/docker-compose.local.yml
    ENV_FILE := .env
endif

# Директория скриптов
SCRIPTS_DIR := scripts

# Пути к конфигурационным файлам
PYTEST_CONFIG := pytest.ini
PYPROJECT_CONFIG := pyproject.toml

# Python переменные
PYTHON := python3
VENV := .venv
VENV_ACTIVATE := . $(VENV)/bin/activate

help:
	@echo "$(BOLD)$(CYAN)SOP LLM Service - Доступные команды$(RESET)"
	@echo "$(CYAN)========================================$(RESET)"
	@echo ""
	@echo "$(BOLD)$(YELLOW)ОКРУЖЕНИЯ:$(RESET)"
	@echo "  $(GREEN)ENV=local$(RESET)         - Локальная разработка (все в Docker + volumes для hot-reload)"
	@echo "  $(GREEN)ENV=infra$(RESET)         - Только инфраструктура (Redis БЕЗ Backend)"
	@echo "  $(GREEN)ENV=dev$(RESET)           - Dev окружение (stateless backend для Kubernetes)"
	@echo "  $(GREEN)По умолчанию$(RESET)      - ENV=local"
	@echo ""
	@echo "$(BOLD)$(BLUE)Примеры использования:$(RESET)"
	@echo "  $(CYAN)make up$(RESET)                   - Запустить локальное окружение (ENV=local)"
	@echo "  $(CYAN)make ENV=local up$(RESET)         - Запустить полное локальное окружение с hot-reload"
	@echo "  $(CYAN)make ENV=infra up$(RESET)         - Запустить только инфраструктуру (Redis)"
	@echo "  $(CYAN)make ENV=dev up$(RESET)           - Запустить stateless backend для dev"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Установка зависимостей:$(RESET)"
	@echo "  $(GREEN)install$(RESET)           - Установка production зависимостей"
	@echo "  $(GREEN)install-dev$(RESET)       - Установка с dev зависимостями"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Запуск приложения:$(RESET)"
	@echo "  $(GREEN)run$(RESET)               - Запустить приложение локально"
	@echo "  $(GREEN)run-dev$(RESET)           - Запустить с hot-reload (uvicorn --reload)"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Управление Docker:$(RESET)"
	@echo "  $(GREEN)up$(RESET)                - Запустить сервисы"
	@echo "  $(GREEN)down$(RESET)              - Остановить все сервисы"
	@echo "  $(GREEN)restart$(RESET)           - Перезапустить все сервисы"
	@echo "  $(GREEN)ps$(RESET)                - Показать статус сервисов"
	@echo "  $(GREEN)build$(RESET)             - Пересобрать Docker образы"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Логирование и отладка:$(RESET)"
	@echo "  $(GREEN)logs$(RESET)              - Показать все логи"
	@echo "  $(GREEN)logs-app$(RESET)          - Показать логи приложения"
	@echo "  $(GREEN)logs-redis$(RESET)        - Показать логи Redis"
	@echo "  $(GREEN)shell$(RESET)             - Открыть оболочку в контейнере приложения"
	@echo "  $(GREEN)shell-redis$(RESET)       - Открыть Redis CLI"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Качество кода:$(RESET)"
	@echo "  $(GREEN)lint$(RESET)              - Проверка кода (ruff check)"
	@echo "  $(GREEN)format$(RESET)            - Автоформатирование кода (ruff format + check --fix)"
	@echo "  $(GREEN)type-check$(RESET)        - Проверить типы (mypy)"
	@echo "  $(GREEN)check$(RESET)             - Запустить все проверки (lint + type-check)"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Тестирование:$(RESET)"
	@echo "  $(GREEN)test$(RESET)              - Запустить все тесты"
	@echo "  $(GREEN)test-unit$(RESET)         - Запустить только unit тесты"
	@echo "  $(GREEN)test-integration$(RESET)  - Запустить только integration тесты"
	@echo "  $(GREEN)test-coverage$(RESET)     - Запустить тесты с отчетом о покрытии"
	@echo ""
	@echo "$(BOLD)$(YELLOW)Очистка:$(RESET)"
	@echo "  $(GREEN)clean$(RESET)             - Очистить временные файлы и кэш"
	@echo "  $(GREEN)clean-models$(RESET)      - Очистить кэш моделей HuggingFace"
	@echo "  $(GREEN)clean-all$(RESET)         - Полная очистка (включая Docker тома)"
	@echo ""

install:
	@echo "$(CYAN)Установка production зависимостей...$(RESET)"
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(YELLOW)Создание виртуального окружения...$(RESET)"; \
		$(PYTHON) -m venv $(VENV); \
	fi
	@$(VENV_ACTIVATE) && pip install --upgrade pip setuptools wheel
	@$(VENV_ACTIVATE) && pip install -e .
	@echo "$(GREEN)Установка завершена$(RESET)"

install-dev:
	@echo "$(CYAN)Установка dev зависимостей...$(RESET)"
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(YELLOW)Создание виртуального окружения...$(RESET)"; \
		$(PYTHON) -m venv $(VENV); \
	fi
	@$(VENV_ACTIVATE) && pip install --upgrade pip setuptools wheel
	@$(VENV_ACTIVATE) && pip install -e ".[dev]"
	@echo "$(GREEN)Установка dev зависимостей завершена$(RESET)"

run:
	@echo "$(CYAN)Запуск приложения...$(RESET)"
	@$(VENV_ACTIVATE) && python -m uvicorn src.app:app --host 0.0.0.0 --port 8000

run-dev:
	@echo "$(CYAN)Запуск приложения с hot-reload...$(RESET)"
	@$(VENV_ACTIVATE) && python -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload --reload-dir src

up:
	@echo "$(CYAN)Запуск сервисов (ENV=$(ENV))...$(RESET)"
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "$(RED)Ошибка: Файл окружения $(ENV_FILE) не найден!$(RESET)"; \
		echo "$(YELLOW)Пожалуйста, создайте файл конфигурации из примера:$(RESET)"; \
		echo "  cp .docker/configs/.env.local $(ENV_FILE)"; \
		exit 1; \
	fi
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d
	@echo "$(GREEN)Сервисы запущены успешно$(RESET)"
	@echo ""
	@echo "$(CYAN)Доступные сервисы:$(RESET)"
	@echo "  API:             http://localhost:8001"
	@echo "  API Docs:        http://localhost:8001/docs"
	@echo "  Metrics:         http://localhost:9091/metrics"
	@echo "  Redis Commander: http://localhost:8082"

down:
	@echo "$(CYAN)Остановка сервисов...$(RESET)"
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down
	@echo "$(GREEN)Сервисы остановлены$(RESET)"

restart: down up

ps:
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps

build:
	@echo "$(CYAN)Сборка Docker образов...$(RESET)"
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) build
	@echo "$(GREEN)Сборка завершена$(RESET)"

logs:
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f

logs-app:
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f --tail=100 app

logs-redis:
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f --tail=100 redis

shell:
	@echo "$(CYAN)Подключение к контейнеру приложения...$(RESET)"
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec app /bin/bash

shell-redis:
	@echo "$(CYAN)Подключение к Redis CLI...$(RESET)"
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec redis redis-cli

lint:
	@echo "$(CYAN)Проверка кода с помощью ruff...$(RESET)"
	@$(VENV_ACTIVATE) && ruff check src tests
	@echo "$(GREEN)Проверка завершена$(RESET)"

format:
	@echo "$(CYAN)Форматирование кода...$(RESET)"
	@$(VENV_ACTIVATE) && ruff format src tests
	@$(VENV_ACTIVATE) && ruff check --fix src tests
	@echo "$(GREEN)Форматирование завершено$(RESET)"

type-check:
	@echo "$(CYAN)Проверка типов с помощью mypy...$(RESET)"
	@$(VENV_ACTIVATE) && mypy --config-file $(PYPROJECT_CONFIG) src
	@echo "$(GREEN)Проверка типов завершена$(RESET)"

check: lint type-check
	@echo "$(GREEN)Все проверки пройдены успешно$(RESET)"

test:
	@echo "$(CYAN)Запуск всех тестов...$(RESET)"
	@$(VENV_ACTIVATE) && pytest -c $(PYTEST_CONFIG)
	@echo "$(GREEN)Все тесты завершены$(RESET)"

test-unit:
	@echo "$(CYAN)Запуск unit тестов...$(RESET)"
	@$(VENV_ACTIVATE) && pytest -c $(PYTEST_CONFIG) -m unit
	@echo "$(GREEN)Unit тесты завершены$(RESET)"

test-integration:
	@echo "$(CYAN)Запуск integration тестов...$(RESET)"
	@$(VENV_ACTIVATE) && pytest -c $(PYTEST_CONFIG) -m integration
	@echo "$(GREEN)Integration тесты завершены$(RESET)"

test-coverage:
	@echo "$(CYAN)Запуск тестов с покрытием...$(RESET)"
	@$(VENV_ACTIVATE) && pytest -c $(PYTEST_CONFIG) --cov=src --cov-report=html --cov-report=term-missing --cov-report=xml
	@echo "$(GREEN)Отчет о покрытии готов: $(CYAN)htmlcov/index.html$(RESET)"

clean:
	@echo "$(CYAN)Очистка временных файлов...$(RESET)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.pyd" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf htmlcov/ 2>/dev/null || true
	@rm -rf .coverage 2>/dev/null || true
	@rm -rf coverage.xml 2>/dev/null || true
	@rm -rf dist/ 2>/dev/null || true
	@rm -rf build/ 2>/dev/null || true
	@echo "$(GREEN)Временные файлы удалены$(RESET)"

clean-models:
	@echo "$(YELLOW)ВНИМАНИЕ: Это удалит все кэшированные модели!$(RESET)"
	@read -p "Вы уверены? Введите 'yes' для продолжения: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(CYAN)Удаление кэша моделей...$(RESET)"; \
		rm -rf ~/.cache/huggingface/* 2>/dev/null || true; \
		rm -rf models/ 2>/dev/null || true; \
		echo "$(GREEN)Кэш моделей очищен$(RESET)"; \
	else \
		echo "$(YELLOW)Отменено$(RESET)"; \
	fi

clean-all: down
	@echo "$(RED)ВНИМАНИЕ: Это удалит все контейнеры, тома и временные файлы!$(RESET)"
	@read -p "Вы уверены? Введите 'yes' для продолжения: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(CYAN)Удаление всех Docker ресурсов...$(RESET)"; \
		$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down -v --rmi local 2>/dev/null || true; \
		$(MAKE) clean; \
		echo "$(GREEN)Полная очистка завершена$(RESET)"; \
	else \
		echo "$(YELLOW)Отменено$(RESET)"; \
	fi
