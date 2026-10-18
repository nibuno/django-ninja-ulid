import pytest
from django.test import Client
from ulid import ULID

from poc.models import Item, Owner, Tag


@pytest.fixture
def http():
    return Client(raise_request_exception=False)


@pytest.fixture
def item(db):
    owner = Owner.objects.create(name="owner")
    tag = Tag.objects.create(name="tag")
    item = Item.objects.create(name="sample", owner=owner)
    item.tags.add(tag)
    return Item.objects.prefetch_related("tags").get(pk=item.pk)


@pytest.fixture
def ulid_text():
    return str(ULID())
