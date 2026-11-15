# Security

Scrip distributes an early Windows terminal release at https://scrip.anwardev.me. Installers
are currently unsigned. The download site is public; the companion service and private
agent activity run locally. A monitored public security response service has not been
established, and live host-version certification remains outstanding.

## Reporting

A dedicated monitored private disclosure inbox is still outstanding. Existing project
collaborators can contact the maintainer through their established private channel. Keep
API tokens, command arguments, database contents, and exploitable permission details private.
No response-time commitment is currently offered.

## Terminal authorization

The 0.4.0 terminal workflow uses local SQLite state directly. `scrip start` authorizes every
shell command in the first valid conversation to bind, within the configured project, for
up to 24 hours. This includes deletion, writes, network access, and publishing. The working
directory is not an OS sandbox. Native Ask/Deny rules and explicit Scrip deny rules apply.
Other conversations do not inherit the grant. `scrip stop` revokes future Scrip approvals.
Questions and other tool types remain outside command authorization. Exact-command mode
is available with `scrip start --exact`. Invalid callbacks request native review.

Only `scrip setup --apply` installs the named documented project hook after review. Start
and stop modify private authorization state. Local state can contain commands and workspace
paths and is accessible to the same OS user. Uninstall preserves that state and project hooks.
Remove the Scrip hook before uninstalling. The public website's security page describes the
shipped terminal scope. The following boundaries also cover optional source components.

## Current boundaries

The service binds to loopback and requires a local bearer token. Tokens and local state must
remain private. State includes command arguments and questions; it is not encrypted by Scrip.
The service is not intended for remote exposure or untrusted multi-user access. Processes
running as the same OS user can access local state and management commands.

Rules are explicit local configuration, not a model safety verdict. Approvals use exact
arguments and event replay protection; the host owns execution. Questions are never answered
automatically. Hook adapters use documented interfaces and default to observation.

The desktop provisions a local API token automatically. Hardened platform filesystem
permissions, retention/deletion controls, publisher signing, signed updates, live host
certification, and a release security review remain outstanding. Back up private state before
upgrades; forward database migrations do not provide downgrade support.

Notification failures retain only an exception type, not exception messages. Manual alert
retry requires a still-pending question or permission request, never grants permission, and
does not replay a host operation. OS notification submission is not proof of display or reading.
