# Scrip product plan

Scrip helps developers manage interruptions across supported coding agents through explicit
permission policies, an input inbox, notifications, and action history. The initial customer
hypothesis is independent developers and small teams using multiple coding agents. Demand,
pricing, retention, and time savings remain unvalidated.

## Current foundation

The repository contains one Python product: typed events, deterministic policy decisions,
application orchestration separated from storage/HTTP, SQLite migrations and durable state,
an authenticated local service, CLI, and two documented-hook adapters. Adapter protocol and
local process tests exist; live host certification and desktop notifications do not.

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
2. **Build the desktop experience.** Prototype a tray client, native notification sink, and
   inbox. Open the originating host for answers where supported; do not imply local
   acknowledgement answers the agent. Design delivery retries, deduplication, retention,
   and diagnostics around real failures before broader deployment.
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

A desktop notification/inbox proof of concept, followed by live adapter certification in
isolated environments. Select the desktop toolkit after testing notification, tray, packaging,
and accessibility requirements. Keep the core usable through the CLI and local API.
