# Cursor × DevContainer（Agent隔離の最小構成）

Cursor の Agent によるターミナル実行を DevContainer 内に閉じ込め、ホストマシンへ
直接コマンドが当たらないようにするための最小テンプレート。

会社PC など「AI にコマンドを任せたいが、ホスト全体を触らせたくない」環境向け。

## 置き場所

`devcontainer.json` を、対象リポジトリ直下の以下に置く:

```
<対象リポジトリ>/.devcontainer/devcontainer.json
```

この repo（memo-pad）の `cursor-devcontainer/devcontainer.json` はそのコピー（参照用）。

## セットアップ手順

```
1. 対象リポジトリ直下に .devcontainer/devcontainer.json を作成（本ファイルのコピー）
2. Cursor でそのフォルダを開く
3. コマンドパレット → "Dev Containers: Reopen in Container"
4. 初回はイメージ pull（数分）
5. ビルド後、postCreateCommand が自動実行される
```

## 隔離の正確な範囲

| 対象 | Agent が触れるか |
|------|------------------|
| マウントされた作業フォルダ（＝このリポジトリ） | **触れる**。コンテナ内の編集はホスト側の同フォルダに反映される（bind マウント） |
| ホストのそれ以外（`~/`・他リポジトリ・共有ドライブ等） | 触れない（コンテナ外） |
| ホストへの直接コマンド実行 | しない（コンテナ内で完結） |

要点: **「プロジェクトフォルダの中は従来通り／その外側がコンテナで遮断」**。
blast radius は「このリポジトリ + コンテナ」に限定される。ホスト全体は守られるが、
当該リポジトリは守られない（git でのバージョン管理は必須）。

## 検証（隔離できているかの確認）

Reopen 後、Cursor の統合ターミナルで:

```bash
whoami                # → vscode（root でない）
hostname              # → コンテナID（ホスト名でない）
cat /etc/os-release   # → Debian bookworm（ホストOSでない）
```

さらに Agent に `pwd && ls -la && whoami` を実行させ、上と同じコンテナ内コンテキストで
動くか確認する。一致すれば「Agent の実行＝コンテナ内」が取れている。

> Cursor のフォークはくせがあるため、Agent が在host実行に化けていないかを
> この検証で必ず一度確認する（「隔離できているはず」と推測で置かない）。

## 落とし穴

- **Docker Desktop のライセンス**: 会社利用で有償条件に触れる場合あり。
  引っかかるなら Rancher Desktop / Podman が代替（別途確認）。
- **初回 pull が社内プロキシで失敗**: `mcr.microsoft.com` への到達を確認。
  詰まるなら社内レジストリ/プロキシ設定が要る。
- **`customizations.vscode` を足すときは慎重に**: 起動失敗の主因。
  足すなら1個ずつ、上の検証で都度確認。
- **ネットワークは開いたまま**: コンテナはデフォルトで外部通信可。
  ここを締めるのは次の硬化ステップ（最小版ではやらない）。

## 次のステップ

このコンテナ内から Confluence などの MCP サーバを使う場合は、`mcp.json` を別途用意する
（Cursor に居たまま社内ドキュメントを参照する口）。本テンプレートで Agent 隔離が
取れていることを確認してから進める。

## 参考

- Agent Security | Cursor Docs: https://cursor.com/docs/agent/security
- Implementing a secure sandbox for local agents | Cursor: https://cursor.com/blog/agent-sandboxing
- Dev Containers spec: https://containers.dev/
