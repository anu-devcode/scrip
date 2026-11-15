"""Prepare an allowlisted public website and versioned terminal download bundle."""

import argparse
import hashlib
import json
import re
import shutil
import tarfile
import zipfile
from datetime import UTC, datetime
from email.parser import Parser
from pathlib import Path

from packaging.version import Version

from scrip_core import __version__

ROOT = Path(__file__).resolve().parents[1]
# The expanded website is retained under web/expanded and deliberately excluded.
WEB_FILES = ("index.html", "404.html", "styles.css", "robots.txt", "sitemap.xml")
ASSETS = {
    "wordmark.svg": "v2/scrip-logo-v2.svg",
    "icon.png": "v2/icons/scrip-icon-128.png",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_wheel(wheel: Path, version: str = __version__) -> None:
    expected = f"scrip_companion-{version}-py3-none-any.whl"
    if wheel.name != expected or wheel.is_symlink() or not wheel.is_file():
        raise ValueError(f"Expected a regular {expected} artifact")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError("Wheel must contain exactly one package metadata file")
        metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
        if metadata["Name"] != "scrip-companion" or metadata["Version"] != version:
            raise ValueError("Wheel metadata does not match the release version")
        for name in names:
            path = Path(name)
            if (
                not name.startswith(("scrip_core/", f"scrip_companion-{version}.dist-info/"))
                or ".." in path.parts
                or "\\" in name
                or path.name in ("api-token", ".env", "connection.json")
                or path.suffix in (".sqlite3", ".pyc", ".pem")
            ):
                raise ValueError(f"Unexpected/private wheel content: {name}")


def build_public_site(
    wheel: Path,
    destination: Path,
    commit: str,
    *,
    installer: Path,
    source: Path = ROOT,
    version: str = __version__,
) -> Path:
    Version(version)
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A full lowercase source commit SHA is required")
    validate_wheel(wheel, version)
    expected_installer = f"Scrip-Terminal-{version}-windows-x64-setup.exe"
    if installer.name != expected_installer or installer.is_symlink() or not installer.is_file():
        raise ValueError(f"Expected a regular {expected_installer} installer")
    with installer.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("Windows installer is not an executable")
    if destination.exists():
        raise ValueError("Output directory already exists; choose a new release staging directory")
    for path in [
        *(source / "web" / name for name in WEB_FILES),
        *(source / "assets/brand" / name for name in ASSETS.values()),
    ]:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"A regular release input is required: {path.name}")
    destination.mkdir(parents=True)
    downloads = destination / "downloads"
    assets = destination / "assets"
    downloads.mkdir()
    assets.mkdir()
    replacements = {
        "__SCRIP_VERSION__": version,
        "__SCRIP_WHEEL__": wheel.name,
        "__SCRIP_SHA256__": sha256(wheel),
        "__SCRIP_WHEEL_SIZE__": f"{wheel.stat().st_size / 1024:.0f} KB",
        "__SCRIP_INSTALLER__": installer.name,
        "__SCRIP_INSTALLER_SHA256__": sha256(installer),
        "__SCRIP_INSTALLER_SIZE__": f"{installer.stat().st_size / (1024 * 1024):.0f} MB",
    }
    for name in WEB_FILES:
        content = (source / "web" / name).read_text(encoding="utf-8")
        for token, value in replacements.items():
            content = content.replace(token, value)
        if "__SCRIP_" in content:
            raise ValueError(f"Unresolved release token in {name}")
        (destination / name).write_text(content, encoding="utf-8", newline="\n")
    for name, original in ASSETS.items():
        shutil.copyfile(source / "assets/brand" / original, assets / name)
    shutil.copyfile(wheel, downloads / wheel.name)
    shutil.copyfile(installer, downloads / installer.name)
    (downloads / "SHA256SUMS").write_text(
        f"{sha256(wheel)}  {wheel.name}\n{sha256(installer)}  {installer.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    metadata = {
        "version": version,
        "commit": commit,
        "prerelease": Version(version).is_prerelease,
        "built_at": datetime.now(UTC).isoformat(),
        "artifact": {
            "filename": wheel.name,
            "sha256": sha256(wheel),
            "bytes": wheel.stat().st_size,
        },
        "installer": {
            "platform": "windows-x64",
            "filename": installer.name,
            "sha256": sha256(installer),
            "bytes": installer.stat().st_size,
            "signed": False,
        },
    }
    (destination / "release.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    (destination / "health.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "service": "scrip-downloads",
                "version": version,
                "commit": commit,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    # The manifest covers every public file except itself; no repository tree is copied.
    files = {
        path.relative_to(destination).as_posix(): sha256(path)
        for path in sorted(destination.rglob("*"))
        if path.is_file()
    }
    manifest = {"version": version, "commit": commit, "files": files}
    (destination / "SITE-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def make_archive(site: Path, output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_relative_to(site):
        raise ValueError("Archive must be outside the public tree")
    with tarfile.open(output, "w:gz") as archive:
        for path in sorted(site.rglob("*")):
            if path.is_symlink():
                raise ValueError("Public site must not contain symlinks")
            if path.is_file():
                archive.add(path, arcname=path.relative_to(site).as_posix(), recursive=False)
    return sha256(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wheel",
        type=Path,
        default=Path("dist") / f"scrip_companion-{__version__}-py3-none-any.whl",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--tag")
    args = parser.parse_args()
    if args.tag is not None and args.tag != f"v{__version__}":
        parser.error("Release tag must match the package version exactly")
    site = build_public_site(
        args.wheel.resolve(),
        args.output.resolve(),
        args.commit,
        installer=args.installer.resolve(),
    )
    bundle = site.parent / f"scrip-web-{__version__}.tar.gz"
    digest = make_archive(site, bundle)
    (bundle.parent / "SHA256SUMS").write_text(
        f"{sha256(args.wheel)}  {args.wheel.name}\n"
        f"{sha256(args.installer)}  {args.installer.name}\n{digest}  {bundle.name}\n",
        encoding="utf-8",
    )
    print(json.dumps({"site": str(site), "bundle": str(bundle), "sha256": digest}))


if __name__ == "__main__":
    main()
