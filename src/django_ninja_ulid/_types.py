"""Validation and serialization of the 26-character ULID representation."""

import re
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer, WithJsonSchema
from pydantic_core import PydanticCustomError
from ulid import ULID

_ULID_INPUT_PATTERN = "^[0-7][0-9A-HJKMNP-TV-Za-hjkmnp-tv-z]{25}$"
_ULID_INPUT_SCHEMA = {
    "type": "string",
    "minLength": 26,
    "maxLength": 26,
    "pattern": _ULID_INPUT_PATTERN,
    "examples": ["01ARZ3NDEKTSV4RRFFQ69G5FAV"],
}


def _parse_api_ulid(value: Any) -> ULID:
    if isinstance(value, ULID):
        return value
    if not isinstance(value, str):
        raise PydanticCustomError("ulid_type", "ULID must be a string")
    length = len(value)
    if length != 26:
        raise PydanticCustomError(
            "ulid_length",
            "ULID must be 26 characters long (got {actual_length})",
            {"actual_length": length},
        )
    if re.fullmatch(_ULID_INPUT_PATTERN, value) is None:
        raise PydanticCustomError(
            "ulid_parsing",
            "ULID must use Crockford Base32 and start with a digit from 0 to 7",
        )
    return ULID.from_str(value.upper())


ApiULID = Annotated[
    ULID,
    BeforeValidator(_parse_api_ulid),
    PlainSerializer(str, return_type=str, when_used="always"),
    WithJsonSchema(_ULID_INPUT_SCHEMA),
]
