from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import router
from src.config import settings
from src.core.logging import setup_logging
from src.core.tracing import setup_langsmith
from src.core.llamaindex_setup import setup_llamaindex
from src.vectordb.qdrant_store import ensure_collection
from src.database.session import engine
from src.database.models import Base

import structlog

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    setup_langsmith()
    setup_llamaindex()

    logger.info("starting_arecca", env=settings.app_env)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ensure_collection()
    logger.info("qdrant_collection_ensured")

    yield

    await engine.dispose()
    logger.info("arecca_shutdown")


app = FastAPI(
    title="ARECCA",
    description="Automated Real Estate Contract Compliance Auditor",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )
