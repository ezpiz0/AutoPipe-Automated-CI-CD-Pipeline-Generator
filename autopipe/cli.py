import typer
import sys
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.logging import RichHandler
import logging

app = typer.Typer(
    name="autopipe",
    help="AutoPipe: Deterministic CI/CD Pipeline Generator with Full Platform Integration",
    add_completion=False,
)
console = Console()

def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )


@app.command()
def generate(
    repo_url: str = typer.Argument(..., help="URL or path to the Git repository"),
    output_dir: Path = typer.Option(Path("."), "--output", "-o", help="Directory to output generated files"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """
    Analyze a repository and generate CI/CD configuration (files only).
    """
    setup_logging(verbose)
    logger = logging.getLogger("autopipe")

    logger.info(f"Starting AutoPipe analysis for: {repo_url}")

    from autopipe.core.fetcher import Fetcher
    from autopipe.core.analyzer import Analyzer
    from autopipe.core.resolver import Resolver
    from autopipe.generators.generator import Generator
    from autopipe.validators.validator import Validator
    from autopipe.core.reporter import Reporter

    # Register Detectors
    from autopipe.detectors.java_detector import JavaDetector
    from autopipe.detectors.python_detector import PythonDetector
    from autopipe.detectors.nodejs_detector import NodeJSDetector
    from autopipe.detectors.go_detector import GoDetector
    from autopipe.detectors.dotnet_detector import DotNetDetector
    from autopipe.detectors.php_detector import PhpDetector

    fetcher = Fetcher(repo_url)
    analyzer = Analyzer()
    analyzer.register_detector(JavaDetector())
    analyzer.register_detector(PythonDetector())
    analyzer.register_detector(NodeJSDetector())
    analyzer.register_detector(GoDetector())
    analyzer.register_detector(DotNetDetector())
    analyzer.register_detector(PhpDetector())

    resolver = Resolver()
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    generator = Generator(template_dir)
    validator = Validator()
    reporter = Reporter()

    try:
        # 1. Fetch
        project_root = fetcher.fetch()

        # 2. Analyze
        detected_stacks = analyzer.analyze(project_root)

        # 3. Resolve
        context = resolver.resolve(detected_stacks, str(project_root))

        # 4. Generate
        output_dir.mkdir(parents=True, exist_ok=True)
        generator.generate(context, output_dir)

        # 5. Validate
        success = validator.validate(output_dir)

        # 6. Report
        reporter.report(context, output_dir, success)

        if not success:
            logger.error("Validation failed. See report for details.")
            sys.exit(1)

        return project_root, context

    except Exception as e:
        logger.exception("An error occurred during execution")
        sys.exit(1)
    finally:
        fetcher.cleanup()


@app.command()
def deploy(
    repo_url: str = typer.Argument(..., help="GitHub/GitLab URL to analyze and deploy"),
    project_name: Optional[str] = typer.Option(None, "--name", "-n", help="Project name (auto-detected if not provided)"),
    gitlab_url: str = typer.Option("http://localhost:8080", "--gitlab", help="GitLab server URL"),
    gitlab_token: str = typer.Option(..., "--token", "-t", help="GitLab API token"),
    sonar_url: str = typer.Option("http://localhost:9000", "--sonar", help="SonarQube server URL"),
    sonar_token: str = typer.Option("", "--sonar-token", help="SonarQube token (auto-generated if not provided)"),
    nexus_url: str = typer.Option("http://localhost:8081", "--nexus", help="Nexus server URL"),
    nexus_user: str = typer.Option("admin", "--nexus-user", help="Nexus username"),
    nexus_password: str = typer.Option("admin123", "--nexus-password", help="Nexus password"),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Wait for pipeline completion"),
    timeout: int = typer.Option(600, "--timeout", help="Pipeline timeout in seconds"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """
    🚀 FULL DEPLOYMENT: Analyze repo, generate CI/CD, deploy to GitLab, SonarQube & Nexus.

    This command does everything in one shot:
    1. Clones and analyzes the repository
    2. Generates CI/CD configuration
    3. Creates GitLab project and configures variables
    4. Creates SonarQube project
    5. Pushes code and runs pipeline
    6. Waits for results and shows summary

    Example:
        python -m autopipe deploy https://github.com/user/repo.git -t your-gitlab-token
    """
    setup_logging(verbose)
    logger = logging.getLogger("autopipe")

    # Extract project name from URL if not provided
    if not project_name:
        from urllib.parse import urlparse
        parsed = urlparse(repo_url)
        project_name = Path(parsed.path).stem
        if project_name.endswith('.git'):
            project_name = project_name[:-4]
        project_name = project_name.replace('_', '-').lower()

    logger.info("=" * 60)
    logger.info("🚀 AutoPipe Full Deployment")
    logger.info("=" * 60)
    logger.info(f"Repository:    {repo_url}")
    logger.info(f"Project Name:  {project_name}")
    logger.info(f"GitLab:        {gitlab_url}")
    logger.info(f"SonarQube:     {sonar_url}")
    logger.info(f"Nexus:         {nexus_url}")
    logger.info("=" * 60)

    # Import components
    from autopipe.core.fetcher import Fetcher
    from autopipe.core.analyzer import Analyzer
    from autopipe.core.resolver import Resolver
    from autopipe.generators.generator import Generator
    from autopipe.validators.validator import Validator
    from autopipe.integrations.platform_manager import PlatformManager, PlatformConfig

    # Register Detectors
    from autopipe.detectors.java_detector import JavaDetector
    from autopipe.detectors.python_detector import PythonDetector
    from autopipe.detectors.nodejs_detector import NodeJSDetector
    from autopipe.detectors.go_detector import GoDetector
    from autopipe.detectors.dotnet_detector import DotNetDetector
    from autopipe.detectors.php_detector import PhpDetector

    # Setup output directory - use system temp or local .temp folder
    import tempfile
    base_temp = Path(tempfile.gettempdir()) / "autopipe"
    output_dir = base_temp / f"{project_name}-output"
    output_dir.mkdir(parents=True, exist_ok=True)

    fetcher = Fetcher(repo_url)

    try:
        # PHASE 1: Fetch and Analyze
        logger.info("\n📥 PHASE 1: Fetching Repository")
        logger.info("-" * 40)
        project_root = fetcher.fetch()
        logger.info(f"✓ Repository fetched to: {project_root}")

        # PHASE 2: Analyze
        logger.info("\n🔍 PHASE 2: Analyzing Code")
        logger.info("-" * 40)
        analyzer = Analyzer()
        analyzer.register_detector(JavaDetector())
        analyzer.register_detector(PythonDetector())
        analyzer.register_detector(NodeJSDetector())
        analyzer.register_detector(GoDetector())
        analyzer.register_detector(DotNetDetector())
        analyzer.register_detector(PhpDetector())

        detected_stacks = analyzer.analyze(project_root)

        if detected_stacks:
            for stack in detected_stacks:
                logger.info(f"✓ Detected: {stack.language} ({stack.framework or 'no framework'})")
        else:
            logger.warning("No language/framework detected, using defaults")

        # PHASE 3: Generate CI/CD
        logger.info("\n⚙️  PHASE 3: Generating CI/CD Configuration")
        logger.info("-" * 40)

        resolver = Resolver()
        context = resolver.resolve(detected_stacks, str(project_root))

        # Override metadata.name with CLI --name parameter for consistent naming
        # This ensures SonarQube, GitLab, and Nexus all use the same project name
        context.metadata.name = project_name

        template_dir = Path(__file__).resolve().parent.parent / "templates"
        generator = Generator(template_dir)
        generator.generate(context, output_dir)

        validator = Validator()
        if validator.validate(output_dir):
            logger.info("✓ CI/CD configuration generated and validated")
        else:
            logger.warning("⚠ Validation warnings (continuing anyway)")

        # List generated files
        for f in output_dir.iterdir():
            logger.info(f"  📄 {f.name}")

        # PHASE 4: Deploy to Platforms
        logger.info("\n🚀 PHASE 4: Deploying to Platforms")
        logger.info("-" * 40)

        config = PlatformConfig(
            gitlab_url=gitlab_url,
            gitlab_token=gitlab_token,
            sonar_url=sonar_url,
            sonar_token=sonar_token,
            nexus_url=nexus_url,
            nexus_user=nexus_user,
            nexus_password=nexus_password,
        )

        manager = PlatformManager(config)
        result = manager.deploy_project(
            project_name=project_name,
            source_path=project_root,
            generated_files_path=output_dir,
            wait_for_pipeline=wait,
            pipeline_timeout=timeout
        )

        # Final status
        if result.get("pipeline_status") == "success":
            logger.info("\n" + "🎉" * 20)
            logger.info("DEPLOYMENT SUCCESSFUL!")
            logger.info("🎉" * 20)
            sys.exit(0)
        elif result.get("errors"):
            logger.error(f"\n❌ Deployment errors: {result['errors']}")
            sys.exit(1)
        else:
            logger.info(f"\nPipeline status: {result.get('pipeline_status', 'unknown')}")
            sys.exit(0)

    except Exception as e:
        logger.exception(f"Deployment failed: {e}")
        sys.exit(1)
    finally:
        fetcher.cleanup()


@app.command()
def status(
    gitlab_url: str = typer.Option("http://localhost:8080", "--gitlab", help="GitLab server URL"),
    sonar_url: str = typer.Option("http://localhost:9000", "--sonar", help="SonarQube server URL"),
    nexus_url: str = typer.Option("http://localhost:8081", "--nexus", help="Nexus server URL"),
):
    """
    Check status of all platform services.
    """
    setup_logging(False)
    logger = logging.getLogger("autopipe")
    import requests

    logger.info("Checking platform status...")
    logger.info("-" * 40)

    services = [
        ("GitLab", gitlab_url, "/api/v4/version"),
        ("SonarQube", sonar_url, "/api/system/status"),
        ("Nexus", nexus_url, "/service/rest/v1/status"),
    ]

    all_ok = True
    for name, url, endpoint in services:
        try:
            resp = requests.get(f"{url}{endpoint}", timeout=5)
            if resp.status_code < 400:
                logger.info(f"✅ {name}: Online ({url})")
            else:
                logger.info(f"⚠️  {name}: Responding but returned {resp.status_code}")
                all_ok = False
        except Exception as e:
            logger.info(f"❌ {name}: Offline or unreachable ({url})")
            all_ok = False

    if all_ok:
        logger.info("\n✅ All services are operational!")
    else:
        logger.info("\n⚠️  Some services may have issues")


if __name__ == "__main__":
    app()
