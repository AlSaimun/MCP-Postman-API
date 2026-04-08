"""Express.js API generator."""

from __future__ import annotations

from pathlib import Path

from ..base_generator import BaseGenerator
from ..types import FieldDefinition, GeneratedFile, GenerationResult, HttpMethod, PostmanEndpoint, ProjectContext, Framework


class ExpressGenerator(BaseGenerator):
    """Generator for Express.js REST APIs."""

    TYPE_MAPPING = {
        "str": "String",
        "string": "String",
        "text": "String",
        "int": "Number",
        "integer": "Number",
        "float": "Number",
        "decimal": "Number",
        "bool": "Boolean",
        "boolean": "Boolean",
        "date": "Date",
        "datetime": "Date",
        "timestamp": "Date",
        "uuid": "String",
        "email": "String",
        "url": "String",
        "json": "Object",
    }

    def detect_project(self, project_path: Path) -> ProjectContext | None:
        """Detect Express.js project."""
        import json

        package_json = project_path / "package.json"
        if not package_json.exists():
            return None

        try:
            with open(package_json, encoding="utf-8") as f:
                data = json.load(f)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                
                if "express" not in deps:
                    return None

                entry_file = None
                if "main" in data:
                    entry_file = project_path / data["main"]
                else:
                    for candidate in ["index.js", "server.js", "app.js", "index.ts", "server.ts", "app.ts"]:
                        if (project_path / candidate).exists():
                            entry_file = project_path / candidate
                            break

                return ProjectContext(
                    framework=Framework.EXPRESS,
                    root_path=project_path,
                    project_name=data.get("name", project_path.name),
                    entry_file=entry_file,
                    config_file=package_json,
                    package_manager="npm",
                )
        except Exception:  # noqa: BLE001
            return None

    def generate_resource(
        self,
        resource_name: str,
        fields: list[FieldDefinition],
        app_name: str | None = None,
        route_prefix: str | None = None,
    ) -> GenerationResult:
        """Generate Express.js resource files."""
        resource_class = self.normalize_resource_name(resource_name)
        route_name = self.camel_case(resource_name)
        route_prefix = route_prefix or "api"

        # Detect if using TypeScript
        is_typescript = self._is_typescript_project()
        ext = "ts" if is_typescript else "js"

        files = []
        messages = []

        # Determine structure (src/ or root)
        src_dir = self.context.root_path / "src"
        base_dir = src_dir if src_dir.exists() else self.context.root_path

        # Model (Mongoose schema)
        models_dir = base_dir / "models"
        model_file = models_dir / f"{resource_class}.{ext}"
        files.append(GeneratedFile(model_file, self._generate_model(resource_class, fields, is_typescript)))

        # Controller
        controllers_dir = base_dir / "controllers"
        controller_file = controllers_dir / f"{route_name}Controller.{ext}"
        files.append(GeneratedFile(controller_file, self._generate_controller(resource_class, route_name, is_typescript)))

        # Routes
        routes_dir = base_dir / "routes"
        route_file = routes_dir / f"{route_name}.{ext}"
        files.append(GeneratedFile(route_file, self._generate_routes(resource_class, route_name, is_typescript)))

        postman_endpoints = self.get_postman_endpoints(resource_name, route_prefix)

        messages.append(f"Generated Express.js resource '{resource_class}'")
        messages.append(f"Add to your app: app.use('/{route_prefix}/{self.kebab_case(resource_name)}', require('./routes/{route_name}'));")
        if "mongoose" in self._get_dependencies():
            messages.append("Remember to connect to MongoDB")

        return GenerationResult(
            files=files,
            postman_endpoints=postman_endpoints,
            messages=messages,
        )

    def get_postman_endpoints(self, resource_name: str, route_prefix: str) -> list[PostmanEndpoint]:
        """Generate Postman endpoints for Express API."""
        route = self.kebab_case(resource_name)
        base_url = f"{{{{base_url}}}}/{route_prefix}/{route}"
        item_name = self.normalize_resource_name(resource_name)

        return [
            PostmanEndpoint(name=f"List {item_name}", method=HttpMethod.GET, url=base_url),
            PostmanEndpoint(
                name=f"Create {item_name}",
                method=HttpMethod.POST,
                url=base_url,
                headers={"Content-Type": "application/json"},
                body={},
            ),
            PostmanEndpoint(name=f"Get {item_name}", method=HttpMethod.GET, url=f"{base_url}/:id"),
            PostmanEndpoint(
                name=f"Update {item_name}",
                method=HttpMethod.PUT,
                url=f"{base_url}/:id",
                headers={"Content-Type": "application/json"},
                body={},
            ),
            PostmanEndpoint(name=f"Delete {item_name}", method=HttpMethod.DELETE, url=f"{base_url}/:id"),
        ]

    def get_type_mapping(self) -> dict[str, str]:
        """Get Express/Mongoose type mapping."""
        return self.TYPE_MAPPING

    def _is_typescript_project(self) -> bool:
        """Check if project uses TypeScript."""
        tsconfig = self.context.root_path / "tsconfig.json"
        return tsconfig.exists()

    def _get_dependencies(self) -> dict:
        """Get project dependencies."""
        import json
        try:
            with open(self.context.config_file, encoding="utf-8") as f:
                data = json.load(f)
                return {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        except Exception:  # noqa: BLE001
            return {}

    def _generate_model(self, resource_class: str, fields: list[FieldDefinition], is_typescript: bool) -> str:
        """Generate Mongoose model."""
        schema_fields = []
        for field in fields:
            field_type = self.TYPE_MAPPING.get(field.type.lower(), "String")
            required = "false" if field.nullable else "true"
            schema_fields.append(f"  {field.name}: {{ type: {field_type}, required: {required} }},")
        
        schema_str = "\n".join(schema_fields)
        
        if is_typescript:
            return f'''import {{ Schema, model, Document }} from 'mongoose';

interface I{resource_class} extends Document {{
  {chr(10).join(f"  {f.name}: {self._ts_type(f.type)};" for f in fields)}
  createdAt: Date;
  updatedAt: Date;
}}

const {resource_class}Schema = new Schema<I{resource_class}>(
  {{
{schema_str}
  }},
  {{ timestamps: true }}
);

export default model<I{resource_class}>('{resource_class}', {resource_class}Schema);
'''
        else:
            return f'''const {{ Schema, model }} = require('mongoose');

const {resource_class}Schema = new Schema(
  {{
{schema_str}
  }},
  {{ timestamps: true }}
);

module.exports = model('{resource_class}', {resource_class}Schema);
'''

    def _generate_controller(self, resource_class: str, route_name: str, is_typescript: bool) -> str:
        """Generate Express controller."""
        if is_typescript:
            return f'''import {{ Request, Response }} from 'express';
import {resource_class} from '../models/{resource_class}';

export const getAll{resource_class}s = async (req: Request, res: Response) => {{
  try {{
    const items = await {resource_class}.find().sort({{ createdAt: -1 }});
    res.json(items);
  }} catch (error) {{
    res.status(500).json({{ message: 'Error fetching {resource_class.lower()}s', error }});
  }}
}};

export const create{resource_class} = async (req: Request, res: Response) => {{
  try {{
    const item = new {resource_class}(req.body);
    await item.save();
    res.status(201).json(item);
  }} catch (error) {{
    res.status(400).json({{ message: 'Error creating {resource_class.lower()}', error }});
  }}
}};

export const get{resource_class}ById = async (req: Request, res: Response) => {{
  try {{
    const item = await {resource_class}.findById(req.params.id);
    if (!item) return res.status(404).json({{ message: '{resource_class} not found' }});
    res.json(item);
  }} catch (error) {{
    res.status(500).json({{ message: 'Error fetching {resource_class.lower()}', error }});
  }}
}};

export const update{resource_class} = async (req: Request, res: Response) => {{
  try {{
    const item = await {resource_class}.findByIdAndUpdate(req.params.id, req.body, {{ new: true }});
    if (!item) return res.status(404).json({{ message: '{resource_class} not found' }});
    res.json(item);
  }} catch (error) {{
    res.status(400).json({{ message: 'Error updating {resource_class.lower()}', error }});
  }}
}};

export const delete{resource_class} = async (req: Request, res: Response) => {{
  try {{
    const item = await {resource_class}.findByIdAndDelete(req.params.id);
    if (!item) return res.status(404).json({{ message: '{resource_class} not found' }});
    res.status(204).send();
  }} catch (error) {{
    res.status(500).json({{ message: 'Error deleting {resource_class.lower()}', error }});
  }}
}};
'''
        else:
            return f'''const {resource_class} = require('../models/{resource_class}');

exports.getAll{resource_class}s = async (req, res) => {{
  try {{
    const items = await {resource_class}.find().sort({{ createdAt: -1 }});
    res.json(items);
  }} catch (error) {{
    res.status(500).json({{ message: 'Error fetching {resource_class.lower()}s', error }});
  }}
}};

exports.create{resource_class} = async (req, res) => {{
  try {{
    const item = new {resource_class}(req.body);
    await item.save();
    res.status(201).json(item);
  }} catch (error) {{
    res.status(400).json({{ message: 'Error creating {resource_class.lower()}', error }});
  }}
}};

exports.get{resource_class}ById = async (req, res) => {{
  try {{
    const item = await {resource_class}.findById(req.params.id);
    if (!item) return res.status(404).json({{ message: '{resource_class} not found' }});
    res.json(item);
  }} catch (error) {{
    res.status(500).json({{ message: 'Error fetching {resource_class.lower()}', error }});
  }}
}};

exports.update{resource_class} = async (req, res) => {{
  try {{
    const item = await {resource_class}.findByIdAndUpdate(req.params.id, req.body, {{ new: true }});
    if (!item) return res.status(404).json({{ message: '{resource_class} not found' }});
    res.json(item);
  }} catch (error) {{
    res.status(400).json({{ message: 'Error updating {resource_class.lower()}', error }});
  }}
}};

exports.delete{resource_class} = async (req, res) => {{
  try {{
    const item = await {resource_class}.findByIdAndDelete(req.params.id);
    if (!item) return res.status(404).json({{ message: '{resource_class} not found' }});
    res.status(204).send();
  }} catch (error) {{
    res.status(500).json({{ message: 'Error deleting {resource_class.lower()}', error }});
  }}
}};
'''

    def _generate_routes(self, resource_class: str, route_name: str, is_typescript: bool) -> str:
        """Generate Express routes."""
        if is_typescript:
            return f'''import {{ Router }} from 'express';
import {{
  getAll{resource_class}s,
  create{resource_class},
  get{resource_class}ById,
  update{resource_class},
  delete{resource_class},
}} from '../controllers/{route_name}Controller';

const router = Router();

router.get('/', getAll{resource_class}s);
router.post('/', create{resource_class});
router.get('/:id', get{resource_class}ById);
router.put('/:id', update{resource_class});
router.delete('/:id', delete{resource_class});

export default router;
'''
        else:
            return f'''const express = require('express');
const router = express.Router();
const {{
  getAll{resource_class}s,
  create{resource_class},
  get{resource_class}ById,
  update{resource_class},
  delete{resource_class},
}} = require('../controllers/{route_name}Controller');

router.get('/', getAll{resource_class}s);
router.post('/', create{resource_class});
router.get('/:id', get{resource_class}ById);
router.put('/:id', update{resource_class});
router.delete('/:id', delete{resource_class});

module.exports = router;
'''

    def _ts_type(self, field_type: str) -> str:
        """Convert to TypeScript type."""
        mapping = {
            "str": "string",
            "string": "string",
            "text": "string",
            "int": "number",
            "integer": "number",
            "float": "number",
            "decimal": "number",
            "bool": "boolean",
            "boolean": "boolean",
            "date": "Date",
            "datetime": "Date",
            "timestamp": "Date",
            "uuid": "string",
            "email": "string",
            "url": "string",
            "json": "any",
        }
        return mapping.get(field_type.lower(), "any")
