# Cursor desktop integration

Implemented in the development tree; not included in the published v0.2.1 installer.
Reference: [Cursor's official hook documentation](https://cursor.com/docs/hooks), reviewed
2026-10-31. Protocol fixtures and Scrip subprocess tests do not certify a live Cursor version.

## Connect

Run the current source desktop, choose **Connections → Cursor**, select one local project,
and choose visibility or shell/MCP rules. Review the complete proposed `.cursor/hooks.json`
before saving. Existing settings and other hooks are preserved and backed up. Configuration
alone does not start an agent; start a new conversation to receive actual events.

Disconnect removes only Scrip-owned entries. It preserves later user edits and hooks installed
before Scrip, including exact matching entries. Each host has a separate connection receipt,
so Claude Code and Cursor can share a project without sharing configuration ownership.

## Supported capabilities

| Surface | Behavior |
| --- | --- |
| Session start/end and turn stop | Session visibility; turn failures enqueue alerts |
| Completed tools | Records names and inputs, drops outputs |
| Shell/MCP permissions in rules mode | Exact allow/deny rules; other requests ask in Cursor |
| Visibility mode | No permission hooks installed |
| Structured questions, answers, resume | Unsupported; interact in Cursor |
| Remote, WSL, cloud, multi-root | Unsupported by this local connector |

Generic `preToolUse` does not enforce `ask`, so it is not installed. Rules mode uses
`beforeShellExecution` and `beforeMCPExecution`; timeouts/crashes block through `failClosed`.
When Scrip can return a valid unavailable response, it returns native `ask`. Other permission
surfaces retain Cursor behavior. Scrip does not execute the proposed command or MCP call.

Shell rules include the full command, absolute cwd within the workspace, and sandbox flag.
MCP rules include server name, tool, exact input, and the documented endpoint or launch command.
Hooks without sufficient identity are rejected and return native review. Exact matching is
not a command safety classifier; inspect all arguments before saving a rule.

Cursor shell/MCP hooks provide no unique per-call ID. Scrip scopes matching operations to the
conversation, workspace, and generation. An identical call in the same generation shares a
scope and cannot receive automatic allow twice. A changed payload under that identity conflicts
and falls back to native review. A new generation can match the rule again. Parallel identical
calls can share an inbox entry; individual-call tracking is not guaranteed by this interface.

Project hook commands reference the local Scrip installation and private state. Do not commit
or copy generated hooks into cloud/remote environments. Known remote execution is rejected;
this is not a remote transport. No installed IDE files are read or modified by setup or tests.

## Validation still required before release

Use an explicitly selected disposable workspace and record Cursor version and OS. Check
observed lifecycle/tool events, allow/deny/ask, duplicate commands, MCP identity changes,
unavailable service, crash/timeout behavior, OS alert display, and selective disconnect.
Use harmless fixtures; do not run proposed commands as part of repository tests. Record results
before describing any host/version/platform combination as certified.
