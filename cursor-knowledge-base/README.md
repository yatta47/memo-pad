# Cursor で「ドメイン知識を溜めて使うほど育つ」仕組みを組む

Cursor（IDE）で、業務ドメイン知識・設計判断・運用ノウハウを蓄積し、複数リポジトリ横断で引ける自己改善型の仕組みを作るときの設計メモ。2026-06 時点の挙動を最新調査＋セカンドオピニオンで確認した版。Cursor は半年で仕様が変わるので、挙動が違えば公式 changelog / docs を最優先。

関連メモ: [Cursor / Claude Code 的な自律タスク消化の設計メモ](./agentic-task-loop.md)

## 前提となる現行仕様（誤解しやすい点）

### 永続記憶は Rules 一本（Memories は廃止）

- Cursor IDE の対話 Agent の自動 **Memories 機能は v2.1.x（2025-11）で削除済み**。公式スタンスは「組み込み永続記憶手段＝Rules が唯一」。
- 移行は `Cmd+Shift+P → Export memories` で `.mdc` 化して Rules に取り込む。
- memory files が残るのは **Automations（バックグラウンドエージェント）文脈のみ**。
- → 「メモリ蓄積で記憶」を当てにせず、Rules ＋ リポジトリ内のドキュメントに寄せるのが現行の正攻法。

### self-improving rules は公式機能ではない

- 「self-improving rules」という機能名は存在しない。100% コミュニティ運用パターン。
- 実体は `.mdc` に「同じ指摘/説明が 2 回出たらルール化を**提案**せよ」とメタ指示を置き、人が承認して追記する**半自動**。
- 完全自律のルール自己書き換えはバージョン依存で信頼性が保証されない。**提案止まりにして肥大化を防ぐ**のが定石。
- IDE 単体では「毎日勝手にふりかえる」完全自律ループは回らない（それは Automations / Background Agent 側）。

### カスタマイズ機能の住み分け

| 機能 | 発火 | コンテキスト | 用途 |
|------|------|-------------|------|
| Rules (`.cursor/rules/*.mdc`) | 自動（常時 or ファイル一致） | 会話冒頭に毎回（alwaysApply 時） | 守らせ続ける規約・前提 |
| AGENTS.md | 自動（常時） | 冒頭に載る | rules の簡易版・クロスツール標準 |
| Skills (`.cursor/skills/<name>/SKILL.md`) | 半自動（説明文で関連時にロード）＋ `/` 手動 | 名前・説明だけ常駐、本文は必要時 | たまに使う手順書 |
| Commands（`/` 保存プロンプト） | 手動 | 呼んだ時だけ | 自分でトリガーする定型 |
| Hooks (`hooks.json`) | 完全自動（イベント駆動・非 LLM） | 載らない | 編集後フォーマット等 |

一文ルール: 毎回やらかす整形を直す→ Rule / デプロイ時だけチェックリスト→ Skill / 編集後に自動フォーマット→ Hook / 自分のタイミングで定型→ Command。

## マルチルートワークスペースのスコープ（最重要・誤解多い）

「フォルダ A の `.cursor/` が、ワークスペースに後から足したリポジトリ B にも効く」は**誤り**。検証済みの挙動:

| 要素 | ルートを跨ぐ？ | 備考 |
|------|:---:|------|
| コードベースインデックス / @mention / セマンティック検索 | ✅ | 足したフォルダを横断して**引ける**（retrieval は跨ぐ） |
| **User Rules**（グローバル設定） | ✅ | 全プロジェクト共通・git に入らない。跨がせたい振る舞いはここ |
| **グローバル Skills**（`~/.cursor/skills/`） | ✅ | 全プロジェクトで使える。跨がせたい手順はここ |
| Project Rules（`<repo>/.cursor/rules/*.mdc`） | ❌ | そのルート内のファイルのみ。マルチルートで未読込バグ報告多数 |
| Project Skills（`<repo>/.cursor/skills/`） | ❌ | そのルートのみ |

置き場ルール:
- **跨がせたい** → User Rules / `~/.cursor/skills/`（グローバル）
- **跨がせない** → `<repo>/.cursor/rules/`（そのリポジトリ専用）

## 落とし穴

- **User Rule のトークン税**: User Rule は Agent で常時ロード＝毎リクエスト課金。重い参照手順を直書きせず、**極小の振る舞い指示だけ User Rule に置き、手順は `~/.cursor/skills/` に逃がす**。`disable-model-invocation: true` ＋ 明示 `/skill` 呼び出しで発火を確実化。
- **alwaysApply の積み上げ**: 20 ルール×200 行で 16,000+ tokens/回。常時ロードはコンテキストの 10–15% を焼く。alwaysApply 合計 2,000 tokens 未満 / 1 ファイル 500 行未満が目安。
- **インデックス ≠ セキュリティ境界**: フォルダをワークスペースに足してインデックスさせると、チャンクは embedding 計算で Cursor サーバへ送信される。「git に入れない」と「Cursor/LLM 経路に出さない」は別問題。機密はライセンス/Privacy 規程の許可を確認してから。シークレット・PII はライセンス可否と無関係に置かない。
- **検索品質**: コードベース索引はコード用の埋め込み。自然言語ドキュメント（用語集・仕様）はヒット率が落ちうる。→ ルーティング表（`_index.md`）＋ 1 ファイル 1 論点 ＋ frontmatter で補う。
- **鮮度**: 溜める仕組みだけでは「知識が正しいまま残る」保証がない。owner / updated / confidence を frontmatter に持たせ、stale を明示する。
- **User Rules は個人プロジェクトでも発火**: アカウント全体適用。会社/個人を分けるなら **Cursor プロファイル分離**が機械的な唯一解（条件文は LLM 任せで不確定）。

## 知識蓄積の設計パターン（複数リポジトリ横断・git 非管理）

```
知識本体  : ~/work-knowledge/（git init しない＝リポジトリを汚さない）
              domain/    業務ルール・用語・外部仕様
              design/    コード設計判断（なぜこの構成か）
              playbooks/ 作業手順・運用ノウハウ
              _index.md  用語 → 正規ファイル → 別名 → 更新日のルーティング表
              _backlog.md 引いて無かった知識（N 件超で昇格 or 削除）
            ↑ マルチルートワークスペースに追加 → インデックス & @mention が全リポ横断
規約層    : AGENTS.md（各リポジトリ／守らせる前提）
振る舞い  : User Rule 極小（「ドメイン知識を推測で埋めるな／必要なら /domain-recall」）
手順      : ~/.cursor/skills/domain-recall/（グローバル・明示呼び出し）
鮮度      : 各 md 冒頭 frontmatter（type/system/owner/updated/confidence/aliases）＋ 1 ファイル 1 論点
バックアップ: NAS へ restic（履歴付き）＋ スナップショット＋ 月 1 復元テスト
```

### frontmatter 雛形

```markdown
---
type: domain        # domain | design | playbook
system: <subsystem>
owner: <team-or-person>
updated: 2026-06-24
confidence: confirmed   # confirmed | draft | stale
aliases: [別名1, 別名2]
---
```

### domain-recall SKILL.md（グローバル・明示呼び出し）

```markdown
---
name: domain-recall
description: ドメイン知識(~/work-knowledge/)を参照し、無ければバックログに記録、教わったら昇格を提案する
disable-model-invocation: true   # 自動発火させない。/domain-recall で明示起動
---

# domain-recall

## 参照（引く）
1. ~/work-knowledge/_index.md で該当の正規ファイルを特定し @mention する
2. frontmatter の confidence と updated を確認。stale や古い更新日は「古い可能性」と添える
3. 推測でドメインの空白を埋めない

## 記録（無かった時）
- ~/work-knowledge/_backlog.md に1行追記を提案。N件超なら先に既存の昇格/削除を促す

## 昇格（教わった時）
- 該当バケットへの追記を「提案」する（差分形式）。frontmatter を必ず付ける
- 1ファイル1論点を守る。自動でファイルを書き換えず承認を待つ
```

### 段階導入（一気に作らない）

1. domain 1 枚 ＋ `_index.md` ＋ User Rule ＋ ワークスペース定義
2. 使いながら `_backlog.md` を溜め、溜まったら昇格
3. プロファイル分離 ＋ NAS restic ＋ PR テンプレに「domain-recall 実行済: y/n」

## 出典

- Cursor Docs: Rules / Skills / Data Use（cursor.com/docs, cursor.com/data-use）
- Cursor 公式フォーラム: Memories 削除（v2.1.x）、マルチルート rules 未読込バグ各種
- コミュニティ: self-improving rules（sashido.io / morphllm / devlato rules.mdc / awesome-cursor-rules-mdc）
