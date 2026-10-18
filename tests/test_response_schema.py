from types import SimpleNamespace
from uuid import UUID

import pytest
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.test.utils import isolate_apps
from django.utils.translation import gettext_lazy as _
from pydantic import ValidationError
from ulid import ULID
from ulid_django.models import ULIDField

from poc.adapter import create_ulid_response_schema
from poc.api import api
from poc.models import Item
from poc.schemas import AdaptedItem

SAMPLE = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@pytest.fixture
def schema_models():
    calls = []

    def generate_default():
        calls.append("generated")
        return ULID()

    with isolate_apps("poc"):
        class Reference(models.Model):
            key = ULIDField(primary_key=True, default=ULID)
            code = models.CharField(max_length=20, unique=True)

            class Meta:
                app_label = "poc"

        class IntegerReference(models.Model):
            external_id = ULIDField(unique=True)
            code = models.CharField(max_length=20, unique=True)

            class Meta:
                app_label = "poc"

        class UUIDReference(models.Model):
            key = models.UUIDField(primary_key=True)

            class Meta:
                app_label = "poc"

        class CustomULIDField(ULIDField):
            pass

        class Subject(models.Model):
            key = ULIDField(primary_key=True, default=ULID, verbose_name=_("公開ID"), help_text=_("保存済みのID"))
            nullable_id = ULIDField(null=True, default=None)
            blank_id = ULIDField(blank=True)
            fixed_id = ULIDField(default=ULID.from_str(SAMPLE))
            generated_id = ULIDField(default=generate_default, verbose_name="public token", help_text="Stored token")
            custom_id = CustomULIDField(verbose_name="API token")
            owner = models.ForeignKey(
                Reference, null=True, on_delete=models.SET_NULL, db_column="owner_ref",
                related_name="owned_subjects", verbose_name=_("所有者"), help_text=_("所有者のID"),
            )
            integer_owner = models.ForeignKey(IntegerReference, on_delete=models.CASCADE)
            uuid_owner = models.ForeignKey(UUIDReference, on_delete=models.CASCADE)
            tags = models.ManyToManyField(Reference, blank=True, related_name="tagged_subjects")
            owner_by_code = models.ForeignKey(Reference, to_field="code", related_name="coded_subjects", on_delete=models.CASCADE)
            owner_by_ulid = models.ForeignKey(IntegerReference, to_field="external_id", related_name="ulid_subjects", on_delete=models.CASCADE)
            integer_by_code = models.ForeignKey(IntegerReference, to_field="code", related_name="coded_subjects", on_delete=models.CASCADE)
            owner_by_pk = models.ForeignKey(Reference, to_field="key", related_name="pk_subjects", on_delete=models.CASCADE)
            profile = models.OneToOneField(Reference, related_name="profile_subject", on_delete=models.CASCADE)

            class Meta:
                app_label = "poc"

        class CompositeSubject(models.Model):
            pk = models.CompositePrimaryKey("tenant_id", "sequence")
            tenant_id = models.IntegerField()
            sequence = models.IntegerField()

            class Meta:
                app_label = "poc"

        yield SimpleNamespace(subject=Subject, reference=Reference, composite=CompositeSubject, calls=calls)


@pytest.mark.parametrize("fields", [[], None])
def test_empty_selection_is_rejected_instead_of_exposing_all_fields(fields):
    with pytest.raises(ValueError, match="fields must be a non-empty list"):
        create_ulid_response_schema(Item, name="EmptySelection", fields=fields)


def test_unknown_field_is_rejected():
    with pytest.raises(FieldDoesNotExist):
        create_ulid_response_schema(Item, name="UnknownSelection", fields=["not_a_field"])


@pytest.mark.parametrize("field_name", ["owner_by_code", "owner_by_ulid", "integer_by_code"])
def test_non_pk_to_field_is_rejected_before_ulid_type_selection(schema_models, field_name):
    with pytest.raises(ValueError, match=rf"{field_name}: to_field"):
        create_ulid_response_schema(schema_models.subject, name="NonPKReference", fields=[field_name])


def test_explicit_pk_reference_has_the_same_normalized_metadata_as_default(schema_models):
    subject = schema_models.subject
    assert "to_field" not in subject._meta.get_field("owner").deconstruct()[3]
    assert "to_field" not in subject._meta.get_field("owner_by_pk").deconstruct()[3]
    schema = create_ulid_response_schema(subject, name="ExplicitPKReference", fields=["owner_by_pk"])
    assert schema.model_validate({"owner_by_pk_id": SAMPLE}).model_dump() == {"owner_by_pk": SAMPLE}


def test_only_selected_fields_are_exposed(schema_models):
    schema = create_ulid_response_schema(schema_models.subject, name="SelectedKey", fields=["key"])
    assert list(schema.model_fields) == ["key"]
    # Unsupported relations elsewhere on the model do not prevent a safe selection.
    assert schema.model_validate({"key": SAMPLE}).model_dump() == {"key": SAMPLE}


@pytest.mark.parametrize("field_name", ["owned_subjects", "tagged_subjects", "profile_subject"])
def test_reverse_relations_are_rejected(schema_models, field_name):
    with pytest.raises(ValueError, match="only forward ForeignKey and ManyToManyField"):
        create_ulid_response_schema(schema_models.reference, name="ReverseReference", fields=[field_name])


def test_forward_one_to_one_is_explicitly_unsupported(schema_models):
    with pytest.raises(ValueError, match="OneToOneField is not supported"):
        create_ulid_response_schema(schema_models.subject, name="OneToOneReference", fields=["profile"])


def test_composite_primary_key_is_explicitly_unsupported(schema_models):
    with pytest.raises(ValueError, match="composite primary keys"):
        create_ulid_response_schema(schema_models.composite, name="CompositeResponse", fields=["tenant_id"])


@pytest.mark.parametrize("field_name", ["key", "nullable_id", "blank_id", "fixed_id", "generated_id", "owner", "tags"])
def test_overridden_response_fields_are_required_without_model_defaults(schema_models, field_name):
    schema = create_ulid_response_schema(schema_models.subject, name="RequiredResponse", fields=[field_name])
    with pytest.raises(ValidationError) as error:
        schema.model_validate({})
    assert error.value.errors()[0]["type"] == "missing"
    assert schema_models.calls == []
    assert schema.model_json_schema(by_alias=False)["required"] == [field_name]


@pytest.mark.parametrize("field_name, allowed", [("key", False), ("blank_id", False), ("nullable_id", True), ("owner", True)])
def test_null_is_allowed_only_when_the_model_field_is_nullable(schema_models, field_name, allowed):
    schema = create_ulid_response_schema(schema_models.subject, name="NullableResponse", fields=[field_name])
    source_name = "owner_id" if field_name == "owner" else field_name
    if allowed:
        assert schema.model_validate({source_name: None}).model_dump() == {field_name: None}
    else:
        with pytest.raises(ValidationError):
            schema.model_validate({source_name: None})


def test_title_description_and_lazy_translations_are_preserved(schema_models):
    schema = create_ulid_response_schema(
        schema_models.subject, name="LabeledResponse", fields=["key", "generated_id", "custom_id", "owner"],
    )
    fields = schema.model_json_schema(by_alias=False)["properties"]
    assert fields["key"]["title"] == "公開ID"
    assert fields["key"]["description"] == "保存済みのID"
    assert fields["owner"]["title"] == "所有者"
    assert fields["owner"]["description"] == "所有者のID"
    assert fields["generated_id"]["title"] == "Public Token"
    assert fields["generated_id"]["description"] == "Stored token"
    assert fields["custom_id"]["title"] == "API token"


def test_ulid_field_subclass_is_supported(schema_models):
    schema = create_ulid_response_schema(schema_models.subject, name="SubclassResponse", fields=["custom_id"])
    assert schema.model_validate({"custom_id": SAMPLE.lower()}).model_dump() == {"custom_id": SAMPLE}


def test_fk_alias_uses_python_attribute_instead_of_database_column(schema_models, db, django_assert_num_queries):
    schema = create_ulid_response_schema(schema_models.subject, name="RenamedPKResponse", fields=["key", "owner"])
    instance = schema_models.subject(key=ULID.from_str(SAMPLE), owner_id=ULID.from_str(SAMPLE))
    schema_models.calls.clear()
    with django_assert_num_queries(0):
        result = schema.model_validate(instance)
    assert result.model_dump() == {"key": SAMPLE, "owner": SAMPLE}
    assert result.model_dump(by_alias=True) == {"key": SAMPLE, "owner_id": SAMPLE}


def test_uuid_and_integer_fk_types_are_unchanged(schema_models):
    schema = create_ulid_response_schema(
        schema_models.subject, name="OrdinaryFKResponse", fields=["integer_owner", "uuid_owner"],
    )
    uuid_value = UUID("12345678-1234-4678-9234-567812345678")
    result = schema.model_validate({"integer_owner_id": 42, "uuid_owner_id": uuid_value})
    assert result.integer_owner == 42
    assert isinstance(result.uuid_owner, UUID)
    assert result.model_dump(mode="json") == {"integer_owner": 42, "uuid_owner": str(uuid_value)}
    fields = schema.model_json_schema(by_alias=False)["properties"]
    assert fields["integer_owner"]["type"] == "integer"
    assert fields["uuid_owner"]["format"] == "uuid"


def test_prefetched_response_does_not_fetch_owner_or_repeat_m2m_query(item, django_assert_num_queries):
    with django_assert_num_queries(0):
        result = AdaptedItem.model_validate(item).model_dump()
    assert result["owner"] == str(item.owner_id)
    assert result["tags"]


@pytest.mark.parametrize("source_kind", ["manager", "queryset", "models", "ulids", "strings", "tuple"])
def test_related_id_conversion_accepts_supported_collection_sources(item, source_kind, django_assert_num_queries):
    schema = create_ulid_response_schema(Item, name="RelatedIDCollection", fields=["tags"])
    tags = list(item.tags.all())
    sources = {
        "manager": item.tags,
        "queryset": item.tags.all(),
        "models": tags,
        "ulids": [tag.pk for tag in tags],
        "strings": [str(tag.pk).lower() for tag in tags],
        "tuple": tuple(tags),
    }
    with django_assert_num_queries(0):
        result = schema.model_validate({"tags": sources[source_kind]}).model_dump()
    assert result == {"tags": [str(tag.pk) for tag in tags]}


def test_many_to_many_does_not_accept_null():
    schema = create_ulid_response_schema(Item, name="NonNullRelatedIDs", fields=["tags"])
    with pytest.raises(ValidationError):
        schema.model_validate({"tags": None})
    assert schema.model_validate({"tags": []}).model_dump() == {"tags": []}


@pytest.mark.parametrize("by_alias, prefix, owner_name", [(False, "adapted", "owner"), (True, "adapted-alias", "owner_id")])
def test_http_alias_and_openapi_property_names_match(http, item, by_alias, prefix, owner_name):
    response = http.get(f"/api/{prefix}/items/{item.pk}")
    assert response.status_code == 200
    body = response.json()
    assert body[owner_name] == str(item.owner_id)
    assert ("owner" if by_alias else "owner_id") not in body
    spec = api.get_openapi_schema()
    output = spec["paths"][f"/api/{prefix}/items/{{item_id}}"]["get"]["responses"][200]["content"]["application/json"]["schema"]
    definition = spec["components"]["schemas"][output["$ref"].rsplit("/", 1)[1]]
    assert owner_name in definition["properties"]
    assert owner_name in definition["required"]


def test_explicit_modelschema_overrides_handle_real_relations(http, item):
    response = http.get(f"/api/explicit/items/{item.pk}")
    assert response.status_code == 200
    assert response.json() == http.get(f"/api/adapted/items/{item.pk}").json()


@pytest.mark.parametrize("order", [(False, True), (True, False)])
def test_ninja_171_shares_component_between_mixed_alias_modes(order):
    """Record why the PoC gives the two alias modes separate schema names."""
    from alias_cases import observe_mixed_aliases

    observed = observe_mixed_aliases(order)
    assert observed["responses"]["plain"] == {"status": 200, "body": {"owner": "example"}}
    assert observed["responses"]["aliased"] == {"status": 200, "body": {"owner_id": "example"}}
    assert len(set(observed["openapi_response_refs"].values())) == 1
    expected = ["owner_id" if order[-1] else "owner"]
    assert observed["documented_properties"] == {"plain": expected, "aliased": expected}


def test_single_mode_serialization_alias_matches_openapi():
    from alias_cases import observe_serialization_alias

    observed = observe_serialization_alias()
    assert observed["responses"]["aliased"] == {"status": 200, "body": {"alias1": "foo", "alias2": "bar"}}
    assert set(observed["documented_properties"]["aliased"]) == {"alias1", "alias2"}
