"""Platform Manager - integrates with GitLab, SonarQube, and Nexus."""
import requests
import time
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlparse, quote

logger = logging.getLogger("autopipe")


@dataclass
class PlatformConfig:
    """Configuration for all platforms."""
    # GitLab
    gitlab_url: str = "http://localhost:8080"
    gitlab_token: str = ""

    # SonarQube
    sonar_url: str = "http://localhost:9000"
    sonar_token: str = ""
    sonar_admin_user: str = "admin"
    sonar_admin_password: str = "Qwerty123"

    # Nexus
    nexus_url: str = "http://localhost:8081"
    nexus_user: str = "admin"
    nexus_password: str = "Qwerty123"

    # Git config
    git_user_name: str = "AutoPipe"
    git_user_email: str = "autopipe@example.com"


class GitLabIntegration:
    """GitLab API integration."""

    def __init__(self, url: str, token: str):
        self.url = url.rstrip('/')
        self.token = token
        self.headers = {"PRIVATE-TOKEN": token}

    def create_project(self, name: str, visibility: str = "public") -> Dict[str, Any]:
        """Create a new GitLab project."""
        logger.info(f"Creating GitLab project: {name}")
        response = requests.post(
            f"{self.url}/api/v4/projects",
            headers=self.headers,
            json={"name": name, "visibility": visibility, "initialize_with_readme": False}
        )
        if response.status_code == 201:
            project = response.json()
            # Fix URL for display (replace gitlab.example.com with localhost)
            display_url = project['web_url'].replace("http://gitlab.example.com", self.url).replace("https://gitlab.example.com", self.url)
            logger.info(f"✓ GitLab project created: {display_url}")
            return project
        elif response.status_code == 400 and "has already been taken" in response.text:
            # Project exists, get it
            logger.info(f"Project {name} already exists, fetching...")
            return self.get_project(name)
        else:
            raise Exception(f"Failed to create project: {response.text}")

    def get_project(self, name: str) -> Dict[str, Any]:
        """Get project by name."""
        response = requests.get(
            f"{self.url}/api/v4/projects",
            headers=self.headers,
            params={"search": name}
        )
        projects = response.json()
        for p in projects:
            if p['name'] == name:
                return p
        raise Exception(f"Project {name} not found")

    def set_variable(self, project_id: int, key: str, value: str, protected: bool = False):
        """Set CI/CD variable for project."""
        # Check if exists first
        check = requests.get(
            f"{self.url}/api/v4/projects/{project_id}/variables/{key}",
            headers=self.headers
        )

        if check.status_code == 200:
            # Update existing
            response = requests.put(
                f"{self.url}/api/v4/projects/{project_id}/variables/{key}",
                headers=self.headers,
                data={"value": value, "protected": str(protected).lower()}
            )
        else:
            # Create new
            response = requests.post(
                f"{self.url}/api/v4/projects/{project_id}/variables",
                headers=self.headers,
                data={"key": key, "value": value, "protected": str(protected).lower()}
            )

        if response.status_code in [200, 201]:
            logger.info(f"  ✓ Variable {key} configured")
        else:
            logger.warning(f"  ! Variable {key} may have issues: {response.status_code}")

    def get_pipeline_status(self, project_id: int, pipeline_id: int) -> Dict[str, Any]:
        """Get pipeline status."""
        response = requests.get(
            f"{self.url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}",
            headers=self.headers
        )
        return response.json()

    def get_latest_pipeline(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Get the latest pipeline for project."""
        response = requests.get(
            f"{self.url}/api/v4/projects/{project_id}/pipelines",
            headers=self.headers,
            params={"per_page": 1}
        )
        pipelines = response.json()
        return pipelines[0] if pipelines else None

    def get_pipeline_jobs(self, project_id: int, pipeline_id: int) -> list:
        """Get jobs for a pipeline."""
        response = requests.get(
            f"{self.url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs",
            headers=self.headers
        )
        return response.json()


class SonarQubeIntegration:
    """SonarQube API integration."""

    def __init__(self, url: str, user: str, password: str, token: str = ""):
        self.url = url.rstrip('/')
        self.auth = (user, password)
        self.token = token

    def create_project(self, project_key: str, name: str) -> bool:
        """Create a SonarQube project."""
        logger.info(f"Creating SonarQube project: {name}")
        response = requests.post(
            f"{self.url}/api/projects/create",
            auth=self.auth,
            params={"name": name, "project": project_key}
        )
        if response.status_code == 200:
            logger.info(f"✓ SonarQube project created: {self.url}/dashboard?id={project_key}")
            return True
        elif "already exists" in response.text.lower():
            logger.info(f"SonarQube project {name} already exists")
            return True
        else:
            logger.warning(f"SonarQube project creation: {response.text}")
            return False

    def get_token(self, name: str = "autopipe") -> str:
        """Get or create a user token."""
        if self.token:
            return self.token

        # Try to create a new token
        response = requests.post(
            f"{self.url}/api/user_tokens/generate",
            auth=self.auth,
            params={"name": f"{name}-{int(time.time())}"}
        )
        if response.status_code == 200:
            return response.json().get('token', '')
        return ""

    def get_measures(self, project_key: str) -> Dict[str, Any]:
        """Get project measures."""
        response = requests.get(
            f"{self.url}/api/measures/component",
            auth=self.auth,
            params={
                "component": project_key,
                "metricKeys": "ncloc,bugs,vulnerabilities,code_smells,coverage,security_rating"
            }
        )
        return response.json() if response.status_code == 200 else {}


class PlatformManager:
    """Main platform manager that orchestrates all integrations."""

    def __init__(self, config: PlatformConfig):
        self.config = config
        self.gitlab = GitLabIntegration(config.gitlab_url, config.gitlab_token)
        self.sonar = SonarQubeIntegration(
            config.sonar_url,
            config.sonar_admin_user,
            config.sonar_admin_password,
            config.sonar_token
        )

    def deploy_project(
        self,
        project_name: str,
        source_path: Path,
        generated_files_path: Path,
        wait_for_pipeline: bool = True,
        pipeline_timeout: int = 600
    ) -> Dict[str, Any]:
        """
        Deploy a complete project to all platforms.

        Returns a dict with status of all operations.
        """
        result = {
            "project_name": project_name,
            "gitlab_project": None,
            "sonarqube_project": False,
            "pipeline_status": None,
            "pipeline_url": None,
            "errors": []
        }

        try:
            # 1. Create GitLab project
            logger.info("=" * 50)
            logger.info("STEP 1: Creating GitLab Project")
            logger.info("=" * 50)
            gitlab_project = self.gitlab.create_project(project_name)
            result["gitlab_project"] = gitlab_project
            project_id = gitlab_project['id']

            # 2. Configure CI/CD variables
            logger.info("\nSTEP 2: Configuring CI/CD Variables")
            logger.info("-" * 50)
            self._setup_gitlab_variables(project_id)

            # 3. Create SonarQube project
            logger.info("\nSTEP 3: Creating SonarQube Project")
            logger.info("-" * 50)
            result["sonarqube_project"] = self.sonar.create_project(project_name, project_name)

            # 4. Prepare and push code
            logger.info("\nSTEP 4: Pushing Code to GitLab")
            logger.info("-" * 50)
            self._push_code(
                source_path,
                generated_files_path,
                gitlab_project,
                project_name
            )

            # 5. Wait for pipeline (optional)
            if wait_for_pipeline:
                logger.info("\nSTEP 5: Waiting for Pipeline")
                logger.info("-" * 50)
                result["pipeline_status"], result["pipeline_url"] = self._wait_for_pipeline(
                    project_id,
                    timeout=pipeline_timeout
                )

            # 6. Show results
            logger.info("\n" + "=" * 50)
            logger.info("DEPLOYMENT COMPLETE!")
            logger.info("=" * 50)
            self._print_summary(result, project_name)

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            result["errors"].append(str(e))

        return result

    def _setup_gitlab_variables(self, project_id: int):
        """Setup all required CI/CD variables for all package managers."""
        # Convert localhost URLs to Docker network hostnames for CI/CD jobs
        nexus_internal_url = self.config.nexus_url.replace("localhost", "nexus")

        variables = {
            # SonarQube
            "SONAR_TOKEN": self.config.sonar_token or self.sonar.get_token(),
            "SONAR_HOST_URL": "http://sonarqube:9000",
            # Nexus base URL
            "NEXUS_URL": nexus_internal_url,
            "NEXUS_USERNAME": self.config.nexus_user,
            "NEXUS_PASSWORD": self.config.nexus_password,
            # Python (PyPI)
            "PYPI_REPOSITORY_URL": f"{nexus_internal_url}/repository/pypi-hosted/",
            "PYPI_USERNAME": self.config.nexus_user,
            "PYPI_PASSWORD": self.config.nexus_password,
            # Node.js (npm)
            "NPM_REGISTRY_URL": f"{nexus_internal_url}/repository/npm-hosted/",
            "NPM_USERNAME": self.config.nexus_user,
            "NPM_PASSWORD": self.config.nexus_password,
            # Java/Kotlin (Maven)
            "MAVEN_REPOSITORY_URL": f"{nexus_internal_url}/repository/maven-releases/",
            "MAVEN_SNAPSHOTS_URL": f"{nexus_internal_url}/repository/maven-snapshots/",
            "MAVEN_USERNAME": self.config.nexus_user,
            "MAVEN_PASSWORD": self.config.nexus_password,
            # .NET (NuGet)
            "NUGET_REPOSITORY_URL": f"{nexus_internal_url}/repository/nuget-hosted/",
            "NUGET_API_KEY": self.config.nexus_password,
        }

        for key, value in variables.items():
            if value:
                self.gitlab.set_variable(project_id, key, value)

    def _push_code(
        self,
        source_path: Path,
        generated_files_path: Path,
        gitlab_project: Dict,
        project_name: str
    ):
        """Push code to GitLab."""
        import os
        import stat

        def remove_readonly(func, path, excinfo):
            """Handle read-only files on Windows."""
            os.chmod(path, stat.S_IWRITE)
            func(path)

        # Create working directory - use system temp folder
        import tempfile
        base_temp = Path(tempfile.gettempdir()) / "autopipe"
        base_temp.mkdir(parents=True, exist_ok=True)
        work_dir = base_temp / f"{project_name}-deploy"
        if work_dir.exists():
            shutil.rmtree(work_dir, onerror=remove_readonly)

        # Copy source files, excluding .git directory
        logger.info(f"Copying source from {source_path}...")
        shutil.copytree(
            source_path,
            work_dir,
            ignore=shutil.ignore_patterns('.git', '.git/**', '__pycache__', '*.pyc')
        )

        # Handle existing CI/CD configs - backup and replace
        existing_ci_files = ['.gitlab-ci.yml', '.github', '.travis.yml', 'azure-pipelines.yml', 'Jenkinsfile']
        for ci_file in existing_ci_files:
            existing = work_dir / ci_file
            if existing.exists():
                backup_name = f"{ci_file}.autopipe-backup"
                backup_path = work_dir / backup_name
                if existing.is_file():
                    shutil.move(str(existing), str(backup_path))
                    logger.info(f"  Backed up existing {ci_file} to {backup_name}")
                elif existing.is_dir():
                    shutil.move(str(existing), str(backup_path))
                    logger.info(f"  Backed up existing {ci_file}/ to {backup_name}/")

        # Copy generated CI/CD files
        logger.info(f"Copying CI/CD files from {generated_files_path}...")
        for item in generated_files_path.iterdir():
            dest = work_dir / item.name
            if item.is_file():
                shutil.copy2(item, dest)

        # Initialize git and push
        token = self.config.gitlab_token
        gitlab_host = urlparse(self.config.gitlab_url).netloc
        repo_path = gitlab_project['path_with_namespace']

        # URL with embedded credentials
        push_url = f"http://root:{token}@{gitlab_host}/{repo_path}.git"

        commands = [
            ["git", "init"],
            ["git", "config", "user.name", self.config.git_user_name],
            ["git", "config", "user.email", self.config.git_user_email],
            ["git", "add", "-A"],
            ["git", "commit", "-m", "Initial commit via AutoPipe"],
            ["git", "branch", "-M", "main"],
            ["git", "remote", "add", "origin", push_url],
            ["git", "push", "-u", "origin", "main", "--force"],
        ]

        for cmd in commands:
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'  # Replace unencodable characters
            )
            if result.returncode != 0 and "already exists" not in result.stderr:
                if "remote" not in cmd[1]:  # Ignore remote errors
                    logger.debug(f"Command {' '.join(cmd)}: {result.stderr}")

        logger.info(f"✓ Code pushed to GitLab")

    def _wait_for_pipeline(
        self,
        project_id: int,
        timeout: int = 600
    ) -> tuple:
        """Wait for pipeline to complete."""
        logger.info("Waiting for pipeline to start...")

        # Wait for pipeline to appear
        pipeline = None
        for _ in range(30):
            pipeline = self.gitlab.get_latest_pipeline(project_id)
            if pipeline:
                break
            time.sleep(2)

        if not pipeline:
            logger.warning("No pipeline found")
            return "unknown", None

        pipeline_id = pipeline['id']
        pipeline_url = pipeline['web_url']
        # Fix URL for display
        display_url = pipeline_url.replace("http://gitlab.example.com", self.config.gitlab_url).replace("https://gitlab.example.com", self.config.gitlab_url)
        logger.info(f"Pipeline #{pipeline_id} started: {display_url}")

        # Wait for completion
        start_time = time.time()
        last_status = ""

        while time.time() - start_time < timeout:
            status_data = self.gitlab.get_pipeline_status(project_id, pipeline_id)
            status = status_data.get('status', 'unknown')

            if status != last_status:
                logger.info(f"  Pipeline status: {status}")
                last_status = status

                # Show job statuses
                jobs = self.gitlab.get_pipeline_jobs(project_id, pipeline_id)
                for job in sorted(jobs, key=lambda x: x.get('id', 0)):
                    job_status = job.get('status', 'unknown')
                    job_name = job.get('name', 'unknown')
                    emoji = "✓" if job_status == "success" else "✗" if job_status == "failed" else "⏳"
                    if job_status in ['success', 'failed', 'running']:
                        logger.info(f"    {emoji} {job_name}: {job_status}")

            if status in ['success', 'failed', 'canceled']:
                return status, pipeline_url

            time.sleep(10)

        return "timeout", pipeline_url

    def _fix_gitlab_url(self, url: str) -> str:
        """Replace gitlab.example.com with actual localhost URL."""
        if url:
            return url.replace("http://gitlab.example.com", self.config.gitlab_url).replace("https://gitlab.example.com", self.config.gitlab_url)
        return url

    def _print_summary(self, result: Dict, project_name: str):
        """Print deployment summary."""
        gitlab_project = result.get("gitlab_project", {})

        logger.info(f"\nProject: {project_name}")
        logger.info("-" * 40)

        if gitlab_project:
            gitlab_url = self._fix_gitlab_url(gitlab_project.get('web_url', 'N/A'))
            logger.info(f"GitLab:     {gitlab_url}")

        logger.info(f"SonarQube:  {self.config.sonar_url}/dashboard?id={project_name}")
        logger.info(f"Nexus:      {self.config.nexus_url}/#browse/browse:pypi-hosted")

        if result.get("pipeline_url"):
            pipeline_url = self._fix_gitlab_url(result['pipeline_url'])
            logger.info(f"Pipeline:   {pipeline_url}")

        status = result.get("pipeline_status", "unknown")
        if status == "success":
            logger.info("\n✅ All systems operational!")
        elif status == "failed":
            logger.info("\n⚠️  Pipeline had failures - check GitLab for details")
        else:
            logger.info(f"\nPipeline status: {status}")
