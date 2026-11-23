import json
import re
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError
from ulid import ULID

from poc.adapter import ApiULID
from poc.api import api
from poc.models import Item
from poc.schemas import AdaptedItem, AutoItem, RawEcho

SAMPLE = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
INVALID_ULIDS = [
    (123, "ulid_type", None),
    (None, "ulid_type", None),
    ({}, "ulid_type", None),
    ([], "ulid_type", None),
    (-1, "ulid_type", None),
    (True, "ulid_type", None),
    ("short", "ulid_length", {"actual_length": 5}),
    (SAMPLE[:-1], "ulid_length", {"actual_length": 25}),
    (SAMPLE + "0", "ulid_length", {"actual_length": 27}),
    (SAMPLE + "\n", "ulid_length", {"actual_length": 27}),
    (f" {SAMPLE} ", "ulid_length", {"actual_length": 28}),
    (SAMPLE[:-1] + "\n", "ulid_parsing", None),
    (SAMPLE[:-1] + "I", "ulid_parsing", None),
    (SAMPLE[:-1] + "\N{LATIN SMALL LETTER LONG S}", "ulid_parsing", None),
    ("8" + "Z" * 25, "ulid_parsing", None),
    ("Z" * 26, "ulid_parsing", None),
]


def post_id(http, mode, value):
    return http.post(
        f"/api/{mode}/echo", data=json.dumps({"id": value}), content_type="application/json"
    )


@pytest.mark.upstream
def test_model_schema_maps_ulid_to_uuid():
    assert UUID in AutoItem.model_fields["id"].annotation.__args__
    assert UUID in AutoItem.model_fields["owner"].annotation.__args__


@pytest.mark.upstream
def test_auto_schema_rejects_valid_ulid_input(http, ulid_text):
    response = post_id(http, "auto", ulid_text)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "uuid_parsing"


@pytest.mark.upstream
def test_auto_response_fails_on_real_ulid_model(http, item):
    response = http.get(f"/api/auto/items/{item.pk}")
    assert response.status_code == 500
    assert response.exc_info[0] is ValidationError


@pytest.mark.upstream
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


@pytest.mark.upstream
def test_raw_explicit_ulid_fails_json_encoding(http, ulid_text):
    response = post_id(http, "raw", ulid_text)
    assert response.status_code == 500
    assert response.exc_info[0] is TypeError
    assert "not JSON serializable" in str(response.exc_info[1])


@pytest.mark.parametrize("value", [SAMPLE, SAMPLE.lower()])
def test_adapter_ulid_round_trip(http, value):
    response = post_id(http, "adapted", value)
    assert response.status_code == 200
    assert response.json()["id"] == SAMPLE


@pytest.mark.upstream
@pytest.mark.parametrize("value", [None, {}, [], -1])
def test_raw_ulid_wrong_json_types_raise_500(http, value):
    response = post_id(http, "raw", value)
    assert response.status_code == 500
    assert response.exc_info[0] in (TypeError, OverflowError)


@pytest.mark.upstream
def test_raw_ulid_validation_accepts_numeric_id():
    payload = RawEcho.model_validate({"id": 42})
    assert str(payload.id) == "0000000000000000000000001A"


@pytest.mark.parametrize("value, error_type, ctx", INVALID_ULIDS)
def test_adapter_validation_errors(value, error_type, ctx):
    with pytest.raises(ValidationError) as error:
        TypeAdapter(ApiULID).validate_python(value)
    detail = error.value.errors()[0]
    assert detail["type"] == error_type
    assert detail.get("ctx") == ctx


@pytest.mark.parametrize("value, error_type, ctx", INVALID_ULIDS)
def test_adapter_rejects_invalid_input_with_422(http, value, error_type, ctx):
    response = post_id(http, "adapted", value)
    assert response.status_code == 422
    detail = response.json()["detail"][0]
    assert detail["loc"] == ["body", "payload", "id"]
    assert detail["type"] == error_type
    assert detail.get("ctx") == ctx


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


@pytest.mark.upstream
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
    adapter = TypeAdapter(ApiULID)
    assert adapter.validate_python(item.pk) == item.pk
    assert adapter.dump_json(item.pk).decode() == json.dumps(str(item.pk))
