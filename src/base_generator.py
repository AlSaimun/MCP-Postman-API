"""Abstract base generator for all framework generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .types import FieldDefinition, GenerationResult, PostmanEndpoint, ProjectContext


class BaseGenerator(ABC):
    """Abstract base class for framework-specific API generators.
    
    This class defines the contract that all framework generators must implement.
    It follows the Template Method pattern for consistent generation flow.
    """

    def __init__(self, context: ProjectContext) -> None:
        """Initialize the generator with project context.
        
        Args:
            context: Detected project context information
        """
        self.context = context

    @abstractmethod
    def detect_project(self, project_path: Path) -> ProjectContext | None:
        """Detect if this is a valid project for this framework.
        
        Args:
            project_path: Path to the project root
            
        Returns:
            ProjectContext if detected, None otherwise
        """

    @abstractmethod
    def generate_resource(
        self,
        resource_name: str,
        fields: list[FieldDefinition],
        app_name: str | None = None,
        route_prefix: str | None = None,
    ) -> GenerationResult:
        """Generate API resource files.
        
        Args:
            resource_name: Name of the resource (e.g., 'User', 'Product')
            fields: List of field definitions
            app_name: Optional app/module name
            route_prefix: Optional route prefix
            
        Returns:
            GenerationResult with generated files and endpoints
        """

    @abstractmethod
    def get_postman_endpoints(
        self,
        resource_name: str,
        route_prefix: str,
    ) -> list[PostmanEndpoint]:
        """Generate Postman endpoints for the resource.
        
        Args:
            resource_name: Name of the resource
            route_prefix: API route prefix
            
        Returns:
            List of Postman endpoints
        """

    @abstractmethod
    def get_type_mapping(self) -> dict[str, str]:
        """Get framework-specific type mapping.
        
        Returns:
            Dict mapping generic types to framework types
        """

    def normalize_resource_name(self, name: str) -> str:
        """Normalize resource name to framework conventions.
        
        Args:
            name: Raw resource name
            
        Returns:
            Normalized name
        """
        import re
        cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", name).strip()
        return "".join(p.capitalize() for p in cleaned.split()) or "Resource"

    def snake_case(self, name: str) -> str:
        """Convert name to snake_case.
        
        Args:
            name: Input name
            
        Returns:
            snake_case version
        """
        import re
        s = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_")
        s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
        return s.lower() or "resource"

    def kebab_case(self, name: str) -> str:
        """Convert name to kebab-case.
        
        Args:
            name: Input name
            
        Returns:
            kebab-case version
        """
        return self.snake_case(name).replace("_", "-")

    def camel_case(self, name: str) -> str:
        """Convert name to camelCase.
        
        Args:
            name: Input name
            
        Returns:
            camelCase version
        """
        words = self.snake_case(name).split("_")
        return words[0] + "".join(w.capitalize() for w in words[1:])
