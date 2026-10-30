#!/usr/bin/env bash
# Prepare only Scrip's static publishing directories. Does not reload or modify Caddy/Anbabi.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  printf 'Run this preparation script with sudo.\n' >&2
  exit 1
fi
root=/srv/scrip-web
tools=/usr/local/lib/scrip-web
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -L "$root" || -L "$tools" ]]; then
  printf 'Refusing symlink deployment/tool roots.\n' >&2
  exit 1
fi
if [[ -e "$root" && ! -f "$root/.scrip-public-distribution" ]]; then
  printf 'Refusing an existing unmarked deployment directory.\n' >&2
  exit 1
fi
if [[ -e "$tools" && ! -f "$tools/.scrip-publisher" ]]; then
  printf 'Refusing an existing unmarked tool directory.\n' >&2
  exit 1
fi
if id scrip-deploy >/dev/null 2>&1; then
  if [[ ! -f "$tools/.scrip-publisher" ]]; then
    printf 'Refusing to adopt an unrelated existing scrip-deploy account.\n' >&2
    exit 1
  fi
else
  useradd --system --user-group --create-home --home-dir /var/lib/scrip-deploy --shell /bin/sh scrip-deploy
fi
install -d -m 755 "$tools"
printf '1\n' > "$tools/.scrip-publisher"
install -m 755 "$source_dir/publish.py" "$tools/publish.py"
install -d -m 755 -o scrip-deploy -g scrip-deploy "$root"
sudo -u scrip-deploy python3 "$tools/publish.py" init
printf 'Prepared %s. Caddy and Anbabi have not been changed.\n' "$root"
