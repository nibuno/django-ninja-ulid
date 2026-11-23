"""Check the public API from a consumer's perspective with mypy."""

from typing import Annotated, assert_type

from django.db import models
from ninja import Schema
from pydantic import BaseModel, BeforeValidator, TypeAdapter
from ulid import ULID

from django_ninja_ulid import ApiULID
from django_ninja_ulid.orm import create_ulid_response_schema, related_ids

# Keep the callable outside Annotated metadata so mypy checks its signature.
normalize_related_ids = BeforeValidator(related_ids)


class ItemResponse(BaseModel):
    id: ApiULID
    tags: Annotated[list[ApiULID], normalize_related_ids]


def check_public_api(model: type[models.Model]) -> None:
    text = "01arz3ndektsv4rrffq69g5fav"
    item = ItemResponse.model_validate({"id": text, "tags": [text]})
    assert_type(item.id, ULID)
    assert_type(item.tags, list[ULID])

    adapter = TypeAdapter(ApiULID)
    assert_type(adapter.validate_python(text), ULID)

    schema = create_ulid_response_schema(model, name="ItemOut", fields=["id", "tags"])
    assert_type(schema, type[Schema])
