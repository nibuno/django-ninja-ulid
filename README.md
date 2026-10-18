# django-ninja-ulid

Django Ninjaで26文字のULIDを扱うための型と、既存のULIDFieldから応答Schemaを作るアダプタです。IDの保存・復元・生成には既存ライブラリを使います。

現在は[privateリポジトリ](https://github.com/nibuno/django-ninja-ulid)で公開を準備しています。配布名は`django-ninja-ulid`、import名は`django_ninja_ulid`、ライセンスはMITです。Python 3.12〜3.14、Django 5.2.18／6.1.2、SQLite／PostgreSQL 18.6の12通りで動作を確認しました。[確認した環境と再実行手順](https://github.com/nibuno/django-ninja-ulid/blob/main/docs/compatibility.md)

初回版は`0.1.0`です。現在は公開準備中で、PyPIにはまだアップロードしていません。ソースを取得した後、このディレクトリでインストールできます。

```bash
python -m pip install .
# Djangoモデルと連携する場合
python -m pip install '.[orm]'
```

公開後は、型だけなら`django-ninja-ulid==0.1.0`、モデル連携も使うなら`django-ninja-ulid[orm]==0.1.0`を導入します。

## 型だけを使う

```python
from ninja import Schema
from django_ninja_ulid import ApiULID


class ItemInput(Schema):
    id: ApiULID
```

`ApiULID`のimportはDjangoの設定やモデル連携を読み込みません。`python-ulid-django`のインストールも不要です。基礎の依存にはDjango・Django Ninja・Pydantic・python-ulidを含めています。

型はPydanticから直接利用することもできます。

```python
from pydantic import TypeAdapter
from django_ninja_ulid import ApiULID

adapter = TypeAdapter(ApiULID)
value = adapter.validate_python("01arz3ndektsv4rrffq69g5fav")
assert adapter.dump_python(value) == "01ARZ3NDEKTSV4RRFFQ69G5FAV"
```

- ASCIIの26文字を受け付け、小文字を大文字へ正規化します。
- 禁止文字や先頭が0〜7を超える表記、整数・真偽値・オブジェクト・配列などを拒否します。
- PythonのULIDオブジェクトは内部値として受け付けます。
- 出力は大文字の26文字の文字列です。NinjaがPython形式で応答を取り出す場合も文字列化します。
- nullを許可する箇所は`ApiULID | None`とします。入力の省略は、手書きSchemaで既定値を指定します。

## Djangoモデルと連携する

モデル連携には`orm` extraを使います。公開後の導入名は`django-ninja-ulid[orm]`です。このextraが`python-ulid-django`を追加します。モデル連携のimportはDjangoの初期化後に行います。

```python
from django_ninja_ulid.orm import create_ulid_response_schema
from myapp.models import Item

ItemOutput = create_ulid_response_schema(
    Item,
    name="ItemOutput",
    fields=["id", "public_uuid", "name", "owner", "tags"],
)
```

対象は`python-ulid-django`のULIDFieldと、その派生Fieldです。通常のUUIDはUUIDのまま扱います。外部キー・多対多は、関連先のモデル全体ではなく主キーを返します。

上書きするULID項目は全て応答に必須です。モデルの既定値・ID生成関数を引き継がず、保存済みのIDの欠落を新しいIDで補いません。

| 設定 | 応答の扱い |
|---|---|
| 単一ULID、`null=False` | 必須、null不可 |
| 単一ULID・外部キー、`null=True` | 必須、明示的なnullは可 |
| 多対多 | 必須、空配列は可、nullは不可 |
| ULID以外の項目 | Ninjaの型・必須性・既定値を保持 |

title・descriptionは`verbose_name`・`help_text`から作ります。外部キーはPython属性の`attname`から読み、DB列名は使いません。

## 手書きModelSchema

外部キーの読み取りと、多対多のモデルからPKへの変換も指定します。

```python
from typing import Annotated
from ninja import ModelSchema
from pydantic import BeforeValidator, Field
from django_ninja_ulid import ApiULID
from django_ninja_ulid.orm import related_ids
from myapp.models import Item


class ItemOutput(ModelSchema):
    id: ApiULID
    owner: ApiULID | None = Field(..., alias=Item._meta.get_field("owner").attname)
    tags: Annotated[list[ApiULID], BeforeValidator(related_ids)]

    class Meta:
        model = Item
        fields = ["id", "public_uuid", "name", "owner", "tags"]
```

`related_ids`はManager・QuerySet・モデルのリストやタプルをPKのリストへ変換します。IDの形式検証は後続の`ApiULID`が担当します。

## 対応範囲と制限

生成関数は、ネストしない応答専用です。次の設定を生成時に拒否します。

- 空の`fields`と`None`。
- 非主キーを参照する`to_field`付き外部キー。
- 逆参照、OneToOneField、複合主キー。

`to_field="主キー名"`はDjangoが通常の主キー参照と同じ状態へ正規化するため、通常の参照として扱います。作成・PATCH入力の自動生成、ネスト、他のFieldライブラリ、非同期API、性能保証は対象に含めません。

Ninja 1.7.1で同じSchemaを異なる`by_alias`設定に共有すると、OpenAPIの定義が上書きされます。応答形式ごとに別の`name`でSchemaを生成してください。HTTP応答自体は各設定に従います。

また、OpenAPIは入力と応答に同じパターンを使うため、応答側も小文字を許容する記述になります。実際の出力は大文字です。

## ローカルでの再実行

このディレクトリだけで開発環境と配布物を準備できます。Djangoモデルを使うテストのため、`orm` extraも指定します。

```bash
uv sync --extra orm
uv run --extra orm pytest -q --junitxml=local-checks/pytest.xml
uv build
uv run --extra orm twine check dist/*
```

`tests/poc`は元のPoCのAPIをテスト用に保持したものです。`tests/poc/adapter.py`はインストールした`django_ninja_ulid`を読み、元のPoCの実装へは依存しません。wheelには`src/django_ninja_ulid`だけを含めます。

## 対応環境

| Python | Django | SQLite | PostgreSQL 18.6 |
|---|---|---|---|
| 3.12 | 5.2.18／6.1.2 | 両方で成功 | 両方で成功 |
| 3.13 | 5.2.18／6.1.2 | 両方で成功 | 両方で成功 |
| 3.14 | 5.2.18／6.1.2 | 両方で成功 | 両方で成功 |

各組み合わせで、型・モデル連携などの82件のテストと、新規Djangoプロジェクトでのmigration・作成・取得・OpenAPI確認が成功しています。リリース検査のテストはこれらに追加しています。Ninja 1.7.1、Pydantic 2.13.5、python-ulid 4.0.1、python-ulid-django 1.6.0を検証済みの版として固定しています。

依存指定はDjango 5.2.18以降の5.2系と6.1.2以降の6.1系のパッチ更新を許可しますが、対応を確認した版は上表に限ります。Django 6.0、他の依存の版、追加のDBは対応宣言に含めません。SQLiteの実測版などは[検証記録](https://github.com/nibuno/django-ninja-ulid/blob/main/docs/compatibility.md)を参照してください。

[GitHub Actions](https://github.com/nibuno/django-ninja-ulid/actions/workflows/ci.yml)とローカルの実行は、同じ[ci-matrix.json](ci-matrix.json)を使います。CIではsdistから作ったwheelを通常インストールし、ORM extraなしの型単体の利用も確認します。

## バージョンと問い合わせ

公開APIは`ApiULID`、`create_ulid_response_schema`、`related_ids`です。`0.x`では破壊的変更をマイナー版、互換性を保つ修正をパッチ版で出します。変更と移行方法をCHANGELOGへ記録し、非推奨化を経られる変更は事前に案内します。[互換性方針](https://github.com/nibuno/django-ninja-ulid/blob/main/docs/versioning.md)、[変更履歴](https://github.com/nibuno/django-ninja-ulid/blob/main/CHANGELOG.md)

不具合報告には、利用した版・DB・最小のモデルとSchema・再現手順を添えてください。[開発・報告の手順](https://github.com/nibuno/django-ninja-ulid/blob/main/CONTRIBUTING.md)に必要な情報をまとめています。公開までの作業と実施待ちの項目は[リリース手順](https://github.com/nibuno/django-ninja-ulid/blob/main/docs/releasing.md)を参照してください。
