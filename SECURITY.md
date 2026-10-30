# Security

Scrip distributes an early Windows desktop release at https://scrip.anwardev.me. Installers
are currently unsigned. The download site is public; the companion service and private
agent activity run locally. A monitored public security response service has not been
established, and live host-version certification remains outstanding.

## Reporting

Before public release, maintainers must activate a monitored private disclosure channel and
replace this paragraph with its verified contact details. Until then, report potential issues
privately to the maintainer through the existing project communication channel. Do not post
API tokens, private tool arguments, database contents, or exploitable permission details in
public issues. No response-time commitment is currently offered.

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
