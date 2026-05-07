"""FastAPI web app factory."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import RedirectResponse


def create_app(db_url: str | None = None) -> FastAPI:
    from ..db import get_store
    store = get_store(db_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = store
        yield
        store.close()

    app = FastAPI(title="convaix", version="0.2.0", lifespan=lifespan)

    from .api import router as api_router
    from .htmx import router as htmx_router
    app.include_router(api_router, prefix="/api")
    app.include_router(htmx_router, prefix="/htmx")

    @app.get("/")
    def root():
        return RedirectResponse("/htmx/")

    return app
