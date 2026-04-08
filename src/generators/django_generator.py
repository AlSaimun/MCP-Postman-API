"""Django REST Framework API generator."""

from __future__ import annotations

import re
from pathlib import Path

from ..base_generator import BaseGenerator
from ..types import FieldDefinition, GeneratedFile, GenerationResult, HttpMethod, PostmanEndpoint, ProjectContext, Framework


class DjangoGenerator(BaseGenerator):
    """Generator for Django REST Framework APIs."""

    TYPE_MAPPING = {
        "str": "models.CharField(max_length=255)",
        "string": "models.CharField(max_length=255)",
        "text": "models.TextField()",
        "int": "models.IntegerField()",
        "integer": "models.IntegerField()",
        "float": "models.FloatField()",
        "decimal": "models.DecimalField(max_digits=10, decimal_places=2)",
        "bool": "models.BooleanField(default=False)",
        "boolean": "models.BooleanField(default=False)",
        "date": "models.DateField()",
        "datetime": "models.DateTimeField()",
        "timestamp": "models.DateTimeField()",
        "uuid": "models.UUIDField(unique=True)",
        "email": "models.EmailField()",
        "url": "models.URLField()",
        "json": "models.JSONField()",
    }

    def detect_project(self, project_path: Path) -> ProjectContext | None:
        """Detect Django project."""
        manage_py = project_path / "manage.py"
        if not manage_py.exists():
            for candidate in project_path.glob("**/manage.py"):
                project_path = candidate.parent
                manage_py = candidate
                break
            else:
                return None

        project_name = self._find_project_package(project_path)
        return ProjectContext(
            framework=Framework.DJANGO,
            root_path=project_path,
            project_name=project_name,
            entry_file=manage_py,
            package_manager="pip",
        )

    def generate_resource(
        self,
        resource_name: str,
        fields: list[FieldDefinition],
        app_name: str | None = None,
        route_prefix: str | None = None,
    ) -> GenerationResult:
        """Generate Django REST Framework resource files."""
        if not app_name:
            app_name = self.snake_case(resource_name)

        resource_class = self.normalize_resource_name(resource_name)
        app_slug = self.snake_case(app_name)
        route_prefix = route_prefix or app_slug

        # Determine app location
        apps_dir = self.context.root_path / "apps"
        app_root = apps_dir if apps_dir.exists() else self.context.root_path
        app_path = app_root / app_slug

        # Calculate import path
        if app_root == self.context.root_path:
            app_import = app_slug
        else:
            rel = app_root.relative_to(self.context.root_path)
            app_import = ".".join((*rel.parts, app_slug))

        # Generate files
        files = []
        messages = []

        # App files
        files.append(GeneratedFile(app_path / "__init__.py", ""))
        files.append(
            GeneratedFile(
                app_path / "apps.py",
                self._generate_apps_config(app_slug, app_import),
            )
        )
        files.append(
            GeneratedFile(
                app_path / "models.py",
                self._generate_models(resource_class, fields),
            )
        )
        files.append(
            GeneratedFile(
                app_path / "serializers.py",
                self._generate_serializers(resource_class),
            )
        )
        files.append(
            GeneratedFile(
                app_path / "views.py",
                self._generate_views(resource_class),
            )
        )
        files.append(
            GeneratedFile(
                app_path / "urls.py",
                self._generate_urls(resource_name, resource_class),
            )
        )
        files.append(
            GeneratedFile(
                app_path / "tests.py",
                self._generate_tests(resource_class, resource_name),
            )
        )

        # Wire into project
        if self.context.project_name:
            project_pkg_path = self.context.root_path / self.context.project_name

            # Update settings.py
            settings_file = project_pkg_path / "settings.py"
            if settings_file.exists():
                settings_content = settings_file.read_text(encoding="utf-8")
                updated_settings = self._ensure_installed_app(
                    settings_content, f"{app_import}.apps.{self.normalize_resource_name(app_slug)}Config"
                )
                files.append(GeneratedFile(settings_file, updated_settings, overwrite=True))
                messages.append(f"Updated {settings_file.relative_to(self.context.root_path)}")

            # Update urls.py
            urls_file = project_pkg_path / "urls.py"
            if urls_file.exists():
                urls_content = urls_file.read_text(encoding="utf-8")
                updated_urls = self._ensure_include_import(urls_content)
                route_line = f"path('api/{self.snake_case(route_prefix)}/', include('{app_import}.urls')),"
                updated_urls = self._ensure_urlpattern(updated_urls, route_line)
                files.append(GeneratedFile(urls_file, updated_urls, overwrite=True))
                messages.append(f"Updated {urls_file.relative_to(self.context.root_path)}")

        # Generate Postman endpoints
        postman_endpoints = self.get_postman_endpoints(resource_name, route_prefix)

        messages.append(f"Generated Django app '{app_slug}' with resource '{resource_class}'")
        messages.append("Run: python manage.py makemigrations && python manage.py migrate")

        return GenerationResult(
            files=files,
            postman_endpoints=postman_endpoints,
            messages=messages,
        )

    def get_postman_endpoints(self, resource_name: str, route_prefix: str) -> list[PostmanEndpoint]:
        """Generate Postman endpoints for Django REST API."""
        route = self.snake_case(resource_name)
        base_url = f"{{{{base_url}}}}/api/{self.snake_case(route_prefix)}/{route}/"
        item_name = self.normalize_resource_name(resource_name)

        return [
            PostmanEndpoint(
                name=f"List {item_name}",
                method=HttpMethod.GET,
                url=base_url,
            ),
            PostmanEndpoint(
                name=f"Create {item_name}",
                method=HttpMethod.POST,
                url=base_url,
                headers={"Content-Type": "application/json"},
                body={},
            ),
            PostmanEndpoint(
                name=f"Retrieve {item_name}",
                method=HttpMethod.GET,
                url=base_url + "1/",
            ),
            PostmanEndpoint(
                name=f"Update {item_name}",
                method=HttpMethod.PUT,
                url=base_url + "1/",
                headers={"Content-Type": "application/json"},
                body={},
            ),
            PostmanEndpoint(
                name=f"Partial Update {item_name}",
                method=HttpMethod.PATCH,
                url=base_url + "1/",
                headers={"Content-Type": "application/json"},
                body={},
            ),
            PostmanEndpoint(
                name=f"Delete {item_name}",
                method=HttpMethod.DELETE,
                url=base_url + "1/",
            ),
        ]

    def get_type_mapping(self) -> dict[str, str]:
        """Get Django type mapping."""
        return self.TYPE_MAPPING

    def _find_project_package(self, root: Path) -> str | None:
        """Find Django project package with settings.py and urls.py."""
        for candidate in root.iterdir():
            if candidate.is_dir():
                if (candidate / "settings.py").exists() and (candidate / "urls.py").exists():
                    return candidate.name
        return None

    def _generate_models(self, resource_class: str, fields: list[FieldDefinition]) -> str:
        """Generate Django models.py file."""
        field_lines = []
        for field in fields:
            field_type = self.TYPE_MAPPING.get(field.type.lower(), self.TYPE_MAPPING["string"])
            if field.nullable:
                field_type = field_type.replace(")", ", null=True, blank=True)")
            field_lines.append(f"    {field.name} = {field_type}")

        field_str = "\n".join(field_lines)
        first_field = fields[0].name if fields else "id"

        return f'''from django.db import models


class {resource_class}(models.Model):
{field_str}
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.{first_field})

    class Meta:
        ordering = ['-created_at']
'''

    def _generate_serializers(self, resource_class: str) -> str:
        """Generate Django serializers.py file."""
        return f'''from rest_framework import serializers
from .models import {resource_class}


class {resource_class}Serializer(serializers.ModelSerializer):
    class Meta:
        model = {resource_class}
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')
'''

    def _generate_views(self, resource_class: str) -> str:
        """Generate Django views.py file."""
        return f'''from rest_framework import viewsets, filters
from rest_framework.permissions import AllowAny
from .models import {resource_class}
from .serializers import {resource_class}Serializer


class {resource_class}ViewSet(viewsets.ModelViewSet):
    queryset = {resource_class}.objects.all().order_by('-id')
    serializer_class = {resource_class}Serializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['id']
    ordering_fields = '__all__'
'''

    def _generate_urls(self, resource_name: str, resource_class: str) -> str:
        """Generate Django urls.py file."""
        route = self.snake_case(resource_name)
        return f'''from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import {resource_class}ViewSet

router = DefaultRouter()
router.register(r'{route}', {resource_class}ViewSet, basename='{route}')

urlpatterns = [
    path('', include(router.urls)),
]
'''

    def _generate_tests(self, resource_class: str, resource_name: str) -> str:
        """Generate Django tests.py file."""
        route = self.snake_case(resource_name)
        return f'''from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class {resource_class}APITests(APITestCase):
    def test_list_endpoint_exists(self):
        url = reverse('{route}-list')
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_{route.lower()}(self):
        url = reverse('{route}-list')
        data = {{}}
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
'''

    def _generate_apps_config(self, app_slug: str, app_import: str) -> str:
        """Generate Django apps.py file."""
        app_class = self.normalize_resource_name(app_slug)
        return f'''from django.apps import AppConfig


class {app_class}Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = '{app_import}'
'''

    def _ensure_include_import(self, urls_content: str) -> str:
        """Ensure 'include' is imported in urls.py."""
        if "from django.urls import" in urls_content:
            if "include" in urls_content:
                return urls_content
            return re.sub(
                r"from django\.urls import ([^\n]+)",
                lambda m: f"from django.urls import {m.group(1).strip()}, include",
                urls_content,
                count=1,
            )
        return "from django.urls import include, path\n" + urls_content

    def _ensure_installed_app(self, settings_content: str, app_config_path: str) -> str:
        """Ensure app is added to INSTALLED_APPS."""
        if app_config_path in settings_content:
            return settings_content

        m = re.search(r"INSTALLED_APPS\s*=\s*\[(.*?)\]", settings_content, flags=re.S)
        if not m:
            return settings_content + f"\nINSTALLED_APPS = ['{app_config_path}']\n"

        block = m.group(1)
        addition = f"\n    '{app_config_path}',"
        if "rest_framework" not in block:
            addition = "\n    'rest_framework'," + addition

        new_block = block + addition + "\n"
        return settings_content[: m.start(1)] + new_block + settings_content[m.end(1) :]

    def _ensure_urlpattern(self, urls_content: str, line: str) -> str:
        """Ensure URL pattern is added to urlpatterns."""
        if line in urls_content:
            return urls_content

        m = re.search(r"urlpatterns\s*=\s*\[(.*?)\]", urls_content, flags=re.S)
        if not m:
            return urls_content + f"\nurlpatterns = [\n    {line}\n]\n"

        block = m.group(1)
        insertion = f"\n    {line}"
        new_block = block + insertion + "\n"
        return urls_content[: m.start(1)] + new_block + urls_content[m.end(1) :]
