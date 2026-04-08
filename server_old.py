from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("django-api-postman-generator")
POSTMAN_API_BASE = "https://api.getpostman.com"


def _strip_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
        return value[1:-1]
    return value


def _load_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, _strip_env_value(value))


def _load_dotenv_candidates() -> None:
    cwd = Path.cwd()
    candidates = [
        cwd / ".env",
        cwd / ".env.local",
        cwd.parent / ".env",
        cwd.parent / ".env.local",
    ]
    for candidate in candidates:
        _load_env_file(candidate)


_load_dotenv_candidates()


@dataclass
class FieldDef:
    name: str
    django_type: str


TYPE_MAP: dict[str, str] = {
    "str": "models.CharField(max_length=255)",
    "string": "models.CharField(max_length=255)",
    "text": "models.TextField()",
    "int": "models.IntegerField()",
    "integer": "models.IntegerField()",
    "float": "models.FloatField()",
    "bool": "models.BooleanField(default=False)",
    "boolean": "models.BooleanField(default=False)",
    "date": "models.DateField()",
    "datetime": "models.DateTimeField()",
    "uuid": "models.UUIDField(unique=True)",
}


# ---------- helpers ----------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _snake(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_")
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower() or "resource"


def _pascal(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", name).strip()
    return "".join(p.capitalize() for p in cleaned.split()) or "Resource"


def _parse_fields(fields: list[str] | None) -> list[FieldDef]:
    if not fields:
        return [FieldDef("name", TYPE_MAP["string"])]

    parsed: list[FieldDef] = []
    for raw in fields:
        if ":" not in raw:
            fname = _snake(raw)
            parsed.append(FieldDef(fname, TYPE_MAP["string"]))
            continue
        left, right = raw.split(":", 1)
        fname = _snake(left)
        mapped = TYPE_MAP.get(right.strip().lower(), TYPE_MAP["string"])
        parsed.append(FieldDef(fname, mapped))
    return parsed


def _find_django_root(project_path: str) -> Path:
    root = Path(project_path).resolve()
    if (root / "manage.py").exists():
        return root

    # fallback: search depth-2 for manage.py
    for child in root.glob("**/manage.py"):
        return child.parent

    return root


def _find_project_pkg(root: Path) -> str | None:
    # Django package that contains settings.py and urls.py
    for candidate in root.iterdir():
        if candidate.is_dir() and (candidate / "settings.py").exists() and (candidate / "urls.py").exists():
            return candidate.name
    return None


def _suggest_app_root(root: Path) -> Path:
    apps_dir = root / "apps"
    return apps_dir if apps_dir.exists() else root


def _app_import_path(root: Path, app_root: Path, app_name: str) -> str:
    app_name = _snake(app_name)
    if app_root == root:
        return app_name
    rel = app_root.relative_to(root)
    return ".".join((*rel.parts, app_name))


def _ensure_include_import(urls_content: str) -> str:
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


def _ensure_installed_app(settings_content: str, app_config_path: str) -> str:
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


def _ensure_urlpattern(urls_content: str, line: str) -> str:
    if line in urls_content:
        return urls_content

    m = re.search(r"urlpatterns\s*=\s*\[(.*?)\]", urls_content, flags=re.S)
    if not m:
        return urls_content + f"\nurlpatterns = [\n    {line}\n]\n"

    block = m.group(1)
    insertion = f"\n    {line}"
    new_block = block + insertion + "\n"
    return urls_content[: m.start(1)] + new_block + urls_content[m.end(1) :]


def _generate_models(resource_class: str, field_defs: list[FieldDef]) -> str:
    fields = "\n".join(f"    {f.name} = {f.django_type}" for f in field_defs)
    return (
        "from django.db import models\n\n\n"
        f"class {resource_class}(models.Model):\n"
        f"{fields}\n"
        "    created_at = models.DateTimeField(auto_now_add=True)\n"
        "    updated_at = models.DateTimeField(auto_now=True)\n\n"
        "    def __str__(self) -> str:\n"
        f"        return str(self.{field_defs[0].name})\n"
    )


def _generate_serializers(resource_class: str) -> str:
    return (
        "from rest_framework import serializers\n"
        f"from .models import {resource_class}\n\n\n"
        f"class {resource_class}Serializer(serializers.ModelSerializer):\n"
        "    class Meta:\n"
        f"        model = {resource_class}\n"
        "        fields = '__all__'\n"
    )


def _generate_views(resource_class: str) -> str:
    return (
        "from rest_framework import viewsets\n"
        f"from .models import {resource_class}\n"
        f"from .serializers import {resource_class}Serializer\n\n\n"
        f"class {resource_class}ViewSet(viewsets.ModelViewSet):\n"
        f"    queryset = {resource_class}.objects.all().order_by('-id')\n"
        f"    serializer_class = {resource_class}Serializer\n"
    )


def _generate_urls(resource_name: str, resource_class: str) -> str:
    route = _snake(resource_name)
    return (
        "from django.urls import include, path\n"
        "from rest_framework.routers import DefaultRouter\n"
        f"from .views import {resource_class}ViewSet\n\n"
        "router = DefaultRouter()\n"
        f"router.register(r'{route}', {resource_class}ViewSet, basename='{route}')\n\n"
        "urlpatterns = [\n"
        "    path('', include(router.urls)),\n"
        "]\n"
    )


def _generate_tests(resource_class: str, resource_name: str) -> str:
    route = _snake(resource_name)
    return (
        "from django.urls import reverse\n"
        "from rest_framework import status\n"
        "from rest_framework.test import APITestCase\n\n\n"
        f"class {resource_class}APITests(APITestCase):\n"
        "    def test_list_endpoint_exists(self):\n"
        f"        url = reverse('{route}-list')\n"
        "        response = self.client.get(url)\n"
        "        self.assertNotEqual(response.status_code, status.HTTP_404_NOT_FOUND)\n"
    )


def _generate_apps_py(app_class: str, app_name: str) -> str:
    return (
        "from django.apps import AppConfig\n\n\n"
        f"class {app_class}Config(AppConfig):\n"
        "    default_auto_field = 'django.db.models.BigAutoField'\n"
        f"    name = '{app_name}'\n"
    )


def _build_postman_folder(resource_name: str, route_prefix: str) -> dict[str, Any]:
    route = _snake(resource_name)
    base = "{{base_url}}"
    collection_route = f"{base}/api/{_snake(route_prefix)}/{route}/"
    item_name = _pascal(resource_name)

    return {
        "name": item_name,
        "item": [
            {
                "name": f"List {item_name}",
                "request": {"method": "GET", "url": collection_route},
            },
            {
                "name": f"Create {item_name}",
                "request": {
                    "method": "POST",
                    "header": [{"key": "Content-Type", "value": "application/json"}],
                    "body": {"mode": "raw", "raw": "{}"},
                    "url": collection_route,
                },
            },
            {
                "name": f"Retrieve {item_name}",
                "request": {"method": "GET", "url": collection_route + "1/"},
            },
            {
                "name": f"Update {item_name}",
                "request": {
                    "method": "PUT",
                    "header": [{"key": "Content-Type", "value": "application/json"}],
                    "body": {"mode": "raw", "raw": "{}"},
                    "url": collection_route + "1/",
                },
            },
            {
                "name": f"Delete {item_name}",
                "request": {"method": "DELETE", "url": collection_route + "1/"},
            },
        ],
    }


def _sync_postman_cloud(
    collection: dict[str, Any],
    api_key: str,
    collection_uid: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }
    payload = json.dumps({"collection": collection}).encode("utf-8")

    if collection_uid:
        url = f"{POSTMAN_API_BASE}/collections/{collection_uid}"
        req = request.Request(url=url, data=payload, headers=headers, method="PUT")
    else:
        query = f"?{parse.urlencode({'workspace': workspace_id})}" if workspace_id else ""
        url = f"{POSTMAN_API_BASE}/collections{query}"
        req = request.Request(url=url, data=payload, headers=headers, method="POST")

    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body) if body else {}
            summary = data.get("collection", {}) if isinstance(data, dict) else {}
            return {
                "ok": True,
                "status_code": resp.status,
                "collection_uid": summary.get("uid", collection_uid),
                "collection_name": summary.get("name", collection.get("info", {}).get("name")),
            }
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        return {
            "ok": False,
            "status_code": exc.code,
            "error": detail or str(exc),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc),
        }


# ---------- plan builder ----------
def _create_plan(
    project_path: str,
    app_name: str,
    resource_name: str,
    fields: list[str] | None,
    route_prefix: str | None,
    include_postman: bool,
) -> dict[str, Any]:
    django_root = _find_django_root(project_path)
    app_root = _suggest_app_root(django_root)
    app_slug = _snake(app_name)
    app_path = app_root / app_slug
    app_import = _app_import_path(django_root, app_root, app_slug)

    resource_class = _pascal(resource_name)
    field_defs = _parse_fields(fields)
    route_prefix_slug = _snake(route_prefix or app_slug)

    project_pkg = _find_project_pkg(django_root)

    file_changes: list[dict[str, Any]] = []

    app_class_name = _pascal(app_slug)
    file_changes.extend(
        [
            {
                "path": str((app_path / "__init__.py").resolve()),
                "mode": "create_or_keep",
                "content": "",
            },
            {
                "path": str((app_path / "apps.py").resolve()),
                "mode": "create_or_overwrite",
                "content": _generate_apps_py(app_class_name, app_import),
            },
            {
                "path": str((app_path / "models.py").resolve()),
                "mode": "create_or_overwrite",
                "content": _generate_models(resource_class, field_defs),
            },
            {
                "path": str((app_path / "serializers.py").resolve()),
                "mode": "create_or_overwrite",
                "content": _generate_serializers(resource_class),
            },
            {
                "path": str((app_path / "views.py").resolve()),
                "mode": "create_or_overwrite",
                "content": _generate_views(resource_class),
            },
            {
                "path": str((app_path / "urls.py").resolve()),
                "mode": "create_or_overwrite",
                "content": _generate_urls(resource_name, resource_class),
            },
            {
                "path": str((app_path / "tests.py").resolve()),
                "mode": "create_or_overwrite",
                "content": _generate_tests(resource_class, resource_name),
            },
        ]
    )

    if project_pkg:
        settings_path = django_root / project_pkg / "settings.py"
        urls_path = django_root / project_pkg / "urls.py"

        settings_content = _read(settings_path)
        app_config_path = f"{app_import}.apps.{app_class_name}Config"
        settings_updated = _ensure_installed_app(settings_content, app_config_path)

        urls_content = _read(urls_path)
        urls_content = _ensure_include_import(urls_content)
        line = f"path('api/{route_prefix_slug}/', include('{app_import}.urls')),"  # noqa: E501
        urls_updated = _ensure_urlpattern(urls_content, line)

        file_changes.extend(
            [
                {
                    "path": str(settings_path.resolve()),
                    "mode": "patch",
                    "content": settings_updated,
                },
                {
                    "path": str(urls_path.resolve()),
                    "mode": "patch",
                    "content": urls_updated,
                },
            ]
        )

    if include_postman:
        postman_path = django_root / "postman_collection.json"
        current = _read(postman_path)
        if current:
            try:
                collection = json.loads(current)
            except json.JSONDecodeError:
                collection = {}
        else:
            collection = {}

        if "info" not in collection:
            collection["info"] = {
                "name": "Django Generated APIs",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            }
        if "item" not in collection or not isinstance(collection["item"], list):
            collection["item"] = []

        folder_name = _pascal(resource_name)
        existing_names = {x.get("name") for x in collection["item"] if isinstance(x, dict)}
        if folder_name not in existing_names:
            collection["item"].append(_build_postman_folder(resource_name, route_prefix_slug))

        file_changes.append(
            {
                "path": str(postman_path.resolve()),
                "mode": "create_or_patch_json",
                "content": json.dumps(collection, indent=2),
            }
        )

    return {
        "project_path": str(django_root),
        "project_package": project_pkg,
        "app_name": app_slug,
        "app_import": app_import,
        "resource_name": _snake(resource_name),
        "resource_class": resource_class,
        "fields": [f"{f.name}:{f.django_type}" for f in field_defs],
        "route_prefix": route_prefix_slug,
        "changes": file_changes,
    }


def _apply_plan(plan: dict[str, Any], overwrite: bool = True) -> dict[str, Any]:
    created: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for change in plan.get("changes", []):
        path = Path(change["path"])
        mode = change["mode"]
        content = change.get("content", "")

        exists = path.exists()
        if exists and mode in {"create_or_overwrite", "create_or_patch_json"} and not overwrite:
            # patch mode always updates. create_or_overwrite respects overwrite.
            if mode == "create_or_overwrite":
                skipped.append(str(path))
                continue

        _write(path, content)
        if exists:
            updated.append(str(path))
        else:
            created.append(str(path))

    return {"created": created, "updated": updated, "skipped": skipped}


# ---------- MCP tools ----------
@mcp.tool()
def detect_project_type(project_path: str) -> dict[str, Any]:
    """Detect whether target path is a Django project and return discovery metadata."""
    root = _find_django_root(project_path)
    project_pkg = _find_project_pkg(root)

    return {
        "detected": bool((root / "manage.py").exists() and project_pkg),
        "framework": "django" if (root / "manage.py").exists() else "unknown",
        "django_root": str(root),
        "project_package": project_pkg,
        "apps_root": str(_suggest_app_root(root)),
    }


@mcp.tool()
def suggest_target_path(project_path: str, app_name: str) -> dict[str, str]:
    """Suggest best path for a new Django app/module."""
    root = _find_django_root(project_path)
    app_root = _suggest_app_root(root)
    app_slug = _snake(app_name)
    return {
        "django_root": str(root),
        "app_root": str(app_root),
        "suggested_app_path": str((app_root / app_slug).resolve()),
    }


@mcp.tool()
def show_plan(
    project_path: str,
    app_name: str,
    resource_name: str,
    fields: list[str] | None = None,
    route_prefix: str | None = None,
    include_postman: bool = True,
) -> dict[str, Any]:
    """Build a dry-run plan for generating Django API files + optional Postman collection updates."""
    return _create_plan(
        project_path=project_path,
        app_name=app_name,
        resource_name=resource_name,
        fields=fields,
        route_prefix=route_prefix,
        include_postman=include_postman,
    )


@mcp.tool()
def apply_changes(plan: dict[str, Any], overwrite: bool = True) -> dict[str, Any]:
    """Apply a previously generated plan to filesystem."""
    result = _apply_plan(plan, overwrite=overwrite)
    return {"status": "ok", **result}


@mcp.tool()
def sync_postman_collection(
    collection_path: str,
    api_key: str | None = None,
    collection_uid: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Push a local postman_collection.json to Postman Cloud using API key auth."""
    key = api_key or os.getenv("POSTMAN_API_KEY")
    if not key:
        return {
            "ok": False,
            "error": "Missing Postman API key. Provide api_key or set POSTMAN_API_KEY env var.",
        }

    path = Path(collection_path).resolve()
    if not path.exists():
        return {"ok": False, "error": f"Collection file not found: {path}"}

    try:
        collection = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Invalid JSON in collection file: {exc}"}

    resolved_collection_uid = collection_uid or os.getenv("POSTMAN_COLLECTION_UID")
    resolved_workspace_id = workspace_id or os.getenv("POSTMAN_WORKSPACE_ID")

    result = _sync_postman_cloud(
        collection=collection,
        api_key=key,
        collection_uid=resolved_collection_uid,
        workspace_id=resolved_workspace_id,
    )
    return {"collection_path": str(path), **result}


@mcp.tool()
def create_django_api(
    project_path: str,
    app_name: str,
    resource_name: str,
    fields: list[str] | None = None,
    route_prefix: str | None = None,
    include_postman: bool = True,
    overwrite: bool = True,
    postman_sync: bool = False,
    postman_api_key: str | None = None,
    postman_collection_uid: str | None = None,
    postman_workspace_id: str | None = None,
) -> dict[str, Any]:
    """One-shot helper: create plan and immediately apply it for a Django API resource."""
    plan = _create_plan(
        project_path=project_path,
        app_name=app_name,
        resource_name=resource_name,
        fields=fields,
        route_prefix=route_prefix,
        include_postman=include_postman,
    )
    applied = _apply_plan(plan, overwrite=overwrite)
    response: dict[str, Any] = {
        "status": "ok",
        "summary": {
            "django_root": plan["project_path"],
            "app": plan["app_import"],
            "resource": plan["resource_class"],
            "route_prefix": plan["route_prefix"],
        },
        **applied,
    }

    if include_postman and postman_sync:
        postman_file = next(
            (
                change["path"]
                for change in plan.get("changes", [])
                if str(change.get("path", "")).endswith("postman_collection.json")
            ),
            None,
        )
        if postman_file:
            key = postman_api_key or os.getenv("POSTMAN_API_KEY")
            resolved_collection_uid = postman_collection_uid or os.getenv("POSTMAN_COLLECTION_UID")
            resolved_workspace_id = postman_workspace_id or os.getenv("POSTMAN_WORKSPACE_ID")
            if not key:
                response["postman_sync"] = {
                    "ok": False,
                    "error": "Missing Postman API key. Provide postman_api_key or set POSTMAN_API_KEY.",
                }
            else:
                try:
                    collection = json.loads(Path(postman_file).read_text(encoding="utf-8"))
                    response["postman_sync"] = _sync_postman_cloud(
                        collection=collection,
                        api_key=key,
                        collection_uid=resolved_collection_uid,
                        workspace_id=resolved_workspace_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    response["postman_sync"] = {"ok": False, "error": str(exc)}

    return response


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
