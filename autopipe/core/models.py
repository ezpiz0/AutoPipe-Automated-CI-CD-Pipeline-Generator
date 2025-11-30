from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Language(str, Enum):
    JAVA = "java"
    KOTLIN = "kotlin"
    PYTHON = "python"
    NODEJS = "nodejs"
    TYPESCRIPT = "typescript"
    GO = "go"
    DOTNET = "dotnet"
    PHP = "php"
    UNKNOWN = "unknown"

class Framework(str, Enum):
    # Java/Kotlin
    SPRING_BOOT = "spring_boot"
    QUARKUS = "quarkus"
    MICRONAUT = "micronaut"
    KTOR = "ktor"
    # Python
    DJANGO = "django"
    FASTAPI = "fastapi"
    FLASK = "flask"
    AIOHTTP = "aiohttp"
    # Node.js/TypeScript
    REACT = "react"
    NEXTJS = "nextjs"
    NESTJS = "nestjs"
    EXPRESS = "express"
    VUE = "vue"
    NUXT = "nuxt"
    ANGULAR = "angular"
    # PHP
    LARAVEL = "laravel"
    SYMFONY = "symfony"
    YII = "yii"
    CODEIGNITER = "codeigniter"
    # .NET
    ASPNET_CORE = "aspnet_core"
    BLAZOR = "blazor"
    # Go
    GIN = "gin"
    ECHO = "echo"
    FIBER = "fiber"
    NONE = "none"

class BuildTool(str, Enum):
    MAVEN = "maven"
    GRADLE = "gradle"
    ANT = "ant"
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    POETRY = "poetry"
    PIP = "pip"
    PIPENV = "pipenv"
    CONDA = "conda"
    UV = "uv"
    GO_MOD = "go_mod"
    DOTNET_CLI = "dotnet_cli"
    COMPOSER = "composer"
    NONE = "none"

class Dependency(BaseModel):
    name: str
    version: str
    is_dev: bool = False

class ProjectMetadata(BaseModel):
    name: str
    version: str = "0.1.0"
    description: Optional[str] = None
    
class DetectedStack(BaseModel):
    language: Language
    framework: Framework = Framework.NONE
    build_tool: BuildTool = BuildTool.NONE
    language_version: str = "latest"
    dependencies: List[Dependency] = Field(default_factory=list)

    # Specific configs
    java_version: Optional[str] = None
    kotlin_version: Optional[str] = None
    dotnet_framework_version: Optional[str] = None # e.g. net8.0
    node_version: Optional[str] = None
    python_version: Optional[str] = None
    go_version: Optional[str] = None
    php_version: Optional[str] = None

    # Project structure info (for non-standard layouts)
    project_root: Optional[str] = None  # Relative path from repo root to project
    source_dir: Optional[str] = None    # Source directory (e.g., "src", "app", "lib")
    config_file: Optional[str] = None   # Main config file path (e.g., "pom.xml", "package.json")
    entrypoint: Optional[str] = None    # Main entry point (e.g., "main.py", "app.js")
    test_dir: Optional[str] = None      # Test directory
    build_output_dir: Optional[str] = None  # Build output (e.g., "dist", "build", "target")

    # Multi-module support
    is_multi_module: bool = False
    parent_project: Optional[str] = None  # For child modules
    modules: List[str] = Field(default_factory=list)  # For parent projects

    # Additional detected info
    has_dockerfile: bool = False
    has_tests: bool = False
    test_framework: Optional[str] = None
    package_manager_lock: Optional[str] = None  # Lock file name for caching

class ProjectContext(BaseModel):
    metadata: ProjectMetadata
    stack: DetectedStack
    root_path: str
    source_path: str = "." # Path to source code relative to root
    docker_context: str = "."

    # For monorepos or complex structures
    is_monorepo: bool = False
    detected_projects: List[DetectedStack] = Field(default_factory=list)  # All detected sub-projects

    extra_vars: Dict[str, Any] = Field(default_factory=dict)
