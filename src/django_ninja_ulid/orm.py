"""Flat response schemas for python-ulid-django model fields.

Install ``django-ninja-ulid[orm]`` and initialize Django before importing this
module. The package root and ApiULID do not import the optional field library.
"""

from typing import Annotated, Any

try:
    from ulid_django.models import ULIDField
except ModuleNotFoundError as error:
    if error.name != "ulid_django":
        raise
    raise ImportError(
        "Django model integration requires python-ulid-django. "
        "Install django-ninja-ulid[orm] to use django_ninja_ulid.orm."
    ) from error

from django.db import models
from ninja import Schema
from ninja.orm import create_schema
from pydantic import BeforeValidator, Field

from . import ApiULID

__all__ = ["create_ulid_response_schema", "related_ids"]


def related_ids(value: Any) -> Any:
    if isinstance(value, models.Manager):
        value = value.all()
    if isinstance(value, models.QuerySet):
        value = list(value)
    if isinstance(value, (list, tuple)):
        return [item.pk if isinstance(item, models.Model) else item for item in value]
    return value


def _ulid_target(field: models.Field) -> models.Field:
    if not field.is_relation:
        return field

    if isinstance(field, models.OneToOneField):
        raise ValueError(f"{field.name}: OneToOneField is not supported")
    if isinstance(field, models.ForeignKey):
        # Explicit references to the primary key normalize to ordinary FK metadata.
        if "to_field" in field.deconstruct()[3]:
            raise ValueError(f"{field.name}: to_field references are not supported")
    elif not isinstance(field, models.ManyToManyField):
        raise ValueError(
            f"{field.name}: only forward ForeignKey and ManyToManyField are supported"
        )

    target = field.related_model._meta.pk
    if isinstance(target, models.CompositePrimaryKey):
        raise ValueError(f"{field.name}: composite primary keys are not supported")
    return target


def create_ulid_response_schema(
    model: type[models.Model], *, name: str, fields: list[str]
) -> type[Schema]:
    """Create a flat response schema using stored IDs and forward PK relations.

    Selected fields must be non-empty. Non-PK to_field references, reverse
    relations, OneToOneField, and composite primary keys are rejected.
    Request/PATCH defaults, nesting, and other field libraries are unsupported.
    """
    if not fields:
        raise ValueError("fields must be a non-empty list of model field names")
    if isinstance(model._meta.pk, models.CompositePrimaryKey):
        raise ValueError("composite primary keys are not supported")

    overrides = []
    for field_name in fields:
        field = model._meta.get_field(field_name)
        ulid_field = _ulid_target(field)
        if not isinstance(ulid_field, ULIDField):
            continue
        if field.many_to_many:
            annotation = Annotated[list[ApiULID], BeforeValidator(related_ids)]
        else:
            annotation = ApiULID | None if field.null else ApiULID

        title = str(field.verbose_name)
        if title == title.lower():
            title = title.title()
        overrides.append(
            (
                field_name,
                annotation,
                Field(
                    ...,
                    title=title,
                    description=str(field.help_text) if field.help_text else None,
                    alias=field.attname if field.is_relation else None,
                ),
            )
        )
    return create_schema(model, name=name, fields=fields, custom_fields=overrides)
