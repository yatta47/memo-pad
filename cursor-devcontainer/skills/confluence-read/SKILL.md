---
name: confluence-read
description: "Confluence Cloud のタスク管理ページを閲覧し、進捗を footer コメントとして追記する。検索・ページMarkdown取得・進捗コメント（dry-run付き）。"
---

# confluence-read

Confluence Cloud を「読む」「進捗をコメントで書く」ための self-contained スキル。
タスク管理を 1 ページの表で集約し、進捗はそのページへのコメントで残す運用を想定。

## 前提

- Confluence **Cloud** 版（atlassian.net）。Data Center 版は非対応。
- `pip install atlassian-python-api`（devcontainer 内で実施）。
- 環境変数で認証（コードに固有情報を持たない）:
  - `CONFLUENCE_BASE_URL` 例 `https://your-org.atlassian.net`（末尾に `/wiki` を付けない）
  - `CONFLUENCE_EMAIL`
  - `CONFLUENCE_API_TOKEN`（[トークン発行](https://id.atlassian.com/manage-profile/security/api-tokens)）

## 使い方（自然言語 → 内部コマンド）

- 「Confluence で "ECS デプロイ" を検索して」
  → `scripts/confluence.py search "ECS デプロイ" [--space KEY]`
- 「このページ（id=123456）の中身を見せて」
  → `scripts/confluence.py page 123456`（本文を Markdown 化。表は `|` 区切り）
- 「スペース一覧 / DEV スペースのページ一覧」
  → `scripts/confluence.py spaces` / `scripts/confluence.py pages --space DEV`
- 「タスク管理ページ（id=123456）に "Issue#42 着手、設計レビュー完了" と進捗を書いて」
  → まず `scripts/confluence.py comment 123456 --text "Issue#42 着手、設計レビュー完了"`（**dry-run**）
  → 投稿対象（ページ名・URL・内容）を確認 → 同じコマンドに `--save` を付けて実投稿

## 安全装置（必ず守る）

- **書き込み（comment）はデフォルト dry-run**。`--save` を付けて初めて実投稿する。
- dry-run / 投稿いずれも、先に **対象ページのタイトルと URL を表示**して page_id 取り違えを防ぐ。
- 書くのは **footer コメント追記のみ**。タスク表（本文）は一切変更しない。
- 完了検証は戻り値の `comment id` で行う（文言依存しない）。
- 取消手段: 投稿コメントの削除は Confluence Web UI から（本ツールは削除しない）。

## 落とし穴 / 限界

- storage→Markdown 変換は MVP。マクロ・添付・ネスト表は簡易/欠落あり。正確な原文は `page --raw`。
- 検索は CQL ベース。CQL 構文は会社環境で 1 件叩いて挙動確認すること（README 参照）。
- 社内情報を外部 AI に渡す行為なので、会社の AI 利用ポリシーの範囲で使う。

## 他スキルとの役割境界

| スキル | 役割 |
|--------|------|
| **confluence-read（本スキル）** | Confluence Cloud の閲覧 + 進捗コメント追記。社内タスク管理向け |
| outline-wiki | 個人 Outline Wiki への投入・検索。社内 Confluence とは別系統 |
| task-create | GitHub Issue 起票。Confluence は扱わない |

本スキルは **ページ本文の編集・作成・削除はしない**（読み + コメント追記に限定）。
本文編集が必要になったら別スキルとして切り出す（SKILL.md 設計原則 §2 のスキル分離基準に従う）。
