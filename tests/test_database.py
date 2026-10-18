"""Run the persistence check on the selected database, including PostgreSQL."""

import os
from uuid import UUID

from django.db import connection
from ulid import ULID

from poc.models import Item


def test_database_selection_and_native_id_round_trip(item):
    expected = os.environ.get("ULID_TEST_DATABASE", "sqlite")
    assert connection.vendor == expected
    restored = Item.objects.prefetch_related("tags").get(pk=item.pk)
    assert isinstance(restored.pk, ULID)
    assert isinstance(restored.owner_id, ULID)
    assert isinstance(restored.public_uuid, UUID)
    assert restored.pk == item.pk
    assert restored.owner_id == item.owner_id
    assert [tag.pk for tag in restored.tags.all()] == [tag.pk for tag in item.tags.all()]
