"""Type definitions for the API generator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class Framework(str, Enum):
    """Supported frameworks."""

    DJANGO = "django"
    LARAVEL = "laravel"
    EXPRESS = "express"
    FASTAPI = "fastapi"
    FLASK = "flask"
    SPRING_BOOT = "spring_boot"
    UNKNOWN = "unknown"


class HttpMethod(str, Enum):
    """HTTP methods for API endpoints."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


@dataclass
class FieldDefinition:
    """Represents a field in a resource model."""

    name: str
    type: str
    nullable: bool = False
    default: Any = None

    def __post_init__(self) -> None:
        """Normalize field name."""
        self.name = self.name.strip().lower()


@dataclass
class ProjectContext:
    """Context information about the detected project."""

    framework: Framework
    root_path: Path
    project_name: str | None = None
    entry_file: Path | None = None
    config_file: Path | None = None
    package_manager: str | None = None

    def __str__(self) -> str:
        return f"{self.framework.value} project at {self.root_path}"


@dataclass
class GeneratedFile:
    """Represents a generated file."""

    path: Path
    content: str
    overwrite: bool = True


@dataclass
class PostmanEndpoint:
    """Represents a Postman API endpoint."""

    name: str
    method: HttpMethod
    url: str
    headers: dict[str, str] | None = None
    body: dict[str, Any] | None = None


@dataclass
class GenerationResult:
    """Result of code generation operation."""

    files: list[GeneratedFile]
    postman_endpoints: list[PostmanEndpoint]
    messages: list[str]
    success: bool = True
