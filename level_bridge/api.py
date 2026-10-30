"""FastAPI application: snapshot, JSON level input, periods, and WebSocket stream."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from level_bridge import __version__
from level_bridge.models import (
    DASHBOARD_SLOT_COUNT,
    SCHEMA_VERSION,
    DashboardSnapshot,
    LevelUpdate,
    Periods,
)
from level_bridge.settings import Settings
from level_bridge.sources.blackhole import BlackHoleSource
from level_bridge.sources.logic_mcp import LogicGainSource
from level_bridge.store import LevelStore, UnknownTrackError
from level_bridge.track_config import load_track_layout

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"
STREAM_PATH = f"{API_PREFIX}/stream"


def _summarize_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "loc": [str(part) for part in error.get("loc", ())],
            "msg": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        for error in errors
    ]


def create_app(settings: Settings) -> FastAPI:
    layout = load_track_layout(settings.tracks_config_path, settings.tracks_example_path)
    store = LevelStore(layout, settings.initial_periods, settings.level_sources)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        tasks: list[asyncio.Task[None]] = []
        blackhole: BlackHoleSource | None = None
        if "blackhole" in settings.level_sources:
            blackhole = BlackHoleSource(settings, store)
            await asyncio.to_thread(blackhole.start)
        if "logic" in settings.level_sources:
            tasks.append(asyncio.create_task(LogicGainSource(settings, store).run()))
        logger.info("Bridge started with sources: %s", ", ".join(sorted(settings.level_sources)))
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if blackhole is not None:
                await asyncio.to_thread(blackhole.stop)
            logger.info("Bridge stopped")

    app = FastAPI(title="Band Levels Bridge", version=__version__, lifespan=lifespan)
    app.state.store = store

    @app.exception_handler(RequestValidationError)
    async def reject_invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        summary = _summarize_errors(list(exc.errors()))
        logger.warning("Rejected %s %s: %s", request.method, request.url.path, summary)
        return JSONResponse(status_code=422, content={"detail": summary})

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get(f"{API_PREFIX}/config")
    async def config() -> dict[str, Any]:
        snapshot = store.snapshot()
        return {
            "schema_version": SCHEMA_VERSION,
            "slot_count": DASHBOARD_SLOT_COUNT,
            "stream_path": STREAM_PATH,
            "tracks": [
                {"slot": track.slot, "track_id": track.id, "name": track.name}
                for track in sorted(layout.tracks, key=lambda item: item.slot)
            ],
            "periods": snapshot.periods.model_dump(),
            "sources": [source.model_dump() for source in snapshot.sources],
        }

    @app.get(f"{API_PREFIX}/snapshot", response_model=DashboardSnapshot)
    async def snapshot() -> DashboardSnapshot:
        return store.snapshot()

    @app.post(f"{API_PREFIX}/levels", status_code=202)
    async def post_levels(update: LevelUpdate, request: Request) -> dict[str, int]:
        if not store.source_enabled("json"):
            logger.warning("Rejected %s %s: json source disabled", request.method, request.url.path)
            raise HTTPException(status_code=409, detail="json level source is disabled")
        try:
            accepted = store.apply_level_update(update)
        except UnknownTrackError as exc:
            logger.warning("Rejected %s %s: %s", request.method, request.url.path, exc)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        logger.info("Accepted %d track levels from %s", accepted, update.source)
        return {"accepted": accepted, "sequence": store.snapshot().sequence}

    @app.get(f"{API_PREFIX}/periods", response_model=Periods)
    async def get_periods() -> Periods:
        return store.periods()

    @app.put(f"{API_PREFIX}/periods", response_model=Periods)
    async def put_periods(periods: Periods) -> Periods:
        return store.set_periods(periods)

    async def send_snapshots(websocket: WebSocket) -> None:
        try:
            while True:
                await websocket.send_text(store.snapshot().model_dump_json())
                await asyncio.sleep(store.periods().publish_interval_ms / 1000.0)
        except (WebSocketDisconnect, RuntimeError, OSError) as exc:
            logger.info("Stopped streaming to %s (%s)", websocket.client, type(exc).__name__)

    @app.websocket(STREAM_PATH)
    async def stream(websocket: WebSocket) -> None:
        await websocket.accept()
        logger.info("Dashboard connected: %s", websocket.client)
        sender = asyncio.create_task(send_snapshots(websocket))
        try:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
            logger.info("Dashboard disconnected: %s", websocket.client)

    return app
