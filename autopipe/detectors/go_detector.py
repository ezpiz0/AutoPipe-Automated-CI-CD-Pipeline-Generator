import re
from pathlib import Path
from typing import Optional, List
from autopipe.core.interfaces import Detector
from autopipe.core.models import DetectedStack, Language, Framework, BuildTool, Dependency


class GoDetector(Detector):
    """
    Enhanced Go detector supporting:
    - go.mod (Go Modules)
    - Various Go frameworks (Gin, Echo, Fiber, Chi, etc.)
    - Monorepo structures
    - Various project layouts
    """

    # Common entrypoint patterns for Go
    ENTRYPOINT_PATTERNS = [
        'main.go',
        'cmd/main.go',
        'cmd/*/main.go',
        'app.go',
        'server.go',
    ]

    def detect(self, project_root: Path) -> Optional[DetectedStack]:
        go_mod = project_root / "go.mod"

        if go_mod.exists():
            return self._analyze_go_mod(go_mod, project_root)

        # Check for Go files without go.mod (legacy or simple projects)
        go_files = list(project_root.glob("*.go"))[:5]
        if go_files:
            return self._analyze_legacy_project(project_root)

        return None

    def _analyze_go_mod(self, path: Path, project_root: Path) -> DetectedStack:
        """Analyze go.mod for project configuration."""
        try:
            content = path.read_text(encoding='utf-8')

            # Detect Go version
            go_version = self._detect_go_version(content)

            # Detect module name
            module_name = self._detect_module_name(content)

            # Extract dependencies
            dependencies = self._extract_dependencies(content)

            # Detect framework
            framework = self._detect_framework(dependencies, content)

            # Detect source directory
            source_dir = self._detect_source_dir(project_root)

            # Detect entrypoint
            entrypoint = self._detect_entrypoint(project_root)

            # Detect test directory
            test_dir = self._detect_test_dir(project_root)

            # Check for multi-module workspace
            is_workspace, workspace_modules = self._detect_workspace(project_root)

            # Detect test framework
            test_framework = self._detect_test_framework(dependencies)

            # Check for existing Dockerfile
            has_dockerfile = self.detect_existing_dockerfile(project_root)

            # Check for tests
            has_tests = self._has_tests(project_root)

            return DetectedStack(
                language=Language.GO,
                framework=framework,
                build_tool=BuildTool.GO_MOD,
                language_version=go_version,
                go_version=go_version,
                config_file='go.mod',
                source_dir=source_dir,
                test_dir=test_dir,
                entrypoint=entrypoint,
                build_output_dir='.',  # Go builds to current dir by default
                is_multi_module=is_workspace,
                modules=workspace_modules,
                dependencies=dependencies,
                has_dockerfile=has_dockerfile,
                has_tests=has_tests,
                test_framework=test_framework,
                package_manager_lock='go.sum' if (project_root / 'go.sum').exists() else None
            )

        except Exception:
            # Fallback to latest stable Go version
            return DetectedStack(
                language=Language.GO,
                build_tool=BuildTool.GO_MOD,
                go_version="1.22",
                language_version="1.22"
            )

    def _analyze_legacy_project(self, project_root: Path) -> DetectedStack:
        """Analyze Go project without go.mod."""
        return DetectedStack(
            language=Language.GO,
            build_tool=BuildTool.GO_MOD,
            go_version="1.22",
            language_version="1.22",
            source_dir=self._detect_source_dir(project_root),
            entrypoint=self._detect_entrypoint(project_root),
            has_dockerfile=self.detect_existing_dockerfile(project_root)
        )

    def _detect_go_version(self, content: str) -> str:
        """Extract Go version from go.mod."""
        # Match "go 1.21" or "go 1.21.0"
        match = re.search(r'^go\s+(\d+\.\d+(?:\.\d+)?)', content, re.MULTILINE)
        if match:
            version = match.group(1)
            # Return major.minor only
            parts = version.split('.')
            if len(parts) >= 2:
                return f"{parts[0]}.{parts[1]}"
            return version
        return "1.22"  # Default to latest stable

    def _detect_module_name(self, content: str) -> Optional[str]:
        """Extract module name from go.mod."""
        match = re.search(r'^module\s+(\S+)', content, re.MULTILINE)
        if match:
            return match.group(1)
        return None

    def _extract_dependencies(self, content: str) -> List[Dependency]:
        """Extract dependencies from go.mod."""
        dependencies = []

        # Parse require block
        require_block = re.search(r'require\s*\((.*?)\)', content, re.DOTALL)
        if require_block:
            for line in require_block.group(1).split('\n'):
                line = line.strip()
                if line and not line.startswith('//'):
                    # Match "github.com/pkg v1.0.0"
                    match = re.match(r'^(\S+)\s+v?(\S+)', line)
                    if match:
                        dependencies.append(Dependency(
                            name=match.group(1),
                            version=match.group(2),
                            is_dev=False
                        ))

        # Parse single require statements
        for match in re.finditer(r'^require\s+(\S+)\s+v?(\S+)', content, re.MULTILINE):
            dependencies.append(Dependency(
                name=match.group(1),
                version=match.group(2),
                is_dev=False
            ))

        return dependencies

    def _detect_framework(self, dependencies: List[Dependency], content: str) -> Framework:
        """Detect Go framework from dependencies."""
        dep_names = {d.name.lower() for d in dependencies}
        content_lower = content.lower()

        # Gin
        if any('gin-gonic/gin' in d for d in dep_names) or 'gin-gonic/gin' in content_lower:
            return Framework.GIN

        # Echo
        if any('labstack/echo' in d for d in dep_names) or 'labstack/echo' in content_lower:
            return Framework.ECHO

        # Fiber
        if any('gofiber/fiber' in d for d in dep_names) or 'gofiber/fiber' in content_lower:
            return Framework.FIBER

        # Chi (not in enum, but common)
        # Buffalo, Beego, etc. could be added

        return Framework.NONE

    def _detect_source_dir(self, project_root: Path) -> Optional[str]:
        """Detect source directory for Go project."""
        # Check for cmd directory (common Go project structure)
        if (project_root / 'cmd').is_dir():
            return 'cmd'

        # Check for internal directory
        if (project_root / 'internal').is_dir():
            return 'internal'

        # Check for pkg directory
        if (project_root / 'pkg').is_dir():
            return 'pkg'

        # Check for src directory
        if (project_root / 'src').is_dir():
            return 'src'

        # Check for app directory
        if (project_root / 'app').is_dir():
            return 'app'

        return None

    def _detect_entrypoint(self, project_root: Path) -> Optional[str]:
        """Detect main entry point for Go project."""
        # Check root main.go
        if (project_root / 'main.go').exists():
            return 'main.go'

        # Check cmd directory
        cmd_dir = project_root / 'cmd'
        if cmd_dir.is_dir():
            # Find first directory with main.go
            for item in cmd_dir.iterdir():
                if item.is_dir() and (item / 'main.go').exists():
                    return f'cmd/{item.name}/main.go'
            # Check for main.go directly in cmd
            if (cmd_dir / 'main.go').exists():
                return 'cmd/main.go'

        # Check for app.go or server.go
        for name in ['app.go', 'server.go']:
            if (project_root / name).exists():
                return name

        return None

    def _detect_test_dir(self, project_root: Path) -> Optional[str]:
        """Detect test directory."""
        # Go tests are typically in the same package
        # Check for dedicated test directories
        for test_dir in ['test', 'tests', 'testing', 'e2e', 'integration']:
            if (project_root / test_dir).is_dir():
                return test_dir
        return None

    def _detect_workspace(self, project_root: Path) -> tuple:
        """Detect Go workspace (go.work)."""
        go_work = project_root / 'go.work'
        if go_work.exists():
            modules = []
            try:
                content = go_work.read_text()
                # Parse use block
                use_block = re.search(r'use\s*\((.*?)\)', content, re.DOTALL)
                if use_block:
                    for line in use_block.group(1).split('\n'):
                        line = line.strip()
                        if line and not line.startswith('//'):
                            modules.append(line)
                # Parse single use statements
                for match in re.finditer(r'^use\s+(\S+)', content, re.MULTILINE):
                    mod = match.group(1)
                    if mod not in modules:
                        modules.append(mod)
                return True, modules
            except Exception:
                pass

        return False, []

    def _detect_test_framework(self, dependencies: List[Dependency]) -> Optional[str]:
        """Detect test framework from dependencies."""
        dep_names = {d.name.lower() for d in dependencies}

        if any('testify' in d for d in dep_names):
            return 'testify'
        if any('ginkgo' in d for d in dep_names):
            return 'ginkgo'
        if any('gomega' in d for d in dep_names):
            return 'gomega'
        if any('gocheck' in d for d in dep_names):
            return 'gocheck'

        return 'testing'  # Standard library

    def _has_tests(self, project_root: Path) -> bool:
        """Check if project has tests."""
        # Check for *_test.go files
        test_files = list(project_root.glob("**/*_test.go"))[:5]
        return len(test_files) > 0
