import pytest
from pathlib import Path
from autopipe.detectors.java_detector import JavaDetector
from autopipe.detectors.python_detector import PythonDetector
from autopipe.detectors.nodejs_detector import NodeJSDetector
from autopipe.detectors.go_detector import GoDetector
from autopipe.detectors.dotnet_detector import DotNetDetector
from autopipe.detectors.php_detector import PhpDetector
from autopipe.core.models import Language, BuildTool, Framework

class TestJavaDetector:
    def test_maven_detection(self):
        detector = JavaDetector()
        sample = Path(__file__).parent / "golden_samples" / "java-maven-spring"
        result = detector.detect(sample)
        
        assert result is not None
        assert result.language == Language.JAVA
        assert result.build_tool == BuildTool.MAVEN
        assert result.framework == Framework.SPRING_BOOT
        assert result.java_version == "17"

class TestPythonDetector:
    def test_poetry_detection(self):
        detector = PythonDetector()
        sample = Path(__file__).parent / "dummy_repo"
        result = detector.detect(sample)
        
        assert result is not None
        assert result.language == Language.PYTHON
        assert result.build_tool == BuildTool.POETRY
        assert result.framework == Framework.FASTAPI

class TestNodeJSDetector:
    def test_npm_react_detection(self):
        detector = NodeJSDetector()
        sample = Path(__file__).parent / "golden_samples" / "nodejs-react"
        result = detector.detect(sample)
        
        assert result is not None
        assert result.language == Language.NODEJS
        assert result.framework == Framework.REACT
        assert result.build_tool == BuildTool.NPM

class TestGoDetector:
    def test_go_mod_detection(self):
        detector = GoDetector()
        sample = Path(__file__).parent / "golden_samples" / "go-service"
        result = detector.detect(sample)
        
        assert result is not None
        assert result.language == Language.GO
        assert result.build_tool == BuildTool.GO_MOD
        assert result.go_version == "1.21"

class TestDotNetDetector:
    def test_dotnet_detection(self):
        detector = DotNetDetector()
        sample = Path(__file__).parent / "golden_samples" / "dotnet-api"
        result = detector.detect(sample)
        
        assert result is not None
        assert result.language == Language.DOTNET
        assert result.build_tool == BuildTool.DOTNET_CLI
        assert result.dotnet_framework_version == "8.0"

class TestPhpDetector:
    def test_composer_laravel_detection(self):
        detector = PhpDetector()
        sample = Path(__file__).parent / "golden_samples" / "php-laravel"
        result = detector.detect(sample)
        
        assert result is not None
        assert result.language == Language.PHP
        assert result.build_tool == BuildTool.COMPOSER
        assert result.framework == Framework.LARAVEL
        assert result.php_version == "8.2"
