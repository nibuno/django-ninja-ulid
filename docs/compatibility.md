# 対応環境と検証方法

更新日：2026-10-18。

## 結論

Python 3.12〜3.14、Django 5.2.18／6.1.2、SQLite／PostgreSQL 18.6の12通りで、型・モデル連携などの82件のテストと新規Djangoプロジェクトの確認が成功した。現時点の対応宣言は、この組み合わせに限る。

`0.1.0`の準備でリリース検査の9件を追加し、現在のCIは各91件を実行する。ライブラリ本体のソースと依存の版は変更していない。以下の実測表とJSONは、切り出し直後の`0.0.0`を検証した記録として保持する。

Ninja 1.7.1、Pydantic 2.13.5、python-ulid 4.0.1、python-ulid-django 1.6.0を固定して検証している。未検証の版まで互換性を保証する結果ではない。基本依存を固定しているため、これらについて最小依存と最新依存は同じ版になる。

## ローカルで確認した組み合わせ

検証日は2026-10-18。PythonはmacOS / Apple Silicon上で実行し、PostgreSQLは専用コンテナのLinux / aarch64上で実行した。パッケージはeditableではなく、作成したwheelから通常インストールした。

| Pythonの実測版 | Django | SQLiteの実測版 | SQLite | PostgreSQL 18.6 |
|---|---|---|---|---|
| 3.12.1 | 5.2.18 | 3.43.1 | 82件成功 | 82件成功 |
| 3.12.1 | 6.1.2 | 3.43.1 | 82件成功 | 82件成功 |
| 3.13.0 | 5.2.18 | 3.45.3 | 82件成功 | 82件成功 |
| 3.13.0 | 6.1.2 | 3.45.3 | 82件成功 | 82件成功 |
| 3.14.5 | 5.2.18 | 3.50.4 | 82件成功 | 82件成功 |
| 3.14.5 | 6.1.2 | 3.50.4 | 82件成功 | 82件成功 |

PostgreSQLのイメージは`postgres:18.6-trixie`、ドライバーはpsycopg 3.3.6。SQLiteは各Pythonに付属する実測版であり、SQLiteの全バージョンを検証したわけではない。PostgreSQLの他のメジャー版も対応宣言には含めない。PostgreSQL 18は、[公式のサポート対象](https://www.postgresql.org/support/versioning/)から選んだ。

ローカルの実測版・件数・配布物とソースのハッシュは[検証記録](verification-2026-10-18.json)に保存した。対応範囲・文書を更新する前のwheelで確認しており、ライブラリ本体のソースは同じである。CIは各コミットから配布物を作り直して検証する。

全12通りで、新しいDjangoプロジェクトの作成、migration、ULIDのPK・FK・M2Mの保存と復元、通常のUUID、HTTPの作成・取得、nullと空の関連、不正入力422、OpenAPIを確認した。aliasの異なる応答には別名のSchemaを使う。

また、Python×Djangoの6通りで、`orm` extraなしのwheelを別の新規環境へ入れた。Fieldライブラリが存在せず、Djangoの設定なしで`ApiULID`を検証・文字列化できること、ORMを使おうとするとextraの導入案内が出ることを確認した。

## 依存指定と対応宣言

`requires-python`は`>=3.12,<3.15`とする。Djangoの依存指定は5.2.18以降の5.2系と6.1.2以降の6.1系を許可し、未検証の6.0系を除く。インストールを許可する範囲と、上表で確認した版は区別する。新しいパッチ版の対応表への追加は、CIで確認してから行う。

Ninja・Pydantic・ULIDライブラリの許容範囲を広げる場合は、追加する版をマトリクスへ入れ、テストと新規インストールが通ってから依存指定を変える。`uv.lock`にはビルド・検証に使った依存も記録している。

## CI

[GitHub ActionsのCI](https://github.com/nibuno/django-ninja-ulid/actions/workflows/ci.yml)は、[ci-matrix.json](../ci-matrix.json)から組み合わせを読み、次を実行する。

1. 固定した開発依存を導入し、sdistからwheelを作成して`twine check`を通す。
2. editableなパッケージをwheelへ入れ替え、対象のDjango版を選ぶ。
3. 各DBで91件のテスト（既存82件とリリース検査9件）と、新規Djangoプロジェクトの確認を実行する。
4. SQLiteの各ジョブでは、別の環境へextraなしで入れ、型だけの利用を確認する。

Pythonは指定した各マイナー版の、runnerで取得できるパッチ版を使う。PostgreSQLは18.6、ドライバーはロックした3.3.6を使う。ジョブごとの結果・実測版は、7日間保存する成果物のXMLとJSONから確認できる。CIの実行状況は上記のリンクで確認する。

Actionは公式リポジトリのコミットに固定し、権限は`contents: read`とする。CIに公開処理は含めない。[uvのGitHub Actions向け手順](https://docs.astral.sh/uv/guides/integration/github/)、[GitHubのPostgreSQLサービスの説明](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers)を基に構成した。

## ローカルで12通りを再実行する

Python 3.12・3.13・3.14と、テスト専用のPostgreSQLを事前に用意する。PostgreSQLのユーザーには、pytestと新規プロジェクトの確認が専用DBを作成・削除できる権限が必要になる。既存のアプリ用DBを指定しない。

```bash
uv sync --locked --extra orm
uv build
export ULID_POSTGRES_HOST=127.0.0.1
export ULID_POSTGRES_PORT=5432
export ULID_POSTGRES_DB=ulid_test
export ULID_POSTGRES_USER=postgres
export ULID_POSTGRES_PASSWORD=postgres
python3 scripts/run_matrix.py
```

上記の認証値は使い捨てのローカル検証用の例である。`run_matrix.py`はDBサーバーの起動・停止を行わない。指定したテスト用サーバーに対し、pytestはテストDBを、新規プロジェクト確認は一意な名前のDBを作成して終了時に削除する。

結果は`local-checks/matrix/results.json`、組み合わせごとのXML・JSON・実行ログへ保存する。これらの一時環境やログはGitへ含めない。
