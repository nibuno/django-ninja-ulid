from typing import Annotated
from uuid import UUID

from ninja import ModelSchema, Schema
from pydantic import BeforeValidator, Field
from ulid import ULID

from .adapter import ApiULID, create_ulid_response_schema, related_ids
from .models import Item


class AutoIdentity(ModelSchema):
    class Meta:
        model = Item
        fields = ["id"]


class AutoItem(ModelSchema):
    class Meta:
        model = Item
        fields = ["id", "public_uuid", "name", "owner", "tags"]


class RawEcho(Schema):
    id: ULID


class ApiEcho(Schema):
    id: ApiULID


class CreateItem(Schema):
    name: str
    owner: ApiULID | None = None
    tags: list[ApiULID] = []


class ManualItem(Schema):
    id: ULID
    public_uuid: UUID
    name: str
    owner: ULID | None
    tags: list[ULID]

    @staticmethod
    def resolve_owner(obj):
        return obj.owner_id

    @staticmethod
    def resolve_tags(obj):
        return [tag.pk for tag in obj.tags.all()]


class ManualFixedItem(ManualItem):
    id: ApiULID
    owner: ApiULID | None
    tags: list[ApiULID]


class ExplicitItem(ModelSchema):
    id: ApiULID
    owner: ApiULID | None = Field(..., alias=Item._meta.get_field("owner").attname)
    tags: Annotated[list[ApiULID], BeforeValidator(related_ids)]

    class Meta:
        model = Item
        fields = ["id", "public_uuid", "name", "owner", "tags"]


AdaptedItem = create_ulid_response_schema(
    Item,
    name="AdaptedItem",
    fields=["id", "public_uuid", "name", "owner", "tags"],
)

# Ninja 1.7.1 shares one OpenAPI component between alias modes, so its last
# definition wins. Give the by_alias=True response a separate schema.
AliasedItem = create_ulid_response_schema(
    Item,
    name="AliasedItem",
    fields=["id", "public_uuid", "name", "owner", "tags"],
)
