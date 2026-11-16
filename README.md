# Scrip

Start and stop shell-command approval for one Antigravity conversation from your project
terminal. The current installer supports **Windows 10/11 x64**.

## Install

[Download Scrip Terminal 0.4.3](https://scrip.anwardev.me/downloads/Scrip-Terminal-0.4.3-windows-x64-setup.exe)

1. Run the installer and keep **Add Scrip to your user PATH** selected.
2. Restart your editor so its terminal and agent hooks receive the new PATH.
3. Open a terminal in your project folder and review the proposed hook setup.

```powershell
scrip setup
scrip setup --apply
```

Setup is needed once per project. It installs the named hook in `.agents/hooks.json`,
preserves unrelated hooks, and backs up existing settings. Begin a new agent turn after
setup. An already-open approval prompt still needs a response in Antigravity.

The installer bundles its runtime and is unsigned. Download checksums are available at
[SHA256SUMS](https://scrip.anwardev.me/downloads/SHA256SUMS).

## Use

```powershell
scrip start
```

Continue your intended Antigravity conversation. The first valid shell-command callback
binds Scrip to that conversation. Subsequent commands in the same conversation receive
Scrip approval until you stop it or 24 hours pass.

```powershell
scrip status --project
scrip stop
```

Start authorizes every shell command in the bound conversation, including writes, deletion,
publishing, and network access. Native Ask/Deny rules still apply. Questions require your
answer. Other conversations and projects do not inherit the grant. Stop revokes future
Scrip approvals. Running commands continue.

To switch conversations, stop and start again. Repeating start while active preserves the
existing binding. Active status alone does not establish that the host delivered a callback.

Setup, start, and stop each print a short confirmation. Use `scrip setup` to inspect the
hook configuration and `scrip status --project` for scope, binding, and expiry details.

## Compatibility and troubleshooting

This release integrates with Antigravity's documented command hooks. You can run the Scrip
command in your usual editor terminal. Approval support depends on the agent's hook interface.
Live Antigravity-version validation is still in progress.

- If `scrip` is unrecognized, restart the terminal's parent application and check the PATH
  installer option. The executable is `%LOCALAPPDATA%\Programs\ScripTerminal\scrip.exe`.
- If approvals still prompt, check `scrip status --project` and Antigravity's native rules.
  Invalid callbacks require native review.
- For exact saved-command mode, updates, and removal, see the
  [project integration guide](docs/integrations/antigravity-project.md).
- Report reproducible bugs through [GitHub Issues](https://github.com/anu-devcode/scrip/issues).
  Keep local databases, tokens, private paths, and raw agent transcripts out of reports.

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
web/             minimal download page and preserved expanded website
assets/brand/    brand source and exports
```

See [development](docs/development.md), [desktop](docs/desktop.md),
[deployment](docs/deployment.md), [architecture](docs/architecture.md), and
[security](SECURITY.md). The source is MIT licensed; bundled dependencies retain their licenses.
