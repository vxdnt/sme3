from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import FRONTEND_DIR


def load_frontend(filename: str) -> str:
    path = FRONTEND_DIR / filename
    if not path.exists():
        fallback = Path(__file__).resolve().parent.parent / "templates" / filename
        if fallback.exists():
            return fallback.read_text(encoding="utf-8")
        raise FileNotFoundError(filename)
    return path.read_text(encoding="utf-8")


def custom_404_html(message: str = "We couldn't find that page.") -> str:
    template = load_frontend("404.html")
    return template.replace("{{message}}", message)


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    is_api = request.url.path.startswith("/api/")
    detail = getattr(exc, "detail", "An error occurred.")
    if exc.status_code == 404:
        if is_api:
            return JSONResponse({"ok": False, "error": detail}, status_code=404)
        accept = request.headers.get("accept", "")
        if "application/json" in accept.lower():
            return JSONResponse({"ok": False, "error": detail}, status_code=404)
        return HTMLResponse(custom_404_html("The page or API endpoint you requested doesn't exist."), status_code=404)
    if exc.status_code == 405:
        if is_api:
            return JSONResponse({"ok": False, "error": detail}, status_code=405)
        return HTMLResponse(custom_404_html("This action is not allowed for this URL."), status_code=405)
    if is_api:
        return JSONResponse({"ok": False, "error": detail}, status_code=exc.status_code)
    return JSONResponse({"detail": detail}, status_code=exc.status_code)
