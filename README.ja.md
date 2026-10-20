# django-ninja-ulid

[![PyPI](https://img.shields.io/pypi/v/django-ninja-ulid.svg)](https://pypi.org/project/django-ninja-ulid/)
[![CI](https://github.com/nibuno/django-ninja-ulid/actions/workflows/ci.yml/badge.svg)](https://github.com/nibuno/django-ninja-ulid/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/nibuno/django-ninja-ulid/blob/main/LICENSE)

[English](https://github.com/nibuno/django-ninja-ulid/blob/main/README.md)

[Django Ninja](https://django-ninja.dev/)のAPIで、[ULID](https://github.com/ulid/spec)を26文字の文字列として受け取り、返すためのライブラリです。

Django Ninjaは、python-ulid-djangoの`ULIDField`をUUID型として扱います。このライブラリはULIDの検証と文字列化を行い、通常のUUIDフィールドを維持したまま応答Schemaを生成します。

- **`ApiULID`**：ULID文字列を検証するPydanticの型。Python上では`ulid.ULID`として扱い、出力時に大文字の文字列へ変換します。
- **`create_ulid_response_schema`**：Djangoモデルから、ネストしない応答Schemaを生成する関数。外部キーと多対多は関連先のIDを返します。
- **`related_ids`**：手書きのSchemaで、関連先のモデルを主キーに変換する関数。

IDの生成と保存には、既存の[python-ulid](https://github.com/mdomke/python-ulid)と[python-ulid-django](https://pypi.org/project/python-ulid-django/)を使います。

## インストール

`ApiULID`を使う場合は通常のインストール、Djangoモデルとの連携も使う場合は`orm` extraを指定します。

```bash
pip install django-ninja-ulid
pip install "django-ninja-ulid[orm]"
```

Python 3.12〜3.14に対応しています。現在はアルファ版で、依存ライブラリを検証済みの版に固定しています。

| 依存ライブラリ | バージョン指定 |
|---|---|
| Django | `>=5.2.18,<6.2`。`6.0.*`、`6.1.0`、`6.1.1`を除外 |
| Django Ninja | `==1.7.1` |
| Pydantic | `==2.13.5` |
| python-ulid | `==4.0.1` |
| python-ulid-django | `==1.6.0`（`orm` extra） |

導入前に、既存プロジェクトの依存条件と合うかを確認してください。通常のインストールにもDjangoとNinjaは含まれますが、`ApiULID`のimport時には読み込まず、Djangoの設定も必要ありません。`orm` extraを指定するとpython-ulid-djangoが追加されます。

## 最小の使い方

既存のDjangoプロジェクトのアプリ内に、`catalog/api.py`を作成します。以下ではアプリ名を`catalog`、プロジェクトのパッケージ名を`config`としています。実際の名前に合わせて読み替えてください。

```python
# catalog/api.py
from ninja import NinjaAPI, Schema

from django_ninja_ulid import ApiULID

api = NinjaAPI()


class Identifier(Schema):
    id: ApiULID


@api.post("/echo", response=Identifier)
def echo(request, payload: Identifier):
    return payload
```

プロジェクトのURL設定にAPIを追加します。既存のルートがある場合は、そのルートも残してください。

```python
# config/urls.py
from django.urls import path

from catalog.api import api

urlpatterns = [path("api/", api.urls)]
```

`python manage.py runserver`で開発サーバーを起動し、小文字のULIDを送ります。

```bash
curl http://127.0.0.1:8000/api/echo \
  -H 'Content-Type: application/json' \
  -d '{"id":"01arz3ndektsv4rrffq69g5fav"}'
```

HTTP 200で、大文字に正規化したULIDが返ります。

```json
{"id":"01ARZ3NDEKTSV4RRFFQ69G5FAV"}
```

`"invalid"`や`42`を送るとHTTP 422になります。関数内の`payload.id`は`ULID`オブジェクトで、応答Schemaによって文字列に変換されます。`ApiULID`はパス引数やクエリ引数にも使えます。次の例ではパス引数に指定します。

## Djangoモデルから応答Schemaを作る

`orm` extraをインストールし、アプリ（この例では`catalog`）を`INSTALLED_APPS`に追加します。ULIDの主キーと、nullを許可する外部キーを定義します。

```python
# catalog/models.py
import uuid

from django.db import models
from ulid import ULID
from ulid_django.models import ULIDField


class Owner(models.Model):
    id = ULIDField(primary_key=True, default=ULID, editable=False)


class Item(models.Model):
    id = ULIDField(primary_key=True, default=ULID, editable=False)
    public_uuid = models.UUIDField(default=uuid.uuid4)
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(Owner, null=True, on_delete=models.SET_NULL)
```

最小例の`catalog/api.py`を、次の内容に置き換えます。URL設定はそのまま使います。`django_ninja_ulid.orm`はDjangoの初期化後にimportしてください。この例では、URL設定から読み込まれるアプリのAPIモジュールでimportします。

```python
# catalog/api.py
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI

from django_ninja_ulid import ApiULID
from django_ninja_ulid.orm import create_ulid_response_schema

from .models import Item

api = NinjaAPI()

ItemOut = create_ulid_response_schema(
    Item,
    name="ItemOut",
    fields=["id", "public_uuid", "name", "owner"],
)


@api.get("/items/{item_id}", response=ItemOut)
def get_item(request, item_id: ApiULID):
    return get_object_or_404(Item, pk=item_id)
```

公開するフィールドは、空でない`fields`リストで指定します。ULIDフィールドと、ULIDの主キーを参照する関連だけを差し替えます。それ以外のフィールドはNinjaの型推論に従います。

テーブルを作り、確認用のデータを1件登録します。

```bash
python manage.py makemigrations catalog
python manage.py migrate
python manage.py shell -c 'from catalog.models import Item; print(Item.objects.create(name="example").pk)'
```

開発サーバーの起動中に`/api/items/<表示されたID>`へアクセスすると、次の形式で返ります。生成されるIDは例と異なります。

```json
{
  "id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "public_uuid": "8f14e45f-ceea-467f-a0e6-4b6f8b8a8c1d",
  "name": "example",
  "owner": null
}
```

ownerを設定した場合、`owner`には関連先のULID文字列が入ります。外部キーは`owner_id`から読み取るため、ownerオブジェクトの取得は行いません。ルートに`by_alias=True`を指定すると、出力のキーは`owner`から`owner_id`に変わります。後述のOpenAPIの制限も確認してください。

### 多対多の関連

ULIDを主キーとする`Tag`モデルを用意した場合は、`Item`に`tags = models.ManyToManyField(Tag)`を追加してマイグレーションを実行し、`ItemOut`の`fields`に`"tags"`を含めます。応答にはULID文字列のリストが入り、関連がなければ`[]`になります。

取得処理は`get_object_or_404(Item.objects.prefetch_related("tags"), pk=item_id)`に置き換えます。一覧を返す場合も、QuerySetに`prefetch_related("tags")`を指定すると、Itemごとにタグを取得するクエリを避けられます。Schemaの生成関数は、クエリの最適化を自動では行いません。

| 選択したフィールド | 応答での扱い |
|---|---|
| ULIDField・ULIDへの外部キー（`null=False`） | キーは常に含まれる。値はnullにならない |
| ULIDField・ULIDへの外部キー（`null=True`） | キーは常に含まれる。値はnullになりうる |
| ULIDの主キーを参照する多対多 | キーは常に含まれる。空のリストはありうるが、nullにはならない |
| ULID以外のフィールド | Ninjaの通常の扱いに従う |

## 手書きのSchemaで使う

Schemaを自分で定義する場合は、`ApiULID`を明示します。次のSchemaを`catalog/schemas.py`に置き、`catalog/api.py`で`from .schemas import ManualItemOut`をimportして、ルートに`response=ManualItemOut`を指定します。

```python
# catalog/schemas.py
from ninja import ModelSchema
from pydantic import Field

from django_ninja_ulid import ApiULID

from .models import Item


class ManualItemOut(ModelSchema):
    id: ApiULID
    owner: ApiULID | None = Field(..., alias="owner_id")

    class Meta:
        model = Item
        fields = ["id", "public_uuid", "name", "owner"]
```

多対多のフィールドには`related_ids`を使います。Manager・QuerySet・モデルのリストを、主キーのリストに変換します。次の定義を同じモジュールの`ManualItemOut`より前に置き、Djangoの初期化後にAPIモジュールから読み込んでください。

```python
# catalog/schemas.py (before ManualItemOut)
from typing import Annotated

from pydantic import BeforeValidator

from django_ninja_ulid import ApiULID
from django_ninja_ulid.orm import related_ids

RelatedULIDs = Annotated[list[ApiULID], BeforeValidator(related_ids)]
```

モデルに`tags`を追加したら、`ModelSchema`内に`tags: RelatedULIDs`を定義し、`Meta.fields`にも`"tags"`を含めてください。

## 検証と文字列化

- HTTPの入力は26文字のASCIIのULID文字列です。小文字も受け付け、大文字に正規化します。
- 先頭は`0`〜`7`に限ります。`I`・`L`・`O`・`U`とその小文字は拒否し、別の文字への読み替えは行いません。
- 数値・真偽値・null・オブジェクト・配列は拒否します。nullを許可する場合は`ApiULID | None`を指定します。
- Python上では、既存の`ulid.ULID`インスタンスも受け付けます。検証後の属性値は`ULID`オブジェクトで、`model_dump()`を含む出力処理では大文字の文字列になります。
- Ninjaの入力検証では、不正値に対してHTTP 422を返します。Pydanticから直接検証する場合は`ValidationError`になります。

Djangoの設定なしでも、次のように使えます。

```python
from pydantic import TypeAdapter
from ulid import ULID

from django_ninja_ulid import ApiULID

adapter = TypeAdapter(ApiULID)
value = adapter.validate_python("01arz3ndektsv4rrffq69g5fav")
assert isinstance(value, ULID)
assert adapter.dump_python(value) == "01ARZ3NDEKTSV4RRFFQ69G5FAV"
```

## ModelSchemaだけでは扱えない理由

固定した依存バージョンでは、次の問題が起きます。

- `ULIDField`は`UUIDField`を継承しているため、NinjaはUUID型として扱います。26文字のULIDを入力するとUUIDの検証でHTTP 422になり、ULIDを持つモデルを返すと応答の検証でHTTP 500になります。
- 手書きのSchemaで`ulid.ULID`型を直接指定するとUUIDの型推論は避けられますが、JSON変換時に`TypeError`が発生し、HTTP 500になる場合があります。
- `register_field("UUIDField", ...)`で全体の型を差し替えると、通常のUUIDフィールドも変更されます。

`ApiULID`は検証と文字列化を明示的に行います。`create_ulid_response_schema`は、選択したULIDフィールドと関連だけにこの型を適用します。

## 対応範囲と制限

`create_ulid_response_schema`は、python-ulid-djangoのフィールドから、ネストしない**応答用**のSchemaを生成します。入力用・PATCH用Schemaの自動生成、ネストした応答、ほかのULIDフィールドライブラリには対応していません。

空の`fields`、主キー以外を参照する`to_field`付きの外部キー、逆参照、`OneToOneField`、複合主キーは、Schemaの作成時に`ValueError`になります。

OpenAPIには次の制限があります。

- Ninja 1.7.1では、同じSchemaを`by_alias`の設定が異なるルートで使い回すと、共有するOpenAPIのフィールド名が最後に登録したルートの設定になります。HTTPの応答は正しく返ります。出力形式ごとに、異なる`name`でSchemaを作成してください。
- OpenAPIの文字パターンは入力と応答の両方で小文字を許可していますが、実際の出力は常に大文字です。

## 動作確認済みの環境

| Python | 検証したDjangoの版 | DB |
|---|---|---|
| 3.12 / 3.13 / 3.14 | 5.2.18 / 6.1.2 | SQLite / PostgreSQL 18.6 |

CIでは12通りすべてを検証します。Djangoの依存指定は5.2系・6.1系の後続パッチ版も許可しますが、インストール可能な版すべてを検証したわけではありません。詳しくは[対応環境と検証方法](https://github.com/nibuno/django-ninja-ulid/blob/main/docs/compatibility.md)を参照してください。

## バージョンの方針と開発への参加

公開APIは`ApiULID`、`create_ulid_response_schema`、`related_ids`の3つです。0.x系の間は、互換性のない変更をマイナー版（例：0.1 → 0.2）で、互換性を保つ修正をパッチ版で公開します。

- [変更履歴](https://github.com/nibuno/django-ninja-ulid/blob/main/CHANGELOG.md)
- [バージョンの方針](https://github.com/nibuno/django-ninja-ulid/blob/main/docs/versioning.md)
- [開発手順と不具合報告](https://github.com/nibuno/django-ninja-ulid/blob/main/CONTRIBUTING.md)
- [Issues](https://github.com/nibuno/django-ninja-ulid/issues)

## ライセンス

[MIT](https://github.com/nibuno/django-ninja-ulid/blob/main/LICENSE)
