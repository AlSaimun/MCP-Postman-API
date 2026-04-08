"""Flask API generator."""

from __future__ import annotations

from pathlib import Path

from ..base_generator import BaseGenerator
from ..types import FieldDefinition, GeneratedFile, GenerationResult, HttpMethod, PostmanEndpoint, ProjectContext, Framework


class FlaskGenerator(BaseGenerator):
    """Generator for Flask REST APIs."""

    TYPE_MAPPING = {
        "str": "db.String(255)",
        "string": "db.String(255)",
        "text": "db.Text",
        "int": "db.Integer",
        "integer": "db.Integer",
        "float": "db.Float",
        "decimal": "db.Numeric(10, 2)",
        "bool": "db.Boolean",
        "boolean": "db.Boolean",
        "date": "db.Date",
        "datetime": "db.DateTime",
        "timestamp": "db.DateTime",
        "uuid": "db.String(36)",
        "email": "db.String(255)",
        "url": "db.String(255)",
        "json": "db.JSON",
    }

    def detect_project(self, project_path: Path) -> ProjectContext | None:
        """Detect Flask project."""
        entry_candidates = ["app.py", "application.py", "run.py", "wsgi.py", "__init__.py"]
        
        for candidate in entry_candidates:
            file_path = project_path / candidate
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if "from flask import" in content or "import flask" in content:
                        return ProjectContext(
                            framework=Framework.FLASK,
                            root_path=project_path,
                            project_name=project_path.name,
                            entry_file=file_path,
                            package_manager="pip",
                        )
                except OSError:
                    continue

        return None

    def generate_resource(
        self,
        resource_name: str,
        fields: list[FieldDefinition],
        app_name: str | None = None,
        route_prefix: str | None = None,
    ) -> GenerationResult:
        """Generate Flask resource files."""
        resource_class = self.normalize_resource_name(resource_name)
        route_name = self.snake_case(resource_name)
        route_prefix = route_prefix or "api"

        files = []
        messages = []

        # Determine structure (app/ or root)
        app_dir = self.context.root_path / "app"
        if not app_dir.exists():
            app_dir = self.context.root_path

        # Models
        models_file = app_dir / "models.py"
        if models_file.exists():
            content = models_file.read_text(encoding="utf-8")
            content += "\n\n" + self._generate_model(resource_class, fields)
            files.append(GeneratedFile(models_file, content, overwrite=True))
        else:
            files.append(GeneratedFile(models_file, self._generate_models_file(resource_class, fields)))

        # Blueprints/Routes
        blueprints_dir = app_dir / "blueprints"
        if not blueprints_dir.exists():
            blueprints_dir = app_dir / "routes"
        
        blueprint_file = blueprints_dir / f"{route_name}.py"
        files.append(GeneratedFile(blueprint_file, self._generate_blueprint(resource_class, route_name)))

        # Schemas (Marshmallow)
        schemas_file = app_dir / "schemas.py"
        if schemas_file.exists():
            content = schemas_file.read_text(encoding="utf-8")
            content += "\n\n" + self._generate_schema(resource_class, fields)
            files.append(GeneratedFile(schemas_file, content, overwrite=True))
        else:
            files.append(GeneratedFile(schemas_file, self._generate_schemas_file(resource_class, fields)))

        postman_endpoints = self.get_postman_endpoints(resource_name, route_prefix)

        messages.append(f"Generated Flask resource '{resource_class}'")
        messages.append(f"Register blueprint: app.register_blueprint({route_name}_bp, url_prefix='/{route_prefix}/{route_name}')")

        return GenerationResult(
            files=files,
            postman_endpoints=postman_endpoints,
            messages=messages,
        )

    def get_postman_endpoints(self, resource_name: str, route_prefix: str) -> list[PostmanEndpoint]:
        """Generate Postman endpoints for Flask API."""
        route = self.snake_case(resource_name)
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
            PostmanEndpoint(name=f"Get {item_name}", method=HttpMethod.GET, url=f"{base_url}/<int:id>"),
            PostmanEndpoint(
                name=f"Update {item_name}",
                method=HttpMethod.PUT,
                url=f"{base_url}/<int:id>",
                headers={"Content-Type": "application/json"},
                body={},
            ),
            PostmanEndpoint(name=f"Delete {item_name}", method=HttpMethod.DELETE, url=f"{base_url}/<int:id>"),
        ]

    def get_type_mapping(self) -> dict[str, str]:
        """Get Flask/SQLAlchemy type mapping."""
        return self.TYPE_MAPPING

    def _generate_models_file(self, resource_class: str, fields: list[FieldDefinition]) -> str:
        """Generate complete models.py file."""
        return f'''from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

{self._generate_model(resource_class, fields)}
'''

    def _generate_model(self, resource_class: str, fields: list[FieldDefinition]) -> str:
        """Generate SQLAlchemy model."""
        field_lines = []
        for field in fields:
            field_type = self.TYPE_MAPPING.get(field.type.lower(), "db.String(255)")
            nullable = str(field.nullable)
            field_lines.append(f"    {field.name} = db.Column({field_type}, nullable={nullable})")

        field_str = "\n".join(field_lines)

        return f'''class {resource_class}(db.Model):
    __tablename__ = '{self.snake_case(resource_class)}s'

    id = db.Column(db.Integer, primary_key=True)
{field_str}
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {{
            'id': self.id,
{chr(10).join(f"            '{f.name}': self.{f.name}," for f in fields)}
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }}
'''

    def _generate_schemas_file(self, resource_class: str, fields: list[FieldDefinition]) -> str:
        """Generate complete schemas.py file."""
        return f'''from marshmallow import Schema, fields

{self._generate_schema(resource_class, fields)}
'''

    def _generate_schema(self, resource_class: str, fields: list[FieldDefinition]) -> str:
        """Generate Marshmallow schema."""
        schema_field_mapping = {
            "str": "fields.Str()",
            "string": "fields.Str()",
            "text": "fields.Str()",
            "int": "fields.Int()",
            "integer": "fields.Int()",
            "float": "fields.Float()",
            "decimal": "fields.Decimal()",
            "bool": "fields.Bool()",
            "boolean": "fields.Bool()",
            "date": "fields.Date()",
            "datetime": "fields.DateTime()",
            "timestamp": "fields.DateTime()",
            "uuid": "fields.Str()",
            "email": "fields.Email()",
            "url": "fields.Url()",
            "json": "fields.Dict()",
        }

        field_lines = []
        for field in fields:
            schema_type = schema_field_mapping.get(field.type.lower(), "fields.Str()")
            if not field.nullable:
                schema_type = schema_type.replace("()", "(required=True)")
            field_lines.append(f"    {field.name} = {schema_type}")

        field_str = "\n".join(field_lines)

        return f'''class {resource_class}Schema(Schema):
    id = fields.Int(dump_only=True)
{field_str}
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


{self.snake_case(resource_class)}_schema = {resource_class}Schema()
{self.snake_case(resource_class)}s_schema = {resource_class}Schema(many=True)
'''

    def _generate_blueprint(self, resource_class: str, route_name: str) -> str:
        """Generate Flask blueprint."""
        return f'''from flask import Blueprint, request, jsonify
from ..models import db, {resource_class}
from ..schemas import {self.snake_case(resource_class)}_schema, {self.snake_case(resource_class)}s_schema

{route_name}_bp = Blueprint('{route_name}', __name__)


@{route_name}_bp.route('/', methods=['GET'])
def get_{route_name}s():
    items = {resource_class}.query.all()
    return jsonify({self.snake_case(resource_class)}s_schema.dump(items)), 200


@{route_name}_bp.route('/', methods=['POST'])
def create_{route_name}():
    data = request.get_json()
    errors = {self.snake_case(resource_class)}_schema.validate(data)
    if errors:
        return jsonify(errors), 400
    
    item = {resource_class}(**data)
    db.session.add(item)
    db.session.commit()
    return jsonify({self.snake_case(resource_class)}_schema.dump(item)), 201


@{route_name}_bp.route('/<int:id>', methods=['GET'])
def get_{route_name}(id):
    item = {resource_class}.query.get_or_404(id)
    return jsonify({self.snake_case(resource_class)}_schema.dump(item)), 200


@{route_name}_bp.route('/<int:id>', methods=['PUT'])
def update_{route_name}(id):
    item = {resource_class}.query.get_or_404(id)
    data = request.get_json()
    
    errors = {self.snake_case(resource_class)}_schema.validate(data, partial=True)
    if errors:
        return jsonify(errors), 400
    
    for key, value in data.items():
        setattr(item, key, value)
    
    db.session.commit()
    return jsonify({self.snake_case(resource_class)}_schema.dump(item)), 200


@{route_name}_bp.route('/<int:id>', methods=['DELETE'])
def delete_{route_name}(id):
    item = {resource_class}.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return '', 204
'''
