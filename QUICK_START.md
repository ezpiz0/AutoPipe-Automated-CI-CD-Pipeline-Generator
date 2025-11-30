# AutoPipe - Быстрый старт

## Требования

- Windows 10/11 с Docker Desktop
- Python 3.10+
- Git
- Минимум 8GB RAM (рекомендуется 16GB)

## Установка за 3 шага

### Шаг 1: Клонирование репозитория

```powershell
git clone -b master https://gateway-codemetrics.saas.sferaplatform.ru/app/sourcecode/api/team43/T1.git
cd T1
```

### Шаг 2: Установка Python зависимостей

```powershell
# Создание виртуального окружения
python -m venv venv

# Активация
.\venv\Scripts\Activate.ps1

# Установка зависимостей
pip install -e .
```

### Шаг 3: Запуск инфраструктуры

```powershell
# Запуск контейнеров
docker-compose up -d

# Ждём пока GitLab запустится (первый запуск ~5-10 минут)
# Проверяем статус:
docker-compose ps
```

## Настройка GitLab (первый запуск)

### 3.1 Получение пароля root

После запуска GitLab (когда http://localhost:8080 станет доступен):

```powershell
docker exec t1-gitlab-1 cat /etc/gitlab/initial_root_password
```

Сохраните этот пароль! Он удалится через 24 часа.

### 3.2 Создание API токена

1. Откройте http://localhost:8080
2. Войдите: логин `root`, пароль из п.3.1
3. Перейдите: **Avatar (справа вверху) → Preferences → Access Tokens**
4. Создайте токен:
   - Name: `autopipe`
   - Expiration: выберите дату
   - Scopes: **api**, **read_api**, **write_repository**
   - Нажмите **Create personal access token**
5. **СКОПИРУЙТЕ ТОКЕН!** (он показывается только один раз)

### 3.3 Создание и регистрация Runner

1. Перейдите: **Admin Area → CI/CD → Runners**
2. Нажмите **New instance runner**
3. Настройки:
   - Tags: `docker, autopipe`
   - Run untagged jobs: ✓
4. Нажмите **Create runner**
5. Скопируйте токен (начинается с `glrt-...`)
6. Зарегистрируйте runner:

```powershell
docker exec -it t1-gitlab-runner-1 gitlab-runner register `
  --non-interactive `
  --url "http://gitlab" `
  --token "ВСТАВЬТЕ_ТОКЕН_СЮДА" `
  --executor "docker" `
  --docker-image "docker:latest" `
  --docker-privileged `
  --docker-volumes "/var/run/docker.sock:/var/run/docker.sock" `
  --docker-network-mode "t1_autopipe-net" `
  --description "autopipe-runner"
```

## Использование AutoPipe

### Анализ репозитория

```powershell
python -m autopipe analyze https://github.com/pallets/flask.git
```

### Генерация пайплайна

```powershell
python -m autopipe generate https://github.com/pallets/flask.git -o output/
```

### Полный деплой (анализ + генерация + пуш в GitLab)

```powershell
python -m autopipe deploy https://github.com/pallets/flask.git -t ВАШ_ТОКЕН
```

## Доступ к сервисам

| Сервис | URL | Логин по умолчанию |
|--------|-----|-------------------|
| GitLab | http://localhost:8080 | root / (см. п.3.1) |
| SonarQube | http://localhost:9000 | admin / admin |
| Nexus | http://localhost:8081 | admin / admin123 |

## Частые проблемы

### GitLab не запускается

```powershell
# Проверьте логи
docker-compose logs gitlab

# Убедитесь что достаточно памяти (нужно 8GB+)
docker stats
```

### Runner не выполняет job'ы

```powershell
# Проверьте статус runner
docker exec t1-gitlab-runner-1 gitlab-runner verify

# Перезапустите runner
docker-compose restart gitlab-runner
```

### ModuleNotFoundError: No module named 'xxx'

```powershell
# Переустановите зависимости
pip install -e .
```

## Остановка и очистка

```powershell
# Остановка
docker-compose down

# Полная очистка (удаление данных)
docker-compose down -v
```

---

Команда 43 - T1 Challenge 2025
