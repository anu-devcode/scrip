import hashlib
import io
import json
import os
import tarfile

import pytest

from deploy.azure.publish import activate, digest, initialize, install, receive


def bundle(tmp_path, *, version="0.1.0a1", commit="a" * 40, changes=None, extras=None):
    files = {
        "index.html": b"public page",
        "health.json": b"{}",
        "release.json": b"{}",
        "downloads/example.whl": b"public package",
    }
    manifest = {
        "version": version,
        "commit": commit,
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
    }
    files["SITE-MANIFEST.json"] = json.dumps(manifest).encode()
    files.update(changes or {})
    archive = tmp_path / f"{version}-{commit[:12]}.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            output.addfile(info, io.BytesIO(content))
        for info in extras or []:
            output.addfile(info, io.BytesIO(b"x") if info.isfile() else None)
    return archive


@pytest.fixture
def distribution(tmp_path):
    root = tmp_path / "scrip-web"
    initialize(root)
    return root


def test_existing_other_product_directory_is_never_adopted(tmp_path):
    other = tmp_path / "anbabi"
    other.mkdir()
    private = other / "accounts.db"
    private.write_bytes(b"private")
    with pytest.raises(ValueError, match="another application"):
        initialize(other)
    assert list(other.iterdir()) == [private]
    assert private.read_bytes() == b"private"


def test_bad_transport_checksum_leaves_live_path_unchanged(distribution, tmp_path):
    archive = bundle(tmp_path)
    with pytest.raises(ValueError, match="checksum"):
        install(archive, distribution, "0" * 64)
    assert not (distribution / "current").exists()
    assert list((distribution / "releases").iterdir()) == []


@pytest.mark.parametrize("name", ["../outside", "/absolute", "assets/../../escape", ".ssh/key"])
def test_archive_path_traversal_is_rejected(distribution, tmp_path, name):
    entry = tarfile.TarInfo(name)
    entry.size = 1
    archive = bundle(tmp_path, extras=[entry])
    with pytest.raises(ValueError, match="safe regular"):
        install(archive, distribution, digest(archive))
    assert not (tmp_path / "outside").exists()
    assert list((distribution / "releases").iterdir()) == []


def test_symlink_archive_entries_are_rejected(distribution, tmp_path):
    entry = tarfile.TarInfo("assets/link")
    entry.type = tarfile.SYMTYPE
    entry.linkname = "/var/lib/anbabi/accounts.db"
    archive = bundle(tmp_path, extras=[entry])
    with pytest.raises(ValueError, match="safe regular"):
        install(archive, distribution, digest(archive))


def test_unlisted_and_modified_content_do_not_become_live(distribution, tmp_path):
    archive = bundle(tmp_path, changes={"unexpected.txt": b"unlisted"})
    with pytest.raises(ValueError, match="Unexpected or missing"):
        install(archive, distribution, digest(archive))
    archive = bundle(tmp_path, changes={"index.html": b"tampered"})
    with pytest.raises(ValueError, match="checksum"):
        install(archive, distribution, digest(archive))
    assert not (distribution / "current").exists()
    assert list((distribution / "releases").iterdir()) == []


@pytest.mark.skipif(os.name == "nt", reason="Atomic deployment activation targets the Linux VM")
def test_publish_retry_and_rollback_are_atomic(distribution, tmp_path):
    first = bundle(tmp_path)
    original = install(first, distribution, digest(first))
    assert install(first, distribution, digest(first)) == original
    second = bundle(tmp_path, version="0.1.0a2", commit="b" * 40)
    latest = install(second, distribution, digest(second))
    assert (distribution / "current").resolve().name == latest
    activate(distribution, original)
    assert (distribution / "current").resolve().name == original
    assert len(list((distribution / "releases").iterdir())) == 2


@pytest.mark.skipif(os.name == "nt", reason="Atomic deployment activation targets the Linux VM")
def test_failed_update_preserves_previous_live_release(distribution, tmp_path):
    first = bundle(tmp_path)
    original = install(first, distribution, digest(first))
    second = bundle(tmp_path, version="0.1.0a2", commit="b" * 40, changes={"index.html": b"bad"})
    with pytest.raises(ValueError, match="checksum"):
        install(second, distribution, digest(second))
    assert (distribution / "current").resolve().name == original


def test_requested_version_cannot_be_swapped(distribution, tmp_path):
    archive = bundle(tmp_path)
    with pytest.raises(ValueError, match="Requested version"):
        install(archive, distribution, digest(archive), version="0.1.0a9")


@pytest.mark.parametrize(
    "command",
    [
        "bash -c whoami",
        "rollback 0.1.0a1-aaaaaaaaaaaa",
        "install ../private " + "a" * 64,
        "install 0.1.0a1 bad-checksum",
        "install 0.1.0a1 " + "a" * 64 + "; echo unexpected",
    ],
)
def test_restricted_receiver_refuses_other_commands(distribution, monkeypatch, command):
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", command)
    with pytest.raises(ValueError):
        receive(distribution)
    assert list((distribution / "incoming").iterdir()) == []
    assert not (distribution / "current").exists()
