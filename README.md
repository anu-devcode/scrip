# Scrip

Scrip Terminal provides project-terminal start/stop controls for shell-command approval
in one Antigravity conversation. The public Windows x64 installer is available at
[ scrip.anwardev.me ](https://scrip.anwardev.me).

## Install and connect

Download **Scrip Terminal 0.4.0** and run the per-user installer. Keep the user-PATH option
selected, then restart your editor so terminals and agent hooks inherit it. The installer
bundles its Python runtime and is currently unsigned.

From your project root, review and explicitly apply the documented hook configuration once.
Existing unrelated hooks are preserved and backed up.

```powershell
scrip setup
scrip setup --apply
```

## Daily use

```powershell
scrip start
scrip status --project
scrip stop
```

Start authorizes all shell commands in one conversation, bound to the first valid command
callback after start. This includes writes, deletion, publishing, and network access. The
grant expires after 24 hours. Stop revokes future Scrip approvals. Native Ask/Deny rules
still apply, and questions require your answer. A working directory provides no OS isolation.
Exact saved-command mode is also available through `scrip start --exact`.

See the [setup guide](https://scrip.anwardev.me/quickstart.html) and
[compatibility notes](https://scrip.anwardev.me/support.html). The terminal installer targets
Windows x64 and Antigravity command hooks. Live host-version validation remains in progress.

## Other components

The Python source also contains a desktop inbox, local authenticated HTTP transport,
notifications, and documented Claude Code/Cursor adapters. Those components have isolated
regression coverage and separate packaging requirements. They are outside the 0.4.0
terminal distribution. No universal IDE or agent compatibility is claimed.

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
