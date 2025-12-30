# Changelog

Все notable changes будут документированы в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
и проект следует [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Pre-commit hooks для автоматической проверки кода
- .env.example для примера конфигурации

### Changed
- Улучшена система логирования с поддержкой structured logging
- Обновлена документация в README.md

## [1.0.0] - 2025-12-30

### Added
- Централизованная конфигурация в src/config.py
- Улучшенная система логирования из wiki-engine проекта
- InterceptHandler для перехвата логов сторонних библиотек
- JSON formatter для production логирования с sanitization секретных данных
- Настройка uvicorn, fastapi, redis, httpx логгеров

### Changed
- Реструктуризация проекта: весь код перенесен в src/
- Точка входа изменена с src.main:app на src.app:app
- Обновлена Docker конфигурация для новой структуры
- Улучшен Makefile с корректными путями
- Type hints: Any → конкретные типы (Logger)

### Removed
- Дублирующий файл src/main.py с неработающими импортами
- Директория config/ из корня (настройки в src/config.py)
- Директория scripts/ с неиспользуемыми утилитами
- Директория docs/ с устаревшей документацией
- Декоративные комментарии типа `# ==== Section ====` (30+ шт)
- 2968 строк устаревшего кода

### Fixed
- Исправлены все импорты config.settings → src.config
- Исправлена точка входа в Docker и Makefile
- Устранены критические проблемы со структурой проекта

## [0.9.0] - 2025-12-29

### Added
- Базовая функциональность SOP LLM Executor
- Поддержка провайдеров: Local (llama.cpp), OpenAI, Anthropic
- Асинхронная обработка задач через TaskProcessor
- Redis для хранения сессий и задач
- GPU Guard для управления VRAM
- Webhook callbacks с retry механизмом
- Idempotency для дедупликации запросов
- REST API с полной документацией Swagger

### Changed
- Переход на FastAPI 0.115+
- Обновление до Python 3.11+

[Unreleased]: https://github.com/vladislav/sop_llm/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/vladislav/sop_llm/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/vladislav/sop_llm/releases/tag/v0.9.0
