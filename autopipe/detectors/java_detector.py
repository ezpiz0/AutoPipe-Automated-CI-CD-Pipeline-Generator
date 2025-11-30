import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from autopipe.core.interfaces import Detector
from autopipe.core.models import DetectedStack, Language, Framework, BuildTool, Dependency


class JavaDetector(Detector):
    """
    Enhanced Java/Kotlin detector supporting:
    - Maven (pom.xml) including multi-module projects
    - Gradle (build.gradle, build.gradle.kts)
    - Ant (build.xml)
    - Various project structures (standard, Spring Boot, Quarkus, etc.)
    """

    def detect(self, project_root: Path) -> Optional[DetectedStack]:
        pom_path = project_root / "pom.xml"
        gradle_path = project_root / "build.gradle"
        gradle_kts_path = project_root / "build.gradle.kts"
        ant_path = project_root / "build.xml"

        # Check for Kotlin-specific indicators
        is_kotlin = self._is_kotlin_project(project_root)

        if pom_path.exists():
            return self._analyze_maven(pom_path, project_root, is_kotlin)
        elif gradle_path.exists() or gradle_kts_path.exists():
            gradle_file = gradle_kts_path if gradle_kts_path.exists() else gradle_path
            return self._analyze_gradle(gradle_file, project_root, is_kotlin)
        elif ant_path.exists():
            return self._analyze_ant(ant_path, project_root, is_kotlin)

        return None

    def _is_kotlin_project(self, project_root: Path) -> bool:
        """Check if project is primarily Kotlin."""
        # Check for Kotlin source files
        kotlin_files = list(project_root.glob("**/*.kt"))[:10]  # Limit search
        java_files = list(project_root.glob("**/*.java"))[:10]

        # If more Kotlin files than Java, it's Kotlin
        if kotlin_files and len(kotlin_files) >= len(java_files):
            return True

        # Check for Kotlin-specific configs
        if (project_root / "build.gradle.kts").exists():
            return True

        return False

    def _analyze_maven(self, pom_path: Path, project_root: Path, is_kotlin: bool) -> DetectedStack:
        try:
            tree = ET.parse(pom_path)
            root = tree.getroot()

            # Handle namespaces
            ns = {'mvn': 'http://maven.apache.org/POM/4.0.0'}

            def find_text(path: str, default: str = None) -> Optional[str]:
                """Find text with or without namespace."""
                elem = root.find(path, ns)
                if elem is None:
                    elem = root.find(path.replace('mvn:', ''))
                return elem.text if elem is not None and elem.text else default

            def find_all(path: str):
                """Find all elements with or without namespace."""
                elems = root.findall(path, ns)
                if not elems:
                    elems = root.findall(path.replace('mvn:', ''))
                return elems

            # Detect Java version
            java_version = self._detect_java_version_maven(root, ns)

            # Detect framework
            framework = self._detect_framework_maven(root, ns, pom_path)

            # Detect if multi-module
            modules = []
            module_elems = find_all('.//mvn:modules/mvn:module')
            for mod in module_elems:
                if mod.text:
                    modules.append(mod.text)

            # Detect dependencies
            dependencies = self._extract_maven_dependencies(root, ns)

            # Detect project info
            artifact_id = find_text('.//mvn:artifactId')
            version = find_text('.//mvn:version', '1.0.0')

            # Detect source directory
            source_dir = self._detect_maven_source_dir(root, ns, project_root)

            # Detect test framework
            test_framework = self._detect_test_framework_maven(dependencies)

            # Check for existing Dockerfile
            has_dockerfile = self.detect_existing_dockerfile(project_root)

            # Detect if project has tests
            has_tests = (project_root / 'src' / 'test').is_dir() or \
                        any(d.name in ['junit', 'testng', 'mockito'] for d in dependencies)

            # Check for Kotlin in Maven
            kotlin_in_maven = any('kotlin' in str(d.name).lower() for d in dependencies)
            if kotlin_in_maven:
                is_kotlin = True

            return DetectedStack(
                language=Language.KOTLIN if is_kotlin else Language.JAVA,
                framework=framework,
                build_tool=BuildTool.MAVEN,
                language_version=java_version,
                java_version=java_version,
                kotlin_version=self._detect_kotlin_version_maven(root, ns) if is_kotlin else None,
                config_file=str(pom_path.relative_to(project_root)) if pom_path != project_root / 'pom.xml' else 'pom.xml',
                source_dir=source_dir,
                test_dir='src/test' if (project_root / 'src' / 'test').is_dir() else None,
                build_output_dir='target',
                is_multi_module=len(modules) > 0,
                modules=modules,
                dependencies=dependencies,
                has_dockerfile=has_dockerfile,
                has_tests=has_tests,
                test_framework=test_framework,
                package_manager_lock=None  # Maven doesn't have lock file
            )

        except Exception as e:
            # Fallback if parsing fails - use Java 21 (latest LTS)
            return DetectedStack(
                language=Language.KOTLIN if is_kotlin else Language.JAVA,
                build_tool=BuildTool.MAVEN,
                java_version="21",
                language_version="21"
            )

    def _detect_java_version_maven(self, root, ns: dict) -> str:
        """Extract Java version from Maven POM."""
        version_paths = [
            './/mvn:properties/mvn:java.version',
            './/mvn:properties/mvn:maven.compiler.source',
            './/mvn:properties/mvn:maven.compiler.target',
            './/mvn:properties/mvn:maven.compiler.release',
            './/mvn:build/mvn:plugins/mvn:plugin[mvn:artifactId="maven-compiler-plugin"]/mvn:configuration/mvn:source',
            './/mvn:build/mvn:plugins/mvn:plugin[mvn:artifactId="maven-compiler-plugin"]/mvn:configuration/mvn:release',
        ]

        for path in version_paths:
            elem = root.find(path, ns)
            if elem is None:
                elem = root.find(path.replace('mvn:', ''))
            if elem is not None and elem.text:
                version = elem.text.strip()
                # Handle "1.8" -> "8", "11", "17", etc.
                if version.startswith('1.'):
                    version = version[2:]
                return version

        return "21"  # Default to latest LTS (Java 21)

    def _detect_kotlin_version_maven(self, root, ns: dict) -> Optional[str]:
        """Extract Kotlin version from Maven POM."""
        paths = [
            './/mvn:properties/mvn:kotlin.version',
            './/mvn:properties/mvn:kotlinVersion',
        ]
        for path in paths:
            elem = root.find(path, ns)
            if elem is None:
                elem = root.find(path.replace('mvn:', ''))
            if elem is not None and elem.text:
                return elem.text.strip()
        return None

    def _detect_framework_maven(self, root, ns: dict, pom_path: Path) -> Framework:
        """Detect framework from Maven POM."""
        pom_content = pom_path.read_text(encoding='utf-8').lower()

        # Spring Boot detection
        parent = root.find('.//mvn:parent', ns)
        if parent is not None:
            artifact = parent.find('mvn:artifactId', ns)
            if artifact is None:
                artifact = parent.find('artifactId')
            if artifact is not None and artifact.text and 'spring-boot' in artifact.text:
                return Framework.SPRING_BOOT

        # Check dependencies for frameworks
        if 'spring-boot' in pom_content:
            return Framework.SPRING_BOOT
        if 'quarkus' in pom_content:
            return Framework.QUARKUS
        if 'micronaut' in pom_content:
            return Framework.MICRONAUT
        if 'ktor' in pom_content:
            return Framework.KTOR

        return Framework.NONE

    def _detect_maven_source_dir(self, root, ns: dict, project_root: Path) -> Optional[str]:
        """Detect source directory from Maven config or filesystem."""
        # Check for custom sourceDirectory in POM
        source_elem = root.find('.//mvn:build/mvn:sourceDirectory', ns)
        if source_elem is None:
            source_elem = root.find('.//build/sourceDirectory')
        if source_elem is not None and source_elem.text:
            return source_elem.text

        # Check standard locations
        if (project_root / 'src' / 'main' / 'java').is_dir():
            return 'src/main/java'
        if (project_root / 'src' / 'main' / 'kotlin').is_dir():
            return 'src/main/kotlin'
        if (project_root / 'src').is_dir():
            return 'src'

        return None

    def _extract_maven_dependencies(self, root, ns: dict) -> List[Dependency]:
        """Extract dependencies from Maven POM."""
        dependencies = []
        deps_elem = root.findall('.//mvn:dependencies/mvn:dependency', ns)
        if not deps_elem:
            deps_elem = root.findall('.//dependencies/dependency')

        for dep in deps_elem[:50]:  # Limit to prevent slowdown
            group_elem = dep.find('mvn:groupId', ns)
            if group_elem is None:
                group_elem = dep.find('groupId')
            artifact_elem = dep.find('mvn:artifactId', ns)
            if artifact_elem is None:
                artifact_elem = dep.find('artifactId')
            version_elem = dep.find('mvn:version', ns)
            if version_elem is None:
                version_elem = dep.find('version')
            scope_elem = dep.find('mvn:scope', ns)
            if scope_elem is None:
                scope_elem = dep.find('scope')

            if artifact_elem is not None and artifact_elem.text:
                name = artifact_elem.text
                if group_elem is not None and group_elem.text:
                    name = f"{group_elem.text}:{name}"
                version = version_elem.text if version_elem is not None and version_elem.text else "unknown"
                is_dev = scope_elem is not None and scope_elem.text in ['test', 'provided']
                dependencies.append(Dependency(name=name, version=version, is_dev=is_dev))

        return dependencies

    def _detect_test_framework_maven(self, dependencies: List[Dependency]) -> Optional[str]:
        """Detect test framework from dependencies."""
        for dep in dependencies:
            name = dep.name.lower()
            if 'junit-jupiter' in name or 'junit5' in name:
                return 'junit5'
            if 'junit' in name:
                return 'junit4'
            if 'testng' in name:
                return 'testng'
            if 'spock' in name:
                return 'spock'
        return None

    def _analyze_gradle(self, gradle_path: Path, project_root: Path, is_kotlin: bool) -> DetectedStack:
        """Analyze Gradle project."""
        try:
            content = gradle_path.read_text(encoding='utf-8')

            # Detect if Kotlin DSL
            is_kotlin_dsl = gradle_path.suffix == '.kts'

            # Detect Java version
            java_version = self._detect_java_version_gradle(content)

            # Detect Kotlin version
            kotlin_version = None
            kotlin_match = re.search(r"kotlin.*['\"](\d+\.\d+(?:\.\d+)?)['\"]", content)
            if kotlin_match:
                kotlin_version = kotlin_match.group(1)
                is_kotlin = True

            # Detect framework
            framework = self._detect_framework_gradle(content)

            # Detect multi-module (settings.gradle)
            modules = self._detect_gradle_modules(project_root)

            # Detect test framework
            test_framework = self._detect_test_framework_gradle(content)

            # Detect source dir
            source_dir = self._detect_gradle_source_dir(content, project_root)

            # Check for existing Dockerfile
            has_dockerfile = self.detect_existing_dockerfile(project_root)

            # Check for tests
            has_tests = (project_root / 'src' / 'test').is_dir()

            # Detect lock file
            lock_file = None
            if (project_root / 'gradle.lockfile').exists():
                lock_file = 'gradle.lockfile'

            return DetectedStack(
                language=Language.KOTLIN if is_kotlin else Language.JAVA,
                framework=framework,
                build_tool=BuildTool.GRADLE,
                language_version=java_version,
                java_version=java_version,
                kotlin_version=kotlin_version,
                config_file=gradle_path.name,
                source_dir=source_dir,
                test_dir='src/test' if has_tests else None,
                build_output_dir='build',
                is_multi_module=len(modules) > 0,
                modules=modules,
                has_dockerfile=has_dockerfile,
                has_tests=has_tests,
                test_framework=test_framework,
                package_manager_lock=lock_file
            )

        except Exception as e:
            # Fallback if parsing fails - use Java 21 (latest LTS)
            return DetectedStack(
                language=Language.KOTLIN if is_kotlin else Language.JAVA,
                build_tool=BuildTool.GRADLE,
                java_version="21",
                language_version="21"
            )

    def _detect_java_version_gradle(self, content: str) -> str:
        """Extract Java version from Gradle build file."""
        patterns = [
            r"sourceCompatibility\s*=\s*['\"]?(\d+(?:\.\d+)?)['\"]?",
            r"targetCompatibility\s*=\s*['\"]?(\d+(?:\.\d+)?)['\"]?",
            r"JavaVersion\.VERSION_(\d+)",
            r"jvmTarget\s*=\s*['\"](\d+)['\"]",
            r"languageVersion\.set\s*\(\s*JavaLanguageVersion\.of\s*\(\s*(\d+)\s*\)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                version = match.group(1)
                if version.startswith('1.'):
                    version = version[2:]
                return version

        return "21"  # Default to latest LTS (Java 21)

    def _detect_framework_gradle(self, content: str) -> Framework:
        """Detect framework from Gradle build file."""
        content_lower = content.lower()

        if 'org.springframework.boot' in content or 'spring-boot' in content_lower:
            return Framework.SPRING_BOOT
        if 'io.quarkus' in content or 'quarkus' in content_lower:
            return Framework.QUARKUS
        if 'io.micronaut' in content or 'micronaut' in content_lower:
            return Framework.MICRONAUT
        if 'io.ktor' in content or 'ktor' in content_lower:
            return Framework.KTOR

        return Framework.NONE

    def _detect_gradle_modules(self, project_root: Path) -> List[str]:
        """Detect Gradle submodules from settings.gradle."""
        modules = []
        settings_files = ['settings.gradle', 'settings.gradle.kts']

        for settings_file in settings_files:
            settings_path = project_root / settings_file
            if settings_path.exists():
                content = settings_path.read_text(encoding='utf-8')
                # Match include ':module', include(':module'), include(":module")
                matches = re.findall(r"include\s*\(?['\"]?:?([^'\")\s]+)['\"]?\)?", content)
                modules.extend(matches)
                break

        return modules

    def _detect_gradle_source_dir(self, content: str, project_root: Path) -> Optional[str]:
        """Detect source directory from Gradle config."""
        # Check standard locations
        if (project_root / 'src' / 'main' / 'kotlin').is_dir():
            return 'src/main/kotlin'
        if (project_root / 'src' / 'main' / 'java').is_dir():
            return 'src/main/java'
        if (project_root / 'src').is_dir():
            return 'src'
        return None

    def _detect_test_framework_gradle(self, content: str) -> Optional[str]:
        """Detect test framework from Gradle dependencies."""
        if 'junit-jupiter' in content or 'useJUnitPlatform' in content:
            return 'junit5'
        if 'junit' in content.lower():
            return 'junit4'
        if 'testng' in content.lower():
            return 'testng'
        if 'spock' in content.lower():
            return 'spock'
        if 'kotest' in content.lower():
            return 'kotest'
        return None

    def _analyze_ant(self, ant_path: Path, project_root: Path, is_kotlin: bool) -> DetectedStack:
        """Analyze Apache Ant build.xml."""
        try:
            tree = ET.parse(ant_path)
            root = tree.getroot()

            java_version = "11"

            # Try to find javac task with target/source attributes
            for javac in root.iter('javac'):
                target = javac.get('target')
                source = javac.get('source')
                if target:
                    java_version = target
                    break
                if source:
                    java_version = source
                    break

            # Try to find property definitions
            for prop in root.iter('property'):
                name = prop.get('name', '')
                if any(x in name for x in ['java.target', 'javac.target', 'ant.build.javac.target']):
                    value = prop.get('value')
                    if value:
                        java_version = value
                        break

            # Detect framework
            framework = Framework.NONE
            content = ant_path.read_text(encoding='utf-8').lower()
            if 'spring' in content:
                framework = Framework.SPRING_BOOT

            # Detect source dir
            source_dir = None
            for elem in root.iter('src'):
                path = elem.get('path')
                if path:
                    source_dir = path
                    break
            if not source_dir:
                source_dir = self.detect_source_dir(project_root)

            return DetectedStack(
                language=Language.JAVA,
                framework=framework,
                build_tool=BuildTool.ANT,
                language_version=java_version,
                java_version=java_version,
                config_file='build.xml',
                source_dir=source_dir,
                build_output_dir='build',
                has_dockerfile=self.detect_existing_dockerfile(project_root),
                has_tests=(project_root / 'test').is_dir()
            )

        except Exception:
            return DetectedStack(
                language=Language.JAVA,
                build_tool=BuildTool.ANT,
                language_version="11",
                java_version="11"
            )
