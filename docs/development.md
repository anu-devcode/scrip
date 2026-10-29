# Development guide

Use Python 3.12+ and `uv`. Run commands from the repository root. Development state can
contain tool arguments and questions; keep it private and separate from real agent work.

## Remote development

Open [Scrip in GitHub Codespaces](https://codespaces.new/anu-devcode/scrip) and select `main`.
The repository's development container uses Python 3.13 and installs the pinned `uv` tool
and locked development dependencies. After setup, use the verification commands below.
The container configuration is provided for remote development; it has not been launched
or certified from this local workspace.

Push changes on a task branch and open a pull request. The
[GitHub Actions workflow](https://github.com/anu-devcode/scrip/actions) checks Windows,
Linux, and macOS and builds the Python distributions. The workflow does not publish releases.
For another remote development environment, clone the repository and follow the same setup
commands. Scrip does not depend on Codespaces.

## Install and verify

```sh
uv sync --locked --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m devtools.demo
uv build
```

The isolated demo and process tests share `devtools/process.py`. They own and clean up their
child service and temporary state, invoke only Scrip hook processes, and never execute a
proposed agent tool. The development helpers and tests are excluded from the installed wheel.

Regenerate the event schema after intentional contract changes, then run the contract tests:

```sh
uv run scrip schema --output contracts/event-v1.schema.json
uv run pytest tests/test_contract.py
```

CI is configured for Windows, Linux, and macOS with Python 3.12/3.13. Configured CI is not
proof of a successful run on every platform. Local verification has been performed on
Windows with Python 3.13. Live host integration is a separate release gate.

## Run a local service

```sh
uv run scrip --data-dir .scrip-dev init --port 18765
uv run scrip --data-dir .scrip-dev serve --port 18765
```

Leave the service running and use another terminal:

```sh
uv run scrip --data-dir .scrip-dev status
uv run scrip --data-dir .scrip-dev sessions
uv run scrip --data-dir .scrip-dev inbox
uv run scrip --data-dir .scrip-dev history
uv run scrip --data-dir .scrip-dev notifications --drain-console
```

`init` creates an API token, connection settings, and a database. It preserves an existing
token. A changed service port requires matching connection settings or another data directory.
Stop the service with Ctrl+C. No background service, startup registration, or host hooks are
installed. `--help` describes all commands.

## Adapter configuration

```sh
uv run scrip --data-dir .scrip-dev adapter capabilities --adapter claude-code
uv run scrip --data-dir .scrip-dev adapter config --adapter claude-code
uv run scrip --data-dir .scrip-dev adapter config --adapter antigravity
```

Generators only print JSON. Review it against the host's current documentation before using
it in a deliberate isolated test setup. They default to `observe`; explicit `--mode enforce`
enables policy responses. Observation does not claim that all native tools await approval.
The adapters' fixture/transport tests do not certify a live host version.

Native protocols are documented at [Antigravity hooks](https://antigravity.google/docs/hooks)
and [Claude Code hooks](https://code.claude.com/docs/en/hooks). The adapters deliberately
retain different response mappings. Unsupported/ambiguous payloads return to native review
in enforcing mode. Plain text questions and answer forwarding are unsupported.

## Rules and questions

An explicitly reviewed rule file contains `id`, `adapter`, absolute `workspace`, `tool`,
full exact `arguments`, and `action` (`allow` or `deny`). Optional fields are `session_id`,
timezone-aware `expires_at`, and `enabled`.

```sh
uv run scrip --data-dir .scrip-dev rules add my-reviewed-rule.json
uv run scrip --data-dir .scrip-dev rules list
uv run scrip --data-dir .scrip-dev rules remove RULE_ID
uv run scrip --data-dir .scrip-dev pause
uv run scrip --data-dir .scrip-dev resume
uv run scrip --data-dir .scrip-dev acknowledge REQUEST_ID
```

There is no prefix matching or automatic import of workspace policies. Review what project
scripts execute before granting rules. Answer questions in the originating agent;
`acknowledge` only dismisses the local request. Pending requests expire after 15 minutes.

## Local HTTP interface

All endpoints require the token; request bodies are limited to 1 MiB. There are no HTTP rule
mutation, tool execution, or answer-forwarding endpoints. The service is intended for one
local user, not public network exposure.

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/health` | Version and status |
| `POST /v1/events` | Validate, persist, and evaluate events |
| `GET /v1/sessions` | Recent sessions |
| `GET /v1/inbox` | Pending local input/review items |
| `POST /v1/inbox/{id}/acknowledge` | Dismiss locally |
| `GET /v1/history` | Recent event/decision history |
| `GET /v1/notifications` | Recent outbox records |

See [architecture](architecture.md) for transaction, replay, and delivery guarantees.
