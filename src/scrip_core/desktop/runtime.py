"""Own the authenticated loopback service for the installed desktop's lifetime."""

import json
import socket
import threading
import time
from pathlib import Path
from urllib.error import URLError

import uvicorn

from ..api import create_app
from ..bootstrap import create_service
from ..client import Client
from ..service import CompanionService
from ..settings import Settings, private_write


class LocalRuntime:
    """Start off the GUI thread. Never take over or stop a separately running service."""

    def __init__(self, data_dir: Path) -> None:
        self.settings = Settings(data_dir)
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None
        self.listener: socket.socket | None = None
        self.service: CompanionService | None = None

    def start(self) -> CompanionService:
        self.settings.initialize()
        self.service = create_service(self.settings.database)
        client = Client(self.settings, timeout=0.4)
        try:
            client.request("/v1/health")
            return self.service
        except (URLError, ValueError, OSError):
            pass
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener = listener
        # Reserve the port before publishing connection metadata. An unrelated listener
        # must never receive Scrip traffic or be terminated to make room.
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        config = self.settings.data_dir / "connection.json"
        temporary = config.with_name("connection.next")
        try:
            temporary.unlink(missing_ok=True)
            private_write(temporary, json.dumps({"base_url": f"http://127.0.0.1:{port}"}))
            temporary.replace(config)
            self.server = uvicorn.Server(
                uvicorn.Config(
                    create_app(self.service, self.settings.token()),
                    host="127.0.0.1",
                    port=port,
                    loop="asyncio",
                    http="h11",
                    ws="none",
                    log_config=None,
                    access_log=False,
                    log_level="warning",
                )
            )
            self.thread = threading.Thread(
                target=self.server.run,
                kwargs={"sockets": [listener]},
                daemon=True,
                name="scrip-local-service",
            )
            self.thread.start()
            deadline = time.monotonic() + 8
            while not self.server.started:
                if not self.thread.is_alive() or time.monotonic() > deadline:
                    raise ValueError("The local connection could not start. Restart Scrip.")
                time.sleep(0.025)
            Client(self.settings).request("/v1/health")
            return self.service
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.thread is not None:
            self.thread.join(timeout=10)
        if self.listener is not None:
            self.listener.close()
