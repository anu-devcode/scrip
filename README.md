# Scrip

A local Python companion for coding agents: explicit permission policies, a shared input
inbox, session history, and durable notification records.

**Status: development alpha.** The core and two hook adapters are covered by protocol and
local process tests. An optional desktop inbox and Qt tray-alert consumer are implemented.
Live host integration, native alert certification, installers, and release certification
remain future work. Compatibility depends on the host's documented interfaces.

## Try it locally

Requires Python 3.12 or newer and `uv`. From this repository:

```sh
uv sync --locked --extra dev --extra desktop
uv run python -m devtools.demo
```

The demo starts a temporary authenticated service, submits sample hook events, demonstrates
an exact permission rule and replay protection, and records a question notification. It
cleans up its own process and state. Proposed agent commands are never executed.

For remote development, [open a GitHub Codespace](https://codespaces.new/anu-devcode/scrip)
or clone [the repository](https://github.com/anu-devcode/scrip) into your development host.
See the [remote setup guide](docs/development.md#remote-development).

## What exists

- Validated, versioned events and an exported [JSON Schema](contracts/event-v1.schema.json).
- Deterministic rules scoped to an adapter, workspace, exact tool arguments, optional session,
  and expiry. Deny takes precedence; unknown actions require host review in enforcing mode.
- Transactional SQLite sessions, event history, pending requests, and notification outbox.
- Separate event orchestration, storage, HTTP transport, CLI, and host adapters.
- Antigravity and Claude Code hook adapters with explicit native permission responses.
  Configuration generation prints JSON for review; it does not install host settings.
- Loopback HTTP service with bearer authentication, bounded request bodies, and typed responses.

Questions require an answer in the originating agent. Local acknowledgement only dismisses
the inbox item. Notifications have console and optional desktop consumers. Scrip's hook
decision is advisory to the host, not an execution sandbox.

## Desktop preview

On a machine with a graphical session, try the inbox with temporary fictional requests:

```sh
uv run --extra desktop scrip desktop --demo
```

The desktop offers full request details, local dismissal, pause/resume, recent sessions, and
tray alerts where the desktop environment supports them. It performs database work on a
background thread and never executes proposed tools or answers questions. See the
[desktop guide](docs/desktop.md) for real-state setup and notification limits.

## Repository

```text
src/scrip_core/
  models.py, policy.py     event contracts and pure permission decisions
  service.py, ports.py     orchestration and storage/delivery interfaces
  records.py              typed application results
  storage/                SQLite transactions, migrations, and queries
  adapters/               shared mechanics and explicit host protocols
  desktop/                optional Qt inbox, worker, and tray consumer
  api.py, client.py        local HTTP transport
  cli.py, commands.py      command parsing and handlers
contracts/                exported event schema
tests/                    regression and protocol tests
devtools/                 shared process harness and isolated demo
docs/                     architecture and development guides
```

One root `pyproject.toml` and `uv.lock` define the Python package. The obsolete JavaScript
extension and vendor-patching tools have been removed from this repository. Existing local
IDE installations are outside this project's maintenance scope.

## Development

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

See the [development guide](docs/development.md), [architecture](docs/architecture.md),
[product plan](PRODUCT_PLAN.md), [contribution guide](CONTRIBUTING.md), and
[security notes](SECURITY.md). Licensed under [MIT](LICENSE).
