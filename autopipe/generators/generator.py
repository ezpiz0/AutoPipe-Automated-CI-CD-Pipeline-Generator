import logging
from pathlib import Path
from enum import Enum
from jinja2 import Environment, FileSystemLoader, select_autoescape
from autopipe.core.models import ProjectContext, Language, Framework, BuildTool

logger = logging.getLogger("autopipe")


def enum_value(val):
    """Extract value from enum or return as-is."""
    if isinstance(val, Enum):
        return val.value
    return val


class Generator:
    def __init__(self, template_dir: Path):
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True
        )
        # Register custom filters
        self.env.filters['enum_value'] = enum_value

        # Add test for comparing with enum values
        self.env.tests['language'] = lambda x, name: enum_value(x) == name
        self.env.tests['framework'] = lambda x, name: enum_value(x) == name
        self.env.tests['build_tool'] = lambda x, name: enum_value(x) == name

    def generate(self, context: ProjectContext, output_dir: Path):
        logger.info(f"Generating configuration for {context.metadata.name}...")
        
        self._render_template("dockerfile.j2", context, output_dir / "Dockerfile")
        self._render_template("gitlab-ci.j2", context, output_dir / ".gitlab-ci.yml")
        
        logger.info("Generation complete.")

    def _render_template(self, template_name: str, context: ProjectContext, output_path: Path):
        template = self.env.get_template(template_name)

        # Convert stack to a dict-like object with enum values converted to strings
        stack_data = self._prepare_stack_data(context.stack)

        content = template.render(
            stack=stack_data,
            metadata=context.metadata,
            context=context
        )

        output_path.write_text(content, encoding="utf-8")
        logger.info(f"Generated: {output_path}")

    def _prepare_stack_data(self, stack):
        """Convert stack to dict with enum values as strings for Jinja templates."""
        # Create a wrapper that returns enum values as strings
        class StackWrapper:
            def __init__(self, stack_obj):
                self._stack = stack_obj

            def __getattr__(self, name):
                val = getattr(self._stack, name)
                if isinstance(val, Enum):
                    return val.value
                return val

        return StackWrapper(stack)
