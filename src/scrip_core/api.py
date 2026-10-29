"""Authenticated local HTTP transport. No SQL or host-specific business rules."""

import secrets
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import __version__
from .errors import ConflictError, StorageError
from .limits import MAX_EVENT_BYTES, MAX_QUERY_ITEMS
from .models import Contract, Event, IngestResult
from .records import CoreStatus, HistoryEntry, NotificationRecord, RequestRecord, SessionRecord
from .service import CompanionService


class ItemsResponse[T](Contract):
    items: list[T]


class InboxResponse(ItemsResponse[RequestRecord]):
    answer_forwarding_supported: Literal[False] = False


class HealthResponse(CoreStatus):
    status: Literal["ok"] = "ok"
    version: str = __version__


class AcknowledgeResponse(Contract):
    acknowledged: Literal[True] = True
    answered_in_agent: Literal[False] = False


class LocalBoundary:
    """Reject browser origins and bound request bodies before validation."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if b"origin" in dict(scope["headers"]):
            await JSONResponse({"detail": "Browser-origin requests are disabled"}, 403)(
                scope,
                receive,
                send,
            )
            return
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > MAX_EVENT_BYTES:
                await JSONResponse({"detail": "Request body is too large"}, 413)(
                    scope, receive, send
                )
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        sent = False

        async def buffered_receive() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, buffered_receive, send)


def create_app(service: CompanionService, token: str) -> FastAPI:
    if len(token) < 32:
        raise ValueError("A strong local API token is required")

    def authenticate(request: Request) -> None:
        supplied = request.headers.get("authorization", "")
        if not secrets.compare_digest(supplied.encode("utf-8"), f"Bearer {token}".encode()):
            raise HTTPException(401, "A valid Scrip bearer token is required")

    app = FastAPI(
        title="Scrip local companion",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(authenticate)],
    )
    app.add_middleware(LocalBoundary)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.exception_handler(ConflictError)
    async def conflict(_request: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, 409)

    @app.exception_handler(StorageError)
    async def unavailable(_request: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, 503)

    @app.get("/v1/health")
    def health() -> HealthResponse:
        return HealthResponse(**service.status().model_dump())

    @app.post("/v1/events")
    def ingest(event: Event) -> IngestResult:
        return service.ingest(event)

    @app.get("/v1/inbox")
    def inbox() -> InboxResponse:
        return InboxResponse(items=service.inbox())

    @app.post("/v1/inbox/{request_id}/acknowledge")
    def acknowledge(request_id: str) -> AcknowledgeResponse:
        if not service.acknowledge(request_id):
            raise HTTPException(404, "Pending request not found or already expired")
        return AcknowledgeResponse()

    @app.get("/v1/sessions")
    def sessions() -> ItemsResponse[SessionRecord]:
        return ItemsResponse[SessionRecord](items=service.sessions())

    @app.get("/v1/history")
    def history(
        limit: Annotated[int, Query(ge=1, le=MAX_QUERY_ITEMS)] = 50,
    ) -> ItemsResponse[HistoryEntry]:
        return ItemsResponse[HistoryEntry](items=service.history(limit))

    @app.get("/v1/notifications")
    def notifications() -> ItemsResponse[NotificationRecord]:
        return ItemsResponse[NotificationRecord](items=service.notifications())

    return app
