from __future__ import annotations

import json
from typing import Any, NoReturn
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .limits import MAX_EVENT_BYTES
from .settings import Settings


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> NoReturn:
        raise ValueError("Scrip connections must not redirect")


class Client:
    def __init__(self, settings: Settings, *, timeout: float = 2.0):
        config = json.loads((settings.data_dir / "connection.json").read_text(encoding="utf-8"))
        self.base_url = config["base_url"]
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.port is None
        ):
            raise ValueError("Scrip must connect directly to an IPv4 loopback endpoint")
        self.token = settings.token()
        self.timeout = timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirects())

    def request(self, path: str, document: dict[str, Any] | None = None) -> dict[str, Any]:
        if not path.startswith("/v1/") or ".." in path:
            raise ValueError("Invalid Scrip endpoint")
        body = None if document is None else json.dumps(document, allow_nan=False).encode("utf-8")
        if body is not None and len(body) > MAX_EVENT_BYTES:
            raise ValueError("Event is too large")
        request = Request(
            self.base_url.rstrip("/") + path,
            data=body,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                document = json.load(response)
                if not isinstance(document, dict):
                    raise ValueError("Scrip returned a non-object response")
                return document
        except HTTPError as error:
            raise ValueError(f"Scrip returned HTTP {error.code}; inspect the service log") from None
