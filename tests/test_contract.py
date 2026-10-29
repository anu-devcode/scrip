import json
from pathlib import Path

from scrip_core.models import EVENT


def test_published_event_contract_matches_runtime():
    published = Path(__file__).parents[1] / "contracts" / "event-v1.schema.json"
    assert json.loads(published.read_text(encoding="utf-8")) == EVENT.json_schema()
