"""Validate main-branch provenance before releasing or deploying artifacts."""

import argparse
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify_main_commit(commit: str, *, repository: Path = ROOT) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A full source commit SHA is required")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "refs/remotes/origin/main"],
        cwd=repository,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("The source commit must already be merged into origin/main")


def verify_bundle(archive: Path, release_tag: str, ref: str, *, repository: Path = ROOT) -> str:
    if ref != "refs/heads/main":
        raise ValueError("Production deployment must run from main")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?", release_tag):
        raise ValueError("Invalid release tag")
    with tarfile.open(archive, "r:gz") as package:
        manifests = [item for item in package.getmembers() if item.name == "SITE-MANIFEST.json"]
        if len(manifests) != 1 or not manifests[0].isfile() or manifests[0].size > 1024 * 1024:
            raise ValueError("A single bounded release manifest is required")
        stream = package.extractfile(manifests[0])
        if stream is None:
            raise ValueError("The release manifest is unreadable")
        with stream:
            manifest = json.load(stream)
    if not isinstance(manifest, dict) or manifest.get("version") != release_tag[1:]:
        raise ValueError("Bundle version must match the release tag")
    commit = manifest.get("commit")
    if not isinstance(commit, str):
        raise ValueError("The release manifest must identify its source commit")
    verify_main_commit(commit, repository=repository)
    tagged = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/tags/{release_tag}^{{commit}}"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if tagged != commit:
        raise ValueError("Bundle source commit must match the release tag")
    return commit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--tag")
    args = parser.parse_args()
    if args.commit and not args.archive and not args.tag:
        verify_main_commit(args.commit)
    elif args.archive and args.tag and not args.commit:
        commit = verify_bundle(args.archive, args.tag, os.environ.get("GITHUB_REF", ""))
        with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as output:
            output.write(f"SCRIP_DEPLOY_COMMIT={commit}\n")
    else:
        parser.error("Use --commit, or --archive together with --tag")


if __name__ == "__main__":
    main()
