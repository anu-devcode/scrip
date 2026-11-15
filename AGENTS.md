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

Development: `uv sync --locked --extra dev --extra desktop`; `uv run pytest`; `uv run ruff check .`;
`uv run ruff format --check .`; `uv run mypy src`. Desktop startup must remain free of seeded events. Use isolated regression fixtures for
protocol checks. Tests must not execute proposed tool commands or modify any installed IDE.

Keep contracts/event-v1.schema.json synchronized with the runtime schema. Test new permission,
isolation, replay, transaction, or delivery behavior with meaningful regression cases.
Do not claim unlimited scale, universal host compatibility, or launch readiness from these tests.

Desktop code uses the optional PySide6 Essentials dependency. Keep database operations off
the GUI thread, render host text as plain text, and submit tray alerts only on the GUI thread.
Offscreen widget tests must never display native alerts or alter a host's settings.

Create branches using conventional purpose prefixes such as `feat/`, `fix/`, `chore/`,
`docs/`, or `refactor/`. Choose a concise descriptive suffix. All changes enter `main`
through a pull request with passing required CI checks. Production deployments run from
`main` and use release commits already merged into `main`.
