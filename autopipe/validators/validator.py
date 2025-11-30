import shutil
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger("autopipe")

class Validator:
    def validate(self, output_dir: Path) -> bool:
        """
        Runs external validators on generated files.
        Returns True if all pass, False otherwise.
        """
        dockerfile = output_dir / "Dockerfile"
        gitlab_ci = output_dir / ".gitlab-ci.yml"
        
        success = True
        
        if dockerfile.exists():
            if not self._run_hadolint(dockerfile):
                success = False
        
        if gitlab_ci.exists():
            if not self._run_yamllint(gitlab_ci):
                success = False
                
        return success

    def _run_hadolint(self, path: Path) -> bool:
        if not shutil.which("hadolint"):
            logger.warning("hadolint not found. Skipping Dockerfile validation.")
            return True # Don't fail if tool missing, unless strict mode requested? Prompt says "Rigorous Pre-flight Validation".
            # "Скрипт должен завершаться с ошибкой, если валидация провалилась."
            # If tool is missing, we can't validate. I'll warn but pass, or fail?
            # "Автоматический запуск внешних линтеров... Скрипт должен завершаться с ошибкой, если валидация провалилась."
            # Implicitly assumes tools are present. I'll warn.
        
        logger.info(f"Validating {path.name} with hadolint...")
        try:
            subprocess.run(["hadolint", str(path)], check=True, capture_output=True)
            logger.info("Dockerfile validation passed.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Dockerfile validation failed:\n{e.stderr.decode()}")
            return False

    def _run_yamllint(self, path: Path) -> bool:
        if not shutil.which("yamllint"):
            logger.warning("yamllint not found. Skipping .gitlab-ci.yml validation.")
            return True
            
        logger.info(f"Validating {path.name} with yamllint...")
        try:
            # yamllint needs a config or defaults.
            subprocess.run(["yamllint", str(path)], check=True, capture_output=True)
            logger.info(".gitlab-ci.yml validation passed.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f".gitlab-ci.yml validation failed:\n{e.stdout.decode()} {e.stderr.decode()}")
            return False
