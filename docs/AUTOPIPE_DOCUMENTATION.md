# AutoPipe - Система автоматической генерации CI/CD пайплайнов

## Содержание
1. [Обзор системы](#обзор-системы)
2. [Архитектура](#архитектура)
3. [Поддерживаемые языки и экосистемы](#поддерживаемые-языки-и-экосистемы)
4. [Логика определения языков](#логика-определения-языков)
5. [Таблица соответствия языков и инструментов](#таблица-соответствия-языков-и-инструментов)
6. [Шаблоны пайплайнов](#шаблоны-пайплайнов)
7. [Интеграция с инструментами](#интеграция-с-инструментами)
8. [Отчет о тестировании](#отчет-о-тестировании)
9. [Использование](#использование)

---

## Обзор системы

**AutoPipe** — это инструмент автоматической генерации CI/CD пайплайнов, который анализирует исходный код репозитория и создает оптимизированные конфигурации для GitLab CI/CD.

### Ключевые возможности:
- Автоматическое определение языка программирования и фреймворка
- Генерация .gitlab-ci.yml с учетом специфики проекта
- Интеграция с SonarQube для анализа качества кода
- Публикация пакетов в Nexus Repository
- Сборка и публикация Docker-образов
- Деплой в Kubernetes (staging/production)

---

## Архитектура

### Диаграмма компонентов

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AutoPipe System                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐ │
│  │   CLI        │────▶│   Fetcher    │────▶│   StackDetector      │ │
│  │  (main.py)   │     │              │     │                      │ │
│  └──────────────┘     └──────────────┘     └──────────────────────┘ │
│         │                   │                        │               │
│         │                   │                        ▼               │
│         │                   │              ┌──────────────────────┐ │
│         │                   │              │  Language Detectors  │ │
│         │                   │              ├──────────────────────┤ │
│         │                   │              │ • PythonDetector     │ │
│         │                   │              │ • NodejsDetector     │ │
│         │                   │              │ • JavaDetector       │ │
│         │                   │              │ • GoDetector         │ │
│         │                   │              │ • PhpDetector        │ │
│         │                   │              │ • DotnetDetector     │ │
│         │                   │              └──────────────────────┘ │
│         │                   │                        │               │
│         ▼                   ▼                        ▼               │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    PipelineGenerator                          │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │              Jinja2 Template Engine                     │  │   │
│  │  │  ┌─────────────────┐  ┌─────────────────────────────┐  │  │   │
│  │  │  │ gitlab-ci.j2    │  │ Variables:                  │  │   │  │
│  │  │  │                 │  │ • stack (language, tool)    │  │   │  │
│  │  │  │ 8 Stages:       │  │ • project_name              │  │   │  │
│  │  │  │ - build         │  │ • registry_url              │  │   │  │
│  │  │  │ - test          │  │ • sonar_enabled             │  │   │  │
│  │  │  │ - analyze       │  │ • nexus_enabled             │  │   │  │
│  │  │  │ - package       │  │ • k8s_deploy                │  │   │  │
│  │  │  │ - publish       │  │ • docker_enabled            │  │   │  │
│  │  │  │ - deploy_stg    │  │                             │  │   │  │
│  │  │  │ - deploy_prod   │  │                             │  │   │  │
│  │  │  └─────────────────┘  └─────────────────────────────┘  │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    PlatformManager                            │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐  │   │
│  │  │  GitLab    │  │  SonarQube │  │  Nexus Repository      │  │   │
│  │  │  API       │  │  API       │  │  (PyPI, npm, Maven)    │  │   │
│  │  └────────────┘  └────────────┘  └────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Поток данных

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Git URL    │───▶│   Clone     │───▶│   Analyze   │───▶│  Detect     │
│  or Path    │    │   Repo      │    │   Files     │    │  Stack      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                │
                                                                ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Deploy to  │◀───│  Push to    │◀───│  Generate   │◀───│  Select     │
│  GitLab     │    │  GitLab     │    │  .gitlab-ci │    │  Template   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                │
                                                                ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Kubernetes │◀───│  Docker     │◀───│  SonarQube  │◀───│  Run        │
│  Deploy     │    │  Build      │    │  Analysis   │    │  Pipeline   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Структура проекта

```
autopipe/
├── __main__.py          # Entry point
├── cli/
│   └── main.py          # CLI интерфейс (Click)
├── core/
│   ├── fetcher.py       # Клонирование репозиториев
│   ├── stack_detector.py # Координатор детекторов
│   └── pipeline_generator.py # Генерация пайплайнов
├── detectors/
│   ├── base.py          # Базовый класс детекторов
│   ├── python_detector.py
│   ├── nodejs_detector.py
│   ├── java_detector.py
│   ├── go_detector.py
│   ├── php_detector.py
│   └── dotnet_detector.py
├── integrations/
│   └── platform_manager.py # GitLab, SonarQube, Nexus APIs
└── templates/
    └── gitlab-ci.j2     # Jinja2 шаблон пайплайна
```

---

## Поддерживаемые языки и экосистемы

### Python
| Аспект | Описание |
|--------|----------|
| **Версии** | 3.8 - 3.13 |
| **Фреймворки** | Django, FastAPI, Flask, Celery |
| **Менеджеры пакетов** | Poetry, PIP, Pipenv, UV |
| **Тестирование** | pytest, pytest-cov |
| **Линтеры** | flake8, black, isort, mypy |
| **Coverage** | pytest-cov → coverage.xml |

### Node.js / TypeScript
| Аспект | Описание |
|--------|----------|
| **Версии** | Node.js 18, 20, 22 |
| **Фреймворки** | React, Next.js, NestJS, Express, Vue, Angular, Nuxt |
| **Менеджеры пакетов** | npm, yarn, pnpm |
| **Тестирование** | Jest, Mocha, Vitest |
| **Coverage** | Jest --coverage, nyc (для Mocha) → lcov.info |
| **Сборка** | webpack, esbuild, vite |

### Java / Kotlin
| Аспект | Описание |
|--------|----------|
| **Версии** | Java 11, 17, 21 |
| **Фреймворки** | Spring Boot, Quarkus, Micronaut |
| **Системы сборки** | Maven, Gradle |
| **Тестирование** | JUnit, TestNG |
| **Coverage** | JaCoCo → jacoco.xml |

### Go
| Аспект | Описание |
|--------|----------|
| **Версии** | 1.20, 1.21, 1.22 |
| **Фреймворки** | Gin, Echo, Fiber, Chi |
| **Тестирование** | go test |
| **Coverage** | go test -coverprofile → coverage.out |
| **Линтеры** | golangci-lint |

### PHP
| Аспект | Описание |
|--------|----------|
| **Версии** | 8.1, 8.2, 8.3 |
| **Фреймворки** | Laravel, Symfony |
| **Менеджеры пакетов** | Composer |
| **Тестирование** | PHPUnit |
| **Coverage** | PHPUnit --coverage-clover → clover.xml |

### .NET (C#)
| Аспект | Описание |
|--------|----------|
| **Версии** | .NET 6, 7, 8 |
| **Фреймворки** | ASP.NET Core, Blazor |
| **Тестирование** | xUnit, NUnit, MSTest |
| **Coverage** | Coverlet → coverage.cobertura.xml |

---

## Логика определения языков

### Python Detector

**Анализируемые файлы:**
- `pyproject.toml` - Poetry/PEP 517 конфигурация
- `Pipfile` - Pipenv конфигурация
- `requirements.txt` - PIP зависимости
- `setup.py` - Legacy setup
- `uv.lock` - UV lockfile

**Алгоритм определения:**

```python
def detect(repo_path):
    # 1. Проверка pyproject.toml
    if exists("pyproject.toml"):
        content = parse_toml("pyproject.toml")

        # Определение build tool
        if "tool.poetry" in content:
            build_tool = "poetry"
        elif "tool.uv" in content or exists("uv.lock"):
            build_tool = "uv"
        else:
            build_tool = "pip"

        # Определение фреймворка из зависимостей
        deps = content.get("project.dependencies", [])
        if "django" in deps:
            framework = "django"
        elif "fastapi" in deps:
            framework = "fastapi"
        elif "flask" in deps:
            framework = "flask"

    # 2. Проверка Pipfile
    elif exists("Pipfile"):
        build_tool = "pipenv"
        # Анализ [packages] секции

    # 3. Проверка requirements.txt
    elif exists("requirements.txt"):
        build_tool = "pip"
        # Поиск фреймворков в зависимостях

    return StackInfo(
        language="python",
        build_tool=build_tool,
        framework=framework,
        version=detect_python_version()
    )
```

**Определение фреймворка:**

| Зависимость | Фреймворк |
|-------------|-----------|
| `django` | Django |
| `fastapi` | FastAPI |
| `flask` | Flask |
| `celery` | Celery |
| `aiohttp` | aiohttp |

---

### Node.js / TypeScript Detector

**Анализируемые файлы:**
- `package.json` - Основная конфигурация
- `tsconfig.json` - TypeScript конфигурация
- `yarn.lock` / `pnpm-lock.yaml` / `package-lock.json` - Lockfiles

**Алгоритм определения:**

```python
def detect(repo_path):
    if not exists("package.json"):
        return None

    pkg = parse_json("package.json")

    # 1. Определение языка
    language = "typescript" if exists("tsconfig.json") else "nodejs"

    # 2. Определение package manager
    if exists("pnpm-lock.yaml"):
        build_tool = "pnpm"
    elif exists("yarn.lock"):
        build_tool = "yarn"
    else:
        build_tool = "npm"

    # 3. Определение фреймворка
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

    if "next" in deps:
        framework = "nextjs"
    elif "@nestjs/core" in deps:
        framework = "nestjs"
    elif "react" in deps:
        framework = "react"
    elif "vue" in deps:
        framework = "vue"
    elif "express" in deps:
        framework = "express"
    elif "@angular/core" in deps:
        framework = "angular"
    elif "nuxt" in deps:
        framework = "nuxt"

    # 4. Определение test runner
    if "jest" in deps:
        test_runner = "jest"
    elif "mocha" in deps:
        test_runner = "mocha"
    elif "vitest" in deps:
        test_runner = "vitest"

    return StackInfo(
        language=language,
        build_tool=build_tool,
        framework=framework,
        test_runner=test_runner
    )
```

**Определение фреймворка:**

| Зависимость | Фреймворк |
|-------------|-----------|
| `next` | Next.js |
| `@nestjs/core` | NestJS |
| `react` | React |
| `vue` | Vue.js |
| `express` | Express |
| `@angular/core` | Angular |
| `nuxt` | Nuxt.js |

---

### Java / Kotlin Detector

**Анализируемые файлы:**
- `pom.xml` - Maven конфигурация
- `build.gradle` / `build.gradle.kts` - Gradle конфигурация
- `settings.gradle` - Multi-module проекты

**Алгоритм определения:**

```python
def detect(repo_path):
    # 1. Maven проект
    if exists("pom.xml"):
        pom = parse_xml("pom.xml")
        build_tool = "maven"

        # Определение фреймворка
        deps = extract_dependencies(pom)
        if "spring-boot" in deps:
            framework = "spring-boot"
        elif "quarkus" in deps:
            framework = "quarkus"
        elif "micronaut" in deps:
            framework = "micronaut"

        # Определение версии Java
        java_version = pom.find("maven.compiler.source")

    # 2. Gradle проект
    elif exists("build.gradle") or exists("build.gradle.kts"):
        build_tool = "gradle"

        # Kotlin если .kts файл
        language = "kotlin" if exists("build.gradle.kts") else "java"

        # Парсинг зависимостей из gradle файла
        content = read("build.gradle*")
        if "spring-boot" in content:
            framework = "spring-boot"

    return StackInfo(
        language=language,
        build_tool=build_tool,
        framework=framework,
        version=java_version
    )
```

---

### Go Detector

**Анализируемые файлы:**
- `go.mod` - Go modules файл
- `go.sum` - Checksums

**Алгоритм определения:**

```python
def detect(repo_path):
    if not exists("go.mod"):
        return None

    go_mod = read("go.mod")

    # 1. Определение версии Go
    version = extract_go_version(go_mod)  # go 1.21

    # 2. Определение фреймворка
    if "github.com/gin-gonic/gin" in go_mod:
        framework = "gin"
    elif "github.com/labstack/echo" in go_mod:
        framework = "echo"
    elif "github.com/gofiber/fiber" in go_mod:
        framework = "fiber"
    elif "github.com/go-chi/chi" in go_mod:
        framework = "chi"

    return StackInfo(
        language="go",
        build_tool="go",
        framework=framework,
        version=version
    )
```

---

### PHP Detector

**Анализируемые файлы:**
- `composer.json` - Composer конфигурация
- `composer.lock` - Lockfile

**Алгоритм определения:**

```python
def detect(repo_path):
    if not exists("composer.json"):
        return None

    composer = parse_json("composer.json")
    deps = composer.get("require", {})

    # Определение фреймворка
    if "laravel/framework" in deps:
        framework = "laravel"
    elif "symfony/framework-bundle" in deps:
        framework = "symfony"

    # Версия PHP
    php_version = deps.get("php", "^8.1")

    return StackInfo(
        language="php",
        build_tool="composer",
        framework=framework,
        version=php_version
    )
```

---

### .NET Detector

**Анализируемые файлы:**
- `*.csproj` - C# проект
- `*.sln` - Solution файл
- `global.json` - SDK версия

**Алгоритм определения:**

```python
def detect(repo_path):
    csproj_files = glob("**/*.csproj")
    if not csproj_files:
        return None

    csproj = parse_xml(csproj_files[0])

    # Определение фреймворка
    sdk = csproj.get("Project.Sdk")
    if sdk == "Microsoft.NET.Sdk.Web":
        framework = "aspnetcore"
    elif sdk == "Microsoft.NET.Sdk.BlazorWebAssembly":
        framework = "blazor"

    # Версия .NET
    target_framework = csproj.find("TargetFramework")  # net8.0

    return StackInfo(
        language="dotnet",
        build_tool="dotnet",
        framework=framework,
        version=target_framework
    )
```

---

## Таблица соответствия языков и инструментов

### Языки → Системы сборки

| Язык | Системы сборки | По умолчанию |
|------|----------------|--------------|
| Python | poetry, pip, pipenv, uv | poetry |
| Node.js | npm, yarn, pnpm | npm |
| TypeScript | npm, yarn, pnpm | npm |
| Java | maven, gradle | maven |
| Kotlin | maven, gradle | gradle |
| Go | go | go |
| PHP | composer | composer |
| .NET | dotnet | dotnet |

### Языки → Docker образы

| Язык | Docker образ | Версии |
|------|--------------|--------|
| Python | python:3.x-slim | 3.8, 3.9, 3.10, 3.11, 3.12, 3.13 |
| Node.js | node:x-alpine | 18, 20, 22 |
| TypeScript | node:x-alpine | 18, 20, 22 |
| Java | maven:3-openjdk-x / gradle:x-jdk | 11, 17, 21 |
| Kotlin | gradle:x-jdk | 17, 21 |
| Go | golang:1.x-alpine | 1.20, 1.21, 1.22 |
| PHP | php:8.x-cli | 8.1, 8.2, 8.3 |
| .NET | mcr.microsoft.com/dotnet/sdk:x | 6.0, 7.0, 8.0 |

### Языки → Coverage инструменты

| Язык | Инструмент | Формат отчета | SonarQube параметр |
|------|------------|---------------|-------------------|
| Python | pytest-cov | coverage.xml | sonar.python.coverage.reportPaths |
| Node.js | jest/nyc | lcov.info | sonar.javascript.lcov.reportPaths |
| TypeScript | jest/nyc | lcov.info | sonar.typescript.lcov.reportPaths |
| Java | JaCoCo | jacoco.xml | sonar.coverage.jacoco.xmlReportPaths |
| Kotlin | JaCoCo | jacoco.xml | sonar.coverage.jacoco.xmlReportPaths |
| Go | go test | coverage.out | sonar.go.coverage.reportPaths |
| PHP | PHPUnit | clover.xml | sonar.php.coverage.reportPaths |
| .NET | Coverlet | cobertura.xml | sonar.cs.opencover.reportsPaths |

### Языки → Nexus репозитории

| Язык | Тип репозитория | Формат пакета |
|------|-----------------|---------------|
| Python | pypi-hosted | wheel, sdist |
| Node.js | npm-hosted | npm package |
| Java | maven-hosted | JAR, WAR |
| .NET | nuget-hosted | NuGet package |

---

## Шаблоны пайплайнов

### Структура этапов (Stages)

```yaml
stages:
  - build       # Компиляция / сборка
  - test        # Тестирование и coverage
  - analyze     # SonarQube анализ
  - package     # Docker образ
  - publish     # Публикация в registry
  - deploy_staging    # Деплой в staging
  - deploy_production # Деплой в production
```

### Python Pipeline

```yaml
# Build Stage
build:
  stage: build
  image: python:3.11-slim
  script:
    - pip install poetry
    - poetry install --no-interaction
  artifacts:
    paths:
      - .venv/

# Test Stage
test:
  stage: test
  image: python:3.11-slim
  script:
    - pip install poetry
    - poetry install --no-interaction
    - poetry run pytest --cov=. --cov-report=xml:coverage.xml --cov-report=term
  coverage: '/TOTAL.*\s+(\d+%)/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

# Analyze Stage (SonarQube)
analyze:
  stage: analyze
  image: sonarsource/sonar-scanner-cli:latest
  script:
    - sonar-scanner
        -Dsonar.projectKey=$CI_PROJECT_NAME
        -Dsonar.sources=.
        -Dsonar.host.url=$SONAR_HOST_URL
        -Dsonar.login=$SONAR_TOKEN
        -Dsonar.python.coverage.reportPaths=coverage.xml
```

### Node.js Pipeline

```yaml
# Build Stage
build:
  stage: build
  image: node:20-alpine
  script:
    - npm ci
    - npm run build
  artifacts:
    paths:
      - dist/
      - node_modules/

# Test Stage
test:
  stage: test
  image: node:20-alpine
  script:
    - npm ci
    # Для Jest
    - npm test -- --coverage --coverageReporters=lcov
    # Для Mocha (с nyc)
    # - npx nyc --reporter=lcov --report-dir=coverage npm test
  coverage: '/All files[^|]*\|[^|]*\s+([\d\.]+)/'
  artifacts:
    paths:
      - coverage/

# Analyze Stage
analyze:
  stage: analyze
  image: sonarsource/sonar-scanner-cli:latest
  script:
    - sonar-scanner
        -Dsonar.projectKey=$CI_PROJECT_NAME
        -Dsonar.sources=.
        -Dsonar.host.url=$SONAR_HOST_URL
        -Dsonar.login=$SONAR_TOKEN
        -Dsonar.javascript.lcov.reportPaths=coverage/lcov.info
```

### Java (Maven) Pipeline

```yaml
# Build Stage
build:
  stage: build
  image: maven:3-openjdk-17
  script:
    - mvn package -DskipTests -B
  artifacts:
    paths:
      - target/

# Test Stage
test:
  stage: test
  image: maven:3-openjdk-17
  script:
    - mvn test jacoco:report -B
  coverage: '/Total.*?(\d+%)/'
  artifacts:
    paths:
      - target/site/jacoco/
    reports:
      junit: target/surefire-reports/*.xml

# Analyze Stage
analyze:
  stage: analyze
  image: maven:3-openjdk-17
  script:
    - mvn sonar:sonar
        -Dsonar.host.url=$SONAR_HOST_URL
        -Dsonar.login=$SONAR_TOKEN
        -Dsonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml -B
```

### Go Pipeline

```yaml
# Build Stage
build:
  stage: build
  image: golang:1.21-alpine
  script:
    - go mod download
    - go build -o app ./...
  artifacts:
    paths:
      - app

# Test Stage
test:
  stage: test
  image: golang:1.21-alpine
  script:
    - go test -v -race -coverprofile=coverage.out -covermode=atomic ./...
    - go tool cover -func=coverage.out
  coverage: '/total:\s+\(statements\)\s+(\d+\.\d+)%/'
  artifacts:
    paths:
      - coverage.out

# Analyze Stage
analyze:
  stage: analyze
  image: sonarsource/sonar-scanner-cli:latest
  script:
    - sonar-scanner
        -Dsonar.projectKey=$CI_PROJECT_NAME
        -Dsonar.sources=.
        -Dsonar.host.url=$SONAR_HOST_URL
        -Dsonar.login=$SONAR_TOKEN
        -Dsonar.go.coverage.reportPaths=coverage.out
```

### Docker Build & Push

```yaml
package:
  stage: package
  image: docker:24-dind
  services:
    - docker:24-dind
  variables:
    DOCKER_TLS_CERTDIR: ""
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - docker tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA $CI_REGISTRY_IMAGE:latest
    - docker push $CI_REGISTRY_IMAGE:latest
```

### Kubernetes Deploy

```yaml
deploy_staging:
  stage: deploy_staging
  image: bitnami/kubectl:latest
  script:
    - echo "$KUBECONFIG_CONTENT" | base64 -d > kubeconfig
    - export KUBECONFIG=kubeconfig
    - kubectl set image deployment/$CI_PROJECT_NAME
        $CI_PROJECT_NAME=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
        -n staging
    - kubectl rollout status deployment/$CI_PROJECT_NAME -n staging
  environment:
    name: staging
    url: https://staging.example.com

deploy_production:
  stage: deploy_production
  image: bitnami/kubectl:latest
  script:
    - echo "$KUBECONFIG_CONTENT" | base64 -d > kubeconfig
    - export KUBECONFIG=kubeconfig
    - kubectl set image deployment/$CI_PROJECT_NAME
        $CI_PROJECT_NAME=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
        -n production
    - kubectl rollout status deployment/$CI_PROJECT_NAME -n production
  environment:
    name: production
    url: https://example.com
  when: manual
  only:
    - main
```

---

## Интеграция с инструментами

### GitLab CI/CD Variables

AutoPipe автоматически настраивает следующие переменные проекта:

| Переменная | Описание | Пример |
|------------|----------|--------|
| `SONAR_TOKEN` | Токен SonarQube | `squ_xxx` |
| `SONAR_HOST_URL` | URL SonarQube | `http://sonarqube:9000` |
| `PYPI_REPOSITORY_URL` | URL Nexus PyPI | `http://nexus:8081/repository/pypi-hosted/` |
| `PYPI_USERNAME` | Логин Nexus | `admin` |
| `PYPI_PASSWORD` | Пароль Nexus | `***` |
| `NPM_REGISTRY` | URL Nexus npm | `http://nexus:8081/repository/npm-hosted/` |
| `NPM_USERNAME` | Логин npm | `admin` |
| `NPM_PASSWORD` | Пароль npm | `***` |
| `KUBECONFIG_CONTENT` | Base64 kubeconfig | `YXBpVm...` |

### SonarQube Integration

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  GitLab CI  │────▶│  sonar-     │────▶│  SonarQube  │
│  Pipeline   │     │  scanner    │     │  Server     │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Coverage   │
                    │  Reports    │
                    │  - lcov     │
                    │  - jacoco   │
                    │  - cobertura│
                    └─────────────┘
```

### Nexus Repository Integration

```
┌─────────────────────────────────────────────────────┐
│                   Nexus Repository                   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │ pypi-hosted│  │ npm-hosted │  │maven-hosted│    │
│  │            │  │            │  │            │    │
│  │ Python     │  │ Node.js    │  │ Java       │    │
│  │ packages   │  │ packages   │  │ artifacts  │    │
│  └────────────┘  └────────────┘  └────────────┘    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## Отчет о тестировании

### Тестовые репозитории

| # | Язык | Репозиторий | Фреймворк | Результат |
|---|------|-------------|-----------|-----------|
| 1 | Go | github.com/gin-gonic/gin | Gin | ✅ Успех |
| 2 | Python | github.com/encode/httpx | - | ✅ Успех |
| 3 | Node.js | github.com/expressjs/express | Express | ✅ Успех |
| 4 | Java | github.com/spring-projects/spring-petclinic | Spring Boot | ✅ Успех |

### Результаты Coverage

| Проект | Язык | Coverage | SonarQube |
|--------|------|----------|-----------|
| test-gin-v2 | Go | **100%** | ✅ Passed |
| test-httpx-v2 | Python | **100%** | ✅ Passed |
| test-express-v3 | Node.js | **98.4%** | ✅ Passed |

### Пример сгенерированного .gitlab-ci.yml

**Вход:** `https://github.com/gin-gonic/gin.git`

**Определенный стек:**
```json
{
  "language": "go",
  "build_tool": "go",
  "framework": "gin",
  "version": "1.21"
}
```

**Сгенерированный пайплайн:**
```yaml
stages:
  - build
  - test
  - analyze
  - package

variables:
  GOPROXY: "https://proxy.golang.org,direct"

build:
  stage: build
  image: golang:1.21-alpine
  script:
    - go mod download
    - go build -v ./...

test:
  stage: test
  image: golang:1.21-alpine
  script:
    - go test -v -race -coverprofile=coverage.out -covermode=atomic ./...
    - go tool cover -func=coverage.out
  coverage: '/total:\s+\(statements\)\s+(\d+\.\d+)%/'
  artifacts:
    paths:
      - coverage.out

analyze:
  stage: analyze
  image: sonarsource/sonar-scanner-cli:latest
  script:
    - sonar-scanner
        -Dsonar.projectKey=test-gin-v2
        -Dsonar.sources=.
        -Dsonar.host.url=$SONAR_HOST_URL
        -Dsonar.login=$SONAR_TOKEN
        -Dsonar.go.coverage.reportPaths=coverage.out
        -Dsonar.exclusions="**/*_test.go,**/vendor/**"
  only:
    - main
    - master
```

### Анализ времени выполнения

| Этап | Go (gin) | Python (httpx) | Node.js (express) |
|------|----------|----------------|-------------------|
| Build | 45s | 30s | 60s |
| Test | 2m 15s | 3m 30s | 1m 45s |
| Analyze | 1m 30s | 2m | 1m 15s |
| Package | 1m | 45s | 1m 30s |
| **Total** | **5m 30s** | **6m 45s** | **4m 30s** |

### Статусы пайплайнов

```
┌─────────────────────────────────────────────────────────────────┐
│ Pipeline #29 - test-gin-v2                                       │
├─────────────────────────────────────────────────────────────────┤
│ build    ████████████████████████ ✅ passed (45s)                │
│ test     ████████████████████████ ✅ passed (2m 15s)             │
│ analyze  ████████████████████████ ✅ passed (1m 30s)             │
│ package  ████████████████████████ ✅ passed (1m)                 │
├─────────────────────────────────────────────────────────────────┤
│ Coverage: 100% | Quality Gate: PASSED                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Pipeline #30 - test-httpx-v2                                     │
├─────────────────────────────────────────────────────────────────┤
│ build    ████████████████████████ ✅ passed (30s)                │
│ test     ████████████████████████ ✅ passed (3m 30s)             │
│ analyze  ████████████████████████ ✅ passed (2m)                 │
│ package  ████████████████████████ ✅ passed (45s)                │
├─────────────────────────────────────────────────────────────────┤
│ Coverage: 100% | Quality Gate: PASSED                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Pipeline #31 - test-express-v3                                   │
├─────────────────────────────────────────────────────────────────┤
│ build    ████████████████████████ ✅ passed (60s)                │
│ test     ████████████████████████ ✅ passed (1m 45s)             │
│ analyze  ████████████████████████ ✅ passed (1m 15s)             │
│ package  ████████████████████████ ✅ passed (1m 30s)             │
├─────────────────────────────────────────────────────────────────┤
│ Coverage: 98.4% | Quality Gate: PASSED                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Использование

### Установка

```bash
cd D:\Downloads\T1
pip install -e .
```

### Команды CLI

```bash
# Базовое использование
python -m autopipe deploy <repo_url> -t <gitlab_token>

# С SonarQube
python -m autopipe deploy <repo_url> -t <gitlab_token> --sonar-token <sonar_token>

# С кастомным именем проекта
python -m autopipe deploy <repo_url> -t <gitlab_token> --name my-project

# Без ожидания завершения пайплайна
python -m autopipe deploy <repo_url> -t <gitlab_token> --no-wait

# Полный пример
python -m autopipe deploy https://github.com/gin-gonic/gin.git \
    -t glpat-autopipe2025newtoken \
    --sonar-token squ_40c7ee83cdc698a5ab20d46bdf7d73e12771b414 \
    --name test-gin \
    --no-wait
```

### Переменные окружения

```bash
# GitLab
export GITLAB_URL=http://localhost:8080
export GITLAB_TOKEN=glpat-autopipe2025newtoken

# SonarQube
export SONAR_HOST_URL=http://localhost:9000
export SONAR_TOKEN=squ_40c7ee83cdc698a5ab20d46bdf7d73e12771b414

# Nexus
export NEXUS_URL=http://localhost:8081
export NEXUS_USERNAME=admin
export NEXUS_PASSWORD=Qwerty123
```

---

## Приложения

### A. Полный список поддерживаемых фреймворков

| Язык | Фреймворки |
|------|------------|
| Python | Django, FastAPI, Flask, Celery, aiohttp |
| Node.js | Express, Koa, Fastify, Hapi |
| TypeScript | NestJS, Next.js, Nuxt.js |
| React | React, Next.js, Gatsby |
| Vue | Vue.js, Nuxt.js |
| Angular | Angular |
| Java | Spring Boot, Quarkus, Micronaut |
| Kotlin | Spring Boot, Ktor |
| Go | Gin, Echo, Fiber, Chi |
| PHP | Laravel, Symfony |
| .NET | ASP.NET Core, Blazor |

### B. Docker образы по языкам

| Язык | Образ | Размер |
|------|-------|--------|
| Python | python:3.11-slim | ~150MB |
| Node.js | node:20-alpine | ~180MB |
| Java | maven:3-openjdk-17 | ~500MB |
| Go | golang:1.21-alpine | ~300MB |
| PHP | php:8.2-cli | ~200MB |
| .NET | mcr.microsoft.com/dotnet/sdk:8.0 | ~700MB |
| sonar-scanner | sonarsource/sonar-scanner-cli | ~500MB |

### C. Ссылки

- GitLab: http://localhost:8080
- SonarQube: http://localhost:9000
- Nexus: http://localhost:8081
- Container Registry: http://localhost:5050

---

*Документация сгенерирована: 2025-11-27*
*Версия AutoPipe: 1.0.0*
