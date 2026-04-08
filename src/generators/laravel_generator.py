"""Laravel API generator."""

from __future__ import annotations

from pathlib import Path

from ..base_generator import BaseGenerator
from ..types import FieldDefinition, GeneratedFile, GenerationResult, HttpMethod, PostmanEndpoint, ProjectContext, Framework


class LaravelGenerator(BaseGenerator):
    """Generator for Laravel REST APIs."""

    TYPE_MAPPING = {
        "str": "string",
        "string": "string",
        "text": "text",
        "int": "integer",
        "integer": "integer",
        "float": "float",
        "decimal": "decimal:10,2",
        "bool": "boolean",
        "boolean": "boolean",
        "date": "date",
        "datetime": "datetime",
        "timestamp": "timestamp",
        "uuid": "uuid",
        "email": "string",  # Laravel uses string with validation
        "url": "string",
        "json": "json",
    }

    def detect_project(self, project_path: Path) -> ProjectContext | None:
        """Detect Laravel project."""
        import json

        artisan = project_path / "artisan"
        composer_json = project_path / "composer.json"

        if not (artisan.exists() and composer_json.exists()):
            return None

        try:
            with open(composer_json, encoding="utf-8") as f:
                data = json.load(f)
                if "laravel/framework" not in data.get("require", {}):
                    return None
        except Exception:  # noqa: BLE001
            return None

        return ProjectContext(
            framework=Framework.LARAVEL,
            root_path=project_path,
            project_name=project_path.name,
            entry_file=artisan,
            config_file=composer_json,
            package_manager="composer",
        )

    def generate_resource(
        self,
        resource_name: str,
        fields: list[FieldDefinition],
        app_name: str | None = None,
        route_prefix: str | None = None,
    ) -> GenerationResult:
        """Generate Laravel resource files."""
        resource_class = self.normalize_resource_name(resource_name)
        route_name = self.kebab_case(resource_name)
        route_prefix = route_prefix or "api"

        files = []
        messages = []

        # Model
        model_path = self.context.root_path / "app" / "Models" / f"{resource_class}.php"
        files.append(GeneratedFile(model_path, self._generate_model(resource_class, fields)))

        # Controller
        controller_path = self.context.root_path / "app" / "Http" / "Controllers" / f"{resource_class}Controller.php"
        files.append(GeneratedFile(controller_path, self._generate_controller(resource_class)))

        # Migration
        migration_name = f"create_{self.snake_case(resource_name)}_table"
        migration_path = self.context.root_path / "database" / "migrations" / f"{self._timestamp()}_{migration_name}.php"
        files.append(GeneratedFile(migration_path, self._generate_migration(resource_class, fields)))

        # Resource (API Resource)
        resource_path = self.context.root_path / "app" / "Http" / "Resources" / f"{resource_class}Resource.php"
        files.append(GeneratedFile(resource_path, self._generate_resource_class(resource_class)))

        # Routes
        api_routes = self.context.root_path / "routes" / "api.php"
        if api_routes.exists():
            routes_content = api_routes.read_text(encoding="utf-8")
            updated_routes = self._add_route(routes_content, resource_class, route_name)
            files.append(GeneratedFile(api_routes, updated_routes, overwrite=True))
            messages.append(f"Updated {api_routes.relative_to(self.context.root_path)}")

        postman_endpoints = self.get_postman_endpoints(resource_name, route_prefix)

        messages.append(f"Generated Laravel resource '{resource_class}'")
        messages.append("Run: php artisan migrate")

        return GenerationResult(
            files=files,
            postman_endpoints=postman_endpoints,
            messages=messages,
        )

    def get_postman_endpoints(self, resource_name: str, route_prefix: str) -> list[PostmanEndpoint]:
        """Generate Postman endpoints for Laravel API."""
        route = self.kebab_case(resource_name)
        base_url = f"{{{{base_url}}}}/{route_prefix}/{route}"
        item_name = self.normalize_resource_name(resource_name)

        return [
            PostmanEndpoint(name=f"List {item_name}", method=HttpMethod.GET, url=base_url),
            PostmanEndpoint(
                name=f"Create {item_name}",
                method=HttpMethod.POST,
                url=base_url,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                body={},
            ),
            PostmanEndpoint(name=f"Show {item_name}", method=HttpMethod.GET, url=f"{base_url}/1"),
            PostmanEndpoint(
                name=f"Update {item_name}",
                method=HttpMethod.PUT,
                url=f"{base_url}/1",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                body={},
            ),
            PostmanEndpoint(name=f"Delete {item_name}", method=HttpMethod.DELETE, url=f"{base_url}/1"),
        ]

    def get_type_mapping(self) -> dict[str, str]:
        """Get Laravel type mapping."""
        return self.TYPE_MAPPING

    def _timestamp(self) -> str:
        """Generate Laravel migration timestamp."""
        from datetime import datetime
        return datetime.now().strftime("%Y_%m_%d_%H%M%S")

    def _generate_model(self, resource_class: str, fields: list[FieldDefinition]) -> str:
        """Generate Laravel model."""
        fillable_fields = ", ".join(f"'{field.name}'" for field in fields)
        
        return f'''<?php

namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;

class {resource_class} extends Model
{{
    use HasFactory;

    protected $fillable = [{fillable_fields}];

    protected $casts = [
        'created_at' => 'datetime',
        'updated_at' => 'datetime',
    ];
}}
'''

    def _generate_controller(self, resource_class: str) -> str:
        """Generate Laravel controller."""
        variable = self.camel_case(resource_class)
        
        return f'''<?php

namespace App\\Http\\Controllers;

use App\\Models\\{resource_class};
use App\\Http\\Resources\\{resource_class}Resource;
use Illuminate\\Http\\Request;

class {resource_class}Controller extends Controller
{{
    public function index()
    {{
        ${resource_class.lower()}s = {resource_class}::latest()->paginate(15);
        return {resource_class}Resource::collection(${resource_class.lower()}s);
    }}

    public function store(Request $request)
    {{
        $validated = $request->validate([
            // Add validation rules here
        ]);

        ${variable} = {resource_class}::create($validated);
        return new {resource_class}Resource(${variable});
    }}

    public function show({resource_class} ${variable})
    {{
        return new {resource_class}Resource(${variable});
    }}

    public function update(Request $request, {resource_class} ${variable})
    {{
        $validated = $request->validate([
            // Add validation rules here
        ]);

        ${variable}->update($validated);
        return new {resource_class}Resource(${variable});
    }}

    public function destroy({resource_class} ${variable})
    {{
        ${variable}->delete();
        return response()->json(null, 204);
    }}
}}
'''

    def _generate_migration(self, resource_class: str, fields: list[FieldDefinition]) -> str:
        """Generate Laravel migration."""
        table_name = self.snake_case(resource_class) + "s"
        
        field_lines = []
        for field in fields:
            field_type = self.TYPE_MAPPING.get(field.type.lower(), "string")
            line = f"$table->{field_type}('{field.name}')"
            if field.nullable:
                line += "->nullable()"
            field_lines.append(f"            {line};")
        
        field_str = "\n".join(field_lines)
        
        return f'''<?php

use Illuminate\\Database\\Migrations\\Migration;
use Illuminate\\Database\\Schema\\Blueprint;
use Illuminate\\Support\\Facades\\Schema;

return new class extends Migration
{{
    public function up(): void
    {{
        Schema::create('{table_name}', function (Blueprint $table) {{
            $table->id();
{field_str}
            $table->timestamps();
        }});
    }}

    public function down(): void
    {{
        Schema::dropIfExists('{table_name}');
    }}
}};
'''

    def _generate_resource_class(self, resource_class: str) -> str:
        """Generate Laravel API Resource."""
        return f'''<?php

namespace App\\Http\\Resources;

use Illuminate\\Http\\Request;
use Illuminate\\Http\\Resources\\Json\\JsonResource;

class {resource_class}Resource extends JsonResource
{{
    public function toArray(Request $request): array
    {{
        return [
            'id' => $this->id,
            'created_at' => $this->created_at,
            'updated_at' => $this->updated_at,
        ];
    }}
}}
'''

    def _add_route(self, routes_content: str, resource_class: str, route_name: str) -> str:
        """Add route to api.php."""
        route_line = f"Route::apiResource('{route_name}', App\\Http\\Controllers\\{resource_class}Controller::class);"
        
        if route_line in routes_content:
            return routes_content
        
        # Add at the end
        return routes_content.rstrip() + f"\n\n{route_line}\n"
