import logging
from pathlib import Path
from typing import List
from autopipe.core.interfaces import Detector
from autopipe.core.models import DetectedStack

logger = logging.getLogger("autopipe")


class Analyzer:
    """
    Enhanced Analyzer that orchestrates all detectors.
    Supports both single-project and monorepo detection.
    """

    def __init__(self, recursive: bool = True):
        """
        Initialize analyzer.

        Args:
            recursive: If True, search for projects recursively in subdirectories.
                      If False, only check root directory.
        """
        self.detectors: List[Detector] = []
        self.recursive = recursive

    def register_detector(self, detector: Detector):
        """Register a new detector."""
        self.detectors.append(detector)

    def analyze(self, project_root: Path) -> List[DetectedStack]:
        """
        Runs all registered detectors on the project root.
        Returns a list of all detected stacks (could be multiple in a mixed repo).

        If recursive mode is enabled, will search subdirectories for additional projects.
        """
        logger.info(f"Analyzing project structure at {project_root}...")

        if self.recursive:
            return self._analyze_recursive(project_root)
        else:
            return self._analyze_single(project_root)

    def _analyze_single(self, project_root: Path) -> List[DetectedStack]:
        """Analyze only the root directory."""
        results = []
        for detector in self.detectors:
            try:
                result = detector.detect(project_root)
                if result:
                    logger.info(f"Detector {detector.__class__.__name__} found match: {result.language}")
                    results.append(result)
            except Exception as e:
                logger.error(f"Detector {detector.__class__.__name__} failed: {e}")

        return results

    def _analyze_recursive(self, project_root: Path) -> List[DetectedStack]:
        """
        Analyze recursively to find all projects.
        Uses each detector's detect_all method for comprehensive search.
        """
        all_results = []
        seen_paths = set()  # Avoid duplicates

        for detector in self.detectors:
            try:
                # First check root directory
                root_result = detector.detect(project_root)
                if root_result:
                    key = (root_result.language, root_result.project_root or "")
                    if key not in seen_paths:
                        logger.info(f"Detector {detector.__class__.__name__} found at root: {root_result.language}")
                        all_results.append(root_result)
                        seen_paths.add(key)

                        # If it's a multi-module project, don't search inside it
                        if root_result.is_multi_module:
                            continue

                # Search recursively
                recursive_results = detector.detect_all(project_root)
                for result in recursive_results:
                    key = (result.language, result.project_root or "")
                    if key not in seen_paths:
                        logger.info(f"Detector {detector.__class__.__name__} found: {result.language} at {result.project_root or 'root'}")
                        all_results.append(result)
                        seen_paths.add(key)

            except Exception as e:
                logger.error(f"Detector {detector.__class__.__name__} failed: {e}")

        # Log summary
        if all_results:
            logger.info(f"Total projects detected: {len(all_results)}")
            for result in all_results:
                loc = result.project_root or "root"
                logger.debug(f"  - {result.language.value}/{result.framework.value} at {loc}")
        else:
            logger.warning("No projects detected in repository")

        return all_results

    def analyze_path(self, project_root: Path, path: str) -> List[DetectedStack]:
        """
        Analyze a specific subdirectory within the project.
        Useful for analyzing specific parts of a monorepo.

        Args:
            project_root: Root of the repository
            path: Relative path to analyze

        Returns:
            List of detected stacks at that path
        """
        target_path = project_root / path
        if not target_path.exists():
            logger.warning(f"Path does not exist: {target_path}")
            return []

        results = []
        for detector in self.detectors:
            try:
                result = detector.detect(target_path)
                if result:
                    result.project_root = path
                    results.append(result)
            except Exception as e:
                logger.error(f"Detector {detector.__class__.__name__} failed at {path}: {e}")

        return results
