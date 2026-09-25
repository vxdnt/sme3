from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import STATIC_DIR
from app.exceptions import http_exception_handler
from app.images import ensure_event_images
from app.lifespan import lifespan
from app.middleware import GracefulShutdownMiddleware
from app.routes import api, events, pages, sme


def create_app() -> FastAPI:
    application = FastAPI(title="SortMyEntries DQR", lifespan=lifespan)
    application.add_middleware(GracefulShutdownMiddleware)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    (STATIC_DIR / "css").mkdir(exist_ok=True)
    (STATIC_DIR / "js").mkdir(exist_ok=True)
    (STATIC_DIR / "images").mkdir(exist_ok=True)
    ensure_event_images()

    application.include_router(sme.router)
    application.include_router(pages.router)
    application.include_router(api.router)
    application.include_router(events.router)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application
