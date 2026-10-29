import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI, Request, Response, status

from review_agents import __version__
from review_agents.config import Settings
from review_agents.db import connect, migrate
from review_agents.worker import ReviewHandler, Worker, not_implemented


def create_app(settings: Settings, handler: ReviewHandler = not_implemented) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with closing(connect(settings.db_path)) as conn:
            migrate(conn)
        worker = Worker(settings.db_path, handler, settings.worker_poll_seconds)
        worker.start()
        app.state.worker = worker
        try:
            yield
        finally:
            await worker.stop()

    app = FastAPI(title="review-agents", version=__version__, lifespan=lifespan)

    @app.get("/healthz")
    def healthz(request: Request, response: Response) -> dict[str, str]:
        problem = None
        try:
            with closing(connect(settings.db_path, create=False)) as conn:
                conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        except sqlite3.Error:
            problem = "database unavailable"
        if problem is None and not request.app.state.worker.alive:
            problem = "worker stopped"
        if problem is not None:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": problem, "version": __version__}
        return {"status": "ok", "version": __version__}

    return app
