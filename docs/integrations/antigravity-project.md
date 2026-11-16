# Antigravity project commands

The v0.4.2 Scrip Terminal Windows build includes a bundled `scrip.exe` console command
and its Python runtime. It does not require Qt, system Python, or the Scrip desktop app.
It installs separately under `%LOCALAPPDATA%/Programs/ScripTerminal`. Use the Scrip Terminal installer from https://scrip.anwardev.me for these commands.
Older desktop installers do not include this workflow.
The installer offers adding Scrip to the current user's PATH for terminal commands. The
project hook resolves Scrip's runtime directly during setup, so it can start even when the
agent host inherited an older PATH. After updating from 0.4.1 or earlier, run
`scrip setup --apply` again, then `scrip start` to replace the earlier PATH-dependent hook.
Begin a new agent turn to load the updated hook.

## One-time reviewed setup

Open a terminal at the root of the project, then preview the hook configuration:

```powershell
scrip setup
```

After reviewing the full `.agents/hooks.json` proposal, explicitly install it:

```powershell
scrip setup --apply
```

Only explicit setup writes the named `scrip-project-commands` hook. Other hooks are
preserved, existing contents are backed up, and changed or unowned entries are refused.
Setup leaves approvals stopped. Reapplying setup updates the owned Scrip hook and backs up the previous contents.

## Daily use

```powershell
scrip start
scrip status --project
scrip stop
```

Start authorizes **all shell commands in one Antigravity conversation** for up to 24 hours.
The first valid command after start binds the grant to its conversation ID; start before
continuing the intended conversation. Other conversations and projects do not inherit it.
Starting again preserves that binding. To switch conversations, stop, then start again.
All commands includes writes, deletion, publishing, and network use. This is deliberate
session authorization, not a classifier or a filesystem/network sandbox. Commands can
access outside resources even though their working directory is inside the project.

Stop revokes future Scrip approvals even through an already-loaded hook. Decisions already
returned and commands already running cannot be recalled. Neither start nor stop edits
host configuration or runs a background polling process. Questions still need your answer;
MCP/browser and other tools are outside command authorization. Native host rules remain in charge.

For the older optional exact-command mode, configure `scrip setup --allow-command 'git status'`
and apply that explicit setup. Run `scrip start --exact` to use only its saved exact rules.
Plain `scrip start` always selects conversation mode. In exact mode, command and working
directory must match; output-wait intervals and display-only summaries are ignored, while
unknown execution options remain part of exact matching.

## Native permission behavior

Scrip returns Antigravity's documented `auto_approve` response for an authorized command. Explicit
native Ask or Deny rules still apply. Commands outside the authorized scope, stopped/expired authorizations, and
duplicate approvals delegate to native host policy. Invalid input or a hook error requests
native review. This new project hook does not force every unknown command to prompt over
your existing native grants.

An already-open approval prompt needs a response in the host. Begin a new agent turn after
setup, then use `scrip status --project` to check delivery. `configured` and `active` report
Scrip's local setup and authorization. `last_hook` records an actual callback, including its
stage and response. If it remains `null` after a new shell-command request, delivery has not
been observed. Confirm that Antigravity opened the same project root and check the app's
version against its documented hook support. Use the callback record to verify delivery even
when the hook-management screen is absent.

If a callback reports `auto_approve` but the command still prompts, inspect explicit Ask/Deny
rules and other enabled hooks in the host. A hook returning `force_ask` can request review.
Structured questions still need your answer.

## Scope and verification

This workflow targets Antigravity's documented `.agents/hooks.json` interface. A terminal in
VS Code, Cursor, or another IDE can run the Scrip command, but that does not grant control of
that IDE's agents. Codex, Claude Code, and Cursor require their own native integration.
Universal IDE/agent compatibility is not claimed.

Regression checks exercise temporary project settings, exact decisions, workspace separation,
revocation, expiry, malformed payloads, replay, and actual Scrip subprocesses. They never execute
the proposed tool command or change an installed IDE. Native artifact checks establish that
the bundled executable works without a separate Python installation. Live Antigravity-version validation is still
required; those checks are not a substitute for observing the current agent deliver an event.

On uninstall, the installer preserves private state and project settings. Stop each configured
project and remove only its `scrip-project-commands` entry through Antigravity's hook settings
before uninstalling. Keep backups until you have verified your unrelated hooks remain intact.

Build the terminal installer on Windows with locked development/build dependencies:

```powershell
uv sync --locked --extra dev --extra build
uv run python -m devtools.build_terminal --compiler PATH_TO_ISCC.exe
```

The build runs the actual bundled console and generated hooks through Windows Command Prompt,
the documented hook shell, with Scrip removed from PATH in a temporary project before compiling
the installer. Release CI also installs into a path containing spaces. It never executes the
proposed agent command. The separate desktop bundle has its own Qt validation gate; passing
terminal checks does not establish that the desktop package works.

References: [official hook contract](https://antigravity.google/docs/hooks) and
[native permission precedence](https://antigravity.google/docs/permissions).
