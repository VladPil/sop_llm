# Contributing Guidelines

Спасибо за интерес к проекту SOP LLM Executor!

## Процесс разработки

### 1. Подготовка окружения

```bash
# Клонировать репозиторий
git clone https://github.com/vladislav/sop_llm.git
cd sop_llm

# Установить зависимости
make install-dev

# Установить pre-commit hooks
pip install pre-commit
pre-commit install
```

### 2. Создание ветки

```bash
# Обновить main
git checkout main
git pull origin main

# Создать feature ветку
git checkout -b feature/ISSUE-123-your-feature-name
```

Формат имени ветки: `{type}/{ticket-id}-{description}`

**Типы веток:**
- `feature/` — новая функциональность
- `bugfix/` — исправление бага
- `refactor/` — рефакторинг
- `docs/` — только документация
- `test/` — только тесты
- `chore/` — обновление зависимостей, CI/CD

### 3. Разработка

**Code Style:**
- Следуйте PEP8
- Используйте type hints везде
- Docstrings в Google Style на русском языке
- Комментарии объясняют "почему", а не "что"

**Проверка кода:**
```bash
# Форматирование
make format

# Линтинг
make lint

# Проверка типов
make type-check

# Все проверки
make check
```

**Тестирование:**
```bash
# Запустить все тесты
make test

# Unit тесты
make test-unit

# С покрытием
make test-coverage
```

### 4. Commit Messages

Используем [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <краткое описание>

<детальное описание>

<footer>
```

**Примеры:**
```bash
feat(providers): добавить поддержку Claude 3 Opus

Реализована интеграция с новой моделью Claude 3 Opus через Anthropic API.

- Добавлен provider для Claude 3 Opus
- Обновлена документация API
- Добавлены unit тесты

Closes #123
```

```bash
fix(gpu): исправить утечку памяти при повторной загрузке модели

При повторной загрузке модели через reload() не освобождалась старая
память. Добавлен явный вызов gc.collect() и torch.cuda.empty_cache().

Fixes #456
```

**Типы коммитов:**
- `feat` — новая функциональность
- `fix` — исправление бага
- `refactor` — рефакторинг
- `docs` — документация
- `test` — тесты
- `style` — форматирование
- `chore` — обновление зависимостей, CI/CD
- `perf` — оптимизация производительности

### 5. Pull Request

```bash
# Синхронизировать с main
git fetch origin main
git merge origin/main

# Запустить все проверки
make check
make test

# Push в remote
git push origin feature/ISSUE-123-your-feature-name

# Создать PR на GitHub
```

**PR Template:**
```markdown
## Описание
[Краткое описание изменений]

## Тип изменений
- [ ] Новая функциональность
- [ ] Исправление бага
- [ ] Breaking change
- [ ] Обновление документации

## Связанные задачи
Closes #123

## Внесённые изменения
- Пункт 1
- Пункт 2

## Тестирование
- [x] Unit тесты проходят
- [x] Integration тесты проходят
- [x] Покрытие ≥ 80%

## Чеклист
- [x] Код соответствует стандартам
- [x] Self-review выполнен
- [x] Комментарии добавлены
- [x] Документация обновлена
- [x] Тесты добавлены
```

### 6. Code Review

**Требования для merge:**
- ✅ Минимум 1 approval
- ✅ Все CI/CD checks прошли
- ✅ Нет merge conflicts
- ✅ Coverage не упал ниже 80%
- ✅ Все комментарии resolved

## Стандарты качества

### Code Coverage
- **Минимум:** 80% для всего проекта
- **Цель:** ≥ 85% для нового кода
- **Исключения:** integration тесты с внешними сервисами

### Производительность
- API endpoints: < 100ms (p95)
- Task processing: зависит от модели
- Memory leaks: не допускаются

### Безопасность
- Не коммитить секреты (.env, keys, passwords)
- Использовать Pydantic для валидации
- Sanitize логи от чувствительных данных

## Полезные команды

```bash
# Разработка
make run-dev              # Запуск с hot-reload
make ENV=local up         # Запуск в Docker

# Качество кода
make format               # Форматирование
make lint                 # Линтинг
make type-check          # Проверка типов
make check               # Все проверки

# Тестирование
make test                # Все тесты
make test-unit           # Unit тесты
make test-coverage       # С отчетом

# Очистка
make clean               # Временные файлы
make clean-all           # Полная очистка
```

## Вопросы?

- GitHub Issues: https://github.com/vladislav/sop_llm/issues
- Документация: https://github.com/vladislav/sop_llm/tree/main/docs

## Лицензия

Внося вклад в проект, вы соглашаетесь с условиями MIT License.
