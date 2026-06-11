from pathlib import Path
from typing import Any, Literal

from admin import LivroAdmin, PaginaAdmin, PasswordResetAdmin, UserAdmin, backend_auth
from admin_config import ADMIN_CONFIG
from database import async_engine
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from middleware.csp import CSPMiddleware
from routes import livro, pagina, token, user
from sqladmin import Admin
from uvicorn import run

app = FastAPI()
app.add_middleware(CSPMiddleware)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(user.router)
app.include_router(token.router)
app.include_router(livro.router)
app.include_router(pagina.router)

templates_dir = str(Path(__file__).parent / "templates")

admin = Admin(
    app,
    async_engine,
    authentication_backend=backend_auth,
    title="Administração",
    templates_dir=templates_dir,
)
admin.templates.env.globals["admin_config"] = ADMIN_CONFIG
admin.add_view(UserAdmin)
admin.add_view(PasswordResetAdmin)
admin.add_view(LivroAdmin)
admin.add_view(PaginaAdmin)


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema: dict[str, Any] = get_openapi(
        title="API Example",
        version="0.2.132",
        summary="Sistema de api em FastApi ",
        description="O acesso desta api é restrito",
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://static.vecteezy.com/system/resources/previews/011/063/921/non_2x/example-button-speech-bubble-example-colorful-web-banner-illustration-vector.jpg"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/heath")
async def health() -> dict[str, Literal["Ok"]]:
    return {"status": "Ok"}


if __name__ == "__main__":
    run("app:app", reload=True)
