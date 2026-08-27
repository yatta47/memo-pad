# Amazon MSK Consumer一括受信試験の確認観点

## 目的

Amazon MSKの任意のTopicへ事前に50,000件のメッセージを保存し、Consumerが滞留メッセージを一括して処理する試験について、Consumer側の確認観点と合否基準を整理する。

この試験で確認するのは、単にConsumerが50,000件を取得できることではない。次を満たすことを確認する。

- メッセージを欠損させない
- 重複や順序がアプリケーションの設計どおりに扱われる
- 要求された時間内にConsumer Lagを解消できる
- 処理中にConsumerおよび下流システムが不安定にならない
- 障害や再起動が発生しても、設計した配信保証どおりに復旧できる

## 重要度の定義

MSK側の確認メトリクスと同じく、Consumer側も次の3段階で整理する。

| 重要度 | 意味 | 判定での扱い |
|---|---|---|
| P0: 必須 | 欠損、処理結果不明、Consumer停止など、正しさと可用性に直結する | 原則として1項目でも異常なら試験不合格 |
| P1: 重要 | Lag解消、処理性能、安定性など、業務要件を満たすための主要観点 | 定義したSLO、継続時間、他メトリクスとの相関で判定 |
| P2: 切り分け | P0/P1異常の原因箇所を特定する詳細情報 | 常時の合否判定には使わず、異常時に追加確認 |

## 重要度付き確認観点一覧

| 確認項目 | 重要度 | 何をもって正常と定義するか | 異常から分かること |
|---|---|---|---|
| 投入件数と処理結果の整合 | P0: 必須 | 投入した50,000件すべてについて、正常完了または設計どおりのDLQなど、最終結果を一意IDで説明できる | 説明できないメッセージがある場合、欠損、処理漏れ、記録漏れのいずれかが発生している |
| 説明できない欠損 | P0: 必須 | `0件` | poll後の処理失敗、早すぎるoffset commit、異常終了時の取りこぼしなど、配信保証が設計どおり機能していない |
| 許容外の重複 | P0: 必須 | `0件`。at-least-onceで再処理を許容する場合は、冪等処理により業務影響がない | offset commit前の再処理、retry、rebalanceなどに対して、冪等性または重複排除が機能していない |
| offset commitと業務処理の整合 | P0: 必須 | 業務処理の成功条件とcommitタイミングが設計どおりで、再起動後も欠損しない | 業務処理前にoffsetが進んでいる、または処理完了後もcommitされず、欠損や過剰な重複が発生する可能性がある |
| エラー、retry、DLQ | P0: 必須 | 異常メッセージが設計した回数・経路で処理され、処理結果不明がなく、DLQ送信失敗がない | poison messageによる処理停止、無限retry、DLQ欠損、後続メッセージのブロックが発生している |
| Consumerの生存と異常終了 | P0: 必須 | 正常系試験中のプロセス、Pod、Taskの異常終了・OOM・意図しない再起動が`0回` | Consumer自体のリソース不足、未処理例外、ヘルスチェック失敗などが発生している |
| Consumer Lag解消 | P1: 重要 | `SumOffsetLag`が継続的に減少し、定義した時間内に0付近へ到達する | Consumerの処理能力不足、停止、下流待ち、特定partitionの遅延が発生している |
| スループット | P1: 重要 | 本番ピーク流入速度と、定義した処理余力を満たす | 継続流入時にLagが増え続ける、または障害復旧後の滞留を要求時間内に解消できない |
| poll間隔 | P1: 重要 | 最大poll間隔が`max.poll.interval.ms`を十分下回る | 1バッチの業務処理、DB/API待ちなどが長く、Consumer Groupから離脱する可能性がある |
| 想定外のrebalance | P1: 重要 | 固定構成の正常系では、初回partition割り当て以外`0回` | poll間隔超過、heartbeat timeout、プロセス再起動、ネットワーク障害などでConsumer Groupが不安定になっている |
| Consumerリソース | P1: 重要 | CPU、メモリ、GC、thread pool、connection poolが許容範囲内で、試験後に収束する | Consumer側のCPU不足、メモリリーク、GC停止、スレッド・接続枯渇が処理を制限している |
| 下流システムの安定性 | P1: 重要 | DB/APIなどで許容外のtimeout、接続枯渇、スロットリング、5xxが発生しない | Consumerの一括処理が下流の処理能力を超え、システム全体では安全に処理できていない |
| partition別Lagと処理量 | P2: 切り分け | Broker/partition構成から説明できない偏りがなく、特定partitionだけLagが残らない | key分布、partition割り当て、特定データの処理時間などに偏りがある |
| メッセージ処理時間のp50/p95/p99/最大値 | P2: 切り分け | 合否は全体SLOで判断し、分位値は遅延原因を説明できる状態にする | 一部データ、DB/API、GCなどによるtail latencyがスループットやpoll間隔を悪化させている |
| Kafkaクライアント詳細ログ・メトリクス | P2: 切り分け | 通常時は重大エラーがなく、異常時にfetch、commit、heartbeat、rebalanceの内訳を追跡できる | Lagや処理停止が、Fetch、commit、Group Coordinatorとの通信のどこで発生したかを特定できる |

## 試験前に固定する条件

50,000件という件数だけでは負荷を定義できないため、少なくとも次を試験条件として記録する。

| 項目 | 記録内容 |
|---|---|
| メッセージ | 件数、平均サイズ、最大サイズ、keyの分布、圧縮方式 |
| Topic | partition数、replication factor、保持期間 |
| Consumer | インスタンス数、スレッド数またはconcurrency、Consumer Group名 |
| Consumer設定 | `max.poll.records`、`max.poll.interval.ms`、`session.timeout.ms`、offset commit方式、`auto.offset.reset` |
| 業務処理 | DB更新、外部API呼び出し、ファイル出力など、受信後に実施する処理 |
| 異常系 | 不正メッセージの割合、retry、DLQの有無 |
| 負荷条件 | 事前投入だけか、試験中にも新規メッセージをProduceするか |
| 合格条件 | Lag解消時間、必要スループット、許容エラー率、許容リソース使用率 |

Kafkaの処理並列度は基本的にpartition数が上限になる。Consumer数がpartition数を超える場合、余ったConsumerにはpartitionが割り当てられない。また、Kafkaが保証する順序はTopic全体ではなくpartition内である。

## Consumer側の確認観点

### 1. 完了性と件数整合

すべての試験メッセージに一意な`eventId`などを付与し、Consumerがpollした件数ではなく、業務処理が完了した結果を照合する。

```text
投入した一意ID = 正常完了した一意ID + DLQなどへ隔離した一意ID
```

確認項目は次のとおり。

- 投入した50,000件すべてについて最終的な処理結果を説明できる
- 説明できない欠損がない
- 同じIDが意図せず複数回処理されていない
- 異常メッセージがretryまたはDLQの設計どおりに処理される
- Kafkaから取得しただけでなく、DB更新などの業務処理完了まで確認する

合否基準例:

```text
投入件数                 50,000件
正常完了件数             49,990件
設計どおりDLQへ送信          10件
説明できない欠損               0件
許容外の重複                   0件
```

### 2. 配信保証、offset、重複

Consumerのoffset commitタイミングと業務処理の完了タイミングを確認する。

- 業務処理前にoffsetをcommitして、障害時に未処理メッセージが失われないか
- 業務処理後、offset commit前に停止した場合、再処理が発生するか
- at-least-once設計の場合、重複を下流の冪等性で吸収できるか
- 自動commitを使用している場合、業務処理との整合性が保証されているか
- Consumer再起動後、想定したoffsetから処理を再開するか

「取得件数が50,000件」と「業務処理が50,000件完了」は別の指標として扱う。

### 3. Consumer Lagと滞留解消時間

試験開始後、Consumer Lagが継続的に減少し、規定時間以内に0付近まで到達することを確認する。

```text
50,000 -> 42,000 -> 31,000 -> 18,000 -> 5,000 -> 0
```

確認項目は次のとおり。

- `SumOffsetLag`が継続的に減少する
- `MaxOffsetLag`から、特定partitionだけ処理が遅れていないことを確認する
- Lagが途中で長時間横ばいにならない
- Lag解消後もConsumerが正常稼働している
- Lagを0にするまでの時間が要求されたSLO以内である

Amazon MSKでは、CloudWatchまたはPrometheusで`SumOffsetLag`、`MaxOffsetLag`、`EstimatedMaxTimeLag`を確認できる。partition単位で確認する場合は`OffsetLag`を使用する。

なお、MSKのConsumer LagメトリクスはConsumer Groupが`STABLE`または`EMPTY`の場合に出力される。メトリクスが欠落していることをLag 0と解釈しない。また、CloudWatchでLagを監視するConsumer Group名にはASCII文字を使用する。

### 4. スループットと処理時間

次の指標を記録する。

- 50,000件すべての処理完了時間
- 平均および最低スループット（件/秒、bytes/秒）
- 1メッセージ当たりの処理時間のp50、p95、p99、最大値
- Lagが最大値から0になるまでの時間

必要な処理能力は、試験件数ではなく本番のピーク流入速度と許容Lag解消時間から決める。

```text
平均処理能力 = 処理件数 / 処理時間
```

継続的にメッセージが流入する環境では、Consumerの処理能力がピーク流入速度以下だとLagが増え続ける。合格基準には、本番ピークに対して必要な余力を明示する。

### 5. poll間隔とrebalance

Consumer GroupのrebalanceはMSK上のGroup Coordinatorが調整するが、partitionの割り当て解除と再取得は各Consumerで発生する。確認の中心はConsumerアプリケーションのログとKafkaクライアントメトリクスとする。

試験開始時の初回partition割り当ては正常である。また、Consumerの追加・停止を意図的に行った場合のrebalanceも想定内である。

Consumer数とpartition数を固定した定常処理中に、次を原因とするrebalanceが発生していないことを確認する。

- `max.poll.interval.ms`を超過した
- heartbeatが`session.timeout.ms`の範囲で届かなかった
- Consumerプロセス、Pod、Taskが再起動した
- 長時間のGC停止やCPU不足が発生した
- ネットワークや認証の問題でGroup Coordinatorと通信できなかった
- Consumerが例外などによりGroupを離脱し、再参加した

Consumer側では次を確認する。

- partitionのassign/revokeログ
- Groupへのjoin/rejoinログ
- heartbeat timeout
- `CommitFailedException`
- 前回の`poll()`から次の`poll()`までの最大時間
- rebalance回数と所要時間

固定構成で行う正常系試験の合否基準例は、「初回割り当てを除き、処理中のrebalanceが0回」である。

### 6. デフォルト設定で50,000件を処理する場合

Apache Kafka Consumerの一般的なデフォルト値は次のとおり。

```text
max.poll.records     = 500
max.poll.interval.ms = 300,000ms（5分）
```

50,000件すべてを一度の`poll()`でConsumerへ渡すのではなく、最大500件ずつ複数回に分けて返す。このため、`max.poll.interval.ms`について問題になるのは50,000件全体の処理時間ではなく、1回の`poll()`で取得したレコードを処理して次の`poll()`を呼ぶまでの時間である。

最大500件を逐次処理する場合の単純計算では、1件当たり平均600msで5分に達する。

| 1件当たりの処理時間 | 500件の処理時間 | 目安 |
|---:|---:|---|
| 10ms | 5秒 | 問題になりにくい |
| 100ms | 50秒 | 余裕あり |
| 300ms | 150秒 | 計測して確認する |
| 500ms | 250秒 | 余裕が小さい |
| 1秒 | 500秒 | `max.poll.interval.ms`超過の可能性が高い |

実際に毎回500件取得するとは限らず、並列処理やバッチ処理の方式によっても所要時間は変わる。実測値として次を記録する。

```text
1回のpollで取得した件数
pollで取得してから当該バッチの業務処理が完了するまでの時間
前回のpollから次のpollまでの時間
```

全50,000件の処理に数時間かかっても、5分以内の間隔で`poll()`を継続していれば、`max.poll.interval.ms`の観点だけでは問題にならない。ただし、全体のLag解消時間が業務要件を満たすかは別途評価する。

デフォルト5分に対してぎりぎり収まることを合格とせず、突発的なDB遅延やGC停止を考慮した余裕を合否基準に含める。

### 7. 事前投入方式での`auto.offset.reset`

新しいConsumer Groupで、先にTopicへ保存した50,000件を読む場合は`auto.offset.reset`を確認する。

一般的なデフォルトの`latest`では、Consumer Groupにcommit済みoffsetがない場合、Topicの末尾から読み始め、事前投入したメッセージを読み取らない可能性がある。

試験では、次のいずれかを明示的に実施する。

- `auto.offset.reset=earliest`を設定して新しいConsumer Groupを使用する
- 試験開始前に対象Consumer Groupのoffsetを意図した位置へ明示的にリセットする

実際の値は、使用しているKafkaクライアントやフレームワークによる上書きを含めた実効設定で確認する。

### 8. Consumerと下流システムの安定性

Consumerプロセスだけでなく、業務処理の依存先も同時に監視する。

Consumer側:

- CPU使用率
- メモリ使用量と処理後の収束
- GC回数と停止時間
- スレッドプール、キュー、コネクションプールの枯渇
- Consumerプロセス、Pod、Taskの再起動回数
- デシリアライズ、commit、timeout、認証、接続エラー

下流側:

- DBの接続数、CPU、ロック、スロークエリ、更新失敗
- 外部APIのレイテンシ、timeout、スロットリング、5xx
- retry件数とretryによる負荷増幅
- DLQ送信失敗

Consumerが高速に取得できても、下流システムを過負荷にしている場合は問題なしとは判断しない。

## 実施する試験シナリオ

### 正常系: 事前投入した50,000件の滞留解消

- Consumer停止中に50,000件を投入する
- 投入件数と一意IDを記録する
- Consumerを起動してLag解消まで計測する
- 件数整合、処理時間、Lag、rebalance、リソース、下流負荷を確認する

この試験は、主に滞留解消能力を確認する。

### 継続流入: ProduceしながらConsume

- 本番ピーク相当の速度でProduceを継続する
- Consumerの処理能力が流入速度を上回り、Lagが増え続けないことを確認する

この試験は、主に定常処理能力を確認する。

### 復旧: 処理中のConsumer停止と再起動

少なくとも次のタイミングを対象とする。

- 業務処理前
- 業務処理後、offset commit前
- offset commit後

rebalanceの発生自体は想定内とし、規定時間内に処理を再開すること、欠損しないこと、重複が設計範囲内であることを確認する。

### 異常系: 下流遅延または失敗

- DBまたは外部APIの応答を遅延させる
- timeout、retry、DLQ、poll間隔、rebalanceへの影響を確認する
- 下流障害の解消後に処理が回復し、Lagを解消できることを確認する

## 合否判定テンプレート

具体的な数値は業務要件から決める。

| 確認項目 | 重要度 | 合格基準 | 結果 | 判定 |
|---|---|---|---|---|
| 件数整合 | P0 | 50,000件すべての処理結果を説明できる |  |  |
| 欠損 | P0 | 説明できない欠損0件 |  |  |
| 重複 | P0 | 許容外の重複0件 |  |  |
| offset・再起動 | P0 | 欠損なし、重複は設計範囲内、規定時間内に復旧 |  |  |
| エラー・DLQ | P0 | 処理結果不明とDLQ送信失敗がない |  |  |
| Consumer生存 | P0 | 正常系で異常終了、OOM、意図しない再起動がない |  |  |
| Lag解消 | P1 | 規定時間以内に0付近まで低下 |  |  |
| スループット | P1 | 本番ピークと必要な余力を満たす |  |  |
| poll間隔 | P1 | `max.poll.interval.ms`に対して十分な余裕がある |  |  |
| rebalance | P1 | 正常系では初回割り当て以外0回 |  |  |
| Consumerリソース | P1 | CPU、メモリ、GC、各poolが許容範囲内 |  |  |
| 下流安定性 | P1 | 接続枯渇、許容外timeout、過負荷なし |  |  |

## 最小構成で確認する場合

試験成績表の項目数を絞る場合でも、次の8項目は確認する。

| 順位 | 確認項目 | 重要度 | 確認目的 |
|---:|---|---|---|
| 1 | 件数整合 | P0 | 50,000件すべての最終結果を説明できること |
| 2 | 欠損・重複 | P0 | 配信保証と冪等性が設計どおりであること |
| 3 | offset・再起動 | P0 | 障害時にも欠損せず再開できること |
| 4 | エラー・DLQ | P0 | 異常メッセージが後続処理を止めず、行き先不明にならないこと |
| 5 | Consumer生存 | P0 | 正常系の一括処理でConsumerが落ちないこと |
| 6 | Consumer Lag解消時間 | P1 | 要求時間内に滞留を解消できること |
| 7 | poll間隔・rebalance | P1 | Consumer Groupが安定して処理を継続できること |
| 8 | Consumerおよび下流リソース | P1 | アプリ単体ではなく処理経路全体に余力があること |

## 参考資料

- [Apache Kafka Consumer Configs](https://kafka.apache.org/documentation/#consumerconfigs)
- [Apache Kafka KafkaConsumer API](https://kafka.apache.org/42/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html)
- [Amazon MSK: Monitor consumer lags](https://docs.aws.amazon.com/msk/latest/developerguide/consumer-lag.html)
- [Amazon MSK metrics for monitoring Standard brokers with CloudWatch](https://docs.aws.amazon.com/msk/latest/developerguide/metrics-details.html)
