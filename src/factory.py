"""Generator factory for creating framework-specific generators."""

from __future__ import annotations

from pathlib import Path

from .base_generator import BaseGenerator
from .framework_detector import FrameworkDetector
from .generators import (
    DjangoGenerator,
    ExpressGenerator,
    FastAPIGenerator,
    FlaskGenerator,
    LaravelGenerator,
    SpringBootGenerator,
)
from .types import Framework, ProjectContext


class GeneratorFactory:
    """Factory for creating framework-specific generators.
    
    This class implements the Factory pattern to instantiate the appropriate
    generator based on the detected or specified framework.
    """

    _GENERATORS = {
        Framework.DJANGO: DjangoGenerator,
        Framework.LARAVEL: LaravelGenerator,
        Framework.EXPRESS: ExpressGenerator,
        Framework.FASTAPI: FastAPIGenerator,
        Framework.FLASK: FlaskGenerator,
        Framework.SPRING_BOOT: SpringBootGenerator,
    }

    @classmethod
    def create(
        cls,
        project_path: str | Path,
        framework: Framework | None = None,
    ) -> BaseGenerator:
        """Create a generator for the given project.
        
        Args:
            project_path: Path to the project directory
            framework: Optional framework override (auto-detected if not provided)
            
        Returns:
            Framework-specific generator instance
            
        Raises:
            ValueError: If framework is unsupported or cannot be detected
        """
        # Auto-detect framework if not specified
        if framework is None:
            context = FrameworkDetector.detect(project_path)
        else:
            # Verify the specified framework
            context = ProjectContext(
                framework=framework,
                root_path=Path(project_path).resolve(),
            )

        # Get the appropriate generator class
        generator_class = cls._GENERATORS.get(context.framework)
        
        if generator_class is None:
            supported = ", ".join(f.value for f in cls._GENERATORS.keys())
            raise ValueError(
                f"Unsupported framework: {context.framework.value}. "
                f"Supported frameworks: {supported}"
            )

        return generator_class(context)

    @classmethod
    def detect_framework(cls, project_path: str | Path) -> ProjectContext:
        """Detect the framework of a project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            ProjectContext with detected framework information
        """
        return FrameworkDetector.detect(project_path)

    @classmethod
    def supported_frameworks(cls) -> list[str]:
        """Get list of supported framework names.
        
        Returns:
            List of supported framework identifiers
        """
        return [f.value for f in cls._GENERATORS.keys()]
