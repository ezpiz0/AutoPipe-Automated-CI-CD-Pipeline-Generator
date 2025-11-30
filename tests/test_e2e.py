import pytest
from pathlib import Path
import shutil
from autopipe.core.fetcher import Fetcher
from autopipe.core.analyzer import Analyzer
from autopipe.core.resolver import Resolver
from autopipe.generators.generator import Generator
from autopipe.validators.validator import Validator

# Import all detectors
from autopipe.detectors.java_detector import JavaDetector
from autopipe.detectors.python_detector import PythonDetector
from autopipe.detectors.nodejs_detector import NodeJSDetector
from autopipe.detectors.go_detector import GoDetector
from autopipe.detectors.dotnet_detector import DotNetDetector
from autopipe.detectors.php_detector import PhpDetector

from autopipe.core.models import Language, BuildTool, Framework

@pytest.fixture
def analyzer():
    """Create an analyzer with all detectors registered."""
    analyzer = Analyzer()
    analyzer.register_detector(JavaDetector())
    analyzer.register_detector(PythonDetector())
    analyzer.register_detector(NodeJSDetector())
    analyzer.register_detector(GoDetector())
    analyzer.register_detector(DotNetDetector())
    analyzer.register_detector(PhpDetector())
    return analyzer

@pytest.fixture
def resolver():
    return Resolver()

@pytest.fixture
def generator():
    template_dir = Path(__file__).parent.parent / "templates"
    return Generator(template_dir)

@pytest.fixture
def output_dir(tmp_path):
    """Create a temporary output directory."""
    output = tmp_path / "output"
    output.mkdir()
    return output

class TestGoldenSamples:
    """Test AutoPipe against Golden Sample repositories."""
    
    def test_java_maven_spring(self, analyzer, resolver, generator, output_dir):
        """Test Java Maven Spring Boot detection and generation."""
        sample_path = Path(__file__).parent / "golden_samples" / "java-maven-spring"
        
        # Analyze
        stacks = analyzer.analyze(sample_path)
        assert len(stacks) == 1
        
        # Verify detection
        stack = stacks[0]
        assert stack.language == Language.JAVA
        assert stack.build_tool == BuildTool.MAVEN
        assert stack.framework == Framework.SPRING_BOOT
        assert stack.java_version == "17"
        
        # Resolve and generate
        context = resolver.resolve(stacks, str(sample_path))
        generator.generate(context, output_dir)
        
        # Verify outputs
        assert (output_dir / "Dockerfile").exists()
        assert (output_dir / ".gitlab-ci.yml").exists()
        
        # Verify Dockerfile contains expected content
        dockerfile_content = (output_dir / "Dockerfile").read_text()
        assert "syntax=docker/dockerfile:1.4" in dockerfile_content
        assert "maven:3.9-eclipse-temurin-17" in dockerfile_content
        assert "mvn package" in dockerfile_content
        
    def test_python_fastapi_poetry(self, analyzer, resolver, generator, output_dir):
        """Test Python FastAPI with Poetry detection."""
        sample_path = Path(__file__).parent / "dummy_repo"
        
        stacks = analyzer.analyze(sample_path)
        assert len(stacks) == 1
        
        stack = stacks[0]
        assert stack.language == Language.PYTHON
        assert stack.build_tool == BuildTool.POETRY
        assert stack.framework == Framework.FASTAPI
        
        context = resolver.resolve(stacks, str(sample_path))
        generator.generate(context, output_dir)
        
        dockerfile_content = (output_dir / "Dockerfile").read_text()
        assert "poetry" in dockerfile_content
        
    def test_nodejs_react(self, analyzer, resolver, generator, output_dir):
        """Test Node.js React detection."""
        sample_path = Path(__file__).parent / "golden_samples" / "nodejs-react"
        
        stacks = analyzer.analyze(sample_path)
        assert len(stacks) == 1
        
        stack = stacks[0]
        assert stack.language == Language.NODEJS
        assert stack.framework == Framework.REACT
        assert stack.build_tool == BuildTool.NPM
        assert stack.node_version == "18"
        
        context = resolver.resolve(stacks, str(sample_path))
        generator.generate(context, output_dir)
        
        gitlab_ci = (output_dir / ".gitlab-ci.yml").read_text()
        assert "node:18" in gitlab_ci
        assert "npm ci" in gitlab_ci
        
    def test_go_service(self, analyzer, resolver, generator, output_dir):
        """Test Go service detection."""
        sample_path = Path(__file__).parent / "golden_samples" / "go-service"
        
        stacks = analyzer.analyze(sample_path)
        assert len(stacks) == 1
        
        stack = stacks[0]
        assert stack.language == Language.GO
        assert stack.build_tool == BuildTool.GO_MOD
        assert stack.go_version == "1.21"
        
        context = resolver.resolve(stacks, str(sample_path))
        generator.generate(context, output_dir)
        
        dockerfile_content = (output_dir / "Dockerfile").read_text()
        assert "golang:1.21" in dockerfile_content
        assert "go build" in dockerfile_content
        
    def test_dotnet_api(self, analyzer, resolver, generator, output_dir):
        """Test .NET API detection."""
        sample_path = Path(__file__).parent / "golden_samples" / "dotnet-api"
        
        stacks = analyzer.analyze(sample_path)
        assert len(stacks) == 1
        
        stack = stacks[0]
        assert stack.language == Language.DOTNET
        assert stack.build_tool == BuildTool.DOTNET_CLI
        assert stack.dotnet_framework_version == "8.0"
        
        context = resolver.resolve(stacks, str(sample_path))
        generator.generate(context, output_dir)
        
        dockerfile_content = (output_dir / "Dockerfile").read_text()
        assert "mcr.microsoft.com/dotnet/sdk:8.0" in dockerfile_content
        assert "dotnet publish" in dockerfile_content
        
    def test_php_laravel(self, analyzer, resolver, generator, output_dir):
        """Test PHP Laravel detection."""
        sample_path = Path(__file__).parent / "golden_samples" / "php-laravel"
        
        stacks = analyzer.analyze(sample_path)
        assert len(stacks) == 1
        
        stack = stacks[0]
        assert stack.language == Language.PHP
        assert stack.build_tool == BuildTool.COMPOSER
        assert stack.framework == Framework.LARAVEL
        assert stack.php_version == "8.2"
        
        context = resolver.resolve(stacks, str(sample_path))
        generator.generate(context, output_dir)
        
        dockerfile_content = (output_dir / "Dockerfile").read_text()
        assert "composer" in dockerfile_content
        assert "php:8.2" in dockerfile_content

class TestDeterminism:
    """Test that AutoPipe produces deterministic results."""
    
    def test_deterministic_output(self, analyzer, resolver, generator, tmp_path):
        """Ensure same input produces identical output."""
        sample_path = Path(__file__).parent / "dummy_repo"
        
        # First run
        output1 = tmp_path / "output1"
        output1.mkdir()
        stacks1 = analyzer.analyze(sample_path)
        context1 = resolver.resolve(stacks1, str(sample_path))
        generator.generate(context1, output1)
        
        # Second run
        output2 = tmp_path / "output2"
        output2.mkdir()
        stacks2 = analyzer.analyze(sample_path)
        context2 = resolver.resolve(stacks2, str(sample_path))
        generator.generate(context2, output2)
        
        # Compare outputs
        dockerfile1 = (output1 / "Dockerfile").read_text()
        dockerfile2 = (output2 / "Dockerfile").read_text()
        assert dockerfile1 == dockerfile2
        
        gitlab1 = (output1 / ".gitlab-ci.yml").read_text()
        gitlab2 = (output2 / ".gitlab-ci.yml").read_text()
        assert gitlab1 == gitlab2
