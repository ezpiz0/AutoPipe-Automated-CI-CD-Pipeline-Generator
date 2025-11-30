import json
import re
from pathlib import Path
from typing import Optional, List
from autopipe.core.interfaces import Detector
from autopipe.core.models import DetectedStack, Language, Framework, BuildTool, Dependency


class PhpDetector(Detector):
    """
    Enhanced PHP detector supporting:
    - composer.json
    - Various PHP frameworks (Laravel, Symfony, Yii, CodeIgniter, etc.)
    - Various project structures
    """

    # Common entrypoint patterns for PHP
    ENTRYPOINT_PATTERNS = [
        'public/index.php',  # Laravel, Symfony, most frameworks
        'index.php',
        'web/index.php',  # Symfony 3
        'web/app.php',
        'artisan',  # Laravel CLI
    ]

    def detect(self, project_root: Path) -> Optional[DetectedStack]:
        composer_json = project_root / "composer.json"

        if composer_json.exists():
            return self._analyze_composer(composer_json, project_root)

        # Check for PHP files without composer.json (legacy projects)
        php_files = list(project_root.glob("*.php"))[:5]
        if php_files:
            return self._analyze_legacy_project(project_root)

        return None

    def _analyze_composer(self, path: Path, project_root: Path) -> DetectedStack:
        """Analyze composer.json for project configuration."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            require = data.get("require", {})
            require_dev = data.get("require-dev", {})
            all_deps = {**require, **require_dev}

            # Detect PHP version
            php_version = self._detect_php_version(require, project_root)

            # Detect framework
            framework = self._detect_framework(require)

            # Extract dependencies
            dependencies = self._extract_dependencies(require, require_dev)

            # Detect entrypoint
            entrypoint = self._detect_entrypoint(project_root, framework)

            # Detect source directory
            source_dir = self._detect_source_dir(data, project_root)

            # Detect test directory
            test_dir = self._detect_test_dir(data, project_root)

            # Detect test framework
            test_framework = self._detect_test_framework(all_deps)

            # Check for existing Dockerfile
            has_dockerfile = self.detect_existing_dockerfile(project_root)

            # Check for tests
            has_tests = test_dir is not None or test_framework is not None

            # Detect lock file
            lock_file = 'composer.lock' if (project_root / 'composer.lock').exists() else None

            return DetectedStack(
                language=Language.PHP,
                framework=framework,
                build_tool=BuildTool.COMPOSER,
                language_version=php_version,
                php_version=php_version,
                config_file='composer.json',
                source_dir=source_dir,
                test_dir=test_dir,
                entrypoint=entrypoint,
                build_output_dir=None,  # PHP doesn't have build output
                dependencies=dependencies,
                has_dockerfile=has_dockerfile,
                has_tests=has_tests,
                test_framework=test_framework,
                package_manager_lock=lock_file
            )

        except Exception:
            return DetectedStack(
                language=Language.PHP,
                build_tool=BuildTool.COMPOSER,
                php_version="8.2",
                language_version="8.2"
            )

    def _analyze_legacy_project(self, project_root: Path) -> DetectedStack:
        """Analyze PHP project without composer.json."""
        # Try to detect framework from directory structure
        framework = Framework.NONE

        # Laravel check
        if (project_root / 'artisan').exists():
            framework = Framework.LARAVEL

        # Symfony check
        if (project_root / 'symfony.lock').exists() or (project_root / 'config' / 'bundles.php').exists():
            framework = Framework.SYMFONY

        entrypoint = self._detect_entrypoint(project_root, framework)

        return DetectedStack(
            language=Language.PHP,
            framework=framework,
            build_tool=BuildTool.COMPOSER,
            php_version="8.2",
            language_version="8.2",
            entrypoint=entrypoint,
            has_dockerfile=self.detect_existing_dockerfile(project_root)
        )

    def _detect_php_version(self, require: dict, project_root: Path) -> str:
        """Detect PHP version from composer.json or config files."""
        # Check composer.json require.php
        if "php" in require:
            version_constraint = require["php"]
            # Parse "^8.1", ">=8.0", "~8.1.0", etc.
            match = re.search(r'(\d+\.\d+)', version_constraint)
            if match:
                return match.group(1)

        # Check .php-version file
        php_version_file = project_root / ".php-version"
        if php_version_file.exists():
            content = php_version_file.read_text().strip()
            match = re.search(r'(\d+\.\d+)', content)
            if match:
                return match.group(1)

        return "8.2"  # Default to recent stable

    def _detect_framework(self, require: dict) -> Framework:
        """Detect PHP framework from dependencies."""
        # Laravel
        if "laravel/framework" in require or "illuminate/support" in require:
            return Framework.LARAVEL

        # Symfony
        if any(key.startswith("symfony/") for key in require):
            # Check if it's a full Symfony app
            if "symfony/framework-bundle" in require or "symfony/symfony" in require:
                return Framework.SYMFONY

        # Yii
        if "yiisoft/yii2" in require or "yiisoft/yii" in require:
            return Framework.YII

        # CodeIgniter
        if "codeigniter4/framework" in require or "codeigniter/framework" in require:
            return Framework.CODEIGNITER

        # Other frameworks could be added: Slim, Lumen, CakePHP, etc.

        return Framework.NONE

    def _extract_dependencies(self, require: dict, require_dev: dict) -> List[Dependency]:
        """Extract dependencies from composer.json."""
        dependencies = []

        for name, version in require.items():
            if name.lower() != 'php' and not name.startswith('ext-'):
                dependencies.append(Dependency(
                    name=name,
                    version=str(version).replace('^', '').replace('~', ''),
                    is_dev=False
                ))

        for name, version in require_dev.items():
            if name.lower() != 'php' and not name.startswith('ext-'):
                dependencies.append(Dependency(
                    name=name,
                    version=str(version).replace('^', '').replace('~', ''),
                    is_dev=True
                ))

        return dependencies

    def _detect_entrypoint(self, project_root: Path, framework: Framework) -> Optional[str]:
        """Detect entrypoint based on framework and filesystem."""
        # Framework-specific entrypoints
        if framework == Framework.LARAVEL:
            if (project_root / 'public' / 'index.php').exists():
                return 'public/index.php'
        elif framework == Framework.SYMFONY:
            if (project_root / 'public' / 'index.php').exists():
                return 'public/index.php'
            if (project_root / 'web' / 'app.php').exists():
                return 'web/app.php'

        # Check common patterns
        for pattern in self.ENTRYPOINT_PATTERNS:
            if (project_root / pattern).exists():
                return pattern

        return None

    def _detect_source_dir(self, data: dict, project_root: Path) -> Optional[str]:
        """Detect source directory from composer.json autoload or filesystem."""
        # Check PSR-4 autoload
        autoload = data.get("autoload", {})
        psr4 = autoload.get("psr-4", {})

        if psr4:
            # Get first source directory
            for namespace, path in psr4.items():
                if isinstance(path, list):
                    path = path[0]
                if path and path != '':
                    # Remove trailing slash
                    return path.rstrip('/')

        # Check for common directories
        for src_dir in ['src', 'app', 'lib', 'App', 'src/App']:
            if (project_root / src_dir).is_dir():
                return src_dir

        return None

    def _detect_test_dir(self, data: dict, project_root: Path) -> Optional[str]:
        """Detect test directory from composer.json or filesystem."""
        # Check autoload-dev
        autoload_dev = data.get("autoload-dev", {})
        psr4_dev = autoload_dev.get("psr-4", {})

        if psr4_dev:
            for namespace, path in psr4_dev.items():
                if 'test' in namespace.lower() or 'test' in str(path).lower():
                    if isinstance(path, list):
                        path = path[0]
                    return path.rstrip('/')

        # Check for common test directories
        for test_dir in ['tests', 'test', 'Tests', 'Test', 'spec']:
            if (project_root / test_dir).is_dir():
                return test_dir

        return None

    def _detect_test_framework(self, deps: dict) -> Optional[str]:
        """Detect test framework from dependencies."""
        dep_names = set(deps.keys())

        if 'phpunit/phpunit' in dep_names:
            return 'phpunit'
        if 'pestphp/pest' in dep_names:
            return 'pest'
        if 'phpspec/phpspec' in dep_names:
            return 'phpspec'
        if 'codeception/codeception' in dep_names:
            return 'codeception'
        if 'behat/behat' in dep_names:
            return 'behat'

        return None
