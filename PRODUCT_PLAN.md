# Scrip product plan

Scrip helps developers manage interruptions across supported coding agents through explicit
permission policies, an input inbox, notifications, and action history. The initial customer
hypothesis is independent developers and small teams using multiple coding agents. Demand,
pricing, retention, and time savings remain unvalidated.

## Current foundation

The repository contains one Python product: typed events, deterministic policy decisions,
application orchestration separated from storage/HTTP, SQLite migrations and durable state,
an authenticated local service, CLI, and three documented-hook adapters. Adapter protocol and
local process tests exist. An optional Qt desktop inbox, background worker, and tray consumer
are implemented with offscreen regression tests. Live host and native OS alert certification
remain outstanding.

The old JavaScript extension, patch plans, and vendor-patching source have been removed.
Installed IDEs are outside repository maintenance. The product uses documented host interfaces
and must not add vendor-file changes or internal command polling.

Implementation details and guarantees live in [architecture](docs/architecture.md).
Run instructions live in [development](docs/development.md).

## Delivery milestones

1. **Finish the local core foundation.** Keep one source tree and lockfile, strict typing,
   regression tests, atomic migrations, clear capability limits, reproducible builds, and
   contributor documentation. Establish performance baselines and data-retention requirements
   before making scale claims.
2. **Validate the desktop experience.** The first Qt tray client, notification sink, and inbox
   exist. Validate OS notification behavior, shutdown, accessibility, and packaging in real
   graphical sessions. Add host navigation only through verified interfaces. Design delivery
   retries, deduplication, retention, and diagnostics around real failures before broader use.
3. **Certify live integrations.** Use separate disposable host test environments, with explicit
   versions and platforms. Verify native allow/ask/deny behavior, questions, retries, timeouts,
   workspace routing, session lifecycle, and clean configuration removal. Leave active user
   IDE installations alone during repository development.
4. **Run a private alpha.** Recruit five developers. Measure missed/duplicate alerts, false
   approvals, time blocked, return usage, and support effort. Any unauthorized approval blocks
   release. Complete client token provisioning, filesystem permissions, privacy controls,
   packaging, upgrade/backup, and install/remove checks.
5. **Prepare the public repository and pilot.** Review ownership/license and dependency notices,
   scan tracked files and history for secrets, activate a monitored private disclosure route,
   run the full CI matrix, publish supported capabilities, and document maintenance ownership.
   Then run a paid pilot with ten relevant users; pricing is an experiment, not a commitment.
6. **Expand from evidence.** Add hosts, platforms, remote connectors, or team features where
   users demonstrate demand. Model independence means policy does not call a specific model;
   it does not make every host controllable. Additional integrations require their own tests.

## Compatibility policy

Support claims belong to a host/version/platform/capability combination. Observation,
permission control, structured input, answer forwarding, and session control are separate
capabilities. A host without a documented integration remains unsupported. No universal IDE,
model, app, or remote-workspace compatibility claim is justified by this core.

## Next product deliverable

Windows x64 packaging and the Azure download site are delivered. The desktop includes
delivery diagnostics and explicit retry for failed alerts about pending requests. The development
tree adds guided local Cursor setup alongside Claude Code, explicit shell/MCP policy mapping,
and one transaction per desktop snapshot. These additions are not in the published v0.2.1 installer.
Next,
validate OS alerts in isolated graphical sessions and certify live adapter behavior with
documented versions. Retention controls, publisher signing, and a monitored private security
disclosure route remain outstanding. Keep the core usable through the CLI and local API.

Complete this local multi-host slice before adding more hosts: validate Cursor in a disposable
desktop workspace, check permission failures and clean disconnect, then publish a checked
installer. Evaluate Codex and Gemini CLI separately against their documented native interfaces;
VS Code is an editor host, so its agent extensions need individual capability checks. Remote/WSL,
cloud, mobile, and token optimization need separate designs and evidence. Reduced database work
and dropped tool outputs are local efficiency improvements, not model-token optimization.
