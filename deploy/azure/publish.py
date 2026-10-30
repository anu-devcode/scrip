#!/usr/bin/env python3
"""Publish verified static Scrip bundles atomically. No application API or Anbabi access."""

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

ROOT_MARKER = ".scrip-public-distribution"
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_CONTENT_BYTES = 200 * 1024 * 1024
VERSION = r"[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?"
RELEASE_ID = re.compile(rf"{VERSION}-[0-9a-f]{{12}}")


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(
        re.fullmatch(r"[A-Za-z0-9_./-]+", name)
        and not path.is_absolute()
        and ".." not in path.parts
        and not any(part.startswith(".") for part in path.parts)
        and path.as_posix() == name
    )


def initialize(root: Path) -> None:
    if not root.is_absolute() or root == Path(root.anchor) or root.is_symlink():
        raise ValueError("An absolute, dedicated, non-symlink deployment root is required")
    marker = root / ROOT_MARKER
    if root.exists() and not marker.exists() and any(root.iterdir()):
        raise ValueError("Refusing to use an existing directory belonging to another application")
    root.mkdir(parents=True, exist_ok=True)
    if marker.exists() and (marker.is_symlink() or marker.read_text() != "1\n"):
        raise ValueError("Unknown deployment root marker")
    marker.write_text("1\n")
    for name in ("incoming", "releases"):
        directory = root / name
        if directory.is_symlink():
            raise ValueError("Deployment directories must not be symlinks")
        directory.mkdir(exist_ok=True)


def require_root(root: Path) -> None:
    if root.is_symlink() or not root.is_absolute():
        raise ValueError("Invalid deployment root")
    marker = root / ROOT_MARKER
    if not marker.is_file() or marker.is_symlink() or marker.read_text() != "1\n":
        raise ValueError("Initialize a dedicated Scrip distribution root first")
    for name in ("incoming", "releases"):
        if (root / name).is_symlink() or not (root / name).is_dir():
            raise ValueError("Invalid deployment directory")


def check_manifest(manifest: object) -> dict:
    if not isinstance(manifest, dict) or set(manifest) != {"version", "commit", "files"}:
        raise ValueError("Invalid site manifest")
    if not isinstance(manifest["version"], str) or not re.fullmatch(VERSION, manifest["version"]):
        raise ValueError("Invalid manifest version")
    if not isinstance(manifest["commit"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", manifest["commit"]
    ):
        raise ValueError("Invalid source commit")
    files = manifest["files"]
    if (
        not isinstance(files, dict)
        or not {"index.html", "health.json", "release.json"} <= files.keys()
    ):
        raise ValueError("Incomplete site manifest")
    for name, checksum in files.items():
        if (
            not isinstance(name, str)
            or not safe_name(name)
            or name == "SITE-MANIFEST.json"
            or not isinstance(checksum, str)
            or not re.fullmatch(r"[0-9a-f]{64}", checksum)
        ):
            raise ValueError("Invalid manifest file entry")
    return manifest


def verify_tree(directory: Path) -> dict:
    manifest_path = directory / "SITE-MANIFEST.json"
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 1024 * 1024:
        raise ValueError("Invalid installed manifest")
    manifest = check_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
    paths = list(directory.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("Release files must not be symlinks")
    actual = {path.relative_to(directory).as_posix() for path in paths if path.is_file()}
    if actual != set(manifest["files"]) | {"SITE-MANIFEST.json"}:
        raise ValueError("Release file set does not match its manifest")
    for name, checksum in manifest["files"].items():
        if digest(directory / name) != checksum:
            raise ValueError(f"Release checksum mismatch: {name}")
    return manifest


def activate(root: Path, release_id: str) -> None:
    require_root(root)
    if not RELEASE_ID.fullmatch(release_id):
        raise ValueError("Invalid release identifier")
    release = root / "releases" / release_id
    if release.is_symlink() or not release.is_dir():
        raise ValueError("Release is not an installed directory")
    manifest = verify_tree(release)
    if release_id != f"{manifest['version']}-{manifest['commit'][:12]}":
        raise ValueError("Installed identity does not match the release directory")
    current = root / "current"
    if current.is_symlink():
        if current.resolve().parent != (root / "releases").resolve():
            raise ValueError("Current link belongs to another location")
    elif current.exists():
        raise ValueError("Refusing to replace a non-symlink current directory")
    temporary = root / f".next-{uuid4().hex}"
    try:
        temporary.symlink_to(Path("releases") / release_id, target_is_directory=True)
        os.replace(temporary, current)
    finally:
        temporary.unlink(missing_ok=True)


def install(archive_path: Path, root: Path, checksum: str, *, version: str | None = None) -> str:
    require_root(root)
    if archive_path.is_symlink() or archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Invalid/oversized release archive")
    if not re.fullmatch(r"[0-9a-f]{64}", checksum) or digest(archive_path) != checksum:
        raise ValueError("Archive checksum mismatch")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > 1000 or sum(item.size for item in members) > MAX_CONTENT_BYTES:
            raise ValueError("Release archive exceeds limits")
        names = [item.name for item in members]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate archive paths")
        if any(not item.isfile() or not safe_name(item.name) for item in members):
            raise ValueError("Only safe regular archive files are accepted")
        if "SITE-MANIFEST.json" not in names:
            raise ValueError("Missing site manifest")
        member = archive.getmember("SITE-MANIFEST.json")
        if member.size > 1024 * 1024:
            raise ValueError("Site manifest is too large")
        stream = archive.extractfile(member)
        if stream is None:
            raise ValueError("Unreadable site manifest")
        manifest = check_manifest(json.loads(stream.read()))
        if set(names) != set(manifest["files"]) | {"SITE-MANIFEST.json"}:
            raise ValueError("Unexpected or missing files in the release archive")
        if version is not None and manifest["version"] != version:
            raise ValueError("Requested version does not match the archive")
        release_id = f"{manifest['version']}-{manifest['commit'][:12]}"
        target = root / "releases" / release_id
        if target.exists() or target.is_symlink():
            if target.is_symlink() or verify_tree(target) != manifest:
                raise ValueError("An immutable release already exists with different content")
        else:
            with tempfile.TemporaryDirectory(prefix=".staging-", dir=root / "releases") as staging:
                destination = Path(staging)
                for item in members:
                    output = destination / item.name
                    output.parent.mkdir(parents=True, exist_ok=True)
                    source = archive.extractfile(item)
                    if source is None:
                        raise ValueError("Unreadable archive entry")
                    with source, output.open("xb") as file:
                        shutil.copyfileobj(source, file, 1024 * 1024)
                    output.chmod(0o644)
                verify_tree(destination)
                destination.chmod(0o755)
                os.replace(destination, target)
    activate(root, release_id)
    return release_id


def receive(root: Path) -> None:
    """Entry point for an OpenSSH forced-command key; never evaluates a shell command."""
    require_root(root)
    command = shlex.split(os.environ.get("SSH_ORIGINAL_COMMAND", ""))
    if len(command) != 3 or command[0] != "install" or not re.fullmatch(VERSION, command[1]):
        raise ValueError("Only install VERSION SHA256 is accepted by this deployment key")
    checksum = command[2]
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("Invalid checksum")
    descriptor, name = tempfile.mkstemp(prefix="upload-", suffix=".tar.gz", dir=root / "incoming")
    uploaded = Path(name)
    try:
        total = 0
        with os.fdopen(descriptor, "wb") as output:
            while block := sys.stdin.buffer.read(1024 * 1024):
                total += len(block)
                if total > MAX_ARCHIVE_BYTES:
                    raise ValueError("Upload exceeds size limit")
                output.write(block)
        release_id = install(uploaded, root, checksum, version=command[1])
        print(json.dumps({"published": release_id}))
    finally:
        uploaded.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/srv/scrip-web"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    commands.add_parser("receive")
    publication = commands.add_parser("install")
    publication.add_argument("archive", type=Path)
    publication.add_argument("--sha256", required=True)
    rollback = commands.add_parser("rollback")
    rollback.add_argument("release_id")
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize(args.root)
        elif args.command == "install":
            print(json.dumps({"published": install(args.archive, args.root, args.sha256)}))
        elif args.command == "rollback":
            activate(args.root, args.release_id)
        else:
            receive(args.root)
    except (ValueError, OSError, tarfile.TarError, json.JSONDecodeError) as error:
        print(f"Scrip publish failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
