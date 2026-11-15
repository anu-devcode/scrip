# Deployment and terminal releases

The production hostname is **https://scrip.anwardev.me**. DNS A record `scrip` points to
`4.222.233.58`, the existing Anbabi Azure VM. Resolve the hostname again before infrastructure
changes: cloud IPs can change. Scrip's site is a separate static virtual host in the existing
Caddy process. Private agent events stay on the user's computer, not on Azure.

## User installation

Download the Scrip Terminal Windows x64 setup and run it. It includes the Python runtime,
installs per user, and offers adding its directory to the user PATH. Restart the editor after
installation, review `scrip setup`, then explicitly install the project hook with
`scrip setup --apply`. Daily use is `scrip start`, `scrip status --project`, and `scrip stop`.
See the [project guide](integrations/antigravity-project.md) for scope and removal.
The installer is unsigned. Live Antigravity-version validation remains in progress.

## Build and release

Version is defined in `src/scrip_core/__init__.py`. Update it, `uv.lock`, and
`docs/releases/VERSION.md`, then merge a verified branch to main and push `vVERSION`.
The Terminal release workflow reruns the Windows/Linux/macOS Python test matrix, builds and
checks the Windows bundle on a Windows runner, compiles the per-user Inno Setup installer,
builds Python distributions and a public static bundle, and publishes immutable release
artifacts. Prerelease versions are marked as such; existing releases are never overwritten.

For a local Windows build:

```powershell
uv sync --locked --extra dev --extra desktop --extra build
uv run python -m devtools.build_terminal --compiler PATH_TO_ISCC.exe
uv build
uv run python -m devtools.release --output dist/release/public --commit FULL_COMMIT_SHA --installer dist/installers/Scrip-Terminal-VERSION-windows-x64-setup.exe --tag vVERSION
```

Build requires Windows x64, Inno Setup, and the locked build extra. The pinned compiler
installer is downloaded from its publisher and its Authenticode signature is checked in CI.
This signature is for the compiler; it does not sign the Scrip installer. Build smoke checks
run only in a temporary directory and never install host settings or seed the normal app.

The release contains setup EXE, wheel, source archive, website archive, and `SHA256SUMS`.
Only explicitly allowlisted website files, branding, wheel, terminal installer, and release metadata are public. Tokens, databases,
SSH keys, repository metadata, private files, and test fixtures are not copied. `release.json`
records source commit, installer platform, signature status, artifact sizes, and hashes.
Checksums verify integrity; they are not signed provenance.

The repository is public and MIT licensed at https://github.com/anu-devcode/scrip.
The public site is a minimal download and command-reference page. The previous expanded
website is preserved under `web/expanded/` and excluded from the public bundle, together
with its animation, analytics scripts, and additional guidance pages. The release builder's
explicit `WEB_FILES` and `ASSETS` lists select the published content. Restore the expanded
sources and their allowlist deliberately when those product pages are needed again.

Website-only changes can reuse the verified installer and wheel from the existing GitHub
release. Build with the new website source commit and publish to a new immutable release
directory. The tool version and existing download bytes stay tied to the original release.
Do not replace assets in an existing GitHub release.

## Capacity and remaining release gates

The audited VM has roughly 846 MiB RAM, 2 GiB swap, and 55 GiB free disk. Scrip adds static
file serving to the existing Caddy process, not another always-on backend. No VM upgrade,
new database, model API key, or payment service is required for this distribution design.
Monitor actual memory, egress, disk use, and download traffic before choosing more capacity.

Signing the Windows installer and future updates requires a publisher-signing identity.
Live host-version and native OS-notification certification remain outstanding. The shipped
terminal installer targets Windows x64 and Antigravity command hooks; other hosts/platforms, mobile,
remote control, shipping workflows, and token optimization are separate product work.

## Shared Azure VM

The operator supplied `anbabi.southafricanorth.cloudapp.azure.com`, SSH user `azureuser`,
and an existing key named `anbabi_key.pem`. A read-only audit confirmed that Anbabi and Caddy
were active. Scrip must not change `/opt/anbabi`, `/var/lib/anbabi`, its backup jobs, port
4177, or its systemd service. The new site uses `/srv/scrip-web` and no additional
always-on application process. Recheck operational state before each infrastructure change.

The cloud IP and resource availability can change; resolve the VM's hostname before setting
DNS. Reuse the existing verified SSH host identity. Do not disable host-key checking or put
the Anbabi administrator private key into GitHub Actions.

### Prepare the dedicated publisher

Copy `deploy/azure/prepare.sh` and `publish.py` together into a new temporary directory on
the VM over the existing operator SSH connection, inspect them, then run `sudo bash prepare.sh`.
The script creates a dedicated `scrip-deploy` account, root-owned publishing code, and a
marked `/srv/scrip-web` directory. It refuses unrelated existing paths/accounts and does not
modify or reload Caddy. No Docker service or Python application daemon is installed.

The publisher accepts only verified static archives: regular safe paths, exact file sets,
SHA-256 hashes, bounded sizes, and a valid release manifest. It stages into a new directory,
verifies all content, then atomically replaces `current`. Old releases remain available.

### Add the hostname once DNS is ready

Use `deploy/azure/configure_host.py` alongside `Caddyfile.template` on the VM. Provide
`--hostname scrip.anwardev.me --expected-caddy-sha256 AUDITED_HASH` through sudo. The
one-time script refuses an existing dedicated file or a changed Caddyfile, saves a backup,
preserves the entire original configuration as a byte-for-byte prefix, and adds only an
import of `/etc/caddy/scrip.caddy`. It validates before graceful reload and restores the
original file if validation/reload fails. Do not restart Anbabi.

The existing firewall must allow HTTP/HTTPS for Caddy's certificate challenge. Confirm the
new hostname resolves to this VM and check any AAAA record too. Caddy can then provision
HTTPS for the new hostname. Do not expose Scrip ports 8765/18765 to the internet.

### Publish an already-built bundle

Transfer the release archive to a new temporary path on the VM and verify its checksum.
Place it in `/srv/scrip-web/incoming` with `scrip-deploy` ownership, then invoke:

```sh
sudo -u scrip-deploy python3 /usr/local/lib/scrip-web/publish.py install /srv/scrip-web/incoming/scrip-web-VERSION.tar.gz --sha256 EXPECTED_SHA256
```

Caddy reads `current`; normal version updates do not require its reload. Verify HTTPS,
`health.json`, `release.json`, the download checksum, and Anbabi's existing public page.

To roll back the website, use an installed identifier shown under `releases/`:

```sh
sudo -u scrip-deploy python3 /usr/local/lib/scrip-web/publish.py rollback VERSION-COMMIT12
```

Rollback verifies old files before switching. It does not downgrade a tester's installed
application or database. There is no automatic old-release pruning; inspect disk use and
retain at least a known working release. Anbabi backups are outside Scrip deployment.

## Optional GitHub-to-Azure publication

The manual **Publish website to Azure VM** workflow is deliberately inactive until setup
is complete. Create a new Scrip-only deployment key; do not reuse the operator key. Add its
public key to the dedicated user's `authorized_keys` with this forced command:

```text
restrict,command="/usr/bin/python3 /usr/local/lib/scrip-web/publish.py receive" ssh-ed25519 PUBLIC_KEY_HERE
```

The receiver accepts only `install VERSION SHA256` and an archive on stdin. It does not
evaluate shell commands, offer SFTP, change Caddy, or access Anbabi paths. Keep authorized
key ownership/permissions appropriate for OpenSSH. Verify the server host key through the
operator's existing trusted connection; do not trust a network key scan by itself.

Set these GitHub values after the hostname and restricted key are ready:

| Scope | Name | Value |
| --- | --- | --- |
| Repository variable | `SCRIP_DEPLOY_ENABLED` | `true` only after setup/verification |
| `azure-production` variable | `SCRIP_DEPLOY_HOST` | Verified VM SSH hostname |
| `azure-production` variable | `SCRIP_SITE_URL` | New Scrip HTTPS origin |
| `azure-production` secret | `SCRIP_DEPLOY_KEY` | New restricted private key |
| `azure-production` secret | `SCRIP_KNOWN_HOSTS` | Verified host-key records |

Run the workflow with an existing release tag. It downloads the published bundle, checks
its checksum, streams it over pinned SSH to the restricted publisher, and verifies the
public version afterward. It cannot bootstrap the server or change other services.

GitHub-hosted runners must be able to reach SSH. If the Azure NSG permits only the operator's
IP, retain that restriction and use manual publication or a deliberately configured trusted
runner/network path. This workflow does not broaden SSH access or alter the NSG. Secrets
and automated Azure publishing are not configured merely by committing the workflow.

## References

- [GitHub reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
- [Caddy automatic HTTPS requirements](https://caddyserver.com/docs/automatic-https)
- [Caddy static file server](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [Azure VM connection guidance](https://learn.microsoft.com/en-us/azure/virtual-machines/linux-vm-connect)
