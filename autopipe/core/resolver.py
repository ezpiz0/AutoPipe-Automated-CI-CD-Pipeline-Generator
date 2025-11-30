import logging
import os
from pathlib import Path
from typing import List, Optional
from autopipe.core.models import (
    ProjectContext, DetectedStack, ProjectMetadata, Language, Framework
)

logger = logging.getLogger("autopipe")


class Resolver:
    """
    Resolves detected stacks into a project context.

    Handles:
    - Multiple detected stacks (monorepos)
    - Language/framework priority
    - Project metadata extraction
    - TypeScript/Kotlin as distinct from JS/Java
    """

    # Priority list: Lower index = Higher priority
    # Backend languages take priority over frontend
    LANGUAGE_PRIORITY = [
        Language.JAVA,
        Language.KOTLIN,  # Kotlin has same priority as Java
        Language.DOTNET,
        Language.GO,
        Language.PYTHON,
        Language.PHP,
        Language.TYPESCRIPT,  # TypeScript backend before plain Node.js
        Language.NODEJS,
    ]

    # Framework priority within a language (lower = higher priority)
    FRAMEWORK_PRIORITY = {
        # Java/Kotlin frameworks
        Framework.SPRING_BOOT: 0,
        Framework.QUARKUS: 1,
        Framework.MICRONAUT: 2,
        Framework.KTOR: 3,

        # Python frameworks
        Framework.DJANGO: 0,
        Framework.FASTAPI: 1,
        Framework.FLASK: 2,
        Framework.AIOHTTP: 3,

        # Node.js/TypeScript frameworks - backend first
        Framework.NESTJS: 0,
        Framework.EXPRESS: 1,
        Framework.NEXTJS: 10,  # SSR, can be both
        Framework.NUXT: 11,   # SSR, can be both
        Framework.ANGULAR: 20,  # Frontend
        Framework.VUE: 21,      # Frontend
        Framework.REACT: 22,    # Frontend

        # Go frameworks
        Framework.GIN: 0,
        Framework.ECHO: 1,
        Framework.FIBER: 2,

        # PHP frameworks
        Framework.LARAVEL: 0,
        Framework.SYMFONY: 1,
        Framework.YII: 2,
        Framework.CODEIGNITER: 3,

        # .NET frameworks
        Framework.ASPNET_CORE: 0,
        Framework.BLAZOR: 1,
    }

    def resolve(self, detected_stacks: List[DetectedStack], root_path: str) -> ProjectContext:
        """
        Resolve detected stacks into a project context.

        For monorepos, identifies the primary stack while preserving
        information about all detected projects.
        """
        if not detected_stacks:
            raise ValueError("No technology stack detected. Cannot generate pipeline.")

        # Check for monorepo
        is_monorepo = len(detected_stacks) > 1

        # Sort stacks by priority
        sorted_stacks = sorted(detected_stacks, key=self._get_priority)

        # Pick the winner (primary stack)
        winner = sorted_stacks[0]
        logger.info(f"Resolved primary stack: {winner.language} ({winner.framework})")

        if is_monorepo:
            logger.info(f"Monorepo detected with {len(detected_stacks)} projects")
            for stack in sorted_stacks[1:]:
                logger.debug(f"  Additional project: {stack.language} at {stack.project_root or '.'}")

        # Extract project metadata
        metadata = self._extract_metadata(winner, root_path)

        return ProjectContext(
            metadata=metadata,
            stack=winner,
            root_path=root_path,
            is_monorepo=is_monorepo,
            detected_projects=detected_stacks if is_monorepo else []
        )

    def resolve_all(self, detected_stacks: List[DetectedStack], root_path: str) -> List[ProjectContext]:
        """
        Resolve all detected stacks into separate project contexts.

        Useful for monorepos where each project needs its own pipeline.
        """
        if not detected_stacks:
            raise ValueError("No technology stack detected. Cannot generate pipeline.")

        contexts = []
        for stack in detected_stacks:
            project_path = os.path.join(root_path, stack.project_root) if stack.project_root else root_path
            metadata = self._extract_metadata(stack, project_path)

            contexts.append(ProjectContext(
                metadata=metadata,
                stack=stack,
                root_path=project_path,
                is_monorepo=False,
                detected_projects=[]
            ))

        # Sort by priority
        contexts.sort(key=lambda ctx: self._get_priority(ctx.stack))

        return contexts

    def _get_priority(self, stack: DetectedStack) -> int:
        """
        Calculate priority score for a stack.
        Lower score = higher priority.
        """
        # Base priority from language
        base_priority = 999
        try:
            base_priority = self.LANGUAGE_PRIORITY.index(stack.language) * 100
        except ValueError:
            pass

        # Framework adjustment
        framework_priority = self.FRAMEWORK_PRIORITY.get(stack.framework, 50)
        base_priority += framework_priority

        # Adjust for specific cases

        # TypeScript with backend framework gets higher priority
        if stack.language == Language.TYPESCRIPT:
            if stack.framework in [Framework.NESTJS, Framework.EXPRESS]:
                base_priority -= 50  # Boost backend TypeScript

        # Node.js frontend frameworks get lower priority
        if stack.language == Language.NODEJS:
            if stack.framework in [Framework.REACT, Framework.VUE, Framework.ANGULAR]:
                base_priority += 200  # Lower priority for pure frontend

        # Kotlin with Ktor is a full backend
        if stack.language == Language.KOTLIN:
            if stack.framework == Framework.KTOR:
                base_priority -= 10  # Boost Ktor projects

        # Projects with Dockerfile might be more "production ready"
        if stack.has_dockerfile:
            base_priority -= 5

        # Projects with tests are more mature
        if stack.has_tests:
            base_priority -= 3

        return base_priority

    def _extract_metadata(self, stack: DetectedStack, root_path: str) -> ProjectMetadata:
        """
        Extract project metadata from stack configuration files.
        """
        name = None
        version = "0.1.0"

        root = Path(root_path)

        # Try to extract from various config files
        if stack.language in [Language.NODEJS, Language.TYPESCRIPT]:
            name, version = self._extract_from_package_json(root, name, version)

        elif stack.language == Language.PYTHON:
            name, version = self._extract_from_python_config(root, stack, name, version)

        elif stack.language in [Language.JAVA, Language.KOTLIN]:
            name, version = self._extract_from_jvm_config(root, stack, name, version)

        elif stack.language == Language.GO:
            name, version = self._extract_from_go_mod(root, name, version)

        elif stack.language == Language.DOTNET:
            name, version = self._extract_from_csproj(root, stack, name, version)

        elif stack.language == Language.PHP:
            name, version = self._extract_from_composer(root, name, version)

        # Fallback: use directory name
        if not name:
            name = root.name or f"auto-generated-{stack.language.value}"

        return ProjectMetadata(name=name, version=version)

    def _extract_from_package_json(self, root: Path, name: Optional[str], version: str) -> tuple:
        """Extract metadata from package.json."""
        import json

        package_json = root / "package.json"
        if package_json.exists():
            try:
                with open(package_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                name = data.get("name", name)
                version = data.get("version", version)
            except Exception:
                pass

        return name, version

    def _extract_from_python_config(self, root: Path, stack: DetectedStack, name: Optional[str], version: str) -> tuple:
        """Extract metadata from Python config files."""
        import json

        # Try pyproject.toml
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomllib
                with open(pyproject, "rb") as f:
                    data = tomllib.load(f)

                # Poetry
                if "tool" in data and "poetry" in data["tool"]:
                    poetry = data["tool"]["poetry"]
                    name = poetry.get("name", name)
                    version = poetry.get("version", version)
                # PEP 621
                elif "project" in data:
                    project = data["project"]
                    name = project.get("name", name)
                    version = project.get("version", version)
            except Exception:
                pass

        # Try setup.py (basic parsing)
        setup_py = root / "setup.py"
        if not name and setup_py.exists():
            try:
                content = setup_py.read_text(encoding="utf-8")
                import re
                match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    name = match.group(1)
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    version = match.group(1)
            except Exception:
                pass

        return name, version

    def _extract_from_jvm_config(self, root: Path, stack: DetectedStack, name: Optional[str], version: str) -> tuple:
        """Extract metadata from Maven/Gradle config."""
        import re
        import xml.etree.ElementTree as ET

        # Maven pom.xml
        pom_xml = root / "pom.xml"
        if pom_xml.exists():
            try:
                tree = ET.parse(pom_xml)
                root_elem = tree.getroot()
                ns = {'m': 'http://maven.apache.org/POM/4.0.0'}

                # Try with namespace
                artifact_id = root_elem.find('m:artifactId', ns)
                if artifact_id is None:
                    artifact_id = root_elem.find('artifactId')
                if artifact_id is not None:
                    name = artifact_id.text

                ver = root_elem.find('m:version', ns)
                if ver is None:
                    ver = root_elem.find('version')
                if ver is not None:
                    version = ver.text
            except Exception:
                pass

        # Gradle build.gradle
        build_gradle = root / "build.gradle"
        if not name and build_gradle.exists():
            try:
                content = build_gradle.read_text(encoding="utf-8")
                match = re.search(r'rootProject\.name\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    name = match.group(1)
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    version = match.group(1)
            except Exception:
                pass

        # settings.gradle
        settings_gradle = root / "settings.gradle"
        if not name and settings_gradle.exists():
            try:
                content = settings_gradle.read_text(encoding="utf-8")
                match = re.search(r'rootProject\.name\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    name = match.group(1)
            except Exception:
                pass

        return name, version

    def _extract_from_go_mod(self, root: Path, name: Optional[str], version: str) -> tuple:
        """Extract metadata from go.mod."""
        import re

        go_mod = root / "go.mod"
        if go_mod.exists():
            try:
                content = go_mod.read_text(encoding="utf-8")
                match = re.search(r'^module\s+(\S+)', content, re.MULTILINE)
                if match:
                    module_path = match.group(1)
                    # Use last part of module path as name
                    name = module_path.split('/')[-1]
            except Exception:
                pass

        return name, version

    def _extract_from_csproj(self, root: Path, stack: DetectedStack, name: Optional[str], version: str) -> tuple:
        """Extract metadata from .csproj file."""
        import xml.etree.ElementTree as ET

        config_file = stack.config_file or ""
        csproj_path = root / config_file if config_file.endswith('.csproj') else None

        if not csproj_path:
            csproj_files = list(root.glob("*.csproj"))
            if csproj_files:
                csproj_path = csproj_files[0]

        if csproj_path and csproj_path.exists():
            try:
                tree = ET.parse(csproj_path)
                root_elem = tree.getroot()

                # Project name from file
                name = csproj_path.stem

                # Version from PropertyGroup
                ver = root_elem.find('.//Version')
                if ver is not None and ver.text:
                    version = ver.text
            except Exception:
                pass

        return name, version

    def _extract_from_composer(self, root: Path, name: Optional[str], version: str) -> tuple:
        """Extract metadata from composer.json."""
        import json

        composer_json = root / "composer.json"
        if composer_json.exists():
            try:
                with open(composer_json, "r", encoding="utf-8") as f:
                    data = json.load(f)

                full_name = data.get("name", "")
                if full_name and "/" in full_name:
                    # vendor/package -> package
                    name = full_name.split("/")[-1]
                elif full_name:
                    name = full_name

                version = data.get("version", version)
            except Exception:
                pass

        return name, version
