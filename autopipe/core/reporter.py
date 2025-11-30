import json
import logging
from pathlib import Path
from typing import Any, Dict
from rich.console import Console
from rich.table import Table
from autopipe.core.models import ProjectContext

logger = logging.getLogger("autopipe")
console = Console()

class Reporter:
    def report(self, context: ProjectContext, output_dir: Path, success: bool):
        """
        Generates a JSON report and prints a summary to the console.
        """
        report_data = {
            "project_name": context.metadata.name,
            "detected_stack": context.stack.model_dump(),
            "output_dir": str(output_dir),
            "success": success
        }
        
        # Save JSON report
        report_path = output_dir / "autopipe_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        
        self._print_summary(context, output_dir, success)

    def _print_summary(self, context: ProjectContext, output_dir: Path, success: bool):
        table = Table(title="AutoPipe Execution Summary")
        
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Project Name", context.metadata.name)
        table.add_row("Language", context.stack.language.value)
        table.add_row("Framework", context.stack.framework.value)
        table.add_row("Build Tool", context.stack.build_tool.value)
        table.add_row("Language Version", context.stack.language_version)
        table.add_row("Output Directory", str(output_dir))
        table.add_row("Status", "[green]SUCCESS[/green]" if success else "[red]FAILED[/red]")
        
        console.print(table)
        console.print(f"\n[bold]Full report saved to:[/bold] {output_dir / 'autopipe_report.json'}")
