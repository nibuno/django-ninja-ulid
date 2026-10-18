"""Validation and serialization of the 26-character ULID representation."""

import re
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer, WithJsonSchema
from ulid import ULID

_ULID_PATTERN = "^[0-7][0-9A-HJKMNP-TV-Z]{25}$"
_ULID_INPUT_PATTERN = "^[0-7][0-9A-HJKMNP-TV-Za-hjkmnp-tv-z]{25}$"


def _parse_api_ulid(value: Any) -> ULID:
    if isinstance(value, ULID):
        return value
    if not isinstance(value, str) or not value.isascii():
        raise ValueError("ULID must be a 26-character ASCII string")
    canonical = value.upper()
    if re.fullmatch(_ULID_PATTERN, canonical) is None:
        raise ValueError("ULID must contain 26 Base32 characters and start with 0–7")
    return ULID.from_str(canonical)


ApiULID = Annotated[
    ULID,
    BeforeValidator(_parse_api_ulid),
    PlainSerializer(str, return_type=str, when_used="always"),
    WithJsonSchema(
        {
            "type": "string",
            "minLength": 26,
            "maxLength": 26,
            "pattern": _ULID_INPUT_PATTERN,
            "examples": ["01ARZ3NDEKTSV4RRFFQ69G5FAV"],
        }
    ),
]
