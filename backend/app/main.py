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
    try:
        from backend.app.db import init_db
        init_db()
        from backend.app.services.jobs import cleanup_stale_jobs
        cleanup_stale_jobs()
        from backend.app.services.embedder import get_embedder
        get_embedder()
    except Exception:
        pass
    yield


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance."""
    settings = get_settings()
    app = FastAPI(
        title="DocuMesh API",
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
        allow_origin_regex=r"https://.*\.vercel\.app|http://localhost.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from backend.app.routes.documents import router as documents_router
    from backend.app.routes.jobs import router as jobs_router
    from backend.app.routes.taxonomy import router as taxonomy_router
    from backend.app.routes.annotations import router as annotations_router
    from backend.app.routes.relations import router as relations_router
    from backend.app.routes.suggestions import router as suggestions_router
    from backend.app.routes.chat import router as chat_router

    app.include_router(documents_router)
    app.include_router(jobs_router)
    app.include_router(taxonomy_router)
    app.include_router(annotations_router)
    app.include_router(relations_router)
    app.include_router(suggestions_router)
    app.include_router(chat_router)

    @app.get("/health", tags=["System"])
    def health_check() -> dict:
        """Health check endpoint confirming API operational status."""
        return {"status": "ok"}

    # Serve production frontend single-page application if built
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    dist_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if dist_dir.exists():
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            file_path = dist_dir / full_path
            if full_path and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(dist_dir / "index.html")

    return app


app = create_app()
