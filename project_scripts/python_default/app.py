# <rbac>
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
# </rbac>
from pathlib import Path
from typing import Any, Literal

# <admin>
from admin.admin_auth import backend_auth
from admin.admin_setup import setup_admin
from database import async_engine
# </admin>
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

# <admin>
from middleware.csp import CSPMiddleware
# </admin>
from router import router

# <admin>
from sqladmin import Admin
# </admin>
# <rbac>
from utils.rbac_router import sync_permissions
# </rbac>
from uvicorn import run

# <rbac>


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # mapeia todas as rotas protegidas e sincroniza a tabela de permissões
    await sync_permissions(app)
    yield


app = FastAPI(lifespan=lifespan)
# </rbac>
# <no-rbac># app = FastAPI()
# <admin>
app.add_middleware(CSPMiddleware)
# </admin>
app.include_router(router)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# <admin>

templates_dir = str(Path(__file__).parent / "templates")

admin = Admin(
    app,
    async_engine,
    authentication_backend=backend_auth,
    title="Administração",
    templates_dir=templates_dir,
)

setup_admin(admin)
# </admin>


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema: dict[str, Any] = get_openapi(
        title="API Example",
        version="0.1.0",
        summary="Sistema de api em FastApi",
        description="O acesso desta api é restrito",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/health")
async def health() -> dict[str, Literal["Ok"]]:
    return {"status": "Ok"}


if __name__ == "__main__":
    run("app:app", reload=True)
