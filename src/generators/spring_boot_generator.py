"""Spring Boot REST API generator."""

from __future__ import annotations

from pathlib import Path

from ..base_generator import BaseGenerator
from ..types import FieldDefinition, GeneratedFile, GenerationResult, HttpMethod, PostmanEndpoint, ProjectContext


class SpringBootGenerator(BaseGenerator):
    """Generator for Spring Boot REST APIs."""

    TYPE_MAPPING = {
        "string": "String",
        "text": "String",
        "int": "Integer",
        "integer": "Integer",
        "long": "Long",
        "decimal": "BigDecimal",
        "float": "Double",
        "double": "Double",
        "bool": "Boolean",
        "boolean": "Boolean",
        "date": "LocalDate",
        "datetime": "LocalDateTime",
        "timestamp": "LocalDateTime",
        "email": "String",
        "url": "String",
        "uuid": "UUID",
    }

    def detect_project(self, path: str) -> ProjectContext:
        """Detect Spring Boot project by looking for pom.xml or build.gradle with Spring Boot."""
        root = Path(path).resolve()
        
        # Check for Maven project
        pom_file = root / "pom.xml"
        if pom_file.exists():
            content = pom_file.read_text(encoding="utf-8")
            if "spring-boot-starter" in content:
                # Find main application class
                src_main_java = root / "src" / "main" / "java"
                if src_main_java.exists():
                    for java_file in src_main_java.rglob("*Application.java"):
                        return ProjectContext(
                            framework=self.context.framework,
                            root_path=root,
                            project_name=root.name,
                            entry_file=java_file,
                            config_file=pom_file,
                            package_manager="maven",
                        )
        
        # Check for Gradle project
        gradle_file = root / "build.gradle"
        gradle_kts_file = root / "build.gradle.kts"
        
        for build_file in [gradle_file, gradle_kts_file]:
            if build_file.exists():
                content = build_file.read_text(encoding="utf-8")
                if "spring-boot" in content or "springBoot" in content:
                    src_main_java = root / "src" / "main" / "java"
                    if src_main_java.exists():
                        for java_file in src_main_java.rglob("*Application.java"):
                            return ProjectContext(
                                framework=self.context.framework,
                                root_path=root,
                                project_name=root.name,
                                entry_file=java_file,
                                config_file=build_file,
                                package_manager="gradle",
                            )
        
        return ProjectContext(framework=self.context.framework, root_path=root, project_name=root.name)

    def generate_resource(
        self,
        resource_name: str,
        fields: list[FieldDefinition],
        app_name: str | None = None,
        route_prefix: str | None = None,
    ) -> GenerationResult:
        """Generate Spring Boot REST API resource."""
        normalized_name = self.normalize_resource_name(resource_name)
        class_name = "".join(word.capitalize() for word in normalized_name.split("_"))
        package_name = app_name or normalized_name.lower()
        route = route_prefix or f"/api/{self.kebab_case(normalized_name)}"
        
        # Determine base package
        base_package = self._get_base_package()
        full_package = f"{base_package}.{package_name}"
        
        # Create package directories
        package_path = self._get_package_path(full_package)
        
        files = []
        messages = []
        
        # 1. Generate Entity
        entity_content = self._generate_entity(class_name, fields, full_package)
        files.append(GeneratedFile(path=package_path / "entity" / f"{class_name}.java", content=entity_content))
        
        # 2. Generate DTO
        dto_content = self._generate_dto(class_name, fields, full_package)
        files.append(GeneratedFile(path=package_path / "dto" / f"{class_name}DTO.java", content=dto_content))
        
        # 3. Generate Repository
        repository_content = self._generate_repository(class_name, full_package)
        files.append(GeneratedFile(path=package_path / "repository" / f"{class_name}Repository.java", content=repository_content))
        
        # 4. Generate Service
        service_content = self._generate_service(class_name, full_package)
        files.append(GeneratedFile(path=package_path / "service" / f"{class_name}Service.java", content=service_content))
        
        # 5. Generate Controller
        controller_content = self._generate_controller(class_name, route, full_package)
        files.append(GeneratedFile(path=package_path / "controller" / f"{class_name}Controller.java", content=controller_content))
        
        messages.append(f"Generated Spring Boot REST API for {class_name}")
        messages.append(f"Package: {full_package}")
        messages.append(f"Endpoint: {route}")
        
        # Generate Postman endpoints
        postman_endpoints = self.get_postman_endpoints(normalized_name, route)
        
        return GenerationResult(files=files, postman_endpoints=postman_endpoints, messages=messages)

    def get_postman_endpoints(self, resource_name: str, route_prefix: str | None = None) -> list[PostmanEndpoint]:
        """Generate Postman endpoints for Spring Boot."""
        route = route_prefix or f"/api/{self.kebab_case(resource_name)}"
        class_name = "".join(word.capitalize() for word in resource_name.split("_"))
        
        return [
            PostmanEndpoint(name=f"List {class_name}s", method=HttpMethod.GET, url=f"{{{{base_url}}}}{route}"),
            PostmanEndpoint(
                name=f"Create {class_name}",
                method=HttpMethod.POST,
                url=f"{{{{base_url}}}}{route}",
                headers={"Content-Type": "application/json"},
                body={"name": "example"},
            ),
            PostmanEndpoint(name=f"Get {class_name}", method=HttpMethod.GET, url=f"{{{{base_url}}}}{route}/{{{{id}}}}"),
            PostmanEndpoint(
                name=f"Update {class_name}",
                method=HttpMethod.PUT,
                url=f"{{{{base_url}}}}{route}/{{{{id}}}}",
                headers={"Content-Type": "application/json"},
                body={"name": "updated"},
            ),
            PostmanEndpoint(name=f"Delete {class_name}", method=HttpMethod.DELETE, url=f"{{{{base_url}}}}{route}/{{{{id}}}}"),
        ]

    def get_type_mapping(self) -> dict[str, str]:
        """Return Java/Spring Boot type mapping."""
        return self.TYPE_MAPPING

    def _get_base_package(self) -> str:
        """Extract base package from main application file."""
        if self.context.entry_file and self.context.entry_file.exists():
            content = self.context.entry_file.read_text(encoding="utf-8")
            for line in content.split("\n"):
                if line.strip().startswith("package "):
                    return line.strip().replace("package ", "").replace(";", "").strip()
        return "com.example.api"

    def _get_package_path(self, package: str) -> Path:
        """Convert package name to file system path."""
        base = self.context.root_path / "src" / "main" / "java"
        for part in package.split("."):
            base = base / part
        return base

    def _generate_entity(self, class_name: str, fields: list[FieldDefinition], package: str) -> str:
        """Generate JPA Entity."""
        imports = {
            "import jakarta.persistence.*;",
            "import lombok.Data;",
            "import lombok.NoArgsConstructor;",
            "import lombok.AllArgsConstructor;",
        }
        
        field_lines = []
        for field in fields:
            java_type = self.TYPE_MAPPING.get(field.type, "String")
            
            # Add specific imports
            if java_type == "BigDecimal":
                imports.add("import java.math.BigDecimal;")
            elif java_type in ["LocalDate", "LocalDateTime"]:
                imports.add("import java.time.*;")
            elif java_type == "UUID":
                imports.add("import java.util.UUID;")
            
            nullable_annotation = "" if field.nullable else "@Column(nullable = false)\n    "
            field_lines.append(f"    {nullable_annotation}private {java_type} {self.camel_case(field.name)};")
        
        return f"""package {package}.entity;

{chr(10).join(sorted(imports))}

@Entity
@Table(name = "{self.snake_case(class_name)}")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class {class_name} {{
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
{chr(10).join(field_lines)}
}}
"""

    def _generate_dto(self, class_name: str, fields: list[FieldDefinition], package: str) -> str:
        """Generate DTO class."""
        imports = {"import lombok.Data;", "import lombok.NoArgsConstructor;", "import lombok.AllArgsConstructor;"}
        
        field_lines = []
        for field in fields:
            java_type = self.TYPE_MAPPING.get(field.type, "String")
            if java_type == "BigDecimal":
                imports.add("import java.math.BigDecimal;")
            elif java_type in ["LocalDate", "LocalDateTime"]:
                imports.add("import java.time.*;")
            elif java_type == "UUID":
                imports.add("import java.util.UUID;")
            field_lines.append(f"    private {java_type} {self.camel_case(field.name)};")
        
        return f"""package {package}.dto;

{chr(10).join(sorted(imports))}

@Data
@NoArgsConstructor
@AllArgsConstructor
public class {class_name}DTO {{
    
    private Long id;
{chr(10).join(field_lines)}
}}
"""

    def _generate_repository(self, class_name: str, package: str) -> str:
        """Generate Spring Data JPA Repository."""
        return f"""package {package}.repository;

import {package}.entity.{class_name};
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface {class_name}Repository extends JpaRepository<{class_name}, Long> {{
}}
"""

    def _generate_service(self, class_name: str, package: str) -> str:
        """Generate Service layer."""
        camel_name = self.camel_case(class_name)
        
        return f"""package {package}.service;

import {package}.dto.{class_name}DTO;
import {package}.entity.{class_name};
import {package}.repository.{class_name}Repository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class {class_name}Service {{
    
    private final {class_name}Repository repository;
    
    public List<{class_name}DTO> findAll() {{
        return repository.findAll().stream()
            .map(this::toDTO)
            .collect(Collectors.toList());
    }}
    
    public Optional<{class_name}DTO> findById(Long id) {{
        return repository.findById(id).map(this::toDTO);
    }}
    
    public {class_name}DTO create({class_name}DTO dto) {{
        {class_name} entity = toEntity(dto);
        entity = repository.save(entity);
        return toDTO(entity);
    }}
    
    public Optional<{class_name}DTO> update(Long id, {class_name}DTO dto) {{
        return repository.findById(id).map(entity -> {{
            updateEntityFromDTO(entity, dto);
            entity = repository.save(entity);
            return toDTO(entity);
        }});
    }}
    
    public boolean delete(Long id) {{
        if (repository.existsById(id)) {{
            repository.deleteById(id);
            return true;
        }}
        return false;
    }}
    
    private {class_name}DTO toDTO({class_name} entity) {{
        {class_name}DTO dto = new {class_name}DTO();
        dto.setId(entity.getId());
        // Map other fields here
        return dto;
    }}
    
    private {class_name} toEntity({class_name}DTO dto) {{
        {class_name} entity = new {class_name}();
        // Map fields here
        return entity;
    }}
    
    private void updateEntityFromDTO({class_name} entity, {class_name}DTO dto) {{
        // Update fields here
    }}
}}
"""

    def _generate_controller(self, class_name: str, route: str, package: str) -> str:
        """Generate REST Controller."""
        camel_name = self.camel_case(class_name)
        
        return f"""package {package}.controller;

import {package}.dto.{class_name}DTO;
import {package}.service.{class_name}Service;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("{route}")
@RequiredArgsConstructor
public class {class_name}Controller {{
    
    private final {class_name}Service service;
    
    @GetMapping
    public ResponseEntity<List<{class_name}DTO>> getAll() {{
        return ResponseEntity.ok(service.findAll());
    }}
    
    @GetMapping("/{{id}}")
    public ResponseEntity<{class_name}DTO> getById(@PathVariable Long id) {{
        return service.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }}
    
    @PostMapping
    public ResponseEntity<{class_name}DTO> create(@RequestBody {class_name}DTO dto) {{
        {class_name}DTO created = service.create(dto);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }}
    
    @PutMapping("/{{id}}")
    public ResponseEntity<{class_name}DTO> update(@PathVariable Long id, @RequestBody {class_name}DTO dto) {{
        return service.update(id, dto)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }}
    
    @DeleteMapping("/{{id}}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {{
        return service.delete(id)
            ? ResponseEntity.noContent().build()
            : ResponseEntity.notFound().build();
    }}
}}
"""
