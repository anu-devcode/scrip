# Desktop inbox

The optional Qt desktop prototype displays pending questions and permission requests,
full request details, recent sessions, pause/resume, and tray alerts. It shares the same
local database as the CLI/service. It does not approve individual requests, forward answers,
execute agent tools, install hooks, or change an IDE.

## Try fictional requests

On Python 3.12–3.15 in a graphical desktop session:

```sh
uv sync --locked --extra desktop
uv run --extra desktop scrip desktop --demo
```

Demo mode uses temporary state, shows one question and one permission request, and removes
that state after exiting. It does not start an HTTP server or connect to an agent. Use Quit
to exit; on desktops with a tray, closing the window keeps it running there.

## Use your local service state

Initialize a deliberate development directory and start the service:

```sh
uv run scrip --data-dir .scrip-dev init --port 18765
uv run scrip --data-dir .scrip-dev serve --port 18765
```

Then open the desktop in another terminal:

```sh
uv run --extra desktop scrip --data-dir .scrip-dev desktop
```

The service and desktop must use the same data directory. Hook configuration is still an
explicit, separate integration step; see [development](development.md#adapter-configuration).
The desktop does not start or stop that service. It can read existing state while the
service is stopped, but hooks cannot submit new events until the service is running.

Select an inbox row to read the full question/options or exact tool arguments. Respond in
the originating agent. **Dismiss locally** acknowledges only the local inbox record and
cancels its undelivered alert; it never answers or grants execution. **Pause auto approvals**
uses the existing global pause policy. It does not stop a tool already running in the host.

## Notification behavior

The desktop polls local state every two seconds on a background thread and claims at most
one alert per refresh. The GUI thread submits a generic title to Qt's system tray API; tool
arguments and question text are not sent to the OS notification. Click an alert or the tray
icon to open the inbox. The tray menu and window both have an explicit Quit action.

If the desktop has no tray/message capability, the inbox remains usable and notification
records stay queued. Shutdown or a timed-out GUI handoff releases the lease for a later
attempt. Cancelled handoffs cannot subsequently show from the GUI queue. Other unexpected
sink failures remain terminal `failed` records under the core's current delivery policy.

`delivered` means accepted by the Qt tray API. It does not prove the OS displayed the alert
or the user read it. Desktop settings, focus modes, Linux tray support, and OS permissions
can affect display. An alert already submitted can outlive a dismissal. Crash recovery and
lease expiry allow duplicates; exactly-once delivery and persistent OS deduplication are
not provided. Do not run the console drain if the desktop should consume those same alerts.

Qt's supported tray behavior varies by platform; see the
[Qt system tray API](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html).
Tests currently cover offscreen widgets and a fake native tray, not actual OS alert display
or live host certification. Native installer, autostart, and signed updates are not provided.

## Headless and remote development

Codespaces and CI can build the package and run the offscreen desktop tests. They do not
provide this native GUI in a browser. Run it in a local or remote graphical desktop session.
The current client reads local state, not a remote agent connector.

For an offscreen image using temporary fictional data:

```sh
uv sync --locked --extra dev --extra desktop
uv run --extra desktop python -m devtools.desktop_preview
```

This writes `dist/desktop-preview.png`, which is ignored by Git. No native notification is
displayed. Full development checks require both the `dev` and `desktop` extras; tests skip
the GUI cases when Qt is intentionally absent from a core-only installation.

## Dependencies

The desktop uses the minimal official `PySide6-Essentials` wheel; Qt is not required by the
headless core. Scrip's source license remains MIT. Qt/PySide carries separate upstream
license terms; see the [package metadata](https://pypi.org/project/PySide6-Essentials/).
Review dependency notices when preparing an installer or redistributing bundled libraries.
