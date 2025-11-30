import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from autopipe.core.interfaces import Detector
from autopipe.core.models import DetectedStack, Language, Framework, BuildTool, Dependency


class NodeJSDetector(Detector):
    """
    Enhanced Node.js/TypeScript detector supporting:
    - package.json with npm, yarn, pnpm
    - TypeScript projects (tsconfig.json)
    - Monorepos (npm workspaces, yarn workspaces, pnpm workspaces, Lerna, Nx, Turborepo)
    - Various frameworks (React, Next.js, NestJS, Express, Vue, Nuxt, Angular)
    - Various project structures
    """

    # Common entrypoint patterns
    ENTRYPOINT_PATTERNS = [
        'index.js', 'index.ts', 'main.js', 'main.ts',
        'app.js', 'app.ts', 'server.js', 'server.ts',
        'src/index.js', 'src/index.ts', 'src/main.js', 'src/main.ts',
        'src/app.js', 'src/app.ts', 'src/server.js', 'src/server.ts',
    ]

    def detect(self, project_root: Path) -> Optional[DetectedStack]:
        package_json = project_root / "package.json"

        if package_json.exists():
            return self._analyze_package_json(package_json, project_root)
        return None

    def _analyze_package_json(self, path: Path, project_root: Path) -> DetectedStack:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            dependencies = data.get("dependencies", {})
            dev_dependencies = data.get("devDependencies", {})
            all_deps = {**dependencies, **dev_dependencies}

            # Detect if TypeScript project
            is_typescript = self._is_typescript_project(project_root, all_deps)

            # Detect framework
            framework = self._detect_framework(all_deps)

            # Detect build tool
            build_tool = self._detect_build_tool(project_root)

            # Detect Node version
            node_version = self._detect_node_version(data, project_root)

            # Detect if monorepo/workspaces
            is_monorepo, workspaces = self._detect_workspaces(data, project_root)

            # Extract dependencies
            parsed_deps = self._parse_dependencies(dependencies, dev_dependencies)

            # Detect entrypoint
            entrypoint = self._detect_entrypoint(data, project_root, is_typescript)

            # Detect source directory
            source_dir = self._detect_source_dir(project_root, is_typescript)

            # Detect test directory and framework
            test_dir = self.detect_test_dir(project_root)
            test_framework = self._detect_test_framework(all_deps, data)

            # Detect build output directory
            build_output = self._detect_build_output(data, project_root)

            # Detect lock file
            lock_file = self._detect_lock_file(project_root, build_tool)

            # Check for existing Dockerfile
            has_dockerfile = self.detect_existing_dockerfile(project_root)

            return DetectedStack(
                language=Language.TYPESCRIPT if is_typescript else Language.NODEJS,
                framework=framework,
                build_tool=build_tool,
                language_version=node_version,
                node_version=node_version,
                config_file='package.json',
                source_dir=source_dir,
                test_dir=test_dir,
                entrypoint=entrypoint,
                build_output_dir=build_output,
                is_multi_module=is_monorepo,
                modules=workspaces,
                dependencies=parsed_deps,
                has_dockerfile=has_dockerfile,
                has_tests=test_dir is not None or test_framework is not None,
                test_framework=test_framework,
                package_manager_lock=lock_file
            )

        except Exception:
            return DetectedStack(
                language=Language.NODEJS,
                build_tool=BuildTool.NPM,
                node_version="20",
                language_version="20"
            )

    def _is_typescript_project(self, project_root: Path, deps: dict) -> bool:
        """Check if project is TypeScript-based."""
        # Check for tsconfig.json
        if (project_root / "tsconfig.json").exists():
            return True

        # Check for TypeScript in dependencies
        if "typescript" in deps:
            return True

        # Check for .ts files
        ts_files = list(project_root.glob("**/*.ts"))[:5]
        if ts_files:
            return True

        return False

    def _detect_framework(self, deps: dict) -> Framework:
        """Detect Node.js/TypeScript framework from dependencies."""
        # Next.js (React SSR)
        if "next" in deps:
            return Framework.NEXTJS

        # Nuxt (Vue SSR)
        if "nuxt" in deps or "nuxt3" in deps:
            return Framework.NUXT

        # NestJS (backend)
        if "@nestjs/core" in deps:
            return Framework.NESTJS

        # Angular
        if "@angular/core" in deps:
            return Framework.ANGULAR

        # Vue
        if "vue" in deps:
            return Framework.VUE

        # React (check after Next.js)
        if "react" in deps:
            return Framework.REACT

        # Express
        if "express" in deps:
            return Framework.EXPRESS

        return Framework.NONE

    def _detect_build_tool(self, project_root: Path) -> BuildTool:
        """Detect package manager from lock files."""
        # Check for pnpm
        if (project_root / "pnpm-lock.yaml").exists():
            return BuildTool.PNPM

        # Check for yarn
        if (project_root / "yarn.lock").exists():
            return BuildTool.YARN

        # Check for bun
        if (project_root / "bun.lockb").exists():
            return BuildTool.NPM  # Treat bun similarly to npm for now

        # Default to npm
        return BuildTool.NPM

    # LTS codename to version mapping
    LTS_CODENAMES = {
        'argon': '4',
        'boron': '6',
        'carbon': '8',
        'dubnium': '10',
        'erbium': '12',
        'fermium': '14',
        'gallium': '16',
        'hydrogen': '18',
        'iron': '20',
        'jod': '22',
    }

    # Minimum supported Node.js version for modern projects
    MIN_SUPPORTED_VERSION = 18

    def _detect_node_version(self, data: dict, project_root: Path) -> str:
        """Detect Node.js version from various sources with smart fallbacks."""
        detected_version = None
        highest_version = 0

        # Check engines in package.json (highest priority)
        engines = data.get("engines", {})
        if "node" in engines:
            detected_version = self._parse_node_version(engines["node"])
            if detected_version:
                try:
                    highest_version = int(detected_version)
                except ValueError:
                    pass

        # For monorepos: scan workspace packages for highest Node version requirement
        workspaces = data.get("workspaces", [])
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("packages", [])

        if workspaces or (project_root / "packages").is_dir() or (project_root / "apps").is_dir():
            # Scan common monorepo directories
            scan_dirs = []
            for ws_pattern in workspaces:
                # Handle glob patterns like "packages/*", "apps/*"
                if '*' in ws_pattern:
                    base = ws_pattern.split('*')[0].rstrip('/')
                    scan_dirs.append(project_root / base)
                else:
                    scan_dirs.append(project_root / ws_pattern)

            # Also check common monorepo directories
            for common_dir in ['packages', 'apps', 'ghost']:  # ghost is specific to Ghost CMS
                if (project_root / common_dir).is_dir():
                    scan_dirs.append(project_root / common_dir)

            # Scan for package.json files and find highest version
            for scan_dir in scan_dirs:
                if not scan_dir.is_dir():
                    continue
                for pkg_file in list(scan_dir.glob("**/package.json"))[:20]:  # Limit to 20 to avoid perf issues
                    try:
                        import json
                        pkg_data = json.loads(pkg_file.read_text(encoding='utf-8'))
                        pkg_engines = pkg_data.get("engines", {})
                        if "node" in pkg_engines:
                            pkg_version = self._parse_node_version(pkg_engines["node"])
                            if pkg_version:
                                try:
                                    pkg_version_int = int(pkg_version)
                                    if pkg_version_int > highest_version:
                                        highest_version = pkg_version_int
                                        detected_version = pkg_version
                                except ValueError:
                                    pass
                    except Exception:
                        pass  # Ignore malformed package.json files

        # Check .nvmrc
        if not detected_version:
            nvmrc = project_root / ".nvmrc"
            if nvmrc.exists():
                content = nvmrc.read_text().strip().lower()
                detected_version = self._parse_node_version(content)

        # Check .node-version
        if not detected_version:
            node_version_file = project_root / ".node-version"
            if node_version_file.exists():
                content = node_version_file.read_text().strip()
                detected_version = self._parse_node_version(content)

        # Check volta in package.json
        if not detected_version:
            volta = data.get("volta", {})
            if "node" in volta:
                detected_version = self._parse_node_version(volta["node"])

        # Check packageManager field for Node version hints
        if not detected_version:
            pkg_manager = data.get("packageManager", "")
            # Some projects use packageManager: "pnpm@8.15.0+sha256..." which may hint at Node version

        # Validate and adjust version
        if detected_version:
            try:
                version_int = int(detected_version)
                # If version is too old, upgrade to modern LTS
                if version_int < self.MIN_SUPPORTED_VERSION:
                    return "22"  # Latest LTS
                # If version is odd (non-LTS), it's fine for development
                return detected_version
            except ValueError:
                pass

        return "22"  # Default to latest LTS (Node 22)

    def _parse_node_version(self, version_str: str) -> str:
        """Parse Node.js version from various formats."""
        if not version_str:
            return None

        version_str = version_str.strip().lower()

        # Handle LTS codenames: "lts/*", "lts/iron", "lts/hydrogen"
        if 'lts' in version_str:
            # lts/* means latest LTS
            if 'lts/*' in version_str or version_str == 'lts':
                return "22"  # Current latest LTS
            # Check for specific codename
            for codename, version in self.LTS_CODENAMES.items():
                if codename in version_str:
                    return version
            return "20"  # Default LTS

        # Handle "latest" or "current"
        if version_str in ['latest', 'current', 'node']:
            return "22"

        # Handle semver ranges: ">=18", "^20", "~18", "18.x", "18.*"
        # Extract the first meaningful version number

        # Pattern for >=X, >X, ^X, ~X
        match = re.search(r'[>=^~]*\s*(\d+)', version_str)
        if match:
            return match.group(1)

        # Pattern for X.x or X.*
        match = re.search(r'^(\d+)\.[x*]', version_str)
        if match:
            return match.group(1)

        # Simple version number
        match = re.search(r'^v?(\d+)', version_str)
        if match:
            return match.group(1)

        return None

    def _detect_workspaces(self, data: dict, project_root: Path) -> tuple:
        """Detect if project uses workspaces (monorepo)."""
        workspaces = []

        # npm/yarn workspaces in package.json
        ws = data.get("workspaces", [])
        if isinstance(ws, dict):
            ws = ws.get("packages", [])
        if ws:
            # Expand glob patterns
            for pattern in ws:
                if '*' in pattern:
                    # Simple glob expansion
                    base = pattern.replace('/*', '').replace('/**', '')
                    base_path = project_root / base
                    if base_path.is_dir():
                        for item in base_path.iterdir():
                            if item.is_dir() and (item / "package.json").exists():
                                workspaces.append(str(item.relative_to(project_root)))
                else:
                    workspaces.append(pattern)
            return True, workspaces

        # pnpm workspaces
        pnpm_workspace = project_root / "pnpm-workspace.yaml"
        if pnpm_workspace.exists():
            try:
                content = pnpm_workspace.read_text()
                # Simple YAML parsing for packages
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('- '):
                        pattern = line[2:].strip().strip('"\'')
                        workspaces.append(pattern)
                return True, workspaces
            except Exception:
                pass

        # Lerna
        lerna_json = project_root / "lerna.json"
        if lerna_json.exists():
            try:
                with open(lerna_json) as f:
                    lerna_data = json.load(f)
                packages = lerna_data.get("packages", ["packages/*"])
                return True, packages
            except Exception:
                pass

        # Nx
        nx_json = project_root / "nx.json"
        if nx_json.exists():
            # Nx projects are typically in apps/ and libs/
            workspaces = []
            for dir_name in ['apps', 'libs', 'packages']:
                dir_path = project_root / dir_name
                if dir_path.is_dir():
                    for item in dir_path.iterdir():
                        if item.is_dir() and (item / "package.json").exists():
                            workspaces.append(str(item.relative_to(project_root)))
            return True, workspaces

        # Turborepo
        turbo_json = project_root / "turbo.json"
        if turbo_json.exists():
            # Turborepo typically uses npm/yarn/pnpm workspaces
            # Check for packages directory
            for dir_name in ['apps', 'packages']:
                dir_path = project_root / dir_name
                if dir_path.is_dir():
                    for item in dir_path.iterdir():
                        if item.is_dir() and (item / "package.json").exists():
                            workspaces.append(str(item.relative_to(project_root)))
            if workspaces:
                return True, workspaces

        return False, []

    def _parse_dependencies(self, deps: dict, dev_deps: dict) -> List[Dependency]:
        """Parse dependencies from package.json."""
        result = []

        for name, version in deps.items():
            result.append(Dependency(
                name=name,
                version=str(version).replace('^', '').replace('~', ''),
                is_dev=False
            ))

        for name, version in dev_deps.items():
            result.append(Dependency(
                name=name,
                version=str(version).replace('^', '').replace('~', ''),
                is_dev=True
            ))

        return result

    def _detect_entrypoint(self, data: dict, project_root: Path, is_typescript: bool) -> Optional[str]:
        """Detect entrypoint from package.json or filesystem."""
        # Check main field
        main = data.get("main")
        if main:
            return main

        # Check module field (ES modules)
        module = data.get("module")
        if module:
            return module

        # Check scripts.start for entry
        scripts = data.get("scripts", {})
        start_script = scripts.get("start", "")
        if start_script:
            # Try to extract file from "node src/index.js" or "ts-node src/index.ts"
            match = re.search(r'(?:node|ts-node|tsx)\s+([^\s]+)', start_script)
            if match:
                return match.group(1)

        # Fallback to filesystem detection
        for pattern in self.ENTRYPOINT_PATTERNS:
            if (project_root / pattern).exists():
                return pattern

        return None

    def _detect_source_dir(self, project_root: Path, is_typescript: bool) -> Optional[str]:
        """Detect source directory."""
        # Check for common source directories
        for src_dir in ['src', 'lib', 'app', 'source']:
            if (project_root / src_dir).is_dir():
                return src_dir

        # For TypeScript, check tsconfig.json
        if is_typescript:
            tsconfig = project_root / "tsconfig.json"
            if tsconfig.exists():
                try:
                    with open(tsconfig) as f:
                        # Remove comments (simple approach)
                        content = re.sub(r'//.*|/\*[\s\S]*?\*/', '', f.read())
                        ts_data = json.loads(content)
                    compiler_options = ts_data.get("compilerOptions", {})
                    root_dir = compiler_options.get("rootDir")
                    if root_dir:
                        return root_dir.lstrip('./')
                except Exception:
                    pass

        return None

    def _detect_test_framework(self, deps: dict, data: dict) -> Optional[str]:
        """Detect test framework from dependencies or scripts."""
        # Check dependencies
        if "jest" in deps or "@types/jest" in deps:
            return "jest"
        if "mocha" in deps or "@types/mocha" in deps:
            return "mocha"
        if "vitest" in deps:
            return "vitest"
        if "ava" in deps:
            return "ava"
        if "jasmine" in deps:
            return "jasmine"
        if "@playwright/test" in deps:
            return "playwright"
        if "cypress" in deps:
            return "cypress"

        # Check scripts
        scripts = data.get("scripts", {})
        test_script = scripts.get("test", "")
        if "jest" in test_script:
            return "jest"
        if "mocha" in test_script:
            return "mocha"
        if "vitest" in test_script:
            return "vitest"

        return None

    def _detect_build_output(self, data: dict, project_root: Path) -> Optional[str]:
        """Detect build output directory."""
        # Check common output directories
        for out_dir in ['dist', 'build', 'out', '.next', '.nuxt']:
            if (project_root / out_dir).is_dir():
                return out_dir

        # Check tsconfig.json for outDir
        tsconfig = project_root / "tsconfig.json"
        if tsconfig.exists():
            try:
                with open(tsconfig) as f:
                    content = re.sub(r'//.*|/\*[\s\S]*?\*/', '', f.read())
                    ts_data = json.loads(content)
                out_dir = ts_data.get("compilerOptions", {}).get("outDir")
                if out_dir:
                    return out_dir.lstrip('./')
            except Exception:
                pass

        return "dist"  # Default

    def _detect_lock_file(self, project_root: Path, build_tool: BuildTool) -> Optional[str]:
        """Detect lock file based on build tool."""
        lock_files = {
            BuildTool.NPM: 'package-lock.json',
            BuildTool.YARN: 'yarn.lock',
            BuildTool.PNPM: 'pnpm-lock.yaml',
        }

        expected_lock = lock_files.get(build_tool)
        if expected_lock and (project_root / expected_lock).exists():
            return expected_lock

        # Check for any lock file
        for lock in ['package-lock.json', 'yarn.lock', 'pnpm-lock.yaml']:
            if (project_root / lock).exists():
                return lock

        return None
