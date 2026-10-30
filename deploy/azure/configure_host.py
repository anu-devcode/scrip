"""Add one isolated Scrip static hostname to an audited Caddy installation."""

import argparse
import hashlib
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--expected-caddy-sha256", required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run through sudo on the audited server")
    if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", args.hostname):
        parser.error("A lowercase DNS hostname is required")
    original = Path("/etc/caddy/Caddyfile")
    dedicated = Path("/etc/caddy/scrip.caddy")
    if original.is_symlink() or dedicated.exists() or dedicated.is_symlink():
        raise ValueError("Refusing an existing dedicated configuration or symlink")
    before = original.read_bytes()
    if hashlib.sha256(before).hexdigest() != args.expected_caddy_sha256:
        raise ValueError("Caddy changed since its audit. Re-audit before configuring the host.")
    template = Path(__file__).with_name("Caddyfile.template").read_text()
    config = template.replace("__SCRIP_HOSTNAME__", args.hostname)
    backup = original.with_name(
        "Caddyfile.scrip-before-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    )
    backup.write_bytes(before)
    backup.chmod(original.stat().st_mode)
    try:
        dedicated.write_text(config)
        dedicated.chmod(0o644)
        # Preserve the complete existing configuration, byte for byte, as a prefix.
        original.write_bytes(before + b"\nimport /etc/caddy/scrip.caddy\n")
        subprocess.run(
            ["caddy", "validate", "--config", str(original), "--adapter", "caddyfile"],
            check=True,
        )
        subprocess.run(["systemctl", "reload", "caddy"], check=True)
    except BaseException:
        original.write_bytes(before)
        dedicated.unlink(missing_ok=True)
        subprocess.run(["systemctl", "reload", "caddy"], check=False)
        raise
    print(f"Added {args.hostname}; original configuration preserved in {backup}")


if __name__ == "__main__":
    main()
