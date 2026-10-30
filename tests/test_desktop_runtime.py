import socket

import pytest

pytest.importorskip("PySide6")

from scrip_core.client import Client  # noqa: E402
from scrip_core.desktop.runtime import LocalRuntime  # noqa: E402


def test_fresh_runtime_has_no_fake_data_and_owns_only_its_loopback_service(tmp_path):
    runtime = LocalRuntime(tmp_path / "state")
    service = runtime.start()
    try:
        health = Client(runtime.settings).request("/v1/health")
        assert health["events"] == 0 and health["rules"] == 0
        assert service.inbox() == [] and service.sessions() == []
        assert runtime.listener.getsockname()[0] == "127.0.0.1"
        assert len(runtime.settings.token()) >= 32
        # A second desktop/runtime can share an authenticated pre-existing service,
        # but must neither replace its connection nor stop it on close.
        other = LocalRuntime(runtime.settings.data_dir)
        other.start()
        assert other.server is None
        other.close()
        assert Client(runtime.settings).request("/v1/health")["events"] == 0
    finally:
        runtime.close()
    assert not runtime.thread.is_alive()
    with pytest.raises(OSError):
        Client(runtime.settings).request("/v1/health")


def test_runtime_does_not_take_over_an_unrelated_listener(tmp_path):
    import json

    from scrip_core.settings import Settings

    settings = Settings(tmp_path)
    settings.initialize()
    with socket.socket() as unrelated:
        unrelated.bind(("127.0.0.1", 0))
        (tmp_path / "connection.json").write_text(
            json.dumps({"base_url": f"http://127.0.0.1:{unrelated.getsockname()[1]}"})
        )
        runtime = LocalRuntime(tmp_path)
        try:
            runtime.start()
            assert runtime.listener.getsockname() != unrelated.getsockname()
            assert unrelated.fileno() >= 0
        finally:
            runtime.close()
