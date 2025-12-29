# Docker Configuration Index

Навигация по документации Docker конфигурации.

## Быстрая навигация

### 🚀 Хочу быстро начать
→ [QUICKSTART.md](QUICKSTART.md) - Быстрый старт за 3 команды

### 📖 Хочу понять структуру
→ [README.md](README.md) - Полная документация по структуре

### 🔄 Мигрирую со старой версии
→ [MIGRATION.md](MIGRATION.md) - Пошаговое руководство по миграции

### 📊 Хочу общий обзор
→ [OVERVIEW.md](OVERVIEW.md) - Архитектура и компоненты

## Структура файлов

```
.docker/
│
├── 📁 dockerfiles/              # Docker образы
│   └── backend/
│       └── Dockerfile           # Multi-stage build
│
├── 📁 configs/                  # Конфигурации
│   ├── .env.local              # Локальная разработка
│   ├── .env.dev                # Dev окружение
│   └── .env.prod               # Production
│
├── 🐳 docker-compose.local.yml  # Full stack разработка
├── 🐳 docker-compose.infra.yml  # Только Redis
├── 🐳 docker-compose.dev.yml    # Stateless deployment
│
└── 📚 Документация
    ├── INDEX.md                 # Этот файл
    ├── QUICKSTART.md           # Быстрый старт
    ├── README.md               # Полная документация
    ├── MIGRATION.md            # Руководство по миграции
    └── OVERVIEW.md             # Обзор архитектуры
```

## Типичные задачи

### Разработка

**Задача:** Запустить приложение локально с hot-reload

```bash
cd .docker
docker-compose -f docker-compose.local.yml up
```

📖 Подробнее: [QUICKSTART.md - Сценарий 1](QUICKSTART.md#сценарий-1-локальная-разработка-full-stack)

---

**Задача:** Запустить только Redis, приложение в IDE

```bash
cd .docker
docker-compose -f docker-compose.infra.yml up
```

📖 Подробнее: [QUICKSTART.md - Сценарий 2](QUICKSTART.md#сценарий-2-только-redis-app-вне-docker)

---

**Задача:** Отладка приложения

```bash
docker-compose -f docker-compose.local.yml exec app bash
# или
docker-compose -f docker-compose.local.yml logs -f app
```

📖 Подробнее: [README.md - Troubleshooting](README.md#troubleshooting)

### Deployment

**Задача:** Deployment в dev окружение

```bash
export REDIS_HOST=redis.dev.example.com
cd .docker
docker-compose -f docker-compose.dev.yml up -d
```

📖 Подробнее: [QUICKSTART.md - Сценарий 3](QUICKSTART.md#сценарий-3-deployment-stateless-app)

---

**Задача:** Сборка production образа

```bash
cd .docker
docker build -f dockerfiles/backend/Dockerfile \
  --build-arg INSTALL_GPU=true \
  -t sop_llm:prod \
  ../..
```

📖 Подробнее: [README.md - Build аргументы](README.md#build-аргументы)

### Обслуживание

**Задача:** Просмотр логов

```bash
docker-compose -f docker-compose.local.yml logs -f app
```

📖 Подробнее: [QUICKSTART.md - Частые задачи](QUICKSTART.md#частые-задачи)

---

**Задача:** Очистка volumes и образов

```bash
docker-compose -f docker-compose.local.yml down -v
docker system prune -a
```

📖 Подробнее: [OVERVIEW.md - Troubleshooting](OVERVIEW.md#troubleshooting)

---

**Задача:** Проверка статуса

```bash
docker-compose -f docker-compose.local.yml ps
docker-compose -f docker-compose.local.yml logs redis
```

📖 Подробнее: [README.md - Healthchecks](README.md#healthchecks)

## Документация по файлам

### Dockerfile

**Файл:** `dockerfiles/backend/Dockerfile`

**Содержит:**
- Multi-stage build (builder + runtime)
- Установка зависимостей из pyproject.toml
- Опциональная GPU поддержка
- Оптимизация размера образа

**Читать:** [OVERVIEW.md - Dockerfile](OVERVIEW.md#1-dockerfile-multi-stage-build)

### Environment configs

**Файлы:**
- `configs/.env.local` - Локальная разработка
- `configs/.env.dev` - Dev окружение
- `configs/.env.prod` - Production

**Содержат:**
- Настройки приложения
- Конфигурация Redis
- Параметры LLM моделей
- Логирование и мониторинг

**Читать:** [OVERVIEW.md - Environment Configs](OVERVIEW.md#2-environment-configs)

### Docker Compose

**Файлы:**
- `docker-compose.local.yml` - Full stack
- `docker-compose.infra.yml` - Только Redis
- `docker-compose.dev.yml` - Stateless app

**Содержат:**
- Определения сервисов
- Volume mapping
- Network конфигурация
- Healthchecks

**Читать:** [OVERVIEW.md - Docker Compose файлы](OVERVIEW.md#3-docker-compose-файлы)

## Сценарии использования

### Я - Backend разработчик

**Мой рабочий процесс:**

1. Запускаю инфраструктуру:
   ```bash
   cd .docker
   docker-compose -f docker-compose.infra.yml up -d
   ```

2. Разрабатываю в IDE (PyCharm/VS Code):
   ```bash
   python -m uvicorn src.main:app --reload
   ```

3. Тестирую:
   ```bash
   pytest
   ```

📖 Читать: [QUICKSTART.md - Сценарий 2](QUICKSTART.md#сценарий-2-только-redis-app-вне-docker)

### Я - Frontend разработчик

**Мой рабочий процесс:**

1. Запускаю полное окружение:
   ```bash
   cd .docker
   docker-compose -f docker-compose.local.yml up
   ```

2. API доступен на http://localhost:8001

3. Документация: http://localhost:8001/docs

📖 Читать: [QUICKSTART.md - Сценарий 1](QUICKSTART.md#сценарий-1-локальная-разработка-full-stack)

### Я - DevOps инженер

**Мой рабочий процесс:**

1. Изучаю документацию:
   - [README.md](README.md) - Структура
   - [OVERVIEW.md](OVERVIEW.md) - Архитектура

2. Настраиваю окружения:
   - Редактирую `.env.dev` и `.env.prod`
   - Настраиваю secrets management

3. Deployment:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

📖 Читать: [OVERVIEW.md - Безопасность](OVERVIEW.md#безопасность)

### Я - мигрирую со старой версии

**Мой рабочий процесс:**

1. Читаю руководство:
   - [MIGRATION.md](MIGRATION.md) - Пошаговая миграция

2. Сравниваю старую и новую структуру

3. Тестирую новую конфигурацию:
   ```bash
   cd .docker
   docker-compose -f docker-compose.local.yml up --build
   ```

4. Переключаюсь на новую структуру

📖 Читать: [MIGRATION.md - Миграция шаг за шагом](MIGRATION.md#миграция-шаг-за-шагом)

## Часто задаваемые вопросы

### В чем разница между docker-compose.*.yml файлами?

- **local.yml** - Полное окружение для разработки (Redis + App + hot-reload)
- **infra.yml** - Только инфраструктура (Redis), app запускается отдельно
- **dev.yml** - Только app (stateless), для deployment

📖 Читать: [OVERVIEW.md - Сравнение конфигураций](OVERVIEW.md#сравнение-конфигураций)

### Как включить GPU поддержку?

1. Установите nvidia-container-toolkit
2. Раскомментируйте `runtime: nvidia` в docker-compose
3. Установите `INSTALL_GPU=true`

📖 Читать: [QUICKSTART.md - GPU Support](QUICKSTART.md#gpu-support)

### Где хранятся логи и кэш моделей?

В Docker volumes:
- `sop_llm_models_cache_*` - Кэш HuggingFace моделей
- `sop_llm_app_logs_*` - Логи приложения
- `sop_llm_redis_data_*` - Данные Redis

📖 Читать: [OVERVIEW.md - Volumes](OVERVIEW.md#volumes)

### Как подключиться к приложению в контейнере?

```bash
docker-compose -f docker-compose.local.yml exec app bash
```

📖 Читать: [QUICKSTART.md - Выполнение команд](QUICKSTART.md#выполнение-команд-в-контейнере)

### Приложение не запускается, что делать?

1. Проверьте логи: `docker-compose -f docker-compose.local.yml logs app`
2. Проверьте Redis: `docker-compose -f docker-compose.local.yml ps redis`
3. Проверьте порты: `netstat -tulpn | grep 8001`

📖 Читать: [QUICKSTART.md - Troubleshooting](QUICKSTART.md#troubleshooting)

## Соглашения и стандарты

Конфигурация следует стандартам **wiki-engine**:

✅ Вся Docker конфигурация в `.docker/`
✅ Разделение окружений (local/dev/prod)
✅ Multi-stage builds
✅ Healthchecks для всех сервисов
✅ Volume persistence для данных
✅ Secrets через переменные окружения (prod)
✅ Документация и примеры

## Обновления

При изменении конфигурации:

1. Обновите соответствующий `.md` файл
2. Пересоберите образы: `docker-compose build --no-cache`
3. Проверьте все сценарии использования
4. Обновите версию в git

## Поддержка

**Проблемы:**
- Проверьте [QUICKSTART.md - Troubleshooting](QUICKSTART.md#troubleshooting)
- Проверьте [OVERVIEW.md - Troubleshooting](OVERVIEW.md#troubleshooting)

**Вопросы:**
- Изучите документацию в этой директории
- Создайте issue в проекте

**Предложения:**
- Pull requests приветствуются
- Следуйте существующим стандартам

---

**Последнее обновление:** 2025-12-03
**Версия:** 1.0.0
**Стандарт:** wiki-engine
