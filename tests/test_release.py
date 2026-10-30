import hashlib
import json
import zipfile

import pytest

from devtools.release import ASSETS, WEB_FILES, build_public_site, make_archive, validate_wheel
from scrip_core import __version__


@pytest.fixture
def release_inputs(tmp_path):
    source = tmp_path / "source"
    (source / "web").mkdir(parents=True)
    brand = source / "assets/brand"
    brand.mkdir(parents=True)
    for name in WEB_FILES:
        (source / "web" / name).write_text("version __SCRIP_VERSION__ __SCRIP_WHEEL__")
    for name in ASSETS.values():
        path = brand / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test-asset")
    (source / "web" / ".env").write_text("SHOULD_NOT_BE_PUBLISHED=private")
    (source / "private.sqlite3").write_bytes(b"private state")
    screenshot = tmp_path / "inbox.png"
    screenshot.write_bytes(b"public-example")
    wheel = tmp_path / f"scrip_companion-{__version__}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as package:
        package.writestr("scrip_core/__init__.py", "")
        package.writestr(
            f"scrip_companion-{__version__}.dist-info/METADATA",
            f"Name: scrip-companion\nVersion: {__version__}\n",
        )
    installer = tmp_path / f"Scrip-{__version__}-windows-x64-setup.exe"
    installer.write_bytes(b"MZ" + b"test executable")
    return source, wheel, screenshot, installer


def test_public_bundle_is_allowlisted_and_uses_exact_wheel_hash(tmp_path, release_inputs):
    source, wheel, screenshot, installer = release_inputs
    public = build_public_site(
        wheel, tmp_path / "public", "a" * 40, screenshot, installer=installer, source=source
    )
    metadata = json.loads((public / "release.json").read_text())
    assert metadata["artifact"]["sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert metadata["version"] == __version__
    assert metadata["installer"]["sha256"] == hashlib.sha256(installer.read_bytes()).hexdigest()
    assert metadata["installer"]["signed"] is False
    assert not (public / ".env").exists()
    assert not (public / "private.sqlite3").exists()
    assert "__SCRIP_" not in (public / "index.html").read_text()
    assert (public / "downloads" / wheel.name).read_bytes() == wheel.read_bytes()
    archive = tmp_path / "web.tar.gz"
    assert len(make_archive(public, archive)) == 64


def test_release_output_never_overwrites_an_existing_directory(tmp_path, release_inputs):
    source, wheel, screenshot, installer = release_inputs
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "other-product.txt"
    sentinel.write_text("leave me")
    with pytest.raises(ValueError, match="already exists"):
        build_public_site(
            wheel, destination, "a" * 40, screenshot, installer=installer, source=source
        )
    assert sentinel.read_text() == "leave me"


@pytest.mark.parametrize(
    "extra", ["scrip_core/api-token", "scrip_core/private.sqlite3", "../key.pem"]
)
def test_private_or_outside_files_are_rejected_from_wheel(release_inputs, extra):
    _, wheel, _, _ = release_inputs
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr(extra, b"private")
    with pytest.raises(ValueError, match="Unexpected/private"):
        validate_wheel(wheel)


def test_commit_and_wheel_version_must_match_the_release(tmp_path, release_inputs):
    source, wheel, screenshot, installer = release_inputs
    with pytest.raises(ValueError, match="commit"):
        build_public_site(
            wheel, tmp_path / "bad", "HEAD", screenshot, installer=installer, source=source
        )
    with pytest.raises(ValueError, match="Expected"):
        validate_wheel(wheel, "9.9.9a1")
