import json

import pytest

from scrip_core.client import Client
from scrip_core.settings import Settings


@pytest.mark.parametrize(
    "url",
    [
        "https://external.invalid",
        "http://localhost:8765",
        "http://127.0.0.1:8765/steal",
        "http://127.0.0.1:8765?x=1",
        "http://user:password@127.0.0.1:8765",
    ],
)
def test_client_rejects_ambiguous_or_non_loopback_targets(tmp_path, url):
    settings = Settings(tmp_path)
    settings.initialize()
    (tmp_path / "connection.json").write_text(json.dumps({"base_url": url}), encoding="utf-8")
    with pytest.raises(ValueError, match="loopback"):
        Client(settings)


def test_initialization_preserves_token(tmp_path):
    settings = Settings(tmp_path)
    settings.initialize()
    token = settings.token()
    settings.initialize()
    assert settings.token() == token
