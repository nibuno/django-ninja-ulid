# django-ninja-ulid

[![PyPI](https://img.shields.io/pypi/v/django-ninja-ulid.svg)](https://pypi.org/project/django-ninja-ulid/)
[![CI](https://github.com/nibuno/django-ninja-ulid/actions/workflows/ci.yml/badge.svg)](https://github.com/nibuno/django-ninja-ulid/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/nibuno/django-ninja-ulid/blob/main/LICENSE)

[日本語](https://github.com/nibuno/django-ninja-ulid/blob/main/README.ja.md)

Accept and return [ULIDs](https://github.com/ulid/spec) as 26-character strings in [Django Ninja](https://django-ninja.dev/) APIs.

Django Ninja infers a UUID type for `python-ulid-django`'s `ULIDField`. This package provides explicit ULID validation and serialization, plus response schemas that preserve ordinary UUID fields.

- **`ApiULID`** validates ULID strings, gives you a `ulid.ULID` in Python, and serializes to an uppercase string.
- **`create_ulid_response_schema`** builds flat response schemas from Django models. Foreign keys and many-to-many relations return IDs rather than nested objects.
- **`related_ids`** converts related model instances to their primary keys for hand-written schemas.

ID generation and storage remain with [python-ulid](https://github.com/mdomke/python-ulid) and [python-ulid-django](https://pypi.org/project/python-ulid-django/).

## Installation

For `ApiULID`, use the base installation. For Django model integration, use the `orm` extra:

```bash
pip install django-ninja-ulid
pip install "django-ninja-ulid[orm]"
```

Python 3.12–3.14 is required. This is an alpha package with dependencies pinned to tested versions:

| Dependency | Version constraint |
|---|---|
| Django | `>=5.2.18,<6.2`, excluding `6.0.*`, `6.1.0`, and `6.1.1` |
| Django Ninja | `==1.7.1` |
| Pydantic | `==2.13.5` |
| python-ulid | `==4.0.1` |
| python-ulid-django | `==1.6.0` (with `orm`) |

Check these constraints against your project's dependencies before installing. The base installation includes Django and Ninja; importing `ApiULID` does not load them or require Django settings. The `orm` extra adds `python-ulid-django`.

## Quick start

In an existing Django project, create `catalog/api.py` in your app. The example uses `catalog` as the app name and `config` as the project package; use your own names if they differ.

```python
# catalog/api.py
from ninja import NinjaAPI, Schema

from django_ninja_ulid import ApiULID

api = NinjaAPI()


class Identifier(Schema):
    id: ApiULID


@api.post("/echo", response=Identifier)
def echo(request, payload: Identifier):
    return payload
```

Add the API to your project's URL configuration, keeping any existing routes:

```python
# config/urls.py
from django.urls import path

from catalog.api import api

urlpatterns = [path("api/", api.urls)]
```

Start the development server with `python manage.py runserver`, then send a lowercase ULID:

```bash
curl http://127.0.0.1:8000/api/echo \
  -H 'Content-Type: application/json' \
  -d '{"id":"01arz3ndektsv4rrffq69g5fav"}'
```

The response is HTTP 200 with an uppercase ULID:

```json
{"id":"01ARZ3NDEKTSV4RRFFQ69G5FAV"}
```

An invalid value such as `"invalid"` or `42` produces HTTP 422. The endpoint's `payload.id` is a `ULID` object; the response schema converts it to a string. You can also use `ApiULID` for path and query parameters, as the next example shows for a path parameter.

## Django model responses

Install the `orm` extra and add your app (`catalog` here) to `INSTALLED_APPS`. Define a model with a ULID primary key and an optional foreign key:

```python
# catalog/models.py
import uuid

from django.db import models
from ulid import ULID
from ulid_django.models import ULIDField


class Owner(models.Model):
    id = ULIDField(primary_key=True, default=ULID, editable=False)


class Item(models.Model):
    id = ULIDField(primary_key=True, default=ULID, editable=False)
    public_uuid = models.UUIDField(default=uuid.uuid4)
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(Owner, null=True, on_delete=models.SET_NULL)
```

Replace `catalog/api.py` from the quick start with this version. Keep the same URL configuration. Import `django_ninja_ulid.orm` after Django has initialized, such as from your app's API module loaded by the URL configuration.

```python
# catalog/api.py
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI

from django_ninja_ulid import ApiULID
from django_ninja_ulid.orm import create_ulid_response_schema

from .models import Item

api = NinjaAPI()

ItemOut = create_ulid_response_schema(
    Item,
    name="ItemOut",
    fields=["id", "public_uuid", "name", "owner"],
)


@api.get("/items/{item_id}", response=ItemOut)
def get_item(request, item_id: ApiULID):
    return get_object_or_404(Item, pk=item_id)
```

Choose the exposed fields explicitly with a non-empty `fields` list. The helper overrides ULID fields and relations to ULID primary keys; all other fields retain Ninja's normal types.

Create the tables and a sample item:

```bash
python manage.py makemigrations catalog
python manage.py migrate
python manage.py shell -c 'from catalog.models import Item; print(Item.objects.create(name="example").pk)'
```

Request `/api/items/<printed-id>` while the development server is running. The response has this shape (the generated IDs will differ):

```json
{
  "id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "public_uuid": "8f14e45f-ceea-467f-a0e6-4b6f8b8a8c1d",
  "name": "example",
  "owner": null
}
```

If an owner is assigned, `owner` contains its ULID string. The foreign key is read through `owner_id`, without fetching the owner object. With `by_alias=True` on the route, the output key is `owner_id` instead of `owner`; see the alias limitation below.

### Many-to-many relations

For a `Tag` model with a ULID primary key, add `tags = models.ManyToManyField(Tag)` to `Item`, run migrations, and include `"tags"` in `ItemOut`'s `fields`. The response contains a list of ULID strings, or `[]` when no tags are assigned.

Replace the detail endpoint's lookup with `get_object_or_404(Item.objects.prefetch_related("tags"), pk=item_id)`. For lists of items, use `prefetch_related("tags")` on the queryset to avoid a separate tag query for each item. The schema helper does not optimize queries automatically.

| Selected field | Response behavior |
|---|---|
| ULIDField or ULID foreign key with `null=False` | Key is always included; value is not null |
| ULIDField or ULID foreign key with `null=True` | Key is always included; value may be null |
| Many-to-many relation to a ULID primary key | Key is always included; list may be empty, never null |
| Non-ULID field | Ninja's usual behavior |

## Hand-written schemas

To control the schema yourself, use `ApiULID` explicitly. Put this schema in `catalog/schemas.py`, import it in `catalog/api.py` with `from .schemas import ManualItemOut`, and set the route's `response=ManualItemOut`:

```python
# catalog/schemas.py
from ninja import ModelSchema
from pydantic import Field

from django_ninja_ulid import ApiULID

from .models import Item


class ManualItemOut(ModelSchema):
    id: ApiULID
    owner: ApiULID | None = Field(..., alias="owner_id")

    class Meta:
        model = Item
        fields = ["id", "public_uuid", "name", "owner"]
```

For many-to-many fields, `related_ids` converts a Manager, QuerySet, or list of model instances into a list of primary keys. Place this definition before `ManualItemOut` in the same module, loaded after Django initialization through your API module:

```python
# catalog/schemas.py (before ManualItemOut)
from typing import Annotated

from pydantic import BeforeValidator

from django_ninja_ulid import ApiULID
from django_ninja_ulid.orm import related_ids

RelatedULIDs = Annotated[list[ApiULID], BeforeValidator(related_ids)]
```

After adding `tags` to the model, declare `tags: RelatedULIDs` inside your `ModelSchema` and include `"tags"` in `Meta.fields`.

## Validation and serialization

- HTTP input must be a 26-character ASCII ULID string. Lowercase is accepted and normalized to uppercase.
- The first character must be `0`–`7`. Characters `I`, `L`, `O`, and `U` (including lowercase) are rejected, not treated as aliases.
- Numbers, booleans, null, objects, and arrays are rejected. Use `ApiULID | None` when null is allowed.
- Python validation also accepts existing `ulid.ULID` instances. Validated attributes are `ULID` objects; serialization, including `model_dump()`, produces uppercase strings.
- Invalid request input produces HTTP 422 in Ninja. Direct Pydantic validation raises `ValidationError`.

You can use the type without configuring Django:

```python
from pydantic import TypeAdapter
from ulid import ULID

from django_ninja_ulid import ApiULID

adapter = TypeAdapter(ApiULID)
value = adapter.validate_python("01arz3ndektsv4rrffq69g5fav")
assert isinstance(value, ULID)
assert adapter.dump_python(value) == "01ARZ3NDEKTSV4RRFFQ69G5FAV"
```

## Why not plain ModelSchema?

With the pinned dependencies:

- `ULIDField` inherits from `UUIDField`, so Ninja infers a UUID type. A 26-character ULID request value fails UUID validation with HTTP 422; a model response containing a ULID fails response validation with HTTP 500.
- Declaring the raw `ulid.ULID` type in a hand-written schema avoids UUID inference, but its output can fail JSON encoding with a `TypeError` and HTTP 500.
- Registering a global replacement with `register_field("UUIDField", ...)` also changes ordinary UUID fields.

`ApiULID` handles validation and serialization explicitly. `create_ulid_response_schema` applies it only to the selected ULID fields and relations.

## Scope and limitations

`create_ulid_response_schema` generates flat **response** schemas for `python-ulid-django` fields. It does not generate request or PATCH schemas, nested responses, or schemas for other ULID field libraries.

An empty `fields` list, a foreign key targeting a non-primary-key `to_field`, reverse relations, `OneToOneField`, and composite primary keys raise `ValueError` when the schema is created.

Two known OpenAPI limitations:

- In Ninja 1.7.1, reusing one schema across routes with different `by_alias` settings causes the last registered route to determine the shared OpenAPI component's field names. HTTP responses remain correct. Create a schema with a distinct `name` for each output format.
- The OpenAPI pattern accepts lowercase in responses as well as requests. Actual serialized output is always uppercase.

## Compatibility

| Python | Tested Django versions | Databases |
|---|---|---|
| 3.12 / 3.13 / 3.14 | 5.2.18 / 6.1.2 | SQLite / PostgreSQL 18.6 |

CI covers all 12 combinations. The Django dependency range also permits later patch versions within 5.2 and 6.1; those are not automatically covered by this tested-version table. See [compatibility and verification details (Japanese)](https://github.com/nibuno/django-ninja-ulid/blob/main/docs/compatibility.md).

## Versioning and contributing

The public API consists of `ApiULID`, `create_ulid_response_schema`, and `related_ids`. During 0.x, breaking changes use a minor release (for example, 0.1 → 0.2); compatible fixes use a patch release.

- [Changelog (Japanese)](https://github.com/nibuno/django-ninja-ulid/blob/main/CHANGELOG.md)
- [Versioning policy (Japanese)](https://github.com/nibuno/django-ninja-ulid/blob/main/docs/versioning.md)
- [Development and bug reports (Japanese)](https://github.com/nibuno/django-ninja-ulid/blob/main/CONTRIBUTING.md)
- [Report an issue](https://github.com/nibuno/django-ninja-ulid/issues)

## License

[MIT](https://github.com/nibuno/django-ninja-ulid/blob/main/LICENSE)
