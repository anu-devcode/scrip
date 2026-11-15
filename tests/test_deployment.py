import io
import json
import subprocess
import tarfile

import pytest

from devtools.deployment import verify_bundle, verify_main_commit


@pytest.fixture
def release_repository(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=repository, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "--initial-branch=main")
    git("config", "user.name", "Scrip test")
    git("config", "user.email", "test@example.invalid")
    (repository / "source.txt").write_text("main")
    git("add", ".")
    git("commit", "-m", "Main release source")
    main = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/main", main)
    git("tag", "v0.4.0")
    git("switch", "-c", "feat/unmerged")
    (repository / "source.txt").write_text("unmerged")
    git("commit", "-am", "Unmerged source")
    branch = git("rev-parse", "HEAD")
    git("tag", "v0.5.0")
    return repository, main, branch


def bundle(tmp_path, commit, version="0.4.0"):
    archive = tmp_path / "site.tar.gz"
    content = json.dumps({"version": version, "commit": commit, "files": {}}).encode()
    with tarfile.open(archive, "w:gz") as package:
        entry = tarfile.TarInfo("SITE-MANIFEST.json")
        entry.size = len(content)
        package.addfile(entry, io.BytesIO(content))
    return archive


def test_main_release_bundle_is_accepted(tmp_path, release_repository):
    repository, main, _ = release_repository
    archive = bundle(tmp_path, main)
    assert verify_bundle(archive, "v0.4.0", "refs/heads/main", repository=repository) == main


@pytest.mark.parametrize("ref", ["refs/heads/feat/change", "refs/tags/v0.4.0", ""])
def test_deployment_requires_main_workflow_ref(tmp_path, release_repository, ref):
    repository, main, _ = release_repository
    with pytest.raises(ValueError, match="run from main"):
        verify_bundle(bundle(tmp_path, main), "v0.4.0", ref, repository=repository)


def test_release_and_bundle_reject_unmerged_commits(tmp_path, release_repository):
    repository, _, branch = release_repository
    with pytest.raises(ValueError, match="already be merged"):
        verify_main_commit(branch, repository=repository)
    with pytest.raises(ValueError, match="already be merged"):
        verify_bundle(
            bundle(tmp_path, branch, "0.5.0"), "v0.5.0", "refs/heads/main", repository=repository
        )


def test_bundle_version_and_source_must_match_tag(tmp_path, release_repository):
    repository, main, _ = release_repository
    with pytest.raises(ValueError, match="version must match"):
        verify_bundle(bundle(tmp_path, main), "v0.5.0", "refs/heads/main", repository=repository)
    with pytest.raises(ValueError, match="source commit must match"):
        verify_bundle(
            bundle(tmp_path, main, "0.5.0"), "v0.5.0", "refs/heads/main", repository=repository
        )


def test_duplicate_manifest_is_rejected(tmp_path, release_repository):
    repository, main, _ = release_repository
    archive = bundle(tmp_path, main)
    with tarfile.open(archive, "w:gz") as package:
        package.addfile(tarfile.TarInfo("SITE-MANIFEST.json"), io.BytesIO())
        package.addfile(tarfile.TarInfo("SITE-MANIFEST.json"), io.BytesIO())
    with pytest.raises(ValueError, match="single bounded"):
        verify_bundle(archive, "v0.4.0", "refs/heads/main", repository=repository)
