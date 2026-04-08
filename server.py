"""Multi-framework API + Postman MCP Server."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from mcp.server.fastmcp import FastMCP

from src.factory import GeneratorFactory
from src.types import FieldDefinition, Framework

mcp = FastMCP("multi-framework-api-postman-generator")
POSTMAN_API_BASE = "https://api.getpostman.com"


# Environment loading
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
    candidates = [cwd / ".env", cwd / ".env.local", cwd.parent / ".env", cwd.parent / ".env.local"]
    for candidate in candidates:
        _load_env_file(candidate)


_load_dotenv_candidates()


# Helpers
def _parse_fields(field_specs: list[str] | None) -> list[FieldDefinition]:
    if not field_specs:
        return [FieldDefinition("name", "string")]
    fields = []
    for spec in field_specs:
        if ":" not in spec:
            fields.append(FieldDefinition(spec.strip(), "string"))
            continue
        name, field_type = spec.split(":", 1)
        nullable = False
        if field_type.endswith("?"):
            nullable = True
            field_type = field_type[:-1]
        fields.append(FieldDefinition(name=name.strip(), type=field_type.strip(), nullable=nullable))
    return fields


def _write_files(files: list, overwrite: bool = True) -> list[str]:
    written = []
    for file in files:
        if not overwrite and file.path.exists():
            continue
        file.path.parent.mkdir(parents=True, exist_ok=True)
        file.path.write_text(file.content, encoding="utf-8")
        written.append(str(file.path))
    return written


def _build_postman_collection(collection_name: str, base_url: str, folders: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "info": {"name": collection_name, "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
        "variable": [{"key": "base_url", "value": base_url, "type": "string"}],
        "item": folders,
    }


def _postman_endpoint_to_folder(endpoints: list, folder_name: str) -> dict[str, Any]:
    items = []
    for endpoint in endpoints:
        item = {"name": endpoint.name, "request": {"method": endpoint.method.value, "url": endpoint.url}}
        if endpoint.headers:
            item["request"]["header"] = [{"key": k, "value": v} for k, v in endpoint.headers.items()]
        if endpoint.body is not None:
            item["request"]["body"] = {"mode": "raw", "raw": json.dumps(endpoint.body, indent=2)}
        items.append(item)
    return {"name": folder_name, "item": items}


def _sync_postman_cloud(collection: dict[str, Any], api_key: str, collection_uid: str | None = None, workspace_id: str | None = None) -> dict[str, Any]:
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
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
            return {"ok": True, "status_code": resp.status, "collection_uid": summary.get("uid", collection_uid), "collection_name": summary.get("name", collection.get("info", {}).get("name"))}
    except error.HTTPError as exc:
        return {"ok": False, "status_code": exc.code, "error": exc.read().decode("utf-8")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# MCP Tools
@mcp.tool()
def detect_framework(project_path: str) -> dict[str, Any]:
    """Detect the framework type of a project."""
    try:
        context = GeneratorFactory.detect_framework(project_path)
        return {
            "success": True,
            "framework": context.framework.value,
            "root_path": str(context.root_path),
            "project_name": context.project_name,
            "entry_file": str(context.entry_file) if context.entry_file else None,
            "package_manager": context.package_manager,
        }
    except Exception as e:
        return {"success": False, "framework": "unknown", "error": str(e)}


@mcp.tool()
def generate_api(
    project_path: str,
    resource_name: str,
    fields: list[str],
    app_name: str | None = None,
    route_prefix: str | None = None,
    framework: str | None = None,
    overwrite: bool = True,
    create_postman: bool = True,
    postman_base_url: str = "http://localhost:8000",
) -> dict[str, Any]:
    """Generate REST API boilerplate for any supported framework."""
    try:
        fw = Framework(framework) if framework else None
        generator = GeneratorFactory.create(project_path, fw)
        field_defs = _parse_fields(fields)
        result = generator.generate_resource(resource_name=resource_name, fields=field_defs, app_name=app_name, route_prefix=route_prefix)
        written_files = _write_files(result.files, overwrite=overwrite)
        postman_file = None
        if create_postman and result.postman_endpoints:
            folder = _postman_endpoint_to_folder(result.postman_endpoints, generator.normalize_resource_name(resource_name))
            collection = _build_postman_collection(collection_name=f"{generator.context.project_name or 'API'} Collection", base_url=postman_base_url, folders=[folder])
            postman_path = generator.context.root_path / "postman_collection.json"
            if postman_path.exists():
                existing = json.loads(postman_path.read_text(encoding="utf-8"))
                existing["item"].append(folder)
                collection = existing
            postman_path.write_text(json.dumps(collection, indent=2), encoding="utf-8")
            postman_file = str(postman_path)
        return {"success": True, "framework": generator.context.framework.value, "files_written": written_files, "postman_collection": postman_file, "messages": result.messages}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def sync_postman_collection(collection_path: str, api_key: str | None = None, collection_uid: str | None = None, workspace_id: str | None = None) -> dict[str, Any]:
    """Sync a Postman collection to Postman Cloud."""
    try:
        api_key = api_key or os.environ.get("POSTMAN_API_KEY")
        if not api_key:
            return {"success": False, "error": "Postman API key required"}
        collection_uid = collection_uid or os.environ.get("POSTMAN_COLLECTION_UID")
        workspace_id = workspace_id or os.environ.get("POSTMAN_WORKSPACE_ID")
        collection_file = Path(collection_path)
        if not collection_file.exists():
            return {"success": False, "error": f"Collection file not found: {collection_path}"}
        collection = json.loads(collection_file.read_text(encoding="utf-8"))
        result = _sync_postman_cloud(collection=collection, api_key=api_key, collection_uid=collection_uid, workspace_id=workspace_id)
        if result["ok"]:
            uid = result["collection_uid"]
            return {"success": True, "collection_uid": uid, "collection_name": result["collection_name"], "url": f"https://www.postman.com/collections/{uid}", "action": "updated" if collection_uid else "created"}
        else:
            return {"success": False, "error": result.get("error", "Unknown error"), "status_code": result.get("status_code")}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def list_supported_frameworks() -> dict[str, Any]:
    """Get list of all supported frameworks."""
    return {"frameworks": GeneratorFactory.supported_frameworks(), "count": len(GeneratorFactory.supported_frameworks())}


if __name__ == "__main__":
    mcp.run()
