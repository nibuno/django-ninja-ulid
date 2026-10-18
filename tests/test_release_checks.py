"""Reject releases with a wrong version, missing files or changed artifacts."""

import importlib.util
import io
from pathlib import Path
import tarfile
import zipfile

import pytest


spec = importlib.util.spec_from_file_location(
    "release_checks", Path(__file__).resolve().parents[1] / "scripts/check_release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname="django-ninja-ulid"\nversion="0.1.0"\n')
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## 0.1.0 (not published)\n")
    directory = tmp_path / "dist"
    directory.mkdir()
    (directory / ".gitignore").write_text("*\n")
    metadata = b"Metadata-Version: 2.4\nName: django-ninja-ulid\nVersion: 0.1.0\n"
    wheel = directory / "django_ninja_ulid-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("django_ninja_ulid/py.typed", "")
        archive.writestr("django_ninja_ulid-0.1.0.dist-info/licenses/LICENSE", "MIT")
        archive.writestr("django_ninja_ulid-0.1.0.dist-info/METADATA", metadata)
    with tarfile.open(directory / "django_ninja_ulid-0.1.0.tar.gz", "w:gz") as archive:
        for name in ["README.md", "CHANGELOG.md", "LICENSE", "pyproject.toml", "src/django_ninja_ulid/py.typed", "PKG-INFO"]:
            data = metadata if name == "PKG-INFO" else b""
            entry = tarfile.TarInfo(f"django_ninja_ulid-0.1.0/{name}")
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
    target = tmp_path / "release-manifest.json"
    return root, directory, target, wheel


@pytest.mark.parametrize("tag", ["v0.2.0", "0.1.0", "v0.1.0a1"])
def test_wrong_release_tag_is_rejected(bundle, tag):
    root, directory, target, _ = bundle
    with pytest.raises(ValueError, match="Tag does not match"):
        release.prepare_manifest(root, directory, target, tag)
    assert not target.exists()


def test_wheel_with_different_metadata_version_is_rejected(bundle):
    root, directory, target, wheel = bundle
    with zipfile.ZipFile(wheel) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, value in contents.items():
            archive.writestr(name, value.replace(b"Version: 0.1.0", b"Version: 0.2.0") if name.endswith("/METADATA") else value)
    with pytest.raises(ValueError, match="metadata does not match"):
        release.prepare_manifest(root, directory, target)


def test_missing_type_marker_is_rejected(bundle):
    root, directory, target, wheel = bundle
    with zipfile.ZipFile(wheel) as archive:
        contents = {name: archive.read(name) for name in archive.namelist() if not name.endswith("py.typed")}
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, value in contents.items():
            archive.writestr(name, value)
    with pytest.raises(ValueError, match="type marker or license"):
        release.prepare_manifest(root, directory, target)


def test_mixed_versions_in_distribution_folder_are_rejected(bundle):
    root, directory, target, _ = bundle
    (directory / "django_ninja_ulid-0.0.0-py3-none-any.whl").write_bytes(b"old release")
    with pytest.raises(ValueError, match="exactly one wheel and one sdist"):
        release.prepare_manifest(root, directory, target)


def test_changed_distribution_is_rejected(bundle):
    root, directory, target, wheel = bundle
    release.prepare_manifest(root, directory, target)
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("unexpected.py", "changed = True")
    with pytest.raises(ValueError, match="SHA256 does not match"):
        release.verify_manifest(directory, target)


def test_different_downloaded_wheel_is_rejected(bundle, tmp_path):
    root, directory, target, wheel = bundle
    release.prepare_manifest(root, directory, target)
    downloaded = tmp_path / "downloaded" / wheel.name
    downloaded.parent.mkdir()
    downloaded.write_bytes(wheel.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="does not match the prepared release"):
        release.verify_downloaded_wheel(downloaded, target)


def test_prepared_files_and_matching_download_are_accepted(bundle):
    root, directory, target, wheel = bundle
    manifest = release.prepare_manifest(root, directory, target, "v0.1.0", "a" * 40)
    assert manifest["source_commit"] == "a" * 40
    assert release.verify_manifest(directory, target) == manifest
    assert release.verify_downloaded_wheel(wheel, target) == manifest
