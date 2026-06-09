# ECR Vulnerability Triage Runbook

## 目的

Amazon ECR enhanced scanning / Amazon Inspector で `CRITICAL` / `HIGH` の脆弱性が検知された際に、
対応要否、優先度、対処方針、例外承認の基準を統一する。

この runbook は「全件を一律に即修正する」のではなく、
判断基準を定義して `Fix / Mitigate / Accept temporarily / False positive` を決めるためのもの。

## 用語

### `fixAvailable`

Amazon Inspector の finding 属性。
脆弱な package に対して、修正版 package version が存在するかを表す。

値:

- `YES`
  - 影響を受けている package 全てに修正版がある
- `NO`
  - 修正版がない
- `PARTIAL`
  - 一部の package には修正版があるが、全てではない

意味:

- `YES` なら、package / base image 更新で直せる可能性が高い
- `NO` なら、vendor 修正版待ちや別 mitigation を考える必要がある
- `PARTIAL` なら、完全解消できる範囲と残件を分けて扱う

参考:

- Amazon Inspector Finding API
- Amazon Inspector finding details

### `exploitAvailable`

Amazon Inspector の finding 属性。
その脆弱性に **既知の exploit が存在するか** を表す。

値:

- `YES`
  - 既知 exploit がある
- `NO`
  - 既知 exploit はない

意味:

- `YES` は「危険度が高い」判断材料になる
- ただし、AWS も明記している通り、これは **exploit が環境内で実際に使われたこと** を意味しない
- あくまで「世の中に exploit が知られているか」の情報

参考:

- Amazon Inspector Finding API
- Amazon Inspector finding details

## 対象

- Amazon ECR enhanced scanning
- Amazon Inspector `Inspector2 Finding`
- 対象 severity:
  - `CRITICAL`
  - `HIGH`

## 基本方針

- `CRITICAL` / `HIGH` は全件 triage 対象とする
- ただし、全件を即時修正扱いにはしない
- severity だけでなく、以下を見て判断する
  - 稼働環境
  - 露出状況
  - exploitability
  - 修正可能性
  - 影響範囲
- 例外受容は可能だが、期限と承認者を必須とする

## New Relic 前提の運用フロー

この runbook では、Amazon Inspector finding を New Relic に通知し、
New Relic 側で集約した上で triage する運用を前提とする。

### 想定構成

1. Amazon ECR enhanced scanning
2. Amazon Inspector finding 発行
3. EventBridge が `Inspector2 Finding` を受信
4. Lambda が通知対象か判定し、New Relic 向け payload を整形
5. New Relic が `aggregationTag` で同一 finding を集約
6. New Relic Workflow が issue activation を通知
7. owner が triage
8. 必要に応じて ticket 化、修正、mitigation、例外承認を行う

### フロー図

```text
Amazon ECR / Inspector
        |
        v
 EventBridge (Inspector2 Finding)
        |
        v
 Lambda
  - severity filter
  - environment filter
  - payload mapping
        |
        v
 New Relic
  - aggregationTag で集約
  - Issue / Workflow 発火
        |
        v
 Service Owner Triage
  - Fix
  - Mitigate
  - Accept temporarily
  - False positive
        |
        v
 Ticket / Exception / Close
```

### New Relic 側で期待すること

- 同じ finding の update イベントを 1 つの issue に集約する
- 初回 activation 時だけ強い通知を出す
- 同一 finding の細かい更新で通知を乱発しない
- close 時は issue 解消に反映する

### 集約キーの考え方

最初は `findingArn` 単位の集約を基本とする。

例:

- `aggregationTag.findingArn = <findingArn>`
- `aggregationTag.repository = <repositoryName>`
- `aggregationTag.imageDigest = <imageDigest>`

理由:

- Inspector finding update でも finding identifier は同一のまま更新される
- 同一 finding の再通知を New Relic 側でまとめやすい
- image 単位や CVE 単位より、最初の運用として解釈しやすい

### Lambda 側の最低限の判定

Lambda 側では複雑な dedupe を持たず、最低限のフィルタだけに留める想定。

- `status = ACTIVE` のみ通知
- `severity = CRITICAL/HIGH` のみ即時通知対象
- `MEDIUM` は送らない、または別 eventType で日次集計向けに送る
- ECR / Inspector finding 以外は捨てる

### Workflow の考え方

New Relic Workflow は以下を基本とする。

- issue が新規 activation した時だけ通知する
- 同一 issue の update では通知を増やしすぎない
- 必要なら `CRITICAL` と `HIGH` で通知先を分ける
- close 時の通知は任意

### Owner が受けた後にやること

1. New Relic issue から finding の基本情報を確認する
2. 対象 image が本番で稼働中か確認する
3. `fixAvailable` と `exploitAvailable` を確認する
4. 露出・到達性・実行経路・権限を確認する
5. この runbook の判定基準に沿って結論を出す
6. ticket 化、または例外承認を行う

### 例外管理

New Relic で issue がまとまっても、受容判断そのものは別管理にした方がよい。

最低限、以下はチケットまたは台帳で持つ。

- finding ARN
- CVE
- repository
- image digest
- 判定結果
- 受容理由
- 承認者
- 期限
- 再評価日

### この構成の狙い

- AWS 側で複雑な通知抑制ロジックを持たない
- ただし全件垂れ流しにもせず、最低限の filter は Lambda で行う
- New Relic 側で issue 集約し、人間の triage 単位を安定させる
- triage / exception の判断は runbook で統一する

## 初動フロー

1. finding を受信する
2. 対象サービスの owner を特定する
3. 対象 image が実際に稼働しているか確認する
4. 以下の triage 項目を記録する
5. `Fix / Mitigate / Accept temporarily / False positive` のいずれかを決定する
6. 必要に応じてチケット化、エスカレーション、期限設定を行う

## Triage 項目

### 1. 基本情報

- Finding ID:
- Finding ARN:
- CVE:
- Severity:
- Repository:
- Image digest:
- Image tag:
- Package name:
- Installed version:
- Fixed version:
- Fix available: `YES / NO / PARTIAL`
- Exploit available: `YES / NO`
- First observed at:
- Environment: `prod / stg / dev`
- Service owner:

### 2. 稼働状況

- この image は現在デプロイ中か: `YES / NO`
- 本番で稼働しているか: `YES / NO`
- 本番へのデプロイ予定があるか: `YES / NO`
- すでに置き換え済みか: `YES / NO`

### 3. 露出・到達性

- インターネット到達可能か: `YES / NO`
- 認証前に到達可能か: `YES / NO`
- 当該 package / 機能は実行経路に乗るか: `YES / NO / UNKNOWN`
- コンテナ権限:
  - `privileged`
  - `root`
  - `non-root`
  - `readonly rootfs`
- 共通 base image で横展開しやすいか: `YES / NO`

### 4. Exploitability

- `exploitAvailable`: `YES / NO`
- 攻撃成立条件の厳しさ: `LOW / MEDIUM / HIGH`
- 想定影響:
  - `RCE`
  - `権限昇格`
  - `認証回避`
  - `情報漏えい`
  - `DoS`
- 追加条件:
  - ローカル実行が必要
  - 認証済みが必要
  - 特殊設定が必要
  - ユーザー操作が必要

### 5. 修正容易性

- `fixAvailable`: `YES / NO / PARTIAL`
- base image 更新だけで解消できるか: `YES / NO`
- アプリ変更が必要か: `YES / NO`
- 互換性リスクは高いか: `YES / NO`
- 代替 mitigation があるか: `YES / NO`

## 判定基準

### A. 即時修正

以下を 1 つ以上満たす場合は即時修正を優先する。

- `CRITICAL` かつ `prod` 稼働中
- `exploitAvailable = YES`
- インターネット到達可能
- 認証前到達可能
- `RCE` / `権限昇格` / `認証回避`
- 共通 base image で横展開影響が大きい
- `fixAvailable = YES` で修正難易度が低い

目安:

- 初動: 24 時間以内
- 修正方針決定: 24 時間以内
- 修正完了目標: 7 日以内

### B. 計画修正

以下に当てはまる場合は、次回リリースまたは期限付き対応とする。

- `HIGH` だが exploit 条件が厳しい
- 本番露出はあるが実行経路が限定的
- fix はあるが互換性確認が必要
- 緊急修正より計画リリースの方が安全

目安:

- 初動: 3 営業日以内
- 修正完了目標: 30 日以内

### C. 一時受容

以下の場合は一時受容を許容する。

- `fixAvailable = NO`
- 本番未稼働
- 実行経路に乗らない
- 代替 mitigation が有効
- 近日中に image 廃止予定
- vendor 修正版待ち

必須条件:

- 受容理由を記録
- 期限を設定
- 承認者を記録
- 再評価日を設定

### D. False Positive / Not Applicable

以下の場合は false positive または非該当としてクローズ可能。

- 対象 package が実際には利用されない
- 影響条件を満たしていないことが確認済み
- スキャナ誤検知が確認できる
- すでに別 image / 別 digest へ置き換え済み

必須条件:

- 根拠 URL または検証結果を残す

## 優先度マトリクス

### P0

- `CRITICAL`
- `prod`
- `exploitAvailable = YES` または外部到達可能
- `RCE` / `権限昇格` / `認証回避`

対応:

- 即時エスカレーション
- 緊急修正または緊急 mitigation

### P1

- `CRITICAL` だが exploit 条件が厳しい
- `HIGH` かつ `prod`
- `fixAvailable = YES`

対応:

- 期限付き修正
- 通常は次回リリースを待たず優先対応

### P2

- `HIGH` だが `stg/dev`
- `HIGH` だが未稼働 image
- 影響限定、または mitigations 有効

対応:

- backlog 化
- 定例 review で追跡

## 記録テンプレート

- 判定: `Fix / Mitigate / Accept temporarily / False positive`
- 理由:
- 影響範囲:
- 実行環境:
- 露出状況:
- exploitability:
- fixAvailable:
- 対応内容:
- 期限:
- owner:
- approver:
- 再評価日:

## 例外ルール

- 無期限の例外受容は禁止
- 例外には必ず期限を持たせる
- 期限切れ時は自動で再 triage する
- 同一 base image 起因の finding は横断管理を検討する

## 備考

- severity のみで判断しない
- CVSS よりも実環境での到達性と exploitability を重視する
- 本番で稼働していない image の優先度は下げてよい
- ただし本番投入予定が近い場合は例外とする

## References

- AWS: Amazon Inspector Finding API
  - <https://docs.aws.amazon.com/inspector/v2/APIReference/API_Finding.html>
- AWS: Viewing details for your Amazon Inspector findings
  - <https://docs.aws.amazon.com/inspector/latest/user/findings-understanding-details.html>
- AWS: Understanding Amazon Inspector findings
  - <https://docs.aws.amazon.com/inspector/latest/user/findings-understanding.html>
