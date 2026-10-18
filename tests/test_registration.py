from uuid import UUID

import pytest
from ninja.orm import create_schema, register_field
from ninja.orm.fields import TYPES
from ulid import ULID

from poc.models import Item


def test_global_uuid_mapping_also_changes_ordinary_uuid():
    original = TYPES["UUIDField"]
    try:
        register_field("UUIDField", ULID)
        schema = create_schema(Item, name="UnsafeRegisteredUuid", fields=["public_uuid"])
        assert schema.model_fields["public_uuid"].annotation is ULID
    finally:
        TYPES["UUIDField"] = original
    assert TYPES["UUIDField"] is UUID


def test_global_ulid_mapping_breaks_m2m_openapi():
    original = TYPES["UUIDField"]
    try:
        register_field("UUIDField", ULID)
        schema = create_schema(Item, name="UnsafeRegisteredManyToMany", fields=["tags"])
        with pytest.raises(KeyError) as error:
            schema.model_json_schema()
        assert error.value.args == (ULID,)
    finally:
        TYPES["UUIDField"] = original
