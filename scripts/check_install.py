"""Check a wheel installation in a fresh Django project with real migrations.

Run this script with the Python environment containing the non-editable wheel
and the orm extra. ULID_TEST_DATABASE selects sqlite or postgresql, using the
same ULID_POSTGRES_* environment variables as the test suite. Only a uniquely
named temporary PostgreSQL database is created and removed by this script.
"""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


MODELS = '''import uuid
from django.db import models
from ulid import ULID
from ulid_django.models import ULIDField

class Owner(models.Model):
    id = ULIDField(primary_key=True, default=ULID)

class Tag(models.Model):
    id = ULIDField(primary_key=True, default=ULID)

class Item(models.Model):
    id = ULIDField(primary_key=True, default=ULID)
    public_uuid = models.UUIDField(default=uuid.uuid4)
    owner = models.ForeignKey(Owner, null=True, on_delete=models.SET_NULL)
    tags = models.ManyToManyField(Tag)
'''

API = '''from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Schema, Status
from pydantic import Field
from django_ninja_ulid import ApiULID
from django_ninja_ulid.orm import create_ulid_response_schema
from .models import Item, Owner, Tag

api = NinjaAPI(urls_namespace="fresh-ulid")
fields = ["id", "public_uuid", "owner", "tags"]
ItemOutput = create_ulid_response_schema(Item, name="ItemOutput", fields=fields)
AliasedOutput = create_ulid_response_schema(Item, name="AliasedOutput", fields=fields)

class ItemInput(Schema):
    owner: ApiULID | None = None
    tags: list[ApiULID] = Field(default_factory=list)

@api.post("/items", response={201: ItemOutput})
def create_item(request, payload: ItemInput):
    owner = get_object_or_404(Owner, pk=payload.owner) if payload.owner else None
    item = Item.objects.create(owner=owner)
    item.tags.set([get_object_or_404(Tag, pk=value) for value in payload.tags])
    return Status(201, item)

@api.get("/items/{item_id}", response=ItemOutput)
def item_detail(request, item_id: ApiULID):
    return get_object_or_404(Item.objects.prefetch_related("tags"), pk=item_id)

@api.get("/aliased/{item_id}", response=AliasedOutput, by_alias=True)
def aliased_detail(request, item_id: ApiULID):
    return get_object_or_404(Item.objects.prefetch_related("tags"), pk=item_id)
'''

PROBE = '''import importlib.metadata
import json
from pathlib import Path
import sys
from uuid import UUID

import django_ninja_ulid
from django.db import connection
from django.test import Client
from ulid import ULID
from sample.api import api
from sample.models import Item, Owner, Tag

assert Path(django_ninja_ulid.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
owner = Owner.objects.create()
tag = Tag.objects.create()
client = Client()
response = client.post("/api/items", data=json.dumps({"owner": str(owner.pk), "tags": [str(tag.pk)]}), content_type="application/json")
assert response.status_code == 201, response.content
body = response.json()
stored = Item.objects.get(pk=ULID.from_str(body["id"]))
assert isinstance(stored.pk, ULID)
assert isinstance(stored.owner_id, ULID)
assert UUID(body["public_uuid"]) == stored.public_uuid
assert body["owner"] == str(owner.pk)
assert body["tags"] == [str(tag.pk)]
read = client.get(f"/api/items/{stored.pk}")
assert read.status_code == 200 and read.json() == body
aliased = client.get(f"/api/aliased/{stored.pk}")
assert aliased.status_code == 200 and aliased.json()["owner_id"] == str(owner.pk)
assert "owner" not in aliased.json()
empty = client.post("/api/items", data="{}", content_type="application/json")
assert empty.status_code == 201
assert empty.json()["owner"] is None and empty.json()["tags"] == []
bad = client.post("/api/items", data=json.dumps({"owner": 42}), content_type="application/json")
assert bad.status_code == 422
spec = api.get_openapi_schema()
for path, schema_name, key in [("/api/items/{item_id}", "ItemOutput", "owner"), ("/api/aliased/{item_id}", "AliasedOutput", "owner_id")]:
    ref = spec["paths"][path]["get"]["responses"][200]["content"]["application/json"]["schema"]["$ref"]
    assert ref == f"#/components/schemas/{schema_name}"
    assert key in spec["components"]["schemas"][schema_name]["properties"]
assert spec["components"]["schemas"]["ItemOutput"]["properties"]["public_uuid"]["format"] == "uuid"
if connection.vendor == "postgresql":
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        server = cursor.fetchone()[0]
else:
    with connection.cursor() as cursor:
        cursor.execute("SELECT sqlite_version()")
        server = cursor.fetchone()[0]
print(json.dumps({"status": "passed", "database": connection.vendor, "server_version": server, "python": sys.version.split()[0], "Django": importlib.metadata.version("Django"), "django-ninja": importlib.metadata.version("django-ninja"), "installed_package": django_ninja_ulid.__file__, "checks": ["migrations", "ULID PK/FK/M2M round trip", "UUID", "create/read", "null/empty relations", "invalid input 422", "OpenAPI", "separate alias schemas"]}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    backend = os.environ.get("ULID_TEST_DATABASE", "sqlite")
    if backend not in {"sqlite", "postgresql"}:
        parser.error(f"unsupported database: {backend}")

    admin = None
    database_name = None
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["DJANGO_SETTINGS_MODULE"] = "fresh.settings"
    environment["ULID_INSTALL_BACKEND"] = backend
    try:
        if backend == "postgresql":
            import psycopg
            from psycopg import sql

            admin = psycopg.connect(
                dbname=os.environ.get("ULID_POSTGRES_DB", "ulid_test"),
                user=os.environ.get("ULID_POSTGRES_USER", "postgres"),
                password=os.environ.get("ULID_POSTGRES_PASSWORD", "postgres"),
                host=os.environ.get("ULID_POSTGRES_HOST", "127.0.0.1"),
                port=os.environ.get("ULID_POSTGRES_PORT", "5432"),
                autocommit=True,
            )
            candidate_name = "ulid_install_" + uuid.uuid4().hex[:16]
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(candidate_name)))
            database_name = candidate_name
            environment["ULID_INSTALL_DB"] = database_name

        with tempfile.TemporaryDirectory(prefix="ulid-fresh-project-") as temporary:
            directory = Path(temporary)

            def run(*command, input=None):
                result = subprocess.run(
                    [sys.executable, *command], cwd=directory, env=environment,
                    text=True, input=input, capture_output=True, check=False,
                )
                if result.returncode:
                    raise RuntimeError(f"Fresh project command failed: {command}\n{result.stdout}\n{result.stderr}")
                return result.stdout

            # startproject does not import the not-yet-created settings module.
            run("-m", "django", "startproject", "fresh", str(directory))
            settings = directory / "fresh/settings.py"
            settings.write_text(settings.read_text() + '''
import os
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
INSTALLED_APPS += ["sample"]
if os.environ["ULID_INSTALL_BACKEND"] == "postgresql":
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["ULID_INSTALL_DB"],
        "USER": os.environ.get("ULID_POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("ULID_POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("ULID_POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("ULID_POSTGRES_PORT", "5432"),
    }}
''')
            app = directory / "sample"
            (app / "migrations").mkdir(parents=True)
            (app / "__init__.py").write_text("")
            (app / "migrations/__init__.py").write_text("")
            (app / "models.py").write_text(MODELS)
            (app / "api.py").write_text(API)
            (directory / "fresh/urls.py").write_text('from django.urls import path\nfrom sample.api import api\nurlpatterns = [path("api/", api.urls)]\n')
            run("manage.py", "makemigrations", "sample", "--noinput")
            run("manage.py", "migrate", "--noinput")
            output = run("manage.py", "shell", "-c", PROBE)
            report = json.loads(next(line for line in output.splitlines() if line.startswith('{"status":')))
            assert report["database"] == backend
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps(report, ensure_ascii=False))
    finally:
        if admin is not None:
            try:
                if database_name is not None:
                    admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name)))
            finally:
                admin.close()


if __name__ == "__main__":
    main()
