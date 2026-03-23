from typing import Any, Literal

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from routes import livro, pagina, token, user
from uvicorn import run

app = FastAPI()
app.include_router(user.router)
app.include_router(token.router)
app.include_router(livro.router)

app.include_router(pagina.router)


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
