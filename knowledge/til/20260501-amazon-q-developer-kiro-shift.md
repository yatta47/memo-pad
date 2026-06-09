# TIL: Amazon Q Developer plugin から Kiro への移行は「補助機能の移行」ではなく「開発環境の重心移動」

## 背景

AWS は `Amazon Q Developer` の IDE plugin と paid subscription の end-of-support を発表し、移行先として `Kiro` を案内している。

公式発表の表現を見る限り、これは単なる plugin の後継ではない。
`Kiro` は `IDE / CLI` として案内されており、`spec-driven development` を前提にした agentic development environment として位置付けられている。

## 重要な日付

- 2026-04-30:
  - AWS が end-of-support announcement を公開
- 2026-05-15:
  - 新規の Q Developer Free Tier account 作成停止
  - 新規の Q Developer subscription 作成停止
- 2026-05-29:
  - Q Developer Pro で `Opus 4.6` 提供終了
  - 最新 coding models は Kiro 側に寄る
- 2027-04-30:
  - Q Developer IDE plugins / paid subscriptions の end of support

## 何が変わるのか

### Amazon Q Developer

- 既存 IDE に追加する plugin
- AI は IDE の中の補助機能
- 開発の主役は人間 + IDE

### Kiro

- それ自体が `IDE / CLI`
- `Specs`, `Hooks`, `Steering files`, `Custom subagents`, `Powers` などを持つ
- AI に作業を渡し、継続的な文脈と検証を前提にした環境
- 開発の重心が「IDE の中の AI」から「AI の作業場としての IDE」へ寄る

## 自分なりの整理

通常の AI plugin は「IDE の中に AI がいる」という感覚に近い。

一方で、agentic IDE は「AI とのインタフェースが IDE になった」と感じる可能性がある。

この違いはかなり本質的で、

- 前者:
  - 人間が主役
  - AI は補助
- 後者:
  - AI への委譲や対話が主役
  - IDE は AI と協業するための作業空間

`Kiro` は公式の打ち出しを見る限り、かなり後者を狙っている。

## Kiro の良さとして見える点

- 単発 prompt ではなく、`spec-driven` な計画から入る
- `hooks` により保存・commit などのイベントで検証や更新を自動化できる
- `steering files` により project-level の持続文脈を持たせられる
- `subagents` / `custom agents` により役割分担のある AI 運用ができる
- CLI と IDE の両面で統一的に使える
- GA 時点で IAM Identity Center、team management、multi-root workspace、property-based testing にも広がっている

## つらくなりそうな点

- 既存 IDE に足すだけではなく、Kiro の流儀に寄る必要がある
- 既存拡張、キーバインド、workspace 慣習との整合を取り直す必要がある
- 単なる code completion の比較では評価しづらく、導入コストが重い
- チームとして `specs`、`hooks`、`steering` の運用設計が必要
- CLI は互換性があるが、設定保存先やライセンス、認証導線は変わる

## 市場の反応メモ

2026-05-01 時点では、公開の反応はかなり割れている。

### 期待されている点

- 補完よりも、計画・実装・検証までつなぐ方向性
- spec-driven development の構造化
- CLI と IDE の一体運用
- チーム管理まで含めた agentic tooling

### 懐疑的な点

- 競合に比べて UX が弱いという声
- 信頼性への不満
- 既存ワークフローにそのまま乗せにくいという声
- 「思想は面白いが完成度はまだ評価待ち」という印象

公開コミュニティでは、`lagging behind the competition`、`not having a tui`、`unreliable` といった不満も見られた。

ただし、この時点の反応は early adopter 中心で、安定した市場評価とまでは言いにくい。

## Kiro を評価する時の観点

`Kiro` は普通の AI coding tool と同じ物差しでは見ない方がよい。

見るべき観点:

- AI が主役の作業導線になっているか
- 文脈保持が一時的な chat を超えているか
- 計画と検証まで自然につながるか
- IDE が単なる表示面ではなく、AI の実行環境として機能しているか
- 人間が監督者として気持ちよく関われるか

## 結論

`Amazon Q Developer` から `Kiro` への移行は、

- 補助機能の置き換え
- plugin の後継製品への移行

というより、

- 開発環境の重心移動
- AI との協業モデルの変更

として見る方が実態に近い。

短期的には移行コストが高そうだが、AWS の本命は明らかに Kiro 側にある。

## References

- AWS DevOps Blog:
  - <https://aws.amazon.com/jp/blogs/devops/amazon-q-developer-end-of-support-announcement/>
- AWS Blog:
  - <https://aws.amazon.com/jp/blogs/news/introducing-kiro/>
  - <https://aws.amazon.com/jp/blogs/news/general-availability/>
- Kiro Docs:
  - <https://kiro.dev/docs/cli/migrating-from-q/>
- Community reaction:
  - <https://www.reddit.com/r/kiroIDE/comments/1rso7vs/i_wish_kiro_or_amazon_q_subscriptions_were_open/>
  - <https://www.reddit.com/r/kiroIDE/comments/1qtkp3v/why_kiro_is_utterly_unreliable_for_development/>
  - <https://www.reddit.com/r/kiroIDE/comments/1sw7pli/leaving_kiro_for_good/>
