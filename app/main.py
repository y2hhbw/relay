from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.accounts import router as accounts_router
from app.api.catalog import router as catalog_router
from app.api.gateway import router as gateway_router
from app.api.internal import router as internal_router
from app.config import Settings
from app.db import Base, create_session_factory
from app.services.rate_limit import InMemoryRateLimiter


def create_app(database_url: str = "sqlite+pysqlite:///./relay.db") -> FastAPI:
    session_factory = create_session_factory(database_url)
    engine = session_factory.kw["bind"]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(bind=engine)
        yield

    app = FastAPI(title="Relay MVP", lifespan=lifespan)
    app.state.settings = Settings()
    app.state.session_factory = session_factory
    app.state.rate_limiter = InMemoryRateLimiter(limit=3)
    app.include_router(accounts_router)
    app.include_router(catalog_router)
    app.include_router(gateway_router)
    app.include_router(internal_router)
    return app


app = create_app()
