import json
import random
import re
from uuid import UUID

import pytest
from ninja import NinjaAPI, Schema
from pydantic import Json, TypeAdapter, ValidationError
from ulid import ULID

from poc.adapter import ApiULID
from poc.api import api
from poc.models import Item
from poc.schemas import AdaptedItem, AutoItem, RawEcho

SAMPLE = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
MAX_ULID = "7" + "Z" * 25
INPUT_PATTERN = "^[0-7][0-9A-HJKMNP-TV-Za-hjkmnp-tv-z]{25}$"
OUTPUT_PATTERN = "^[0-7][0-9A-HJKMNP-TV-Z]{25}$"
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
    (" " + SAMPLE, "ulid_length", {"actual_length": 27}),
    (SAMPLE + " ", "ulid_length", {"actual_length": 27}),
    (f" {SAMPLE} ", "ulid_length", {"actual_length": 28}),
    (SAMPLE[:-1] + "\n", "ulid_parsing", None),
    (SAMPLE[:-1] + "I", "ulid_parsing", None),
    (SAMPLE[:-1] + "\N{LATIN SMALL LETTER LONG S}", "ulid_parsing", None),
    ("\N{FULLWIDTH DIGIT ZERO}" + SAMPLE[1:], "ulid_parsing", None),
    (SAMPLE[:-1] + "\N{FULLWIDTH LATIN CAPITAL LETTER V}", "ulid_parsing", None),
    ("8" + "Z" * 25, "ulid_parsing", None),
    ("Z" * 26, "ulid_parsing", None),
]


def post_id(http, mode, value):
    return http.post(
        f"/api/{mode}/echo", data=json.dumps({"id": value}), content_type="application/json"
    )


def json_component_name(body):
    return body["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[1]


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


@pytest.mark.parametrize(
    "value, error_type, ctx",
    [*INVALID_ULIDS, (SAMPLE.encode("ascii"), "ulid_type", None), (UUID(int=1), "ulid_type", None)],
)
def test_adapter_validation_errors(value, error_type, ctx):
    with pytest.raises(ValidationError) as error:
        TypeAdapter(ApiULID).validate_python(value)
    detail = error.value.errors()[0]
    assert detail["type"] == error_type
    assert detail.get("ctx") == ctx


def test_adapter_matches_input_pattern_and_round_trips():
    rng = random.Random(14)
    crockford = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    # Weight the alphabet to sample both valid strings and single-character near misses.
    alphabet = (crockford + crockford.lower()) * 4 + "ILOUilou０Ａſ"
    pattern = re.compile(INPUT_PATTERN)
    adapter = TypeAdapter(ApiULID)

    for _ in range(4096):
        value = "".join(rng.choices(alphabet, k=26))
        try:
            validated = adapter.validate_python(value)
        except ValidationError as error:
            assert pattern.fullmatch(value) is None, value
            assert error.errors()[0]["type"] == "ulid_parsing", value
        else:
            assert pattern.fullmatch(value) is not None, value
            assert isinstance(validated, ULID)
            assert str(validated) == value.upper() == str(ULID.from_str(value.upper()))


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


def test_list_query_preserves_repeated_ids_in_order(http):
    response = http.get("/api/adapted/query-list", {"ids": [MAX_ULID.lower(), SAMPLE.lower(), MAX_ULID.lower()]})
    assert response.status_code == 200
    assert response.json() == [MAX_ULID, SAMPLE, MAX_ULID]


@pytest.mark.parametrize(
    "invalid, error_type", [("short", "ulid_length"), ("8" + SAMPLE[1:], "ulid_parsing")],
)
def test_list_query_reports_invalid_element(http, invalid, error_type):
    response = http.get("/api/adapted/query-list", {"ids": [SAMPLE, invalid]})
    assert response.status_code == 422
    detail = response.json()["detail"][0]
    assert detail["loc"] == ["query", "ids", 1]
    assert detail["type"] == error_type


def test_query_schema_parses_ulid_fields(http):
    response = http.get("/api/adapted/query-filters", {"owner": SAMPLE.lower(), "tag": MAX_ULID.lower()})
    assert response.status_code == 200
    assert response.json() == {"owner": SAMPLE, "tag": MAX_ULID}


def test_query_schema_reports_invalid_field(http):
    response = http.get("/api/adapted/query-filters", {"owner": SAMPLE, "tag": SAMPLE[:-1] + "I"})
    assert response.status_code == 422
    detail = response.json()["detail"][0]
    assert detail["loc"] == ["query", "tag"]
    assert detail["type"] == "ulid_parsing"


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
    spec = api.get_openapi_schema()
    schemas = spec["components"]["schemas"]
    auto_id = schemas["AutoIdentity"]["properties"]["id"]
    assert any(value.get("format") == "uuid" for value in auto_id["anyOf"])
    operation = spec["paths"]["/api/adapted/items"]["post"]
    request = schemas[json_component_name(operation["requestBody"])]["properties"]
    assert request["tags"]["items"]["pattern"] == INPUT_PATTERN
    adapted = schemas[json_component_name(operation["responses"][201])]["properties"]
    owner_id = next(option for option in adapted["owner"]["anyOf"] if option["type"] == "string")
    for field in (adapted["id"], owner_id, adapted["tags"]["items"]):
        assert field["type"] == "string"
        assert field["minLength"] == field["maxLength"] == 26
        assert field["pattern"] == OUTPUT_PATTERN
        assert "anyOf" not in field
    assert adapted["public_uuid"]["format"] == "uuid"


@pytest.mark.upstream
def test_raw_ulid_openapi_advertises_binary_alternative():
    alternatives = RawEcho.model_json_schema()["properties"]["id"]["anyOf"]
    assert any(value.get("format") == "binary" for value in alternatives)


@pytest.mark.parametrize("mode", ["validation", "serialization"])
def test_public_adapter_advertises_permissive_pattern_in_both_modes(mode):
    assert TypeAdapter(ApiULID).json_schema(mode=mode) == {
        "type": "string",
        "minLength": 26,
        "maxLength": 26,
        "pattern": INPUT_PATTERN,
        "examples": [SAMPLE],
    }


def test_hand_written_schema_keeps_shared_request_and_response_permissive():
    spec = api.get_openapi_schema()
    operation = spec["paths"]["/api/adapted/echo"]["post"]
    later_get = spec["paths"]["/api/adapted/query"]["get"]
    schemas = spec["components"]["schemas"]
    for body in (operation["requestBody"], operation["responses"][200], later_get["responses"][200]):
        assert schemas[json_component_name(body)]["properties"]["id"]["pattern"] == INPUT_PATTERN


@pytest.mark.upstream
@pytest.mark.parametrize("later_response, field_type", [(False, "string"), (True, "integer")])
def test_ninja_reuses_last_definition_for_shared_schema(later_response, field_type):
    """Json[int] takes a JSON string on input and serializes to an integer."""

    class Shared(Schema):
        value: Json[int]

    probe = NinjaAPI()

    @probe.post("/echo", response=Shared)
    def echo(request, payload: Shared):
        return payload

    if later_response:
        @probe.get("/read", response=Shared)
        def read(request):
            return {"value": "1"}

    spec = probe.get_openapi_schema(path_prefix="")
    operation = spec["paths"]["/echo"]["post"]
    name = json_component_name(operation["requestBody"])
    assert json_component_name(operation["responses"][200]) == name
    assert spec["components"]["schemas"][name]["properties"]["value"]["type"] == field_type


def test_ulid_instances_and_canonical_output(item):
    adapter = TypeAdapter(ApiULID)
    assert adapter.validate_python(item.pk) == item.pk
    assert adapter.dump_json(item.pk).decode() == json.dumps(str(item.pk))
