# Миграция Docker конфигурации

## Сравнение старой и новой структуры

### Было (старая структура)

```
.
├── docker-compose.yml         # В корне проекта
└── .docker/
    └── app/
        └── Dockerfile
```

**Проблемы:**
- docker-compose.yml в корне проекта (не следует стандартам)
- Одна конфигурация для всех окружений
- Нет разделения на окружения (local/dev/prod)
- Dockerfile копирует весь проект целиком
- Нет поддержки различных сценариев запуска

### Стало (новая структура по wiki-engine)

```
.docker/
├── dockerfiles/
│   └── backend/
│       └── Dockerfile          # Multi-stage build
├── configs/
│   ├── .env.local             # Локальная разработка
│   ├── .env.dev               # Dev окружение
│   └── .env.prod              # Production окружение
├── docker-compose.local.yml   # Полное окружение
├── docker-compose.infra.yml   # Только инфраструктура
├── docker-compose.dev.yml     # Только app (stateless)
└── README.md                   # Документация
```

**Преимущества:**
- Вся Docker конфигурация в одной директории (.docker/)
- Разделение по окружениям (local/dev/prod)
- Различные сценарии запуска (full/infra-only/app-only)
- Multi-stage build для оптимизации
- Копирование только src/ (не всего проекта)
- Четкая документация и стандарты

## Изменения в Dockerfile

### Старый Dockerfile (.docker/app/Dockerfile)

```dockerfile
# Копировал requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Копировал весь проект
COPY . /app

# Entrypoint на app.main:app
CMD uvicorn app.main:app ...
```

### Новый Dockerfile (.docker/dockerfiles/backend/Dockerfile)

```dockerfile
# Использует pyproject.toml
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir -e .

# Копирует только нужные директории
COPY src/ /app/src/
COPY config/ /app/config/
COPY scripts/ /app/scripts/

# Entrypoint на src.main:app
CMD uvicorn src.main:app ...
```

**Ключевые отличия:**
1. Использует pyproject.toml вместо requirements.txt
2. Копирует только src/, config/, scripts/ (не весь проект)
3. Entrypoint изменен с app.main:app на src.main:app
4. WORKDIR остается /app
5. Multi-stage build для меньшего размера образа

## Изменения в docker-compose

### Старый docker-compose.yml

```yaml
services:
  app:
    build:
      context: .
      dockerfile: .docker/app/Dockerfile
    volumes:
      - .:/app  # Весь проект
    environment:
      # Все переменные вместе
      - APP_ENV=production
```

### Новые docker-compose файлы

#### docker-compose.local.yml (для разработки)

```yaml
services:
  app:
    build:
      context: ../..  # Относительно .docker/
      dockerfile: .docker/dockerfiles/backend/Dockerfile
    volumes:
      - ../../src:/app/src:rw     # Только src/
      - ../../config:/app/config:rw
    env_file:
      - ./configs/.env.local      # Отдельный файл
```

#### docker-compose.infra.yml (только Redis)

```yaml
services:
  redis:
    # Только Redis, без app
```

#### docker-compose.dev.yml (только app)

```yaml
services:
  app:
    # Только app, Redis отдельно
    volumes:
      # Нет маппинга исходников (stateless)
```

## Сценарии использования

### 1. Локальная разработка (раньше)

```bash
# Старый способ
docker-compose up --build
```

### 1. Локальная разработка (теперь)

```bash
# Новый способ - полное окружение
cd .docker
docker-compose -f docker-compose.local.yml up --build
```

### 2. Запуск только Redis (новое)

```bash
# Раньше - не было такой возможности
# Теперь
cd .docker
docker-compose -f docker-compose.infra.yml up
```

Затем запускаете приложение локально:

```bash
python -m uvicorn src.main:app --reload
```

### 3. Deployment (новое)

```bash
# Раньше - использовали тот же docker-compose.yml
# Теперь - отдельный файл для deployment
cd .docker
docker-compose -f docker-compose.dev.yml up --build
```

## Переменные окружения

### Старый подход

Все переменные в docker-compose.yml или корневом .env файле:

```yaml
environment:
  - APP_ENV=production
  - DEBUG=false
  - REDIS_HOST=redis
  # ... и так далее
```

### Новый подход

Три отдельных файла конфигурации:

**configs/.env.local:**
```bash
SOP__DEBUG=true
SOP__SERVER__RELOAD=true
DEVICE=cpu
```

**configs/.env.dev:**
```bash
SOP__DEBUG=false
SOP__SERVER__RELOAD=false
DEVICE=cuda
INSTALL_GPU=true
```

**configs/.env.prod:**
```bash
SOP__DEBUG=false
SOP__LOG__LEVEL=WARNING
DEVICE=cuda
# Секреты через переменные окружения
```

## Миграция шаг за шагом

### Шаг 1: Проверьте текущую работу

```bash
# Убедитесь что старая конфигурация работает
docker-compose down
docker-compose up --build
```

### Шаг 2: Создайте новую структуру

Все файлы уже созданы в `.docker/`

### Шаг 3: Запустите новую конфигурацию

```bash
# Остановите старую
docker-compose down

# Запустите новую
cd .docker
docker-compose -f docker-compose.local.yml up --build
```

### Шаг 4: Проверьте работу

1. API доступен: http://localhost:8001/docs
2. Redis работает: http://localhost:8082 (Redis Commander)
3. Healthcheck: http://localhost:8001/health

### Шаг 5: Обновите документацию

Обновите README.md в корне проекта с новыми инструкциями.

### Шаг 6: Удалите старые файлы (опционально)

```bash
# После проверки что все работает
# Можно удалить старые файлы (или оставить для совместимости)
# mv docker-compose.yml docker-compose.yml.old
# mv .docker/app .docker/app.old
```

## Обратная совместимость

Старые файлы НЕ удалены, поэтому можно:

1. Использовать новую структуру: `cd .docker && docker-compose -f docker-compose.local.yml up`
2. Использовать старую структуру: `docker-compose up` (в корне)

Рекомендуется перейти на новую структуру и удалить старые файлы после тестирования.

## Checklist миграции

- [ ] Все новые файлы созданы в .docker/
- [ ] docker-compose.local.yml запускается без ошибок
- [ ] API доступен и healthcheck проходит
- [ ] Redis подключается
- [ ] Hot-reload работает (изменения в src/ применяются)
- [ ] docker-compose.infra.yml работает (только Redis)
- [ ] docker-compose.dev.yml работает (stateless app)
- [ ] Обновлена документация в README.md
- [ ] CI/CD обновлен (если используется)
- [ ] Старые файлы перемещены/удалены

## Полезные команды

```bash
# Полная очистка старых контейнеров и volumes
docker-compose down -v
docker system prune -a

# Проверка новой структуры
cd .docker
docker-compose -f docker-compose.local.yml config

# Построить образ без запуска
docker-compose -f docker-compose.local.yml build

# Запустить в фоне
docker-compose -f docker-compose.local.yml up -d

# Просмотр логов
docker-compose -f docker-compose.local.yml logs -f app

# Остановка
docker-compose -f docker-compose.local.yml down
```

## Решение проблем

### "No such file or directory: pyproject.toml"

Убедитесь что context указан правильно:
```yaml
build:
  context: ../..  # Должен указывать на корень проекта
  dockerfile: .docker/dockerfiles/backend/Dockerfile
```

### "Cannot find module src.main"

Проверьте PYTHONPATH:
```yaml
environment:
  - PYTHONPATH=/app
```

И убедитесь что src/ скопирован в Dockerfile:
```dockerfile
COPY src/ /app/src/
```

### Redis недоступен при использовании docker-compose.dev.yml

docker-compose.dev.yml не включает Redis. Используйте:
```bash
# Вариант 1: Запустите Redis отдельно
docker-compose -f docker-compose.infra.yml up -d redis

# Вариант 2: Используйте docker-compose.local.yml
docker-compose -f docker-compose.local.yml up
```
