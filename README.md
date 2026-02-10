# Backend Template

A production-ready FastAPI backend with JWT authentication, async SQLAlchemy, and Docker.

## Architecture

```
Request → Route (HTTP layer) → Service (Business Logic) → Repository (Data Access) → Model (Database)
```

Each layer only knows about the layer below it. Services raise domain exceptions — routes never touch the database, repositories never know about HTTP.

### Folder Structure

```
Backend/
├── app/
│   ├── main.py                  # FastAPI app, middleware, lifespan, exception handlers
│   ├── api/
│   │   ├── api_v1.py            # Router aggregation
│   │   ├── deps.py              # Dependency injection (DB, repos, services, auth)
│   │   └── v1/
│   │       ├── auth.py          # Login, refresh, logout routes
│   │       └── users.py         # User CRUD + pagination routes
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (env-based config)
│   │   ├── database.py          # Async engine, session factory, get_db dependency
│   │   ├── exceptions.py        # Domain exceptions (AppException, Unauthorized, Conflict, NotFound)
│   │   └── security.py          # JWT creation/verification, password hashing
│   ├── models/
│   │   ├── user.py              # SQLAlchemy User model
│   │   └── token.py             # SQLAlchemy RefreshToken model
│   ├── repositories/
│   │   ├── user_repo.py         # User data access (CRUD + queries)
│   │   └── token_repo.py        # Token data access (CRUD + revocation)
│   ├── schemas/
│   │   ├── user.py              # Pydantic schemas (UserCreate, UserUpdate, UserResponse)
│   │   ├── token.py             # Pydantic schemas (TokenResponse, TokenPayload, etc.)
│   │   └── pagination.py        # Generic PaginatedResponse + PaginationParams
│   ├── services/
│   │   ├── auth_service.py      # Login, refresh, logout business logic
│   │   └── user_service.py      # User CRUD business logic
│   └── tasks/
│       └── cleanup_tokens.py    # Periodic cleanup of expired/revoked tokens
├── alembic/                     # Database migrations
├── tests/
│   ├── conftest.py              # Test fixtures (in-memory SQLite, async client)
│   └── test_auth.py             # Auth + user test suite
├── .env                         # Environment variables (gitignored)
├── .env.example                 # Documented env template
├── .dockerignore
├── alembic.ini
├── Dockerfile
├── pytest.ini
└── requirements.txt
```

## Key Design Decisions

### Transaction Management

Repositories call `flush()` (sends SQL to DB within the transaction). The `get_db` dependency calls `commit()` once at the end of the request. If anything fails, everything rolls back atomically. No split-transaction data corruption.

### Domain Exceptions

Services never import FastAPI. They raise `UnauthorizedException`, `ConflictException`, etc. A global exception handler in `main.py` maps these to HTTP responses. This keeps services reusable in non-HTTP contexts (CLI, background tasks, WebSockets).

### Token Security

Access and refresh tokens have a `type` claim (`"access"` / `"refresh"`). Both `decode_access_token` and `refresh_access_token` validate the type, preventing token type confusion attacks.

### Lazy Database Initialization

The database engine and session factory are created on first use, not at import time. This prevents crashes during module import if the `.env` is missing, and makes testing with dependency overrides clean.

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- Python 3.12+ (for local development)

### 1. Clone and configure

```bash
cp Backend/.env.example Backend/.env
# Edit Backend/.env with your values (SECRET_KEY, DATABASE_URL, etc.)

# Create root .env for Docker Compose
cp .env.example .env
# Edit .env with your Postgres credentials
```

### 2. Run with Docker

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8080`. Swagger docs at `http://localhost:8080/docs`.

### 3. Run migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 4. Run tests

```bash
cd Backend
pip install -r requirements.txt
pytest -v
```

---

## API Endpoints

### Authentication

| Method | Endpoint               | Description               | Rate Limit |
| ------ | ---------------------- | ------------------------- | ---------- |
| POST   | `/api/v1/auth/login`   | Login (email or username) | 5/min      |
| POST   | `/api/v1/auth/refresh` | Refresh access token      | 10/min     |
| POST   | `/api/v1/auth/logout`  | Revoke refresh token      | 10/min     |

### Users

| Method | Endpoint           | Description            | Auth |
| ------ | ------------------ | ---------------------- | ---- |
| POST   | `/api/v1/users/`   | Register new user      | No   |
| GET    | `/api/v1/users/`   | List users (paginated) | No   |
| GET    | `/api/v1/users/me` | Get current user       | Yes  |
| PATCH  | `/api/v1/users/me` | Update current user    | Yes  |
| DELETE | `/api/v1/users/me` | Delete current user    | Yes  |

---

## How to Add a New Resource

Follow this pattern to add any new entity (e.g., `Project`, `Document`, `Post`):

### 1. Model — `app/models/your_model.py`

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey
from app.core.database import Base

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
```

### 2. Migration

```bash
alembic revision --autogenerate -m "add projects table"
alembic upgrade head
```

### 3. Schema — `app/schemas/your_schema.py`

```python
from pydantic import BaseModel, ConfigDict

class ProjectCreate(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: int
    name: str
    user_id: int
    model_config = ConfigDict(from_attributes=True)
```

### 4. Repository — `app/repositories/your_repo.py`

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project

class ProjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, project: Project) -> Project:
        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)
        return project
```

### 5. Service — `app/services/your_service.py`

```python
from app.repositories.project_repo import ProjectRepository
from app.schemas.project import ProjectCreate
from app.models.project import Project

class ProjectService:
    def __init__(self, project_repo: ProjectRepository):
        self.project_repo = project_repo

    async def create_project(self, user_id: int, data: ProjectCreate) -> Project:
        project = Project(**data.model_dump(), user_id=user_id)
        return await self.project_repo.create(project)
```

### 6. Dependencies — add to `app/api/deps.py`

```python
async def get_project_repo(db: db_dependency) -> ProjectRepository:
    return ProjectRepository(db)

async def get_project_service(repo: Annotated[ProjectRepository, Depends(get_project_repo)]) -> ProjectService:
    return ProjectService(repo)
```

### 7. Route — `app/api/v1/your_route.py`

```python
from fastapi import APIRouter, Depends
from typing import Annotated

router = APIRouter()

@router.post("/", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ProjectService, Depends(get_project_service)],
):
    return await service.create_project(current_user.id, data)
```

### 8. Register — add to `app/api/api_v1.py` and `main.py`

---

## Environment Variables

| Variable                      | Description                        | Example                                                    |
| ----------------------------- | ---------------------------------- | ---------------------------------------------------------- |
| `PROJECT_NAME`                | App name (used in docs, logs)      | `My App`                                                   |
| `DATABASE_URL`                | Async PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/db`              |
| `SECRET_KEY`                  | JWT signing key (min 256-bit)      | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ALGORITHM`                   | JWT algorithm                      | `HS256`                                                    |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL                   | `30`                                                       |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Refresh token TTL                  | `7`                                                        |
| `ALLOWED_ORIGINS`             | CORS origins (JSON array)          | `["http://localhost:3000"]`                                |

---

## Tech Stack

- **FastAPI** — async web framework
- **SQLAlchemy 2.0** — async ORM with mapped columns
- **Alembic** — database migrations
- **Pydantic v2** — validation and settings
- **python-jose** — JWT encoding/decoding
- **passlib + bcrypt** — password hashing
- **slowapi** — rate limiting
- **PostgreSQL** — production database
- **Docker + Docker Compose** — containerization
- **pytest + httpx + aiosqlite** — async testing
