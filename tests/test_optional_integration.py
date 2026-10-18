"""The type must work independently of Django initialization and the ORM extra."""

import subprocess
import sys
import textwrap


def run_isolated(code):
    result = subprocess.run(
        [sys.executable, "-I", "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_type_does_not_import_django_ninja_or_optional_field_library():
    run_isolated('''
        import importlib.abc
        import os
        import sys
        os.environ.pop("DJANGO_SETTINGS_MODULE", None)

        class RejectModelImports(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] in {"django", "ninja", "ulid_django"}:
                    raise AssertionError(f"Unexpected import: {fullname}")

        sys.meta_path.insert(0, RejectModelImports())
        from django_ninja_ulid import ApiULID
        from pydantic import TypeAdapter, ValidationError
        from ulid import ULID

        adapter = TypeAdapter(ApiULID)
        text = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        value = adapter.validate_python(text.lower())
        assert isinstance(value, ULID)
        assert adapter.dump_python(value) == text
        assert adapter.dump_json(value) == ('"' + text + '"').encode()
        for invalid in (None, True, 42, -1, 1.5, {}, [], b"bytes", "I" * 26, "Z" * 26):
            try:
                adapter.validate_python(invalid)
            except ValidationError:
                pass
            else:
                raise AssertionError(f"Accepted invalid input: {invalid!r}")
        assert not {"django", "ninja", "ulid_django"}.intersection(sys.modules)
    ''')


def test_missing_orm_extra_explains_how_to_install_it():
    run_isolated('''
        import importlib.abc
        import os
        import sys
        os.environ.pop("DJANGO_SETTINGS_MODULE", None)

        class MissingFieldLibrary(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "ulid_django":
                    raise ModuleNotFoundError("No module named 'ulid_django'", name=fullname)

        sys.meta_path.insert(0, MissingFieldLibrary())
        try:
            import django_ninja_ulid.orm
        except ImportError as error:
            assert "django-ninja-ulid[orm]" in str(error)
        else:
            raise AssertionError("Expected an installation hint")
        assert "django" not in sys.modules
    ''')


def test_unrelated_import_error_is_not_reported_as_missing_extra():
    run_isolated('''
        import importlib.abc
        import sys

        class BrokenDependency(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "ulid_django":
                    raise ModuleNotFoundError(
                        "Missing transitive dependency", name="field_transitive_dependency"
                    )

        sys.meta_path.insert(0, BrokenDependency())
        try:
            import django_ninja_ulid.orm
        except ModuleNotFoundError as error:
            assert error.name == "field_transitive_dependency"
        else:
            raise AssertionError("Expected the original import error")
    ''')
