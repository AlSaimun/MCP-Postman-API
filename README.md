# Multi-Framework API + Postman MCP Server

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-1.27.0-green.svg)](https://modelcontextprotocol.io/)

A powerful **Model Context Protocol (MCP) server** that generates REST API boilerplate code for 6 major frameworks and automatically syncs with Postman Collections. Built with **SOLID principles**, **design patterns**, and **enterprise-grade architecture**.

## 🚀 Supported Frameworks

- **Django** (Python + Django REST Framework)
- **Laravel** (PHP)
- **Express.js** (Node.js/TypeScript)
- **FastAPI** (Python)
- **Flask** (Python)
- **Spring Boot** (Java)

## ✨ Features

- 🎯 **Auto-detects** your project's framework
- 📝 Generates **models, controllers, routes, and tests**
- 🔄 Creates and **syncs Postman collections** automatically
- 🏗️ Follows **framework-specific best practices**
- 🔌 Works seamlessly with **GitHub Copilot Chat**
- 🎨 **Production-ready** code with proper error handling
- 📦 **Type-safe** code generation with full type hints

## 🛠️ Installation

### 1. Clone & Setup

```bash
git clone <your-repo-url>
cd mcp-api-postman
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure for GitHub Copilot

**macOS/Linux:**
Edit `~/.config/Code/User/settings.json`:

```json
{
  "mcp.servers": {
    "api-generator": {
      "type": "stdio",
      "command": "/full/path/to/mcp-api-postman/venv/bin/python",
      "args": ["-m", "server"],
      "cwd": "/full/path/to/mcp-api-postman"
    }
  }
}
```

**Windows:**
Edit `%APPDATA%\Code\User\settings.json`:

```json
{
  "mcp.servers": {
    "api-generator": {
      "type": "stdio",
      "command": "C:\\full\\path\\to\\mcp-api-postman\\venv\\Scripts\\python.exe",
      "args": ["-m", "server"],
      "cwd": "C:\\full\\path\\to\\mcp-api-postman"
    }
  }
}
```

### 3. Restart VS Code

Fully quit and restart VS Code for the MCP server to load.

## 💬 Usage with GitHub Copilot Chat

### Detect Framework

```
@workspace what framework is this project?
@workspace detect the framework type
```

### Generate APIs

```bash
# Auto-detect framework and generate
@workspace create API for "Product" with name:string, price:decimal, stock:int

# Specify framework explicitly
@workspace create Django API for "User" with email:email, name:string, is_active:bool
@workspace create Laravel API for "Order" with order_number:string, total:decimal, status:string
@workspace create Express API for "Task" with title:string, description:text, completed:boolean
@workspace create FastAPI for "Article" with title:string, content:text, author:string
@workspace create Flask API for "Note" with title:string, body:text, author:string
@workspace create Spring Boot API for "Product" with name:string, price:decimal, quantity:int
```

### Nullable Fields

Add `?` suffix to make fields optional:

```
@workspace create Django API for "Profile" with bio:text?, website:url?, age:int?
```

### Sync to Postman

```
@workspace sync the Postman collection
```

## 🎯 Field Types

| Type | Description | Django | Laravel | Express | FastAPI | Flask | Spring Boot |
|------|-------------|--------|---------|---------|---------|-------|-------------|
| `string` | Short text | CharField | string | String | str | String | String |
| `text` | Long text | TextField | text | String | str | Text | String |
| `int` | Integer | IntegerField | integer | Number | int | Integer | Integer |
| `decimal` | Precise decimal | DecimalField | decimal | Number | Decimal | Numeric | BigDecimal |
| `bool` | Boolean | BooleanField | boolean | Boolean | bool | Boolean | Boolean |
| `date` | Date | DateField | date | Date | date | Date | LocalDate |
| `datetime` | Date & time | DateTimeField | timestamp | Date | datetime | DateTime | LocalDateTime |
| `email` | Email address | EmailField | string | String | EmailStr | String | String |
| `url` | Web URL | URLField | string | String | HttpUrl | String | String |

## 📦 What Gets Generated

### Django
✅ `models.py` - Django ORM models  
✅ `serializers.py` - DRF serializers  
✅ `views.py` - ViewSets with CRUD operations  
✅ `urls.py` - Router configuration  
✅ `admin.py` - Admin registration  
✅ `tests.py` - Unit tests  
✅ Auto-updates `settings.py` and project `urls.py`

**URL Pattern:** `/api/products/` (trailing slash)

### Laravel
✅ `app/Models/Product.php` - Eloquent model  
✅ `app/Http/Controllers/ProductController.php` - Resource controller  
✅ `database/migrations/YYYY_MM_DD_HHMMSS_create_products_table.php` - Migration  
✅ `app/Http/Resources/ProductResource.php` - API resource  
✅ Auto-updates `routes/api.php`

**URL Pattern:** `/api/products` (no trailing slash)

### Express.js
✅ `src/models/Product.js` - Mongoose schema  
✅ `src/controllers/ProductController.js` - Controller with CRUD  
✅ `src/routes/product.js` - Express routes  
✅ Auto-updates `src/app.js` or `src/index.js`  
✅ TypeScript support (auto-detected via `tsconfig.json`)

**URL Pattern:** `/api/products/:id` (param style)

### FastAPI
✅ `app/models.py` - Pydantic models (Base, Create, Update, Response)  
✅ `app/db_models.py` - SQLAlchemy models  
✅ `app/routers/product.py` - FastAPI router with full CRUD  
✅ Auto-updates `app/main.py`  
✅ Full type hints and validation

**URL Pattern:** `/api/products/{id}` (path param)

### Flask
✅ `app/models.py` - SQLAlchemy models  
✅ `app/schemas.py` - Marshmallow schemas  
✅ `app/blueprints/product.py` - Flask blueprint with RESTful routes  
✅ Auto-updates `app/__init__.py` or `app/app.py`

**URL Pattern:** `/api/products/<id>` (angle brackets)

### Spring Boot (NEW!)
✅ `entity/Product.java` - JPA Entity with Lombok  
✅ `dto/ProductDTO.java` - Data Transfer Object  
✅ `repository/ProductRepository.java` - Spring Data JPA Repository  
✅ `service/ProductService.java` - Service layer with business logic  
✅ `controller/ProductController.java` - REST Controller with CRUD endpoints  
✅ Proper package structure following Java conventions

**URL Pattern:** `/api/products/{id}` (path param)  
**Build Tools:** Maven or Gradle (auto-detected)

## 🏗️ Architecture

### Design Patterns Used

- **Factory Pattern** - Generator creation (`GeneratorFactory`)
- **Strategy Pattern** - Framework-specific implementations
- **Template Method** - Shared utilities in base class
- **Chain of Responsibility** - Framework detection

### SOLID Principles

✅ **Single Responsibility** - Each generator handles one framework  
✅ **Open/Closed** - Add frameworks without modifying existing code  
✅ **Liskov Substitution** - All generators interchangeable via base interface  
✅ **Interface Segregation** - Lean interfaces, no fat abstractions  
✅ **Dependency Inversion** - Depend on abstractions, not concretions

### Project Structure

```
mcp-api-postman/
├── server.py                    # MCP server entry point
├── requirements.txt             # Python dependencies (MCP 1.27.0)
├── mcp.json                     # MCP configuration
├── README.md                    # This file
│
└── src/                         # Source code
    ├── types.py                 # Type definitions (Framework, FieldDefinition)
    ├── base_generator.py        # Abstract base class
    ├── framework_detector.py    # Auto-detection logic
    ├── factory.py               # Generator factory
    │
    └── generators/              # Framework implementations
        ├── django_generator.py
        ├── laravel_generator.py
        ├── express_generator.py
        ├── fastapi_generator.py
        ├── flask_generator.py
        └── spring_boot_generator.py
```

## 🔄 Postman Integration

### Automatic Collection Generation

Every API generation creates `postman_collection.json` with CRUD endpoints:

- **GET** `/api/products` - List all
- **POST** `/api/products` - Create
- **GET** `/api/products/{id}` - Get one
- **PUT** `/api/products/{id}` - Update
- **DELETE** `/api/products/{id}` - Delete

### Sync to Postman Cloud

1. Get API key from Postman: Settings → API Keys → Create New
2. Create `.env` file:

```env
POSTMAN_API_KEY=pmat_your_key_here
POSTMAN_WORKSPACE_ID=your_workspace_id_optional
```

3. Generate API and sync:

```
@workspace create Django API for "Product" with name:string, price:decimal
@workspace sync the Postman collection
```

## �� Testing Your Setup

```bash
# Activate virtual environment
source venv/bin/activate  # Windows: venv\Scripts\activate

# Test imports
python -c "from src.factory import GeneratorFactory; print(GeneratorFactory.supported_frameworks())"

# Expected output:
# ['django', 'laravel', 'express', 'fastapi', 'flask', 'spring_boot']
```

## 🎓 How It Works

### 1. Framework Detection

The server automatically detects your framework by looking for marker files:

- **Django:** `manage.py` + `settings.py`
- **Laravel:** `artisan` + `composer.json` with "laravel/framework"
- **Express:** `package.json` with "express" dependency
- **FastAPI:** Python files with `from fastapi import` or `import fastapi`
- **Flask:** Python files with `from flask import` or `import flask`
- **Spring Boot:** `pom.xml` or `build.gradle` with Spring Boot dependencies

### 2. Code Generation

Each generator follows framework conventions:

```python
# Example: Generate Django API
generator = GeneratorFactory.create("/path/to/project")
result = generator.generate_resource(
    resource_name="Product",
    fields=[
        FieldDefinition("name", "string"),
        FieldDefinition("price", "decimal"),
        FieldDefinition("stock", "int", nullable=True)
    ]
)
# Generates 7 files + updates config files
```

### 3. Postman Export

Each generator provides framework-specific endpoints:

- Django: `/api/products/` (trailing slash)
- Laravel/FastAPI/Flask: `/api/products`
- Express: `/api/products/:id`
- Spring Boot: `/api/products/{id}`

## 🐛 Troubleshooting

### MCP Server Not Loading

1. Verify absolute paths in `settings.json`
2. Check `venv/bin/python` exists (or `venv\Scripts\python.exe` on Windows)
3. Restart VS Code completely (File → Quit)

### Framework Not Detected

```
# Manual override:
@workspace create Django API for "Product" with name:string --framework django
```

### Import Errors

```bash
cd /path/to/mcp-api-postman
source venv/bin/activate
python -c "from src.factory import GeneratorFactory"
```

## 🚀 Example Workflow

**Scenario:** Build a blog API with Django

```
# Step 1: Detect framework
@workspace what framework is this?
# Output: Django detected

# Step 2: Generate Post model
@workspace create Django API for "Post" with title:string, content:text, author:string, published_at:datetime

# Step 3: Generate Comment model
@workspace create Django API for "Comment" with post_id:int, author:string, body:text

# Step 4: Sync to Postman
@workspace sync the Postman collection

# Step 5: Test
python manage.py migrate
python manage.py runserver
# Open Postman and test!
```

## 📋 Quick Reference

| Command | Purpose |
|---------|---------|
| `@workspace what framework is this?` | Detect framework |
| `@workspace create API for "Resource" with field:type` | Generate API (auto-detect) |
| `@workspace create Django API for "User" with email:email` | Generate with specific framework |
| `@workspace sync the Postman collection` | Sync to Postman Cloud |
| `field:type?` | Make field nullable |

## 🎯 Advanced Features

### Type Safety

All generators use full type hints for IDE support:

```python
def generate_resource(
    self,
    resource_name: str,
    fields: list[FieldDefinition],
    app_name: str | None = None,
    route_prefix: str | None = None,
) -> GenerationResult:
    ...
```

### Error Handling

Production-ready error handling at MCP tool level:

```python
try:
    generator = GeneratorFactory.create(project_path, framework)
    result = generator.generate_resource(...)
    return {"success": True, "files_written": [...]}
except Exception as e:
    return {"success": False, "error": str(e)}
```

### Extensibility

Add new frameworks easily:

1. Create `src/generators/myframework_generator.py`
2. Extend `BaseGenerator`
3. Implement abstract methods
4. Add to `Framework` enum
5. Register in `GeneratorFactory._GENERATORS`
6. Add detector in `FrameworkDetector`

## 📊 Code Quality

- ✅ **Type hints:** 100% coverage
- ✅ **Docstrings:** All public APIs documented
- ✅ **SOLID principles:** Throughout codebase
- ✅ **Design patterns:** Factory, Strategy, Template Method, Chain of Responsibility
- ✅ **Error handling:** Comprehensive try/except blocks
- ✅ **Clean code:** Self-documenting, minimal comments
- ✅ **Production-ready:** Defensive programming, validation

## 📝 License

MIT License - see LICENSE file

---

**Built with ❤️ using senior software engineering principles**

For questions, issues, or contributions, please open an issue on GitHub.
