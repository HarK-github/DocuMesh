"""FastAPI application entry point."""

import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle handler."""
    # Phase 1 & 7: DB initialization and startup job cleanup
    try:
        from backend.app.db import init_db
        init_db()
    except Exception:
        pass
    yield


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance."""
    settings = get_settings()
    app = FastAPI(
        title="PDF Annotation & Knowledge Graph API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS
    origins: List[str] = (
        json.loads(settings.cors_origins)
        if isinstance(settings.cors_origins, str)
        else settings.cors_origins
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from backend.app.routes.documents import router as documents_router
    from backend.app.routes.jobs import router as jobs_router
    from backend.app.routes.taxonomy import router as taxonomy_router
    from backend.app.routes.annotations import router as annotations_router
    from backend.app.routes.relations import router as relations_router

    app.include_router(documents_router)
    app.include_router(jobs_router)
    app.include_router(taxonomy_router)
    app.include_router(annotations_router)
    app.include_router(relations_router)

    @app.get("/health", tags=["System"])
    def health_check() -> dict:
        """Health check endpoint confirming API operational status."""
        return {"status": "ok"}

    return app


app = create_app()
