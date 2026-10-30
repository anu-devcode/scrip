# Early-alpha deployment

Scrip has two deployment surfaces: a public static product/download site, and a local
application installed by a tester. The public site does not run the agent-control API.
The source repository remains private; publishing the Python wheel distributes its
application modules, not the complete private repository or any runtime state.

## First steps

1. Use the temporary HTTPS preview to download the developer alpha and try the fictional
   desktop demo. Begin with a fresh Python environment and an isolated workspace.
2. Choose the exact Scrip domain/subdomain when ready. Point its DNS A record at the
   existing VM's public IP. Keep Scrip on a separate hostname from Anbabi.
3. Add the dedicated Caddy static-site block after confirming DNS and the existing Anbabi
   configuration. The VM already has Caddy; do not install another public web server.
4. Start with a few invited testers. Establish a monitored support/disclosure contact,
   collect concrete failures, and certify live host/OS combinations before broad promotion.

No new Azure VM, database service, model API key, payment system, or mobile backend is needed
for this alpha. This does not make the broader shipping/mobile/token roadmap implemented.

## Release process

Version is defined once in `src/scrip_core/__init__.py`. For an alpha:

1. Update that version and add `docs/releases/VERSION.md`; update `uv.lock` with `uv sync`.
2. Merge a verified change into `main`.
3. Create/push a matching tag, such as `v0.1.0a1`.

The **Developer alpha release** workflow reuses the full Windows/Linux/macOS CI matrix,
builds the wheel/source distribution, renders a fictional-workspace screenshot, builds an
allowlisted static site, and publishes a GitHub prerelease. Existing release artifacts are
not overwritten. Use a new version for a changed release.

Artifacts: wheel, source archive, `scrip-web-VERSION.tar.gz`, and `SHA256SUMS`. The public
site contains the wheel, public guides, branding, release metadata, and checksums. It does
not copy the repository tree, `.env`, SSH keys, API tokens, or application databases.
GitHub release access follows repository visibility. Do not advertise a private GitHub
download URL as a public download; the static site's wheel URL is the public distribution.

For a local build (use a new output directory):

```sh
uv sync --locked --extra dev --extra desktop
uv build
uv run python -m devtools.desktop_preview
uv run python -m devtools.release --output dist/release/public --commit FULL_COMMIT_SHA --screenshot dist/desktop-preview.png --tag v0.1.0a1
```

`release.json` describes the exact wheel and source commit. `health.json` describes the
public distribution site only. Checksums provide artifact-integrity checks, not a claim of
signed provenance. Native installers and signed updates remain future work.

## Temporary hosted preview

The preview uses the same public files as the Azure bundle. Its non-secret Site identity is
recorded in `deploy/sites/hosting.json`. Provider credentials are not stored in the repository.
Build/copy the verified public tree into the isolated, ignored `dist/hosted-site/dist`
checkout, use the Sites source helper, then save/publish through the native Sites tools.
Preserve the existing project ID and its intended public audience on subsequent updates.

The temporary host is for public product information/downloads. It does not receive local
agent events or private Anbabi/Scrip state. A successful website deployment is not live host
certification, an installed desktop app, or a mobile release.

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

Render `deploy/azure/Caddyfile.template` with the exact validated hostname. Save the new
block separately, for example `/etc/caddy/scrip.caddy`. Back up the existing Caddyfile and
add only an import of that file; preserve Anbabi's entire existing block. Validate the
combined configuration with `caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile`
before a graceful `systemctl reload caddy`. Restore the saved configuration if validation
or reload fails. Do not restart Anbabi.

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
