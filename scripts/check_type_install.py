"""Validate the base wheel without the optional Django field distribution."""

import argparse
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    os.environ.pop("DJANGO_SETTINGS_MODULE", None)
    assert importlib.util.find_spec("ulid_django") is None
    try:
        importlib.metadata.version("python-ulid-django")
    except importlib.metadata.PackageNotFoundError:
        pass
    else:
        raise AssertionError("The base installation contains the optional field library")

    import django_ninja_ulid
    from django_ninja_ulid import ApiULID
    from pydantic import TypeAdapter, ValidationError

    assert Path(django_ninja_ulid.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    adapter = TypeAdapter(ApiULID)
    text = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    value = adapter.validate_python(text.lower())
    assert adapter.dump_python(value) == text
    assert adapter.dump_json(value) == ('"' + text + '"').encode()
    for invalid in [None, True, 42, -1, 1.5, {}, [], b"bytes", "I" * 26, "Z" * 26]:
        try:
            adapter.validate_python(invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"Accepted invalid input: {invalid!r}")
    assert not {"django", "ninja", "ulid_django"}.intersection(sys.modules)
    try:
        import django_ninja_ulid.orm
    except ImportError as error:
        assert "django-ninja-ulid[orm]" in str(error)
    else:
        raise AssertionError("Expected an optional dependency installation hint")
    report = {
        "status": "passed", "python": sys.version.split()[0],
        "package_version": importlib.metadata.version("django-ninja-ulid"),
        "package_file": django_ninja_ulid.__file__,
        "optional_field_installed": False,
        "root_import_did_not_import_django_or_ninja": True,
        "validation_and_serialization": "passed",
        "missing_extra_hint": "passed",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
