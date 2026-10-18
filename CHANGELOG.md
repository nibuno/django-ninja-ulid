# Changelog

## Unreleased

- `ApiULID`による26文字ULIDの検証、正規化、文字列化。
- `create_ulid_response_schema`による、通常の主キーを参照する平坦な応答Schemaの生成。
- 手書きSchemaで使う`related_ids`。
- `python-ulid-django`を`orm` extraへ分離。
- Python 3.12〜3.14、Django 5.2.18／6.1.2、SQLite／PostgreSQL 18.6の12通りで、各82件のテストと新規プロジェクトのmigration・API利用を確認。
- wheelの通常インストールとextraなしの型利用を確認するGitHub Actionsのマトリクス。

初回公開のバージョンは未決定です。`0.0.0`はローカルの配布物検証に使う値です。
