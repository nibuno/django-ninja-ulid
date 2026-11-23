# Changelog

## 0.2.0 — 2026-11-23

### Breaking changes / 互換性のない変更

- `ApiULID` now reports the cause of a validation error in `type`. Clients that checked for `value_error` should handle `ulid_type` for invalid types, `ulid_length` for incorrect string lengths, and `ulid_parsing` for malformed strings.

  `ApiULID`の検証エラーの`type`を、原因に応じて`ulid_type`（入力の型）、`ulid_length`（文字数）、`ulid_parsing`（文字列の形式）に変更。`value_error`でULIDの入力エラーを判定しているクライアントは、新しい3つの値に切り替えてください。

### Changes / 変更

- `create_ulid_response_schema` now emits an uppercase-only ULID `pattern` in the response JSON Schema, including for lists of related IDs. In hand-written schemas, the request and response patterns for `ApiULID` still allow lowercase.

  `create_ulid_response_schema`の応答用JSON Schemaで、ULIDの`pattern`を大文字限定に変更。関連先IDのリストにも適用します。手書きSchemaの`ApiULID`では、入力と応答のパターンで引き続き小文字も許可します。

### Documentation / 文書

- Documented how to create an item with owner and tag IDs, filter items by multiple IDs, and initialize Django before importing the ORM helpers. Added English translations to the changelog.

  READMEに関連先のIDを受け取るリクエストボディ、複数のIDを受け取るクエリ引数、Djangoの初期化時のエラーへの対処を追加。変更履歴に英訳を追加。

## 0.1.2 — 2026-11-23

### Fixes / 修正

- Fixed response schemas that treated `ForeignKey` and `ManyToManyField` IDs as integers when the target model inherited its ULID primary key through Django's multi-table inheritance.

  マルチテーブル継承でULID主キーを引き継いだ子モデルを参照すると、応答Schemaが`ForeignKey`や`ManyToManyField`の関連先IDを整数として扱う不具合を修正。

### Dependencies / 依存条件

- Widened the dependency ranges for Django Ninja, Pydantic, python-ulid, and python-ulid-django to allow updates within each major series.

  Django Ninja、Pydantic、python-ulid、python-ulid-djangoの依存指定を広げ、同じメジャー版内の更新に対応。

- Added Django 6.0 support. CI now tests 6.0.10 and uses 6.1.3 for the 6.1 series.

  Django 6.0系に対応し、CIの検証対象に6.0.10を追加。6.1系の検証対象を6.1.3に更新。

### Documentation / 文書

- Removed explicitly declared fields from `Meta.fields` in the hand-written schema examples in both READMEs, fixing a deprecation warning in Django Ninja 1.8.0.

  英語版・日本語版READMEの手書きSchemaの例を修正。明示したフィールドを`Meta.fields`から外し、Django Ninja 1.8.0での非推奨警告を解消。

## 0.1.1 — 2026-10-20

- Published the README and PyPI description in English and added the Japanese README as `README.ja.md`.

  READMEとPyPIの説明本文を英語に整理し、日本語版を`README.ja.md`として追加。

- Added a runnable request and response example, ORM setup instructions, and details on dependencies, validation, and serialization.

  入出力を確認できる最小例、ORM連携の導入手順、依存条件と検証・文字列化の説明を整備。

- Updated the PyPI summary and documentation link and included the Japanese README in the source distribution.

  PyPIの概要とDocumentationリンクを更新し、日本語READMEをsdistに同梱。

- This release used the same public API, implementation, and dependency versions as 0.1.0.

  公開API・実装・依存バージョンの変更はない。

## 0.1.0 — 2026-10-19

Initial release on October 19 in Japan (October 18 UTC on PyPI).

初回リリース。公開日は日本時間（PyPIの記録では2026-10-18 UTC）。

### Features / 追加した機能

- `ApiULID` validates, normalizes, and serializes 26-character ULIDs.

  `ApiULID`による26文字ULIDの検証、正規化、文字列化。

- `create_ulid_response_schema` generates flat response schemas for relations that reference primary keys.

  `create_ulid_response_schema`による、通常の主キーを参照する平坦な応答Schemaの生成。

- Added `related_ids` for use in hand-written schemas.

  手書きSchemaで使う`related_ids`。

- Moved `python-ulid-django` to the `orm` extra.

  `python-ulid-django`を`orm` extraへ分離。

- Supported 12 combinations of Python 3.12–3.14, Django 5.2.18 or 6.1.2, and SQLite or PostgreSQL 18.6.

  Python 3.12〜3.14、Django 5.2.18／6.1.2、SQLite／PostgreSQL 18.6の12通りを対応範囲とする。

- Added a GitHub Actions matrix to check wheel installation and use of the ULID type without the ORM extra.

  wheelの通常インストールとextraなしの型利用を確認するGitHub Actionsのマトリクス。

- Added a release preparation step that checks the distribution version, planned tag, metadata, required files, and SHA256 hashes before upload.

  配布版・予定タグ・メタデータ・必要な同梱ファイル・SHA256を確認する、アップロードを伴わないリリース準備。

### Initial scope and limitations / 初回の対象外と制限

- Schema generation covered flat responses with primary-key references. Request and PATCH schemas, nested responses, and relations using a non-primary-key `to_field` were outside its scope.

  応答Schemaの生成は平坦な主キー参照のみ。入力・PATCHの自動生成、ネスト、非主キーの`to_field`などは対象外。

- Responses with different `by_alias` settings required distinct schema names.

  `by_alias`設定が異なる応答には、別名のSchemaが必要。

- The OpenAPI response pattern allowed lowercase ULIDs. Serialized ULIDs were always uppercase.

  OpenAPIの応答パターンは小文字も許容するが、実出力は大文字。

During 0.x, breaking changes use a minor release and compatible fixes use a patch release. [Versioning policy (Japanese)](docs/versioning.md)

破壊的変更は`0.x`のマイナー版、互換性を保つ修正はパッチ版とする。[互換性方針](docs/versioning.md)
