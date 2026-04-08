"""Framework detection logic."""

from __future__ import annotations

import json
from pathlib import Path

from .types import Framework, ProjectContext


class FrameworkDetector:
    """Detects the framework type of a project.
    
    Uses marker files and configuration patterns to identify frameworks.
    Implements a chain of responsibility pattern for detection.
    """

    @staticmethod
    def detect(project_path: str | Path) -> ProjectContext:
        """Detect the framework of a project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            ProjectContext with detected framework information
        """
        root = Path(project_path).resolve()

        # Try each detection method in order
        detectors = [
            FrameworkDetector._detect_spring_boot,
            FrameworkDetector._detect_django,
            FrameworkDetector._detect_laravel,
            FrameworkDetector._detect_fastapi,
            FrameworkDetector._detect_flask,
            FrameworkDetector._detect_express,
        ]

        for detector in detectors:
            context = detector(root)
            if context:
                return context

        # Default to unknown
        return ProjectContext(
            framework=Framework.UNKNOWN,
            root_path=root,
        )

    @staticmethod
    def _detect_django(root: Path) -> ProjectContext | None:
        """Detect Django project."""
        # Look for manage.py
        manage_py = root / "manage.py"
        if not manage_py.exists():
            # Try searching in subdirectories
            for candidate in root.glob("**/manage.py"):
                root = candidate.parent
                manage_py = candidate
                break
            else:
                return None

        # Find settings.py to get project name
        project_name = None
        for candidate in root.iterdir():
            if candidate.is_dir():
                settings = candidate / "settings.py"
                urls = candidate / "urls.py"
                if settings.exists() and urls.exists():
                    project_name = candidate.name
                    break

        return ProjectContext(
            framework=Framework.DJANGO,
            root_path=root,
            project_name=project_name,
            entry_file=manage_py,
            package_manager="pip",
        )

    @staticmethod
    def _detect_laravel(root: Path) -> ProjectContext | None:
        """Detect Laravel project."""
        artisan = root / "artisan"
        composer_json = root / "composer.json"

        if not (artisan.exists() and composer_json.exists()):
            return None

        # Verify it's Laravel in composer.json
        try:
            with open(composer_json, encoding="utf-8") as f:
                data = json.load(f)
                require = data.get("require", {})
                if "laravel/framework" not in require:
                    return None
        except (json.JSONDecodeError, OSError):
            return None

        # Get app name from config/app.php
        app_config = root / "config" / "app.php"
        project_name = root.name

        return ProjectContext(
            framework=Framework.LARAVEL,
            root_path=root,
            project_name=project_name,
            entry_file=artisan,
            config_file=app_config,
            package_manager="composer",
        )

    @staticmethod
    def _detect_express(root: Path) -> ProjectContext | None:
        """Detect Express.js project."""
        package_json = root / "package.json"
        if not package_json.exists():
            return None

        try:
            with open(package_json, encoding="utf-8") as f:
                data = json.load(f)
                dependencies = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                
                if "express" not in dependencies:
                    return None

                # Find entry file
                entry_file = None
                if "main" in data:
                    entry_file = root / data["main"]
                else:
                    # Common entry points
                    for candidate in ["index.js", "server.js", "app.js", "index.ts", "server.ts", "app.ts"]:
                        if (root / candidate).exists():
                            entry_file = root / candidate
                            break

                return ProjectContext(
                    framework=Framework.EXPRESS,
                    root_path=root,
                    project_name=data.get("name", root.name),
                    entry_file=entry_file,
                    config_file=package_json,
                    package_manager="npm",
                )
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _detect_fastapi(root: Path) -> ProjectContext | None:
        """Detect FastAPI project."""
        # Look for common FastAPI entry points
        entry_candidates = ["main.py", "app.py", "api.py"]
        
        for candidate in entry_candidates:
            file_path = root / candidate
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if "from fastapi import" in content or "import fastapi" in content:
                        return ProjectContext(
                            framework=Framework.FASTAPI,
                            root_path=root,
                            project_name=root.name,
                            entry_file=file_path,
                            package_manager="pip",
                        )
                except OSError:
                    continue

        # Check requirements.txt or pyproject.toml
        requirements = root / "requirements.txt"
        if requirements.exists():
            try:
                content = requirements.read_text(encoding="utf-8")
                if "fastapi" in content.lower():
                    return ProjectContext(
                        framework=Framework.FASTAPI,
                        root_path=root,
                        project_name=root.name,
                        package_manager="pip",
                    )
            except OSError:
                pass

        return None

    @staticmethod
    def _detect_flask(root: Path) -> ProjectContext | None:
        """Detect Flask project."""
        # Look for common Flask entry points
        entry_candidates = ["app.py", "application.py", "run.py", "wsgi.py"]
        
        for candidate in entry_candidates:
            file_path = root / candidate
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if "from flask import" in content or "import flask" in content:
                        return ProjectContext(
                            framework=Framework.FLASK,
                            root_path=root,
                            project_name=root.name,
                            entry_file=file_path,
                            package_manager="pip",
                        )
                except OSError:
                    continue

        # Check for Flask in __init__.py (application factory pattern)
        init_file = root / "__init__.py"
        if init_file.exists():
            try:
                content = init_file.read_text(encoding="utf-8")
                if "from flask import" in content or "import flask" in content:
                    return ProjectContext(
                        framework=Framework.FLASK,
                        root_path=root,
                        project_name=root.name,
                        entry_file=init_file,
                        package_manager="pip",
                    )
            except OSError:
                pass

        return None

    @staticmethod
    def _detect_spring_boot(root: Path) -> ProjectContext | None:
        """Detect Spring Boot project."""
        # Check for Maven project (pom.xml)
        pom_file = root / "pom.xml"
        if pom_file.exists():
            try:
                content = pom_file.read_text(encoding="utf-8")
                if "spring-boot-starter" in content or "org.springframework.boot" in content:
                    # Find main application class
                    src_main_java = root / "src" / "main" / "java"
                    entry_file = None
                    if src_main_java.exists():
                        for java_file in src_main_java.rglob("*Application.java"):
                            entry_file = java_file
                            break
                    
                    return ProjectContext(
                        framework=Framework.SPRING_BOOT,
                        root_path=root,
                        project_name=root.name,
                        entry_file=entry_file,
                        config_file=pom_file,
                        package_manager="maven",
                    )
            except OSError:
                pass

        # Check for Gradle project (build.gradle or build.gradle.kts)
        for gradle_file in [root / "build.gradle", root / "build.gradle.kts"]:
            if gradle_file.exists():
                try:
                    content = gradle_file.read_text(encoding="utf-8")
                    if "spring-boot" in content or "org.springframework.boot" in content:
                        src_main_java = root / "src" / "main" / "java"
                        entry_file = None
                        if src_main_java.exists():
                            for java_file in src_main_java.rglob("*Application.java"):
                                entry_file = java_file
                                break
                        
                        return ProjectContext(
                            framework=Framework.SPRING_BOOT,
                            root_path=root,
                            project_name=root.name,
                            entry_file=entry_file,
                            config_file=gradle_file,
                            package_manager="gradle",
                        )
                except OSError:
                    pass

        return None
