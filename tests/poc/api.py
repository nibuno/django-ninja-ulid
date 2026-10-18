from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Status
from ulid import ULID

from .adapter import ApiULID
from .models import Item, Owner, Tag
from .schemas import (
    AdaptedItem,
    AliasedItem,
    ApiEcho,
    AutoIdentity,
    AutoItem,
    CreateItem,
    ExplicitItem,
    ManualFixedItem,
    ManualItem,
    RawEcho,
)

api = NinjaAPI(title="ULID integration experiment", urls_namespace="ulid-poc")


@api.post("/auto/echo", response=AutoIdentity)
def auto_echo(request, payload: AutoIdentity):
    return payload


@api.post("/raw/echo", response=RawEcho)
def raw_echo(request, payload: RawEcho):
    return payload


@api.post("/adapted/echo", response=ApiEcho)
def adapted_echo(request, payload: ApiEcho):
    return payload


@api.get("/raw/path/{item_id}", response=RawEcho)
def raw_path(request, item_id: ULID):
    return {"id": item_id}


@api.get("/adapted/path/{item_id}", response=ApiEcho)
def adapted_path(request, item_id: ApiULID):
    return {"id": item_id}


@api.get("/adapted/query", response=ApiEcho)
def adapted_query(request, item_id: ApiULID):
    return {"id": item_id}


def find_item(item_id):
    return get_object_or_404(Item.objects.prefetch_related("tags"), pk=item_id)


@api.get("/auto/items/{item_id}", response=AutoItem)
def auto_item(request, item_id: ULID):
    return find_item(item_id)


@api.get("/manual/items/{item_id}", response=ManualItem)
def manual_item(request, item_id: ULID):
    return find_item(item_id)


@api.get("/adapted/items/{item_id}", response=AdaptedItem)
def adapted_item(request, item_id: ApiULID):
    return find_item(item_id)


@api.get("/adapted-alias/items/{item_id}", response=AliasedItem, by_alias=True)
def adapted_alias_item(request, item_id: ApiULID):
    return find_item(item_id)


@api.get("/explicit/items/{item_id}", response=ExplicitItem)
def explicit_item(request, item_id: ApiULID):
    return find_item(item_id)


@api.get("/manual-fixed/items/{item_id}", response=ManualFixedItem)
def manual_fixed_item(request, item_id: ApiULID):
    return find_item(item_id)


@api.post("/adapted/items", response={201: AdaptedItem})
def create_item(request, payload: CreateItem):
    owner = get_object_or_404(Owner, pk=payload.owner) if payload.owner else None
    tags = [get_object_or_404(Tag, pk=tag_id) for tag_id in payload.tags]
    item = Item.objects.create(name=payload.name, owner=owner)
    item.tags.set(tags)
    return Status(201, item)
