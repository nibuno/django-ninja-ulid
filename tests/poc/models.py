import uuid

from django.db import models
from ulid import ULID
from ulid_django.models import ULIDField


class Owner(models.Model):
    id = ULIDField(primary_key=True, default=ULID, editable=False)
    name = models.CharField(max_length=80)


class Tag(models.Model):
    id = ULIDField(primary_key=True, default=ULID, editable=False)
    name = models.CharField(max_length=80)


class Item(models.Model):
    id = ULIDField(primary_key=True, default=ULID, editable=False)
    public_uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80)
    owner = models.ForeignKey(Owner, null=True, blank=True, on_delete=models.SET_NULL)
    tags = models.ManyToManyField(Tag, blank=True)
