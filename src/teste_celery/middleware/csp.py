from urllib.parse import urlparse

from settings import SETTINGS

# origem do Flower liberada no frame-src (painel embutido no admin)
_flower = urlparse(SETTINGS.FLOWER_URL)
FLOWER_ORIGIN = f"{_flower.scheme}://{_flower.netloc}"

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CSPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/admin"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                f"frame-src 'self' {FLOWER_ORIGIN};"
            )
        return response
