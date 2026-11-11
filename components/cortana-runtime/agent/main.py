"""Owned, authenticated loopback service launched by the Cortana desktop app."""

from contextlib import asynccontextmanager
import asyncio
import os
from fastapi import FastAPI

from core import db, stt
from core.config import settings
from core.tools_loader import load_all_tools
from core.security import LocalSessionAuth
from core.parent_watchdog import start_parent_watchdog
from core.browser_session import close_browser
from core.desktop_drafts import cancel_drafts
from routers import assistant, chat, drafts, health, introspection, stubs, voice, local_architecture

@asynccontextmanager
async def lifespan(_app):
    if settings.host not in {"127.0.0.1", "::1", "localhost"}:
        raise RuntimeError("Cortana must bind to a loopback interface.")
    if len(os.environ.get("CORTANA_API_TOKEN", "")) < 32:
        raise RuntimeError("Start Cortana from its desktop launcher; a fresh authentication token is required.")
    stop_watchdog = start_parent_watchdog()
    try:
        db.init_db()
        load_all_tools()
        from core import local_store, model_profiles
        local_store.recover()
        model_profiles.initialize_selection()
        # Finish CUDA initialization before the desktop advertises voice-ready.
        # Speech initializes on the owner's first recording, not during startup.
        brain_warmup = asyncio.create_task(health.warm_brain())
        from core.workspace_scheduler import run as snapshot_loop
        snapshots = asyncio.create_task(snapshot_loop())
        yield
    finally:
        if 'brain_warmup' in locals():
            brain_warmup.cancel()
        if 'snapshots' in locals():
            snapshots.cancel()
        cancel_drafts()
        close_browser()
        from core.resource_broker import shutdown_owned_gpu
        from fastapi.concurrency import run_in_threadpool
        await run_in_threadpool(shutdown_owned_gpu)
        stop_watchdog()


app = FastAPI(title=settings.app_name, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(LocalSessionAuth)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(drafts.router)
app.include_router(introspection.router)
app.include_router(assistant.router)
app.include_router(stubs.router)
app.include_router(local_architecture.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
