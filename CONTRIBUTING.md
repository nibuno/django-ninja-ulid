# 開発と不具合報告

初回版の範囲は、26文字ULIDの型と、既存ULIDFieldから平坦な応答Schemaを作る処理です。機能の追加や対応範囲を変える場合は、[README](README.md)と[互換性方針](docs/versioning.md)を基に検討します。

## 開発環境

```bash
uv sync --locked --extra orm
uv run --locked --extra orm pytest -q
```

Python・Django・DBの全組み合わせを確認する手順は[対応環境](docs/compatibility.md)にあります。DBの実験にはテスト専用のサーバーを使います。配布物は[リリース手順](docs/releasing.md)で作成し、ソースからの利用と通常インストールの両方を確認します。

## 不具合報告に添える情報

通常の不具合は、[このリポジトリのIssues](https://github.com/nibuno/django-ninja-ulid/issues)へ次の情報を添えて報告できます。リポジトリがprivateの間は、アクセスできる利用者に限ります。

- Python、django-ninja-ulid、Django、Ninja、Pydantic、ULIDライブラリ、DBの版。
- 問題を再現する最小のモデル・Schema・API定義。
- 再現する入力、期待した応答、実際の応答と例外。
- `by_alias`、関連の定義、`fields`、prefetchの有無。

実データ、認証情報、接続先の秘密情報は含めず、再現用の値へ置き換えます。

## 変更時の確認

- 公開APIの変更には、受け入れる入力・出力と変更理由を示す。
- 変更の影響を確認できるテストを追加し、対応するマトリクスを通す。
- 利用方法や互換性が変わる場合はREADMEとCHANGELOGを更新する。
- 対応環境を広げる場合は、依存指定とCIを同時に更新する。

入力・PATCHの自動生成、ネスト、逆参照、非主キーの`to_field`などは現在の対象外です。実装に先立ち、用途と受け入れ条件を相談する範囲とします。
