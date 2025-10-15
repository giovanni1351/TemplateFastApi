from typing import Any, Literal

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from routes import token, user
from uvicorn import run

app = FastAPI()
app.include_router(user.router)
app.include_router(token.router)


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema: dict[str, Any] = get_openapi(
        title="Exata API Example",
        version="0.2.132",
        summary="Sistema exemplo Exata de api em FastApi ",
        description="O acesso desta api é restrito para usuarios da exata",
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://exata.dev/storage/img/exata_BLACK_NO_IT.png"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/heath")
async def health() -> dict[str, Literal["Ok"]]:
    return {"status": "Ok"}


if __name__ == "__main__":
    run("app:app", reload=True)
