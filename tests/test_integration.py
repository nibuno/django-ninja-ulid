import json
import re
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError
from ulid import ULID

from poc.api import api
from poc.models import Item
from poc.schemas import AdaptedItem, AutoItem, ManualItem, RawEcho


def post_id(http, mode, value):
    return http.post(
        f"/api/{mode}/echo", data=json.dumps({"id": value}), content_type="application/json"
    )


def test_model_schema_maps_ulid_to_uuid():
    assert UUID in AutoItem.model_fields["id"].annotation.__args__
    assert UUID in AutoItem.model_fields["owner"].annotation.__args__


def test_auto_schema_rejects_valid_ulid_input(http, ulid_text):
    response = post_id(http, "auto", ulid_text)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "uuid_parsing"


def test_auto_response_fails_on_real_ulid_model(http, item):
    response = http.get(f"/api/auto/items/{item.pk}")
    assert response.status_code == 500
    assert response.exc_info[0] is ValidationError


def test_manual_raw_ulid_response_fails_json_encoding(http, item):
    response = http.get(f"/api/manual/items/{item.pk}")
    assert response.status_code == 500
    assert response.exc_info[0] is TypeError
    assert "not JSON serializable" in str(response.exc_info[1])


def test_manual_fixed_schema_serializes_ulid_relations(http, item):
    response = http.get(f"/api/manual-fixed/items/{item.pk}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(item.pk)
    assert body["owner"] == str(item.owner_id)
    assert body["tags"] == [str(tag.pk) for tag in item.tags.all()]
    assert body["public_uuid"] == str(item.public_uuid)


def test_raw_explicit_ulid_fails_json_encoding(http, ulid_text):
    response = post_id(http, "raw", ulid_text)
    assert response.status_code == 500
    assert response.exc_info[0] is TypeError
    assert "not JSON serializable" in str(response.exc_info[1])


def test_adapter_ulid_round_trip(http, ulid_text):
    response = post_id(http, "adapted", ulid_text)
    assert response.status_code == 200
    assert response.json()["id"] == ulid_text


@pytest.mark.parametrize("value", [None, {}, [], -1])
def test_raw_ulid_wrong_json_types_raise_500(http, value):
    response = post_id(http, "raw", value)
    assert response.status_code == 500
    assert response.exc_info[0] in (TypeError, OverflowError)


def test_raw_ulid_validation_accepts_numeric_id():
    payload = RawEcho.model_validate({"id": 42})
    assert str(payload.id) == "0000000000000000000000001A"


@pytest.mark.parametrize("value", [None, {}, [], -1, 42, True, "short", "I" * 26, "Z" * 26])
def test_adapter_rejects_invalid_input_with_422(http, value):
    response = post_id(http, "adapted", value)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "payload", "id"]


def test_path_parameter_round_trip(http, ulid_text):
    response = http.get(f"/api/adapted/path/{ulid_text}")
    assert response.status_code == 200
    assert response.json()["id"] == ulid_text


@pytest.mark.parametrize("location", ["path", "query"])
def test_adapter_handles_query_and_path(http, ulid_text, location):
    if location == "path":
        response = http.get(f"/api/adapted/path/{ulid_text.lower()}")
    else:
        response = http.get("/api/adapted/query", {"item_id": ulid_text.lower()})
    assert response.status_code == 200
    assert response.json()["id"] == ulid_text


@pytest.mark.parametrize("location", ["path", "query"])
def test_adapter_rejects_bad_query_and_path(http, location):
    if location == "path":
        response = http.get("/api/adapted/path/invalid")
    else:
        response = http.get("/api/adapted/query", {"item_id": "invalid"})
    assert response.status_code == 422


def test_adapter_serializes_pk_fk_m2m_and_preserves_uuid(http, item):
    response = http.get(f"/api/adapted/items/{item.pk}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(item.pk)
    assert body["owner"] == str(item.owner_id)
    assert body["tags"] == [str(tag.pk) for tag in item.tags.all()]
    assert body["public_uuid"] == str(item.public_uuid)
    assert AdaptedItem.model_fields["public_uuid"].annotation is UUID
    assert UUID in AutoItem.model_fields["id"].annotation.__args__


def test_adapter_handles_null_relation_and_empty_m2m(http, db):
    item = Item.objects.create(name="empty")
    response = http.get(f"/api/adapted/items/{item.pk}")
    assert response.status_code == 200
    assert response.json()["owner"] is None
    assert response.json()["tags"] == []


def test_adapter_create_then_read_uses_real_database(http, item):
    response = http.post(
        "/api/adapted/items",
        data=json.dumps({"name": "created", "owner": str(item.owner_id), "tags": [str(t.pk) for t in item.tags.all()]}),
        content_type="application/json",
    )
    assert response.status_code == 201
    created = Item.objects.get(pk=ULID.from_str(response.json()["id"]))
    assert created.owner_id == item.owner_id
    assert list(created.tags.values_list("pk", flat=True)) == list(item.tags.values_list("pk", flat=True))
    read = http.get(f"/api/adapted/items/{created.pk}")
    assert read.status_code == 200
    assert read.json() == response.json()


def test_response_adapter_does_not_generate_missing_id(item):
    with pytest.raises(ValidationError):
        AdaptedItem.model_validate({"public_uuid": item.public_uuid, "name": "missing", "owner_id": None, "tags": []})


def test_openapi_distinguishes_ulid_and_uuid():
    schemas = api.get_openapi_schema()["components"]["schemas"]
    auto_id = schemas["AutoIdentity"]["properties"]["id"]
    assert any(value.get("format") == "uuid" for value in auto_id["anyOf"])
    adapted = schemas["AdaptedItem"]["properties"]
    for field in (adapted["id"], adapted["tags"]["items"]):
        assert field["type"] == "string"
        assert field["minLength"] == field["maxLength"] == 26
        assert field["pattern"].startswith("^")
        assert field["pattern"].endswith("$")
        assert "anyOf" not in field
    assert adapted["public_uuid"]["format"] == "uuid"


def test_raw_ulid_openapi_advertises_binary_alternative():
    alternatives = RawEcho.model_json_schema()["properties"]["id"]["anyOf"]
    assert any(value.get("format") == "binary" for value in alternatives)


def test_openapi_pattern_matches_accepted_lowercase_input(ulid_text):
    schema = api.get_openapi_schema()["components"]["schemas"]["ApiEcho"]
    pattern = schema["properties"]["id"]["pattern"]
    assert re.fullmatch(pattern, ulid_text)
    assert re.fullmatch(pattern, ulid_text.lower())
    assert re.fullmatch(pattern, "Z" * 26) is None
    assert re.fullmatch(pattern, "I" * 26) is None


def test_ulid_instances_and_canonical_output(item):
    from poc.adapter import ApiULID

    adapter = TypeAdapter(ApiULID)
    assert adapter.validate_python(item.pk) == item.pk
    assert adapter.dump_json(item.pk).decode() == json.dumps(str(item.pk))
