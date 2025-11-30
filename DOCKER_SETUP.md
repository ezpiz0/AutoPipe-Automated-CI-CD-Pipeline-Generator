# Инструкция по Запуску Docker Infrastructure

## ⚠️ Проблема
Docker Desktop не запущен. Ошибка: `The system cannot find the file specified`

## ✅ Решение

### Шаг 1: Запустить Docker Desktop

1. **Найдите Docker Desktop** в меню Пуск Windows
2. **Кликните** на иконку Docker Desktop
3. **Дождитесь запуска** - в трее появится иконка кита Docker
4. **Убедитесь что статус "Running"** (обычно 30-60 секунд)

### Шаг 2: Запустить Сервисы

После запуска Docker Desktop, выполните:

```powershell
cd d:/Downloads/T1
docker-compose up -d
```

**Что произойдёт:**
- Скачаются Docker образы (первый раз ~5-10 минут)
- Запустятся 4 контейнера:
  - GitLab CE
  - GitLab Runner
  - SonarQube
  - Nexus Repository

### Шаг 3: Проверить Статус

```powershell
docker-compose ps
```

**Ожидаемый вывод:**
```
NAME                STATUS
gitlab              running
gitlab-runner       running
sonarqube           running
nexus               running
```

### Шаг 4: Дождаться Готовности Сервисов

**GitLab (займёт 3-5 минут):**
```powershell
docker logs gitlab -f
```
Дождитесь сообщения: `gitlab Reconfigured!`

**SonarQube (займёт 1-2 минуты):**
```powershell
docker logs sonarqube -f
```
Дождитесь: `SonarQube is operational`

**Nexus (займёт 1-2 минуты):**
```powershell
docker logs nexus -f
```
Дождитесь: `Started Sonatype Nexus`

---

## 🌐 Доступ к Сервисам

### GitLab CE
- **URL:** http://localhost:8080
- **Логин:** `root`
- **Пароль:** Получить командой:
  ```powershell
  docker exec -it gitlab grep 'Password:' /etc/gitlab/initial_root_password
  ```

### SonarQube
- **URL:** http://localhost:9000
- **Логин:** `admin`
- **Пароль:** `admin`
- При первом входе попросит сменить пароль

### Nexus Repository
- **URL:** http://localhost:8081
- **Логин:** `admin`
- **Пароль:** Получить командой:
  ```powershell
  docker exec -it nexus cat /nexus-data/admin.password
  ```

---

## 🔧 Troubleshooting

### Порты заняты
Если порты 8080, 9000, или 8081 заняты:

```powershell
netstat -ano | findstr :8080
netstat -ano | findstr :9000
netstat -ano | findstr :8081
```

Остановите процессы или измените порты в `docker-compose.yml`

### Недостаточно памяти
Минимальные требования:
- RAM: 8GB (рекомендуется 16GB)
- Disk: 20GB свободного места

В Docker Desktop → Settings → Resources:
- Memory: минимум 6GB
- Disk: минимум 20GB

### Проверка Docker Desktop

```powershell
# Проверить что Docker работает
docker --version
docker ps

# Если не работает - перезапустить Docker Desktop
```

---

## 🚀 Быстрый Старт (После Запуска Docker Desktop)

```powershell
# 1. Перейти в проект
cd d:/Downloads/T1

# 2. Запустить все сервисы
docker-compose up -d

# 3. Подождать 5 минут

# 4. Открыть браузер
start http://localhost:8080  # GitLab
start http://localhost:9000  # SonarQube
start http://localhost:8081  # Nexus
```

---

## 📝 Команды для Управления

```powershell
# Запустить сервисы
docker-compose up -d

# Остановить сервисы
docker-compose down

# Посмотреть логи
docker-compose logs -f

# Посмотреть логи конкретного сервиса
docker-compose logs -f gitlab

# Перезапустить сервис
docker-compose restart gitlab

# Полная очистка (удалит все данные!)
docker-compose down -v
```

---

## ⏱️ Время Запуска

| Сервис | Первый запуск | Последующие запуски |
|--------|--------------|---------------------|
| GitLab CE | 3-5 минут | 1-2 минуты |
| SonarQube | 1-2 минуты | 30-60 секунд |
| Nexus | 1-2 минуты | 30-60 секунд |

**Итого:** ~5-7 минут при первом запуске
