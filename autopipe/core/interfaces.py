from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Set
from autopipe.core.models import DetectedStack
import logging

logger = logging.getLogger("autopipe")


class Detector(ABC):
    """Base detector class with support for recursive project discovery."""

    # Directories to skip during recursive search
    SKIP_DIRS: Set[str] = {
        'node_modules', '.git', '.svn', '.hg', '__pycache__', '.pytest_cache',
        'venv', '.venv', 'env', '.env', 'virtualenv',
        'vendor', 'bower_components',
        'target', 'build', 'dist', 'out', 'bin', 'obj',
        '.idea', '.vscode', '.gradle', '.m2',
        'coverage', '.nyc_output', 'htmlcov',
        '.tox', '.nox', '.eggs',
    }

    # Maximum depth for recursive search
    MAX_DEPTH: int = 5

    @abstractmethod
    def detect(self, project_root: Path) -> Optional[DetectedStack]:
        """
        Analyze the given directory and return a DetectedStack if this detector's
        language/framework is found.
        """
        pass

    def detect_all(self, project_root: Path) -> List[DetectedStack]:
        """
        Recursively find all projects of this type in the repository.
        Returns a list of all detected stacks (for monorepos).
        """
        results = []
        self._search_recursive(project_root, project_root, results, depth=0)
        return results

    def _search_recursive(self, current_path: Path, repo_root: Path,
                          results: List[DetectedStack], depth: int):
        """Recursively search for projects."""
        if depth > self.MAX_DEPTH:
            return

        # Try to detect project at current location
        stack = self.detect(current_path)
        if stack:
            # Store relative path from repo root
            rel_path = current_path.relative_to(repo_root)
            stack.project_root = str(rel_path) if str(rel_path) != '.' else None
            results.append(stack)

            # If this is a multi-module project, don't recurse into modules
            # (they're already handled by the parent detection)
            if stack.is_multi_module:
                return

        # Recurse into subdirectories
        try:
            for item in current_path.iterdir():
                if item.is_dir() and self._should_search_dir(item):
                    self._search_recursive(item, repo_root, results, depth + 1)
        except PermissionError:
            logger.debug(f"Permission denied: {current_path}")

    def _should_search_dir(self, path: Path) -> bool:
        """Check if directory should be searched."""
        name = path.name
        # Skip hidden directories (except common ones like .github)
        if name.startswith('.') and name not in {'.github', '.gitlab'}:
            return False
        # Skip known non-project directories
        if name in self.SKIP_DIRS:
            return False
        # Skip egg-info directories
        if name.endswith('.egg-info'):
            return False
        return True

    def find_files(self, project_root: Path, patterns: List[str],
                   max_depth: int = 3) -> List[Path]:
        """
        Find files matching any of the given patterns within max_depth.
        Useful for finding config files in non-standard locations.
        """
        found = []
        self._find_files_recursive(project_root, patterns, found, 0, max_depth)
        return found

    def _find_files_recursive(self, current: Path, patterns: List[str],
                              found: List[Path], depth: int, max_depth: int):
        """Recursively find files matching patterns."""
        if depth > max_depth:
            return

        try:
            for item in current.iterdir():
                if item.is_file():
                    for pattern in patterns:
                        if item.match(pattern):
                            found.append(item)
                            break
                elif item.is_dir() and self._should_search_dir(item):
                    self._find_files_recursive(item, patterns, found, depth + 1, max_depth)
        except PermissionError:
            pass

    def detect_source_dir(self, project_root: Path) -> Optional[str]:
        """Detect the source directory for the project."""
        common_source_dirs = ['src', 'app', 'lib', 'source', 'sources', 'main']
        for src_dir in common_source_dirs:
            if (project_root / src_dir).is_dir():
                return src_dir
        return None

    def detect_test_dir(self, project_root: Path) -> Optional[str]:
        """Detect the test directory for the project."""
        common_test_dirs = ['test', 'tests', 'spec', 'specs', '__tests__',
                           'test_suite', 'testing']
        for test_dir in common_test_dirs:
            if (project_root / test_dir).is_dir():
                return test_dir
        # Check for src/test (Java style)
        if (project_root / 'src' / 'test').is_dir():
            return 'src/test'
        return None

    def detect_existing_dockerfile(self, project_root: Path) -> bool:
        """Check if project already has a Dockerfile."""
        dockerfile_names = ['Dockerfile', 'dockerfile', 'Dockerfile.dev',
                           'Dockerfile.prod', 'Dockerfile.production']
        for name in dockerfile_names:
            if (project_root / name).exists():
                return True
        return False
