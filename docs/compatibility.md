# 対応環境と検証方法

更新日：2026-11-23。

## 対応環境

Python 3.12・3.13・3.14、Django 5.2.18・6.0.10・6.1.3、SQLite・PostgreSQL 18.6の全18通りをローカルで検証した。どの組み合わせでも98件のテストが通り、wheelを入れた新規DjangoプロジェクトでマイグレーションとAPIの応答を確認した。

Pythonの依存指定は`>=3.12,<3.15`。以下の表に、ライブラリの依存範囲と、SQLiteで下限版と最新版を検証したときの実測版を示す（2026-11-23）。

| 依存ライブラリ | インストールできる範囲 | 下限版（Python 3.12） | 範囲内の最新版（Python 3.14） |
|---|---|---|---|
| Django | `>=5.2.18,<6.2,!=6.1.0,!=6.1.1` | 5.2.18 | 6.1.3 |
| Django Ninja | `>=1.7.1,<2` | 1.7.1 | 1.8.0 |
| Pydantic | `>=2.13.5,<3` | 2.13.5 | 2.14.4 |
| python-ulid | `>=4.0.1,<5` | 4.0.1 | 4.2.0 |
| python-ulid-django（`orm` extra） | `>=1.6.0,<2` | 1.6.0 | 1.6.0 |

下限版では98件すべて、最新版では`upstream`マーカー付きの16件を除く82件のテストが通った。新しい版を検証済みの表に加えるときは、テストと新規インストールを確認する。

Django 6.1.0と6.1.1は初回コミットから除外されている。この2版を除外した理由は文書やコミット履歴に記録されていない。

## 2026-10-18のローカル検証記録

以下は切り出し直後の`0.0.0`の記録である。PythonはmacOS / Apple Silicon上で、PostgreSQLは専用コンテナのLinux / aarch64上で実行した。パッケージは作成したwheelから通常インストールした。`0.1.0`の準備でリリース検査を9件追加した。

| Pythonの実測版 | Django | SQLiteの実測版 | SQLite | PostgreSQL 18.6 |
|---|---|---|---|---|
| 3.12.1 | 5.2.18 | 3.43.1 | 82件成功 | 82件成功 |
| 3.12.1 | 6.1.2 | 3.43.1 | 82件成功 | 82件成功 |
| 3.13.0 | 5.2.18 | 3.45.3 | 82件成功 | 82件成功 |
| 3.13.0 | 6.1.2 | 3.45.3 | 82件成功 | 82件成功 |
| 3.14.5 | 5.2.18 | 3.50.4 | 82件成功 | 82件成功 |
| 3.14.5 | 6.1.2 | 3.50.4 | 82件成功 | 82件成功 |

PostgreSQLのイメージは`postgres:18.6-trixie`、ドライバーはpsycopg 3.3.6。SQLiteは各Pythonに付属する実測版であり、SQLiteの全バージョンを検証したわけではない。PostgreSQLの他のメジャー版も対応宣言には含めない。PostgreSQL 18は、[公式のサポート対象](https://www.postgresql.org/support/versioning/)から選んだ。

当時の実測版・件数・配布物とソースのハッシュは[検証記録](verification-2026-10-18.json)に保存した。

全12通りで、新しいDjangoプロジェクトの作成、migration、ULIDのPK・FK・M2Mの保存と復元、通常のUUID、HTTPの作成・取得、nullと空の関連、不正入力422、OpenAPIを確認した。aliasの異なる応答には別名のSchemaを使う。

また、Python×Djangoの6通りで、`orm` extraなしのwheelを別の新規環境へ入れた。Fieldライブラリが存在せず、Djangoの設定なしで`ApiULID`を検証・文字列化できること、ORMを使おうとするとextraの導入案内が出ることを確認した。

## CI

[GitHub ActionsのCI](https://github.com/nibuno/django-ninja-ulid/actions/workflows/ci.yml)は、[ci-matrix.json](../ci-matrix.json)から検証対象の組み合わせを読み込む。プルリクエストでは、Python 3.12とDjango 5.2.18、Python 3.14とDjango 6.1.3の2組を、それぞれSQLiteとPostgreSQLで検証する（計4通り）。`main`へのpush、手動実行、毎週月曜00:00（UTC）の定期実行、リリースタグのpushでは全18通りを検証する。

各組み合わせで次の手順を実行する。

1. `uv.lock`からビルド・テスト用の依存を導入し、sdistからwheelを作成して`twine check`を通す。
2. editableなパッケージをwheelへ入れ替え、対象のDjango版を選ぶ。
3. 対象のDBでpytestを実行し、新規Djangoプロジェクトの動作を確認する。
4. SQLiteの各ジョブでは、別の環境へextraなしで入れ、型だけの利用を確認する。

Pythonは指定した各マイナー版の、runnerで取得できるパッチ版を使う。PostgreSQLのジョブでのみ18.6のサービスコンテナを起動し、ドライバーはロックした3.3.6を使う。ジョブごとの結果・実測版は、7日間保存する成果物のXMLとJSONから確認できる。CIの実行状況は上記のリンクで確認する。

`dependency-bounds`の2ジョブは、それぞれ新しい仮想環境に`orm` extra付きのwheelを入れ、SQLiteで検証する。`lowest`はPython 3.12で直接依存の下限版を選び、`upstream`を含む全テストを実行する。`highest`はPython 3.14で依存範囲内の最新版を選び、`pytest -m "not upstream"`でライブラリの動作を確認する。各ジョブのログで`uv pip list`の実測版を確認できる。

Actionは公式リポジトリのコミットに固定し、権限は`contents: read`とする。CIに公開処理は含めない。[uvのGitHub Actions向け手順](https://docs.astral.sh/uv/guides/integration/github/)、[GitHubのPostgreSQLサービスの説明](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers)を基に構成した。

## ローカルで18通りを再実行する

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
