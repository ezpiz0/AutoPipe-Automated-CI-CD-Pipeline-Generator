import shutil
import tempfile
import logging
from pathlib import Path
from typing import Optional
from git import Repo

logger = logging.getLogger("autopipe")

class Fetcher:
    def __init__(self, repo_url_or_path: str):
        self.repo_url_or_path = repo_url_or_path
        self.temp_dir: Optional[Path] = None
        self.local_path: Optional[Path] = None

    def fetch(self) -> Path:
        """
        Clones the repo if it's a URL, or verifies the path if it's local.
        Returns the path to the repository root.
        """
        # Check if it's a local path
        path = Path(self.repo_url_or_path)
        if path.exists() and path.is_dir():
            logger.info(f"Using local repository at: {path}")
            self.local_path = path
            return path

        # Assume it's a URL - use system temp folder
        temp_base = Path(tempfile.gettempdir()) / "autopipe"
        temp_base.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="autopipe_", dir=str(temp_base)))
        logger.info(f"Cloning {self.repo_url_or_path} to {self.temp_dir}...")
        try:
            Repo.clone_from(self.repo_url_or_path, self.temp_dir)
            return self.temp_dir
        except Exception as e:
            logger.error(f"Failed to clone repository: {e}")
            self.cleanup()
            raise

    def cleanup(self):
        if self.temp_dir and self.temp_dir.exists():
            logger.info(f"Cleaning up temporary directory: {self.temp_dir}")
            shutil.rmtree(self.temp_dir, ignore_errors=True)
