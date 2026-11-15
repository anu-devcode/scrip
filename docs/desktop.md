# Desktop application

Install the Windows setup from https://scrip.anwardev.me and open Scrip from the Start menu.
The bundled runtime starts the authenticated loopback service automatically. New installations
start without events, sessions, requests, or rules. There is no demo launch mode.

## Connect

In the development tree, Connections offers Claude Code and Cursor. Choose the host and an
existing local project. The published v0.2.1 installer offers Claude Code only.
Claude Code Notifications mode observes
without altering native permission decisions. Rules mode enables exact configured decisions;
unknown requests need native review. Review the complete proposed settings and confirm to
write `.claude/settings.local.json`. Scrip preserves unrelated hooks/settings and saves a
backup. It checks for concurrent edits before saving. No vendor/application files are touched.

Start a new host session. Configured means the expected hooks exist; it does not mean a host
has delivered events. Sessions and Inbox show only actual received activity. The guided
connection supports Claude Code and, in the development tree, local single-root Cursor.
Cursor visibility mode installs no permission hooks. Its rules mode handles shell/MCP
requests and leaves other permission surfaces in Cursor. It does not capture native
structured questions. See [Cursor's capability limits](integrations/cursor.md).
Additional guided host support requires separate implementation and live validation.

## Requests and rules

Read full questions, options, tools, arguments, and workspace context in Inbox. Answer
questions and existing permission prompts in the originating agent. Dismiss locally does
not answer or approve anything. Create an exact approval rule from a pending tool request,
review all fields, then save. Desktop-created rules expire in 24 hours and apply only to
future matching calls in Rules mode. Rules can be paused globally or removed from Rules.
Question tools cannot have execution-approval rules.

Closing the window keeps Scrip in the tray when available. Quit stops the service owned by
the desktop; a separately running authenticated service is not stopped. An unrelated port
listener is never terminated. Notifications can be disabled by OS settings; the inbox works
without them. Native OS display and host-version certification remain outstanding.

## Alert delivery

Open Alerts to see the most recent 100 notification records, their delivery state, attempt
count, and an error type if a send failed. Questions, tool arguments, and exception messages
are not included in this view. Sent means a notification sender accepted it (the desktop
API for tray alerts); it does not confirm the OS displayed it or that you read it. Check Windows
notification settings and focus/do-not-disturb mode if an alert is missing.

Waiting alerts resume when delivery is available. For a failed question or approval alert,
select it and choose Retry failed alert. The original request must still be pending. Scrip
rechecks this when retrying, so stale selections cannot revive resolved, expired, or dismissed
requests. Sent alerts and agent-failure history cannot be retried from this screen. Retrying
sends a notification only; it does not replay a tool, grant permission, or answer a question.

## Disconnect, update, uninstall

Disconnect the project in Connections and restart its agent session to reload hooks.
Only saved Scrip hook entries are removed; other hooks and settings are preserved. Download
and run a newer installer to update. There is no silent updater or rollback of local database
migrations. Uninstall from Windows Settings after disconnecting; private state remains under
`%LOCALAPPDATA%/Scrip`. Back it up before manually removing it.

## Development

```sh
uv sync --locked --extra dev --extra desktop
uv run scrip desktop
uv run python -m devtools.capture_desktop
```

The capture writes `dist/desktop.png` with the actual empty Connections screen and never
starts a host, seeds events, or displays native alerts. Database reads/writes are kept off
the GUI thread. All host-provided text renders as plain text. Offscreen tests do not connect
real workspaces, display OS alerts, or change installed host settings.
