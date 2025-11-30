import re
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

# Compatible TOML import
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

from autopipe.core.interfaces import Detector
from autopipe.core.models import DetectedStack, Language, Framework, BuildTool, Dependency


class PythonDetector(Detector):
    """
    Enhanced Python detector supporting:
    - pyproject.toml (Poetry, PEP 621, Flit, PDM, Hatch)
    - requirements.txt (various locations and naming)
    - Pipfile (Pipenv)
    - setup.py / setup.cfg
    - environment.yml (Conda)
    - uv.lock (UV package manager)
    - Various project structures
    """

    # Common entrypoint patterns
    ENTRYPOINT_PATTERNS = [
        'main.py', 'app.py', 'run.py', 'server.py', 'wsgi.py', 'asgi.py',
        'manage.py',  # Django
        'application.py', '__main__.py'
    ]

    def detect(self, project_root: Path) -> Optional[DetectedStack]:
        # Priority order for config files
        pyproject_path = project_root / "pyproject.toml"
        pipfile_path = project_root / "Pipfile"
        setup_py_path = project_root / "setup.py"
        setup_cfg_path = project_root / "setup.cfg"
        conda_env_path = project_root / "environment.yml"
        conda_env_yaml_path = project_root / "environment.yaml"

        # Check for requirements files in various locations
        requirements_files = self._find_requirements_files(project_root)

        if pyproject_path.exists() and tomllib:
            return self._analyze_pyproject(pyproject_path, project_root)
        elif pipfile_path.exists():
            return self._analyze_pipfile(pipfile_path, project_root)
        elif conda_env_path.exists() or conda_env_yaml_path.exists():
            env_file = conda_env_path if conda_env_path.exists() else conda_env_yaml_path
            return self._analyze_conda(env_file, project_root)
        elif requirements_files:
            return self._analyze_requirements(requirements_files[0], project_root)
        elif setup_py_path.exists() or setup_cfg_path.exists():
            return self._analyze_setup(project_root)

        return None

    def _find_requirements_files(self, project_root: Path) -> List[Path]:
        """Find all requirements files in common locations."""
        patterns = [
            "requirements.txt",
            "requirements/*.txt",
            "requirements-*.txt",
            "requirements_*.txt",
            "reqs.txt",
            "deps.txt",
            "dependencies.txt",
        ]

        found = []
        for pattern in patterns:
            found.extend(project_root.glob(pattern))

        # Sort by priority (main requirements.txt first)
        def sort_key(p):
            name = p.name.lower()
            if name == 'requirements.txt':
                return 0
            if 'prod' in name or 'base' in name:
                return 1
            if 'dev' in name or 'test' in name:
                return 3
            return 2

        return sorted(found, key=sort_key)

    def _analyze_pyproject(self, path: Path, project_root: Path) -> DetectedStack:
        """Analyze pyproject.toml for project configuration."""
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)

            # Detect build tool
            build_tool, dependencies = self._detect_build_tool_pyproject(data, project_root)

            # Detect framework
            framework = self._detect_framework(dependencies)

            # Detect Python version
            python_version = self._detect_python_version_pyproject(data, build_tool)

            # Detect entrypoint
            entrypoint = self._detect_entrypoint_pyproject(data, project_root)

            # Detect test framework
            test_framework = self._detect_test_framework(dependencies)

            # Detect source dir
            source_dir = self._detect_source_dir_pyproject(data, project_root)

            # Detect test dir
            test_dir = self.detect_test_dir(project_root)

            # Detect lock file
            lock_file = self._detect_lock_file(project_root, build_tool)

            # Check for existing Dockerfile
            has_dockerfile = self.detect_existing_dockerfile(project_root)

            # Extract project name
            project_name = data.get('project', {}).get('name') or \
                          data.get('tool', {}).get('poetry', {}).get('name')

            return DetectedStack(
                language=Language.PYTHON,
                framework=framework,
                build_tool=build_tool,
                language_version=python_version,
                python_version=python_version,
                config_file='pyproject.toml',
                source_dir=source_dir,
                test_dir=test_dir,
                entrypoint=entrypoint,
                dependencies=dependencies,
                has_dockerfile=has_dockerfile,
                has_tests=test_dir is not None or test_framework is not None,
                test_framework=test_framework,
                package_manager_lock=lock_file
            )

        except Exception as e:
            return DetectedStack(
                language=Language.PYTHON,
                build_tool=BuildTool.PIP,
                python_version="3.11",
                language_version="3.11"
            )

    def _detect_build_tool_pyproject(self, data: dict, project_root: Path) -> tuple:
        """Detect build tool and extract dependencies from pyproject.toml."""
        dependencies = []

        # Check for Poetry
        tool_poetry = data.get("tool", {}).get("poetry", {})
        if tool_poetry:
            deps = tool_poetry.get("dependencies", {})
            dev_deps = tool_poetry.get("group", {}).get("dev", {}).get("dependencies", {})
            if not dev_deps:
                dev_deps = tool_poetry.get("dev-dependencies", {})

            dependencies = self._parse_poetry_deps(deps, False) + \
                          self._parse_poetry_deps(dev_deps, True)
            return BuildTool.POETRY, dependencies

        # Check for PDM
        if data.get("tool", {}).get("pdm"):
            deps = data.get("project", {}).get("dependencies", [])
            dependencies = self._parse_pep621_deps(deps)
            return BuildTool.PIP, dependencies  # PDM uses pip-compatible format

        # Check for Hatch
        if data.get("tool", {}).get("hatch"):
            deps = data.get("project", {}).get("dependencies", [])
            dependencies = self._parse_pep621_deps(deps)
            return BuildTool.PIP, dependencies

        # Check for Flit
        if data.get("tool", {}).get("flit"):
            deps = data.get("project", {}).get("dependencies", [])
            dependencies = self._parse_pep621_deps(deps)
            return BuildTool.PIP, dependencies

        # Check for UV
        if (project_root / "uv.lock").exists():
            deps = data.get("project", {}).get("dependencies", [])
            dependencies = self._parse_pep621_deps(deps)
            return BuildTool.UV, dependencies

        # Standard PEP 621 (project.dependencies)
        if "project" in data:
            deps = data.get("project", {}).get("dependencies", [])
            opt_deps = data.get("project", {}).get("optional-dependencies", {})
            dependencies = self._parse_pep621_deps(deps)
            for group_deps in opt_deps.values():
                dependencies.extend(self._parse_pep621_deps(group_deps, is_dev=True))
            return BuildTool.PIP, dependencies

        return BuildTool.PIP, dependencies

    def _parse_poetry_deps(self, deps: dict, is_dev: bool) -> List[Dependency]:
        """Parse Poetry-style dependencies."""
        result = []
        for name, version in deps.items():
            if name.lower() == 'python':
                continue
            if isinstance(version, dict):
                version = version.get('version', 'latest')
            result.append(Dependency(
                name=name,
                version=str(version).replace('^', '').replace('~', ''),
                is_dev=is_dev
            ))
        return result

    def _parse_pep621_deps(self, deps: list, is_dev: bool = False) -> List[Dependency]:
        """Parse PEP 621 style dependencies list."""
        result = []
        for dep in deps:
            if isinstance(dep, str):
                # Parse "package>=1.0,<2.0" style
                match = re.match(r'^([a-zA-Z0-9_-]+)(.*)$', dep)
                if match:
                    name = match.group(1)
                    version = match.group(2).strip() or 'latest'
                    result.append(Dependency(name=name, version=version, is_dev=is_dev))
        return result

    def _detect_python_version_pyproject(self, data: dict, build_tool: BuildTool) -> str:
        """Extract Python version from pyproject.toml."""
        detected_version = None

        # Poetry style
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        if "python" in poetry_deps:
            version = str(poetry_deps["python"])
            match = re.search(r'(\d+\.\d+)', version)
            if match:
                detected_version = match.group(1)

        # PEP 621 style
        if not detected_version:
            requires_python = data.get("project", {}).get("requires-python", "")
            if requires_python:
                match = re.search(r'(\d+\.\d+)', requires_python)
                if match:
                    detected_version = match.group(1)

        # If version is too old (< 3.11), use 3.12 for better compatibility
        if detected_version:
            try:
                major, minor = map(int, detected_version.split('.'))
                if major == 3 and minor < 11:
                    return "3.12"  # Use modern Python for older requirements
                return detected_version
            except ValueError:
                pass

        return "3.12"  # Default to latest stable

    def _detect_entrypoint_pyproject(self, data: dict, project_root: Path) -> Optional[str]:
        """Detect entrypoint from pyproject.toml or filesystem."""
        # Poetry scripts
        scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
        if scripts:
            # Return first script's module path
            first_script = list(scripts.values())[0]
            if ':' in first_script:
                module = first_script.split(':')[0]
                return module.replace('.', '/') + '.py'

        # PEP 621 scripts
        scripts = data.get("project", {}).get("scripts", {})
        if scripts:
            first_script = list(scripts.values())[0]
            if ':' in first_script:
                module = first_script.split(':')[0]
                return module.replace('.', '/') + '.py'

        # Fallback to filesystem detection
        return self._detect_entrypoint_filesystem(project_root)

    def _detect_entrypoint_filesystem(self, project_root: Path) -> Optional[str]:
        """Detect entrypoint from common file patterns."""
        # Check root directory first
        for pattern in self.ENTRYPOINT_PATTERNS:
            if (project_root / pattern).exists():
                return pattern

        # Check common source directories
        for src_dir in ['src', 'app', 'lib', project_root.name]:
            src_path = project_root / src_dir
            if src_path.is_dir():
                for pattern in self.ENTRYPOINT_PATTERNS:
                    if (src_path / pattern).exists():
                        return f"{src_dir}/{pattern}"
                # Check for __main__.py
                if (src_path / '__main__.py').exists():
                    return f"{src_dir}/__main__.py"

        return None

    def _detect_source_dir_pyproject(self, data: dict, project_root: Path) -> Optional[str]:
        """Detect source directory from pyproject.toml or filesystem."""
        # Check tool.setuptools.packages
        packages = data.get("tool", {}).get("setuptools", {}).get("packages", {})
        if isinstance(packages, dict) and "find" in packages:
            where = packages["find"].get("where", ["."])
            if where and where[0] != ".":
                return where[0]

        # Check Poetry package config
        poetry_packages = data.get("tool", {}).get("poetry", {}).get("packages", [])
        if poetry_packages:
            first_pkg = poetry_packages[0]
            if isinstance(first_pkg, dict):
                include = first_pkg.get("from", first_pkg.get("include", ""))
                if include:
                    return include

        # Fallback to filesystem detection
        return self.detect_source_dir(project_root)

    def _detect_lock_file(self, project_root: Path, build_tool: BuildTool) -> Optional[str]:
        """Detect lock file based on build tool."""
        lock_files = {
            BuildTool.POETRY: 'poetry.lock',
            BuildTool.PIPENV: 'Pipfile.lock',
            BuildTool.UV: 'uv.lock',
            BuildTool.PIP: 'requirements.txt',  # Not really a lock, but used for caching
        }

        expected_lock = lock_files.get(build_tool)
        if expected_lock and (project_root / expected_lock).exists():
            return expected_lock

        # Check for any lock file
        for lock in ['poetry.lock', 'Pipfile.lock', 'uv.lock', 'pdm.lock']:
            if (project_root / lock).exists():
                return lock

        return None

    def _analyze_pipfile(self, path: Path, project_root: Path) -> DetectedStack:
        """Analyze Pipfile for project configuration."""
        try:
            content = path.read_text(encoding='utf-8')
            dependencies = []

            # Parse Pipfile (TOML-like format)
            # Simple parsing for packages section
            in_packages = False
            in_dev = False

            for line in content.split('\n'):
                line = line.strip()
                if line == '[packages]':
                    in_packages = True
                    in_dev = False
                elif line == '[dev-packages]':
                    in_packages = True
                    in_dev = True
                elif line.startswith('['):
                    in_packages = False
                elif in_packages and '=' in line:
                    parts = line.split('=', 1)
                    name = parts[0].strip().strip('"\'')
                    version = parts[1].strip().strip('"\'')
                    if name.lower() != 'python_version':
                        dependencies.append(Dependency(name=name, version=version, is_dev=in_dev))

            # Detect Python version
            python_version = "3.11"
            match = re.search(r'python_version\s*=\s*["\'](\d+\.\d+)["\']', content)
            if match:
                python_version = match.group(1)

            framework = self._detect_framework(dependencies)
            test_framework = self._detect_test_framework(dependencies)
            entrypoint = self._detect_entrypoint_filesystem(project_root)

            return DetectedStack(
                language=Language.PYTHON,
                framework=framework,
                build_tool=BuildTool.PIPENV,
                language_version=python_version,
                python_version=python_version,
                config_file='Pipfile',
                source_dir=self.detect_source_dir(project_root),
                test_dir=self.detect_test_dir(project_root),
                entrypoint=entrypoint,
                dependencies=dependencies,
                has_dockerfile=self.detect_existing_dockerfile(project_root),
                has_tests=self.detect_test_dir(project_root) is not None,
                test_framework=test_framework,
                package_manager_lock='Pipfile.lock' if (project_root / 'Pipfile.lock').exists() else None
            )

        except Exception:
            return DetectedStack(
                language=Language.PYTHON,
                build_tool=BuildTool.PIPENV,
                python_version="3.11",
                language_version="3.11"
            )

    def _analyze_conda(self, path: Path, project_root: Path) -> DetectedStack:
        """Analyze Conda environment.yml."""
        try:
            # Simple YAML parsing without external dependency
            content = path.read_text(encoding='utf-8')
            dependencies = []
            python_version = "3.11"

            # Very basic YAML parsing for dependencies
            in_deps = False
            for line in content.split('\n'):
                stripped = line.strip()
                if stripped.startswith('dependencies:'):
                    in_deps = True
                    continue
                if in_deps:
                    if stripped.startswith('- '):
                        dep = stripped[2:].strip()
                        if dep.startswith('python'):
                            match = re.search(r'python[=<>]*(\d+\.\d+)', dep)
                            if match:
                                python_version = match.group(1)
                        elif not dep.startswith('pip:'):
                            parts = re.split(r'[=<>]', dep)
                            name = parts[0]
                            version = parts[1] if len(parts) > 1 else 'latest'
                            dependencies.append(Dependency(name=name, version=version, is_dev=False))
                    elif not line.startswith(' ') and not line.startswith('\t'):
                        in_deps = False

            framework = self._detect_framework(dependencies)

            return DetectedStack(
                language=Language.PYTHON,
                framework=framework,
                build_tool=BuildTool.CONDA,
                language_version=python_version,
                python_version=python_version,
                config_file=path.name,
                source_dir=self.detect_source_dir(project_root),
                test_dir=self.detect_test_dir(project_root),
                entrypoint=self._detect_entrypoint_filesystem(project_root),
                dependencies=dependencies,
                has_dockerfile=self.detect_existing_dockerfile(project_root),
                package_manager_lock=path.name
            )

        except Exception:
            return DetectedStack(
                language=Language.PYTHON,
                build_tool=BuildTool.CONDA,
                python_version="3.11",
                language_version="3.11"
            )

    def _analyze_requirements(self, path: Path, project_root: Path) -> DetectedStack:
        """Analyze requirements.txt file."""
        try:
            content = path.read_text(encoding='utf-8')
            dependencies = []

            for line in content.split('\n'):
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#') or line.startswith('-'):
                    continue

                # Parse package==version, package>=version, etc.
                match = re.match(r'^([a-zA-Z0-9_-]+)(.*)$', line)
                if match:
                    name = match.group(1)
                    version = match.group(2).strip() or 'latest'
                    dependencies.append(Dependency(name=name, version=version, is_dev=False))

            framework = self._detect_framework(dependencies)
            test_framework = self._detect_test_framework(dependencies)

            # Try to detect Python version from runtime.txt or .python-version
            python_version = self._detect_python_version_files(project_root)

            return DetectedStack(
                language=Language.PYTHON,
                framework=framework,
                build_tool=BuildTool.PIP,
                language_version=python_version,
                python_version=python_version,
                config_file=str(path.relative_to(project_root)),
                source_dir=self.detect_source_dir(project_root),
                test_dir=self.detect_test_dir(project_root),
                entrypoint=self._detect_entrypoint_filesystem(project_root),
                dependencies=dependencies,
                has_dockerfile=self.detect_existing_dockerfile(project_root),
                has_tests=self.detect_test_dir(project_root) is not None,
                test_framework=test_framework,
                package_manager_lock=path.name
            )

        except Exception:
            return DetectedStack(
                language=Language.PYTHON,
                build_tool=BuildTool.PIP,
                python_version="3.11",
                language_version="3.11"
            )

    def _analyze_setup(self, project_root: Path) -> DetectedStack:
        """Analyze setup.py/setup.cfg project."""
        python_version = self._detect_python_version_files(project_root)
        dependencies = []

        # Try to read setup.cfg for dependencies
        setup_cfg = project_root / "setup.cfg"
        if setup_cfg.exists():
            try:
                import configparser
                config = configparser.ConfigParser()
                config.read(setup_cfg)

                if 'options' in config and 'install_requires' in config['options']:
                    deps_str = config['options']['install_requires']
                    for dep in deps_str.strip().split('\n'):
                        dep = dep.strip()
                        if dep:
                            match = re.match(r'^([a-zA-Z0-9_-]+)(.*)$', dep)
                            if match:
                                dependencies.append(Dependency(
                                    name=match.group(1),
                                    version=match.group(2).strip() or 'latest',
                                    is_dev=False
                                ))
            except Exception:
                pass

        framework = self._detect_framework(dependencies)

        return DetectedStack(
            language=Language.PYTHON,
            framework=framework,
            build_tool=BuildTool.PIP,
            language_version=python_version,
            python_version=python_version,
            config_file='setup.py' if (project_root / 'setup.py').exists() else 'setup.cfg',
            source_dir=self.detect_source_dir(project_root),
            test_dir=self.detect_test_dir(project_root),
            entrypoint=self._detect_entrypoint_filesystem(project_root),
            dependencies=dependencies,
            has_dockerfile=self.detect_existing_dockerfile(project_root)
        )

    def _detect_python_version_files(self, project_root: Path) -> str:
        """Detect Python version from various config files."""
        # Check .python-version (pyenv)
        pyenv_file = project_root / ".python-version"
        if pyenv_file.exists():
            content = pyenv_file.read_text().strip()
            match = re.search(r'(\d+\.\d+)', content)
            if match:
                return match.group(1)

        # Check runtime.txt (Heroku)
        runtime_file = project_root / "runtime.txt"
        if runtime_file.exists():
            content = runtime_file.read_text().strip()
            match = re.search(r'python-(\d+\.\d+)', content)
            if match:
                return match.group(1)

        return "3.11"

    def _detect_framework(self, dependencies: List[Dependency]) -> Framework:
        """Detect Python framework from dependencies."""
        dep_names = {d.name.lower() for d in dependencies}

        # Check for frameworks in priority order
        if 'django' in dep_names:
            return Framework.DJANGO
        if 'fastapi' in dep_names:
            return Framework.FASTAPI
        if 'flask' in dep_names:
            return Framework.FLASK
        if 'aiohttp' in dep_names:
            return Framework.AIOHTTP

        return Framework.NONE

    def _detect_test_framework(self, dependencies: List[Dependency]) -> Optional[str]:
        """Detect test framework from dependencies."""
        dep_names = {d.name.lower() for d in dependencies}

        if 'pytest' in dep_names:
            return 'pytest'
        if 'unittest' in dep_names:
            return 'unittest'
        if 'nose' in dep_names or 'nose2' in dep_names:
            return 'nose'
        if 'hypothesis' in dep_names:
            return 'hypothesis'

        return None
