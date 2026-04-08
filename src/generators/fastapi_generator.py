"""FastAPI generator."""

from __future__ import annotations

from pathlib import Path

from ..base_generator import BaseGenerator
from ..types import FieldDefinition, GeneratedFile, GenerationResult, HttpMethod, PostmanEndpoint, ProjectContext, Framework


class FastAPIGenerator(BaseGenerator):
    """Generator for FastAPI REST APIs."""

    TYPE_MAPPING = {
        "str": "str",
        "string": "str",
        "text": "str",
        "int": "int",
        "integer": "int",
        "float": "float",
        "decimal": "Decimal",
        "bool": "bool",
        "boolean": "bool",
        "date": "date",
        "datetime": "datetime",
        "timestamp": "datetime",
        "uuid": "UUID",
        "email": "EmailStr",
        "url": "AnyUrl",
        "json": "dict",
    }

    def detect_project(self, project_path: Path) -> ProjectContext | None:
        """Detect FastAPI project."""
        entry_candidates = ["main.py", "app.py", "api.py"]
        
        for candidate in entry_candidates:
            file_path = project_path / candidate
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if "from fastapi import" in content or "import fastapi" in content:
                        return ProjectContext(
                            framework=Framework.FASTAPI,
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
        """Generate FastAPI resource files."""
        resource_class = self.normalize_resource_name(resource_name)
        route_name = self.snake_case(resource_name)
        route_prefix = route_prefix or "api"

        files = []
        messages = []

        # Determine structure
        app_dir = self.context.root_path / "app"
        if not app_dir.exists():
            app_dir = self.context.root_path

        # Models (Pydantic)
        models_file = app_dir / "models.py"
        if models_file.exists():
            content = models_file.read_text(encoding="utf-8")
            content += "\n\n" + self._generate_model(resource_class, fields)
            files.append(GeneratedFile(models_file, content, overwrite=True))
        else:
            files.append(GeneratedFile(models_file, self._generate_model_file(resource_class, fields)))

        # Routes
        routers_dir = app_dir / "routers"
        router_file = routers_dir / f"{route_name}.py"
        files.append(GeneratedFile(router_file, self._generate_router(resource_class, route_name, fields)))

        # Database models (SQLAlchemy - optional)
        db_models_file = app_dir / "db_models.py"
        files.append(GeneratedFile(db_models_file, self._generate_db_model(resource_class, fields)))

        postman_endpoints = self.get_postman_endpoints(resource_name, route_prefix)

        messages.append(f"Generated FastAPI resource '{resource_class}'")
        messages.append(f"Add to main: app.include_router({route_name}_router, prefix='/{route_prefix}/{route_name}', tags=['{resource_class}'])")

        return GenerationResult(
            files=files,
            postman_endpoints=postman_endpoints,
            messages=messages,
        )

    def get_postman_endpoints(self, resource_name: str, route_prefix: str) -> list[PostmanEndpoint]:
        """Generate Postman endpoints for FastAPI."""
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
            PostmanEndpoint(name=f"Get {item_name}", method=HttpMethod.GET, url=f"{base_url}/{{item_id}}"),
            PostmanEndpoint(
                name=f"Update {item_name}",
                method=HttpMethod.PUT,
                url=f"{base_url}/{{item_id}}",
                headers={"Content-Type": "application/json"},
                body={},
            ),
            PostmanEndpoint(name=f"Delete {item_name}", method=HttpMethod.DELETE, url=f"{base_url}/{{item_id}}"),
        ]

    def get_type_mapping(self) -> dict[str, str]:
        """Get FastAPI/Pydantic type mapping."""
        return self.TYPE_MAPPING

    def _generate_model_file(self, resource_class: str, fields: list[FieldDefinition]) -> str:
        """Generate complete models.py file."""
        return f'''from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, UUID4
from decimal import Decimal

{self._generate_model(resource_class, fields)}
'''

    def _generate_model(self, resource_class: str, fields: list[FieldDefinition]) -> str:
        """Generate Pydantic model."""
        field_lines = []
        for field in fields:
            field_type = self.TYPE_MAPPING.get(field.type.lower(), "str")
            if field.nullable:
                field_type = f"Optional[{field_type}] = None"
            field_lines.append(f"    {field.name}: {field_type}")

        field_str = "\n".join(field_lines)

        return f'''class {resource_class}Base(BaseModel):
{field_str if field_str else "    pass"}


class {resource_class}Create({resource_class}Base):
    pass


class {resource_class}Update(BaseModel):
{field_str.replace(": ", ": Optional[").replace("str", "str] = None").replace("int", "int] = None") if field_str else "    pass"}


class {resource_class}Response({resource_class}Base):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
'''

    def _generate_router(self, resource_class: str, route_name: str, fields: list[FieldDefinition]) -> str:
        """Generate FastAPI router."""
        return f'''from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from ..models import {resource_class}Create, {resource_class}Update, {resource_class}Response
from ..db_models import {resource_class} as DB{resource_class}
from ..database import get_db

router = APIRouter()


@router.get("/", response_model=List[{resource_class}Response])
def get_{route_name}s(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = db.query(DB{resource_class}).offset(skip).limit(limit).all()
    return items


@router.post("/", response_model={resource_class}Response, status_code=201)
def create_{route_name}(item: {resource_class}Create, db: Session = Depends(get_db)):
    db_item = DB{resource_class}(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/{{item_id}}", response_model={resource_class}Response)
def get_{route_name}(item_id: int, db: Session = Depends(get_db)):
    item = db.query(DB{resource_class}).filter(DB{resource_class}.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="{resource_class} not found")
    return item


@router.put("/{{item_id}}", response_model={resource_class}Response)
def update_{route_name}(item_id: int, item_update: {resource_class}Update, db: Session = Depends(get_db)):
    db_item = db.query(DB{resource_class}).filter(DB{resource_class}.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="{resource_class} not found")
    
    for key, value in item_update.model_dump(exclude_unset=True).items():
        setattr(db_item, key, value)
    
    db.commit()
    db.refresh(db_item)
    return db_item


@router.delete("/{{item_id}}", status_code=204)
def delete_{route_name}(item_id: int, db: Session = Depends(get_db)):
    db_item = db.query(DB{resource_class}).filter(DB{resource_class}.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="{resource_class} not found")
    
    db.delete(db_item)
    db.commit()
    return None
'''

    def _generate_db_model(self, resource_class: str, fields: list[FieldDefinition]) -> str:
        """Generate SQLAlchemy model."""
        db_field_mapping = {
            "str": "String(255)",
            "string": "String(255)",
            "text": "Text",
            "int": "Integer",
            "integer": "Integer",
            "float": "Float",
            "decimal": "Numeric(10, 2)",
            "bool": "Boolean",
            "boolean": "Boolean",
            "date": "Date",
            "datetime": "DateTime",
            "timestamp": "DateTime",
            "uuid": "String(36)",
            "email": "String(255)",
            "url": "String(255)",
            "json": "JSON",
        }

        field_lines = []
        for field in fields:
            db_type = db_field_mapping.get(field.type.lower(), "String(255)")
            nullable = str(field.nullable)
            field_lines.append(f"    {field.name} = Column({db_type}, nullable={nullable})")

        field_str = "\n".join(field_lines)

        return f'''from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, JSON, Date, Numeric
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class {resource_class}(Base):
    __tablename__ = "{self.snake_case(resource_class)}s"

    id = Column(Integer, primary_key=True, index=True)
{field_str}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
'''
