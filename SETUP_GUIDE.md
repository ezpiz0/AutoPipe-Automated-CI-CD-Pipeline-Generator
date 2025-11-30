# AutoPipe - Инструкция по Установке и Настройке

## 1. Системные Требования

- **OS:** Windows 10/11, Linux, macOS
- **Python:** 3.10 или выше
- **Git:** Любая актуальная версия
- **Docker:** (опционально) Для E2E тестов и инфраструктуры

## 2. Быстрая Установка

### Шаг 1: Клонирование репозитория
```bash
cd d:/Downloads
# Репозиторий уже находится в d:/Downloads/T1
cd T1
```

### Шаг 2: Установка зависимостей
```bash
# Установка AutoPipe в editable режиме
python -m pip install -e .

# Для разработки (включая pytest)
python -m pip install -e ".[dev]"
```

### Шаг 3: Проверка установки
```bash
# Проверка CLI
python -m autopipe --help

# Запуск тестов
python -m pytest tests/ -v
```

## 3. Установка Внешних Валидаторов (Рекомендуется)

### hadolint (Dockerfile linter)

**Windows:**
```powershell
# Скачать с GitHub Releases
# https://github.com/hadolint/hadolint/releases
# Разместить hadolint.exe в PATH
```

**Linux/macOS:**
```bash
# Через package manager
brew install hadolint  # macOS
sudo apt install hadolint  # Ubuntu/Debian
```

### yamllint (YAML linter)

```bash
python -m pip install yamllint
```

## 4. Использование

### Базовые команды
```bash
# Анализ локального репозитория
python -m autopipe /path/to/repo

# С указанием выходной директории
python -m autopipe /path/to/repo --output ./generated

# Verbose режим
python -m autopipe /path/to/repo --verbose
```

### Примеры с готовыми Golden Samples
```bash
# Java Spring Boot
python -m autopipe tests/golden_samples/java-maven-spring --output ./java-out

# Python FastAPI
python -m autopipe tests/dummy_repo --output ./python-out

# Node.js React
python -m autopipe tests/golden_samples/nodejs-react --output ./nodejs-out

# Go Service
python -m autopipe tests/golden_samples/go-service --output ./go-out

# .NET API
python -m autopipe tests/golden_samples/dotnet-api --output ./dotnet-out

# PHP Laravel
python -m autopipe tests/golden_samples/php-laravel --output ./php-out
```

## 5. Запуск Тестов

```bash
# Все тесты
python -m pytest tests/ -v

# Только детекторы
python -m pytest tests/test_detectors.py -v

# Только E2E
python -m pytest tests/test_e2e.py -v

# С coverage
python -m pytest tests/ --cov=autopipe --cov-report=html
```

## 6. Инфраструктура для E2E Тестов

### Запуск локального GitLab + инфраструктуры

```bash
# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Остановить
docker-compose down
```

### Доступ к сервисам:
- **GitLab CE**: http://localhost:8080
- **SonarQube**: http://localhost:9000
- **Nexus**: http://localhost:8081

### Первоначальная настройка GitLab:

1. Получить root пароль:
```bash
docker exec -it <gitlab-container-id> grep 'Password:' /etc/gitlab/initial_root_password
```

2. Войти как `root` с полученным паролем

3. Зарегистрировать Runner:
```bash
docker exec -it <runner-container-id> gitlab-runner register
```

## 7. Проверка Детерминизма

```bash
# Первая генерация
python -m autopipe tests/dummy_repo --output ./test1

# Вторая генерация
python -m autopipe tests/dummy_repo --output ./test2

# Сравнение (должно быть идентично)
diff ./test1/Dockerfile ./test2/Dockerfile
diff ./test1/.gitlab-ci.yml ./test2/.gitlab-ci.yml
```

## 8. Troubleshooting

### Проблема: pytest не найден
**Решение:**
```bash
python -m pip install pytest pytest-cov
```

### Проблема: ModuleNotFoundError
**Решение:**
```bash
# Переустановить в editable режиме
python -m pip install -e .
```

### Проблема: Валидаторы не найдены
**Решение:**
AutoPipe корректно работает без валидаторов, но лучше установить их для полной валидации. См. раздел 3.

### Проблема: Docker compose не запускается
**Решение:**
```bash
# Проверить Docker
docker --version

# Проверить docker-compose
docker-compose --version

# Очистить старые контейнеры
docker-compose down -v
docker-compose up -d
```

## 9. Структура Проекта

```
d:/Downloads/T1/
├── autopipe/           # Исходный код
├── templates/          # Jinja2 шаблоны
├── tests/             # Тесты и Golden Samples
├── examples/          # Сгенерированные примеры
├── docker-compose.yml # Инфраструктура
├── pyproject.toml     # Конфигурация проекта
├── README.md          # Основная документация
├── TESTING_REPORT.md  # Отчет о тестировании
└── SETUP_GUIDE.md     # Эта инструкция
```

## 10. Дальнейшие Шаги

1. **Генерация для своих проектов:**
   ```bash
   python -m autopipe /path/to/your/project --output ./generated
   ```

2. **Интеграция в CI/CD:**
   - Добавить сгенерированные файлы в репозиторий
   - Настроить GitLab Runner
   - Запустить пайплайн

3. **Настройка SonarQube и Nexus:**
   - Создать проекты в SonarQube
   - Настроить репозитории в Nexus
   - Добавить токены в GitLab CI variables
