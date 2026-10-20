# Changelog

## 0.1.1 （未公開）

- READMEとPyPIの説明本文を英語に整理し、日本語版を`README.ja.md`として追加。
- 入出力を確認できる最小例、ORM連携の導入手順、依存条件と検証・文字列化の説明を整備。
- PyPIの概要とDocumentationリンクを更新し、日本語READMEをsdistに同梱。
- 公開API・実装・依存バージョンの変更はない。

## 0.1.0 — 2026-10-19

初回リリース。公開日は日本時間（PyPIの記録では2026-10-18 UTC）。

### 追加した機能

- `ApiULID`による26文字ULIDの検証、正規化、文字列化。
- `create_ulid_response_schema`による、通常の主キーを参照する平坦な応答Schemaの生成。
- 手書きSchemaで使う`related_ids`。
- `python-ulid-django`を`orm` extraへ分離。
- Python 3.12〜3.14、Django 5.2.18／6.1.2、SQLite／PostgreSQL 18.6の12通りを対応範囲とする。
- wheelの通常インストールとextraなしの型利用を確認するGitHub Actionsのマトリクス。
- 配布版・予定タグ・メタデータ・必要な同梱ファイル・SHA256を確認する、アップロードを伴わないリリース準備。

### 初回の対象外と制限

- 応答Schemaの生成は平坦な主キー参照のみ。入力・PATCHの自動生成、ネスト、非主キーの`to_field`などは対象外。
- `by_alias`設定が異なる応答には、別名のSchemaが必要。
- OpenAPIの応答パターンは小文字も許容するが、実出力は大文字。

破壊的変更は`0.x`のマイナー版、互換性を保つ修正はパッチ版とする。[互換性方針](docs/versioning.md)
