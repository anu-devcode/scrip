# Scrip

Scrip is a local desktop companion for coding agents. It keeps structured questions,
permission requests, sessions, and exact approval rules in one place.

## Install

Download the Windows x64 setup from **https://scrip.anwardev.me**. The installer includes
Python and Qt, adds a Start menu shortcut, and opens a clean application. No terminal or
Python environment is required. The current installer is unsigned.

Open Connections, select a Claude Code workspace, review its settings, then connect.
Restart the agent session. Activity appears only when actual hook events arrive.
Scrip never seeds sessions or modifies IDE application files.

## Current scope

- Guided Claude Code workspace setup through documented hooks, with review and backups.
- A local inbox, session visibility, and tray notifications where supported by the OS.
- An Alerts screen with delivery status and explicit retry for failed pending-request alerts.
- Exact scoped approval rules with a 24-hour expiry when created in the desktop.
- Rule pause/revocation and explicit disconnection that preserves other host settings.
- An authenticated loopback service managed automatically by the desktop.

Questions and existing permission prompts are resolved in the originating agent. A saved
rule applies to future exact matches only, in Rules mode. The host retains its own controls.
Live host-version and native notification certification remain outstanding. Native macOS/Linux
installers, other guided host connections, mobile, remote control, deployment automation,
and token optimization are future work. Compatibility comes from host interfaces, not models.

## Develop

```sh
uv sync --locked --extra dev --extra desktop
uv run scrip desktop
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Normal desktop startup uses persistent local state and no fictional data. Tests use isolated
fixtures. Never point tests at a real workspace or existing application state.

## Structure

```text
src/scrip_core/   domain, orchestration, adapters, transports, storage, desktop
contracts/       synchronized event contract
tests/           isolated regression and protocol cases
devtools/        build, release, process-test, and screenshot tooling
deploy/          Windows installer and Azure static publishing
web/             public website and getting-started guide
assets/brand/    brand source and exports
```

See [development](docs/development.md), [desktop](docs/desktop.md),
[deployment](docs/deployment.md), [architecture](docs/architecture.md), and
[security](SECURITY.md). The source is MIT licensed; bundled dependencies retain their licenses.
