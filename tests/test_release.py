import hashlib
import json
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

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
    wheel = tmp_path / f"scrip_companion-{__version__}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as package:
        package.writestr("scrip_core/__init__.py", "")
        package.writestr(
            f"scrip_companion-{__version__}.dist-info/METADATA",
            f"Name: scrip-companion\nVersion: {__version__}\n",
        )
    installer = tmp_path / f"Scrip-Terminal-{__version__}-windows-x64-setup.exe"
    installer.write_bytes(b"MZ" + b"test executable")
    return source, wheel, installer


def test_public_bundle_is_allowlisted_and_uses_exact_wheel_hash(tmp_path, release_inputs):
    source, wheel, installer = release_inputs
    public = build_public_site(
        wheel, tmp_path / "public", "a" * 40, installer=installer, source=source
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
    source, wheel, installer = release_inputs
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "other-product.txt"
    sentinel.write_text("leave me")
    with pytest.raises(ValueError, match="already exists"):
        build_public_site(wheel, destination, "a" * 40, installer=installer, source=source)
    assert sentinel.read_text() == "leave me"


@pytest.mark.parametrize(
    "extra", ["scrip_core/api-token", "scrip_core/private.sqlite3", "../key.pem"]
)
def test_private_or_outside_files_are_rejected_from_wheel(release_inputs, extra):
    _, wheel, _ = release_inputs
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr(extra, b"private")
    with pytest.raises(ValueError, match="Unexpected/private"):
        validate_wheel(wheel)


def test_commit_and_wheel_version_must_match_the_release(tmp_path, release_inputs):
    source, wheel, installer = release_inputs
    with pytest.raises(ValueError, match="commit"):
        build_public_site(wheel, tmp_path / "bad", "HEAD", installer=installer, source=source)
    with pytest.raises(ValueError, match="Expected"):
        validate_wheel(wheel, "9.9.9a1")


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.headings = 0
        self.inline_code = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            assert attrs["id"] not in self.ids, "Duplicate HTML ID"
            self.ids.add(attrs["id"])
        if tag == "h1":
            self.headings += 1
        if tag in ("script", "style") and "src" not in attrs:
            self.inline_code = True
        assert not any(key.startswith("on") for key in attrs), "Inline event handler"
        assert "style" not in attrs, "Inline style violates the site's CSP"
        for key in ("href", "src", "srcset"):
            if key in attrs:
                self.links.append(attrs[key])
        if "data-copy" in attrs:
            assert attrs["data-copy"].strip()
            assert attrs.get("type") == "button"


def test_real_site_has_working_local_links_and_no_inline_scripts(tmp_path, release_inputs):
    _, wheel, installer = release_inputs
    public = build_public_site(wheel, tmp_path / "site", "b" * 40, installer=installer)
    pages = {}
    for path in public.glob("*.html"):
        parser = PageLinks()
        parser.feed(path.read_text(encoding="utf-8"))
        assert parser.headings == 1, path.name
        assert not parser.inline_code, path.name
        pages[path.name] = parser
    for name, parser in pages.items():
        for link in parser.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            target = unquote(url.path).lstrip("/")
            target = "index.html" if target in ("", "./") and url.path else target
            target = target or name
            assert (public / target).is_file(), (name, link)
            if url.fragment:
                assert url.fragment in pages[Path(target).name].ids, (name, link)
    manifest = json.loads((public / "SITE-MANIFEST.json").read_text())
    assert "assets/inbox.png" not in manifest["files"]
    assert all(name in manifest["files"] for name in WEB_FILES)
    assert "Scrip-Terminal-" in (public / "index.html").read_text(encoding="utf-8")

    logo = (public / "assets/wordmark.svg").read_text(encoding="utf-8")
    assert 'id="word-letter-s"' not in logo
    assert all(f'id="word-letter-{letter}"' in logo for letter in "crip")
    privacy = (public / "privacy.html").read_text(encoding="utf-8")
    assert "data-analytics-optout" in privacy
    assert "analytics-preferences.js" in privacy
    assert (public / "analytics-preferences.js").is_file()
