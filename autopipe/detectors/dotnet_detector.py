import xml.etree.ElementTree as ET
import re
import json
from pathlib import Path
from typing import Optional, List
from autopipe.core.interfaces import Detector
from autopipe.core.models import DetectedStack, Language, Framework, BuildTool, Dependency


class DotNetDetector(Detector):
    """
    Enhanced .NET/C# detector supporting:
    - .csproj files (SDK-style and legacy)
    - .sln solution files
    - Various .NET frameworks (ASP.NET Core, Blazor, etc.)
    - Various project structures
    - NuGet packages
    """

    def detect(self, project_root: Path) -> Optional[DetectedStack]:
        # Look for .csproj files
        csproj_files = list(project_root.glob("*.csproj"))

        # Check for solution file
        sln_files = list(project_root.glob("*.sln"))

        if csproj_files:
            return self._analyze_csproj(csproj_files[0], project_root)
        elif sln_files:
            return self._analyze_solution(sln_files[0], project_root)

        return None

    def _analyze_csproj(self, path: Path, project_root: Path) -> DetectedStack:
        """Analyze .csproj file for project configuration."""
        try:
            tree = ET.parse(path)
            root = tree.getroot()

            # Detect target framework
            target_framework = self._detect_target_framework(root)
            version = self._extract_version(target_framework)

            # Detect SDK type (Web, Console, Library, etc.)
            sdk_type = root.get('Sdk', '')
            is_web = 'Web' in sdk_type or self._is_web_project(root)

            # Detect framework
            framework = self._detect_framework(root, path, is_web)

            # Extract dependencies (NuGet packages)
            dependencies = self._extract_dependencies(root)

            # Detect entrypoint
            entrypoint = self._detect_entrypoint(project_root, path)

            # Detect source directory
            source_dir = self._detect_source_dir(project_root)

            # Detect test project
            is_test_project = self._is_test_project(root, path)
            test_framework = self._detect_test_framework(dependencies)

            # Detect multi-project solution
            is_multi_project, projects = self._detect_solution_projects(project_root)

            # Check for existing Dockerfile
            has_dockerfile = self.detect_existing_dockerfile(project_root)

            return DetectedStack(
                language=Language.DOTNET,
                framework=framework,
                build_tool=BuildTool.DOTNET_CLI,
                language_version=version,
                dotnet_framework_version=version,
                config_file=path.name,
                source_dir=source_dir,
                entrypoint=entrypoint,
                build_output_dir='bin/Release',
                is_multi_module=is_multi_project,
                modules=projects,
                dependencies=dependencies,
                has_dockerfile=has_dockerfile,
                has_tests=is_test_project or test_framework is not None,
                test_framework=test_framework,
                package_manager_lock='packages.lock.json' if (project_root / 'packages.lock.json').exists() else None
            )

        except Exception:
            return DetectedStack(
                language=Language.DOTNET,
                build_tool=BuildTool.DOTNET_CLI,
                dotnet_framework_version="8.0",
                language_version="8.0"
            )

    def _analyze_solution(self, path: Path, project_root: Path) -> DetectedStack:
        """Analyze .sln solution file."""
        try:
            content = path.read_text(encoding='utf-8')

            # Extract project paths from solution
            projects = []
            for match in re.finditer(r'Project\([^)]+\)\s*=\s*"[^"]+",\s*"([^"]+\.csproj)"', content):
                proj_path = match.group(1).replace('\\', '/')
                projects.append(proj_path)

            # Find main project (usually the one with same name as solution)
            main_project = None
            sln_name = path.stem
            for proj in projects:
                if sln_name in proj:
                    proj_path = project_root / proj
                    if proj_path.exists():
                        main_project = proj_path
                        break

            # If no match, use first non-test project
            if not main_project:
                for proj in projects:
                    proj_path = project_root / proj
                    if proj_path.exists() and 'test' not in proj.lower():
                        main_project = proj_path
                        break

            # If still no match, use first project
            if not main_project and projects:
                proj_path = project_root / projects[0]
                if proj_path.exists():
                    main_project = proj_path

            if main_project:
                stack = self._analyze_csproj(main_project, project_root)
                stack.is_multi_module = len(projects) > 1
                stack.modules = projects
                return stack

            return DetectedStack(
                language=Language.DOTNET,
                build_tool=BuildTool.DOTNET_CLI,
                dotnet_framework_version="8.0",
                language_version="8.0",
                is_multi_module=len(projects) > 1,
                modules=projects
            )

        except Exception:
            return DetectedStack(
                language=Language.DOTNET,
                build_tool=BuildTool.DOTNET_CLI,
                dotnet_framework_version="8.0",
                language_version="8.0"
            )

    def _detect_target_framework(self, root) -> str:
        """Extract target framework from .csproj."""
        # Check TargetFramework (single target)
        tf = root.find(".//TargetFramework")
        if tf is not None and tf.text:
            return tf.text

        # Check TargetFrameworks (multi-target)
        tfs = root.find(".//TargetFrameworks")
        if tfs is not None and tfs.text:
            # Return first target
            return tfs.text.split(';')[0]

        return "net8.0"  # Default

    def _extract_version(self, target_framework: str) -> str:
        """Extract version number from target framework."""
        # net8.0 -> 8.0
        # net6.0-windows -> 6.0
        # netcoreapp3.1 -> 3.1
        # netstandard2.1 -> 2.1

        if target_framework.startswith("net") and not target_framework.startswith("netcoreapp") and not target_framework.startswith("netstandard"):
            match = re.search(r'net(\d+\.\d+)', target_framework)
            if match:
                return match.group(1)

        if target_framework.startswith("netcoreapp"):
            match = re.search(r'netcoreapp(\d+\.\d+)', target_framework)
            if match:
                return match.group(1)

        if target_framework.startswith("netstandard"):
            match = re.search(r'netstandard(\d+\.\d+)', target_framework)
            if match:
                return match.group(1)

        return "8.0"

    def _is_web_project(self, root) -> bool:
        """Check if project is a web project."""
        # Check for web SDK
        sdk = root.get('Sdk', '')
        if 'Web' in sdk or 'Razor' in sdk or 'Blazor' in sdk:
            return True

        # Check for web-related packages
        for pkg_ref in root.findall(".//PackageReference"):
            include = pkg_ref.get('Include', '')
            if any(x in include for x in ['Microsoft.AspNetCore', 'Blazor', 'SignalR']):
                return True

        return False

    def _detect_framework(self, root, path: Path, is_web: bool) -> Framework:
        """Detect .NET framework from project file."""
        # Check SDK
        sdk = root.get('Sdk', '')

        # Blazor
        if 'Blazor' in sdk:
            return Framework.BLAZOR

        # Check for Blazor packages
        for pkg_ref in root.findall(".//PackageReference"):
            include = pkg_ref.get('Include', '')
            if 'Blazor' in include:
                return Framework.BLAZOR

        # ASP.NET Core
        if is_web:
            return Framework.ASPNET_CORE

        return Framework.NONE

    def _extract_dependencies(self, root) -> List[Dependency]:
        """Extract NuGet package references from .csproj."""
        dependencies = []

        for pkg_ref in root.findall(".//PackageReference"):
            name = pkg_ref.get('Include', '')
            version = pkg_ref.get('Version', 'latest')

            if not version:
                # Version might be in child element
                ver_elem = pkg_ref.find('Version')
                version = ver_elem.text if ver_elem is not None else 'latest'

            if name:
                # Check if it's a development dependency
                is_dev = any(x in name.lower() for x in ['test', 'mock', 'analyzer', 'coverlet'])
                dependencies.append(Dependency(name=name, version=version, is_dev=is_dev))

        return dependencies

    def _detect_entrypoint(self, project_root: Path, csproj_path: Path) -> Optional[str]:
        """Detect main entry point."""
        # Check for Program.cs
        if (project_root / "Program.cs").exists():
            return "Program.cs"

        # Check for Startup.cs (older ASP.NET Core)
        if (project_root / "Startup.cs").exists():
            return "Program.cs"  # Still use Program.cs as entrypoint

        # Check project directory
        proj_dir = csproj_path.parent
        if (proj_dir / "Program.cs").exists():
            return str((proj_dir / "Program.cs").relative_to(project_root))

        return None

    def _detect_source_dir(self, project_root: Path) -> Optional[str]:
        """Detect source directory."""
        # Check for common .NET project structures
        for src_dir in ['src', 'Source', 'Sources', 'App']:
            if (project_root / src_dir).is_dir():
                return src_dir
        return None

    def _is_test_project(self, root, path: Path) -> bool:
        """Check if project is a test project."""
        # Check SDK
        sdk = root.get('Sdk', '')
        if 'Test' in sdk:
            return True

        # Check project name
        if 'test' in path.stem.lower() or 'tests' in path.stem.lower():
            return True

        # Check for test framework packages
        for pkg_ref in root.findall(".//PackageReference"):
            include = pkg_ref.get('Include', '')
            if any(x in include for x in ['xunit', 'NUnit', 'MSTest', 'Microsoft.NET.Test']):
                return True

        return False

    def _detect_test_framework(self, dependencies: List[Dependency]) -> Optional[str]:
        """Detect test framework from dependencies."""
        dep_names = {d.name.lower() for d in dependencies}

        if any('xunit' in d for d in dep_names):
            return 'xunit'
        if any('nunit' in d for d in dep_names):
            return 'nunit'
        if any('mstest' in d for d in dep_names):
            return 'mstest'

        return None

    def _detect_solution_projects(self, project_root: Path) -> tuple:
        """Detect if there's a solution with multiple projects."""
        sln_files = list(project_root.glob("*.sln"))
        if not sln_files:
            return False, []

        try:
            content = sln_files[0].read_text(encoding='utf-8')
            projects = []
            for match in re.finditer(r'Project\([^)]+\)\s*=\s*"[^"]+",\s*"([^"]+\.csproj)"', content):
                projects.append(match.group(1).replace('\\', '/'))
            return len(projects) > 1, projects
        except Exception:
            return False, []
