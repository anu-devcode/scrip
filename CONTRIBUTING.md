# Contributing to Scrip

Scrip is an open-source development alpha. Read [AGENTS.md](AGENTS.md),
[architecture](docs/architecture.md), and [development](docs/development.md) before changing
permission, adapter, or persistence behavior.

## Setup

```sh
uv sync --locked --extra dev --extra desktop
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m devtools.demo
uv build
```

## Branches and merging

Use `feat/`, `fix/`, `chore/`, `docs/`, or another conventional purpose prefix, followed by
a descriptive name. Open a pull request into `main` and pass the required CI checks.
`main` is protected from direct pushes, force pushes, and deletion. Resolve open review
conversations before merging. Administrators follow the same branch rules.

Azure publication runs from `main`. Release tags must identify commits already merged into
`main`. The production environment accepts the `main` branch only.

## Change guidelines

- Keep policy and orchestration independent of SQLite, HTTP, and host-specific payloads.
- Share mechanics with a demonstrated second use. Preserve native permission semantics in
  each adapter. Avoid compatibility aliases and speculative plugin/framework layers.
- Use documented host APIs; configuration generators print proposed configuration for review.
  Do not patch, inspect, or change installed IDE application files.
- Add meaningful regressions for permission, workspace isolation, replay, transaction,
  lifecycle, or delivery changes. Tests must not execute proposed agent tool commands.
- Update the event schema with intentional contract changes. Add forward-only atomic schema
  migrations; never change the meaning of an already-released migration.
- Keep dependency changes in `pyproject.toml` and commit the updated `uv.lock`. Run
  `uv sync --locked --extra dev --extra desktop` before verification.
- Document actual capability limits. Fixture tests do not establish live host compatibility,
  multi-platform support, security certification, or production scale.

When proposing a change, explain the concrete behavior, relevant tradeoffs, and validation.
Keep unrelated refactors separate. Do not include tokens, private questions, database files,
local machine paths, or host transcripts containing sensitive information.

## Before publishing

The maintainer must configure repository ownership/contact details and private vulnerability
reporting, review licensing and dependency notices, check tracked content and history for
secrets, and confirm the CI matrix passes. This guide does not mean the project has already
been published or certified for production use. See [SECURITY.md](SECURITY.md).
