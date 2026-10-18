# django-ninja-ulid

[![CI](https://github.com/nibuno/django-ninja-ulid/actions/workflows/ci.yml/badge.svg)](https://github.com/nibuno/django-ninja-ulid/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/nibuno/django-ninja-ulid/blob/main/LICENSE)

[Django Ninja](https://django-ninja.dev/)のAPIで、[ULID](https://github.com/ulid/spec)を26文字の文字列として入出力するためのライブラリです。

- **`ApiULID`**：ULIDを検証・正規化し、26文字の文字列として出力するPydanticの型
- **`create_ulid_response_schema`**：ULIDFieldを含むDjangoモデルから、応答用のSchemaを作る関数

IDの保存と生成は、既存の[python-ulid-django](https://pypi.org/project/python-ulid-django/)に任せます。このライブラリは、API側の型と変換だけを担当します。

## なぜ必要か

python-ulid-djangoの`ULIDField`をDjango Ninjaの`ModelSchema`でそのまま使うと、次の問題が起きます。

- `ULIDField`は`UUIDField`を継承しているため、NinjaはこのフィールドをUUID型として扱います。26文字のULIDを入力すると、UUIDとして検証されて422になります。
- 応答では、ULIDオブジェクトがJSONに変換できず、500になります。
- `register_field("UUIDField", ...)`で型を差し替えると、通常の`UUIDField`までULIDとして扱われてしまいます。

このライブラリは、ULIDのフィールドだけを判別して型を差し替えます。通常のUUIDはUUIDのまま残ります。

## インストール

```bash
# 型（ApiULID）だけを使う場合
pip install django-ninja-ulid

# Djangoモデルとの連携も使う場合
pip install "django-ninja-ulid[orm]"
```

`orm` extraを付けると、python-ulid-djangoも一緒にインストールされます。

## 使い方

### `ApiULID`：入力と出力の型

```python
from ninja import NinjaAPI, Schema
from django_ninja_ulid import ApiULID

api = NinjaAPI()


class ItemIn(Schema):
    owner_id: ApiULID


@api.get("/items/{item_id}")
def get_item(request, item_id: ApiULID):
    ...
```

- 入力は26文字のASCII文字列だけを受け付けます。小文字は大文字に正規化します。
- 使えない文字、128bitを超える値（先頭が8以降）、整数・真偽値・null・オブジェクト・配列は、422の検証エラーになります。
- 出力は、常に大文字26文字の文字列です。
- nullを許可したい場合は、`ApiULID | None`と書きます。
- `ApiULID`だけを使う場合は、Djangoの設定もpython-ulid-djangoも読み込みません。Pydanticの`TypeAdapter`からも使えます。

### `create_ulid_response_schema`：モデルから応答Schemaを作る

```python
from django.db import models
from ulid import ULID
from ulid_django.models import ULIDField


class Owner(models.Model):
    id = ULIDField(primary_key=True, default=ULID, editable=False)


class Tag(models.Model):
    id = ULIDField(primary_key=True, default=ULID, editable=False)


class Item(models.Model):
    id = ULIDField(primary_key=True, default=ULID, editable=False)
    public_uuid = models.UUIDField()
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(Owner, null=True, on_delete=models.SET_NULL)
    tags = models.ManyToManyField(Tag)
```

```python
from django_ninja_ulid.orm import create_ulid_response_schema

ItemOut = create_ulid_response_schema(
    Item,
    name="ItemOut",
    fields=["id", "public_uuid", "name", "owner", "tags"],
)


@api.get("/items/{item_id}", response=ItemOut)
def get_item(request, item_id: ApiULID):
    return Item.objects.prefetch_related("tags").get(pk=str(item_id))
```

```json
{
  "id": "01JABCDXYZ0123456789ABCDEF",
  "public_uuid": "8f14e45f-ceea-467f-a0e6-4b6f8b8a8c1d",
  "name": "example",
  "owner": "01JABCDXYZ0123456789ABCDEG",
  "tags": ["01JABCDXYZ0123456789ABCDEH"]
}
```

- ULIDのフィールドだけを`ApiULID`に差し替えます。ULID以外のフィールドは、Ninjaの型推論のまま残ります。
- 外部キーと多対多は、関連先のモデルではなく主キーのULIDを返します。
- 公開するフィールドは`fields`で必ず指定します。空のリストは拒否します。
- `django_ninja_ulid.orm`は、Djangoの初期化が終わってからimportしてください。

| モデルの定義 | 応答での扱い |
|---|---|
| ULIDField（`null=False`） | 必須、nullにならない |
| ULIDField・外部キー（`null=True`） | 必須、nullになりうる |
| 多対多 | 必須、空の配列はありうる、nullにならない |
| ULID以外のフィールド | Ninjaの通常の扱いのまま |

### 手書きの`ModelSchema`で使う

Schemaを自分で書く場合は、`ApiULID`と`related_ids`を組み合わせます。

```python
from typing import Annotated

from ninja import ModelSchema
from pydantic import BeforeValidator, Field

from django_ninja_ulid import ApiULID
from django_ninja_ulid.orm import related_ids


class ItemOut(ModelSchema):
    id: ApiULID
    owner: ApiULID | None = Field(..., alias="owner_id")
    tags: Annotated[list[ApiULID], BeforeValidator(related_ids)]

    class Meta:
        model = Item
        fields = ["id", "public_uuid", "name", "owner", "tags"]
```

`related_ids`は、Manager・QuerySet・モデルのリストを主キーのリストに変換します。

## 対応範囲

`create_ulid_response_schema`は、ネストしない応答専用です。次の設定を渡すと`ValueError`になります。

- 空の`fields`
- 主キー以外を参照する`to_field`付きの外部キー
- 逆参照、`OneToOneField`、複合主キー

入力用・PATCH用Schemaの自動生成、ネストした応答、python-ulid-django以外のULIDFieldには、まだ対応していません。

## 既知の制限

- Ninja 1.7.1では、同じSchemaを`by_alias`の設定が違うルートで使い回すと、OpenAPIの定義が後から登録したほうで上書きされます。HTTPの応答自体は正しく返ります。出力形式ごとに、別の`name`でSchemaを作ってください。
- OpenAPIでは入力と応答に同じ文字パターンを使っているため、応答側も小文字を許すように書かれます。実際の出力は常に大文字です。

## 動作確認済みの環境

| Python | Django | DB |
|---|---|---|
| 3.12 / 3.13 / 3.14 | 5.2.18 / 6.1.2 | SQLite / PostgreSQL 18.6 |

上の12通りすべての組み合わせを、GitHub Actionsで検証しています。依存ライブラリは、検証済みの次の版に固定しています。

- Django Ninja 1.7.1
- Pydantic 2.13.5
- python-ulid 4.0.1
- python-ulid-django 1.6.0（`orm` extra）

詳しい検証内容は[docs/compatibility.md](https://github.com/nibuno/django-ninja-ulid/blob/main/docs/compatibility.md)にまとめています。

## バージョンの方針

公開APIは、`ApiULID`、`create_ulid_response_schema`、`related_ids`の3つです。

0.x系の間は、互換性のない変更をマイナーバージョン（例：0.1 → 0.2）で、互換性を保つ修正をパッチバージョン（例：0.1.0 → 0.1.1）で出します。変更内容と移行方法は[CHANGELOG](https://github.com/nibuno/django-ninja-ulid/blob/main/CHANGELOG.md)に記録します。詳しくは[docs/versioning.md](https://github.com/nibuno/django-ninja-ulid/blob/main/docs/versioning.md)を見てください。

## 開発に参加する

不具合の報告や開発の手順は、[CONTRIBUTING.md](https://github.com/nibuno/django-ninja-ulid/blob/main/CONTRIBUTING.md)にまとめています。

## ライセンス

[MIT License](https://github.com/nibuno/django-ninja-ulid/blob/main/LICENSE)
