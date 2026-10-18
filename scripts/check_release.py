"""Inspect release files without uploading them or importing package code."""

import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile
import tomllib
import zipfile


NAME = "django-ninja-ulid"
STEM = "django_ninja_ulid"


def validate_version(version):
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("A stable three-part release version is required")


def validate_source(root, tag=""):
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    version = project["version"]
    validate_version(version)
    if project["name"] != NAME:
        raise ValueError("Unexpected distribution name")
    if tag and tag != f"v{version}":
        raise ValueError("Tag does not match the project version")
    if not re.search(rf"^## {re.escape(version)}(?:\s|$)", (root / "CHANGELOG.md").read_text(), re.MULTILINE):
        raise ValueError("The version must have a CHANGELOG section")
    return version


def distribution_names(version):
    validate_version(version)
    return {f"{STEM}-{version}-py3-none-any.whl", f"{STEM}-{version}.tar.gz"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_metadata(raw, version):
    metadata = BytesParser().parsebytes(raw)
    if metadata["Name"] != NAME or metadata["Version"] != version:
        raise ValueError("Distribution metadata does not match the release")


def inspect_wheel(path, version):
    prefix = f"{STEM}-{version}.dist-info"
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        required = {"django_ninja_ulid/py.typed", f"{prefix}/licenses/LICENSE"}
        if not required <= names:
            raise ValueError("Wheel is missing the type marker or license")
        inspect_metadata(archive.read(f"{prefix}/METADATA"), version)


def inspect_distributions(directory, version):
    expected = distribution_names(version)
    # uv build creates this marker in its output directory.
    if {path.name for path in directory.iterdir() if path.name != ".gitignore"} != expected:
        raise ValueError("Expected exactly one wheel and one sdist for this version")
    wheel = directory / f"{STEM}-{version}-py3-none-any.whl"
    inspect_wheel(wheel, version)
    prefix = f"{STEM}-{version}"
    with tarfile.open(directory / f"{prefix}.tar.gz") as archive:
        required = {f"{prefix}/{name}" for name in (
            "README.md", "CHANGELOG.md", "LICENSE", "pyproject.toml",
            "src/django_ninja_ulid/py.typed",
        )}
        if not required <= set(archive.getnames()):
            raise ValueError("Sdist is missing release documentation, license or type marker")
        inspect_metadata(archive.extractfile(f"{prefix}/PKG-INFO").read(), version)
    return {name: digest(directory / name) for name in sorted(expected)}


def prepare_manifest(root, directory, target, tag="", commit=""):
    version = validate_source(root, tag)
    if commit and not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Source commit must be a full Git commit SHA")
    manifest = {
        "distribution": NAME,
        "version": version,
        "expected_tag": tag or f"v{version}",
        "source_commit": commit or None,
        "files": inspect_distributions(directory, version),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def read_manifest(path):
    manifest = json.loads(path.read_text())
    if manifest["distribution"] != NAME or manifest["expected_tag"] != f"v{manifest['version']}":
        raise ValueError("Unexpected release identity")
    if set(manifest["files"]) != distribution_names(manifest["version"]):
        raise ValueError("Unexpected distribution filenames")
    return manifest


def verify_manifest(directory, target):
    manifest = read_manifest(target)
    if inspect_distributions(directory, manifest["version"]) != manifest["files"]:
        raise ValueError("Distribution SHA256 does not match the manifest")
    return manifest


def verify_downloaded_wheel(path, target):
    manifest = read_manifest(target)
    if path.name != f"{STEM}-{manifest['version']}-py3-none-any.whl" or digest(path) != manifest["files"].get(path.name):
        raise ValueError("Downloaded wheel does not match the prepared release")
    inspect_wheel(path, manifest["version"])
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tag", default="")
    parser.add_argument("--commit", default="")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--downloaded-wheel", type=Path)
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()
    if args.verify:
        manifest = verify_manifest(args.dist_dir, args.manifest)
    elif args.downloaded_wheel:
        manifest = verify_downloaded_wheel(args.downloaded_wheel, args.manifest)
    else:
        manifest = prepare_manifest(args.root, args.dist_dir, args.manifest, args.tag, args.commit)
    if args.github_output:
        artifact = f"release-{manifest['version']}-{manifest['source_commit'] or 'working-tree'}"
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            output.write(f"version={manifest['version']}\nartifact_name={artifact}\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
