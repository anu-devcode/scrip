# Scrip contributor instructions

The repository is the Python product, using a conventional src layout and a single root
pyproject.toml/uv.lock. The obsolete JavaScript extension and IDE patching tools have been
removed at the user's explicit request. Do not restore, uninstall, inspect, or otherwise
change the installed Antigravity application as part of repository work; leave it alone.

Use documented host interfaces only. Do not add vendor-file patching, internal command
polling, or implicit host-configuration installation to this product. Hook adapters are
protocol-tested but are not yet certified inside live agent applications.

Keep policy and event orchestration independent of SQLite, HTTP, and host-specific schemas.
Share mechanics between adapters; keep native permission semantics explicit. Avoid speculative
frameworks, compatibility aliases, and abstraction layers without an actual use case.

Development: `uv sync --locked --extra dev`; `uv run pytest`; `uv run ruff check .`;
`uv run ruff format --check .`; `uv run mypy src`. Run `uv run python -m devtools.demo`
for an isolated demo. It must not execute proposed tool commands or modify any IDE.

Keep contracts/event-v1.schema.json synchronized with the runtime schema. Test new permission,
isolation, replay, transaction, or delivery behavior with meaningful regression cases.
Do not claim unlimited scale, universal host compatibility, or launch readiness from these tests.
