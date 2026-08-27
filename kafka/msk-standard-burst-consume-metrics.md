# Amazon MSK Standard 一括Consume試験の確認メトリクス

## 目的

Amazon MSK StandardのTopicへ事前投入した50,000件のメッセージをConsumerが一括受信する試験について、MSK Broker側の確認メトリクス、重要度、正常の定義、異常時に読み取れる状態を整理する。

Consumerアプリケーション側の件数整合、offset、rebalance、Consumer Lagなどは、[Amazon MSK Consumer一括受信試験の確認観点](./msk-consumer-burst-test-checklist.md)を参照する。

## 重要度の定義

| 重要度 | 意味 | 判定での扱い |
|---|---|---|
| P0: 必須 | 可用性、データ保護、明確な容量超過に直結する | 原則として1項目でも異常なら試験不合格 |
| P1: 重要 | 性能劣化や容量不足を判断する主要メトリクス | 単独の瞬間値ではなく、継続時間と他メトリクスとの相関で判定 |
| P2: 切り分け | P0/P1異常の原因箇所を特定する | 常時の合否判定には使わず、異常時に追加確認 |

## 試験前提と判定方法

CloudWatchのMSK Standardメトリクスは基本的に1分粒度で確認する。試験開始前、試験中、試験終了後の3区間を比較する。

```text
試験前: 5～10分程度のベースライン
試験中: Consumer起動からLag解消まで
試験後: Lag解消後、メトリクスがベースラインへ戻るまで
```

Broker単位のメトリクスはクラスタ平均だけでなく、すべてのBrokerを重ねて最大値と偏りを確認する。平均値だけでは、一部のBrokerへの負荷集中を見落とす可能性がある。

「正常の定義」に記載した数値のうち、AWSが明示している代表的な基準は次の2つである。

- `CpuUser + CpuSystem`はBrokerごとに60%未満を維持する
- `KafkaDataLogsDiskUsed`は85%未満を維持する

それ以外はワークロードやBrokerサイズによって適正値が異なるため、固定された一般閾値ではなく、ベースライン、継続時間、Consumer LagやFetch時間との相関で判定する。

## 合否判定に使う主メトリクス

| Metrics名 | 重要度 | Metricsの説明 | 何をもって正常と定義するか | 異常から分かること |
|---|---|---|---|---|
| `OfflinePartitionsCount` | P0: 必須 | Leaderが存在せず、読み書きできないoffline partitionのクラスタ合計数 | 試験前から終了まで常に`0` | `1`以上なら一部partitionが利用不能。対象partitionのConsumeが停止し、可用性障害が発生している |
| `UnderReplicatedPartitions` | P0: 必須 | 設定されたreplication factorを満たしていないpartition数。Broker単位で確認する | 試験前から終了まで原則`0`。計画メンテナンスを同時に実施する場合は、その影響を試験結果から分離する | Broker、ディスク、ネットワーク、レプリケーション処理のいずれかが追いついていない。継続すると耐障害性が低下する |
| `UnderMinIsrPartitionCount` | P0: 必須 | in-sync replica数が`min.insync.replicas`を下回ったpartition数 | 試験前から終了まで常に`0` | 必要な同期レプリカ数を維持できていない。データ保護水準が低下し、Producer設定によっては書き込み失敗も起こり得る |
| `CpuUser` + `CpuSystem` | P0: 必須 | Brokerのユーザー処理とOS処理に使用しているCPUの合計。CloudWatch Metric MathでBrokerごとに合算する | 各Brokerの1分平均が試験中も`60%未満`。Broker間で一台だけ突出しない | 60%以上が継続する場合、Brokerの処理余力が不足している。Fetchレイテンシ上昇、リクエスト滞留、Broker障害時の負荷引き継ぎ余力不足につながる |
| `TrafficShaping` | P0: 必須 | Brokerのネットワーク割り当てを超過し、パケットがキューイングまたはドロップされたことを示す総合メトリクス | 試験前から終了まで`0`、またはカウンタの増加がない | Brokerのネットワーク帯域またはpacket-per-second上限に到達している。ConsumerのFetch遅延、timeout、再接続の原因になり得る |
| `KafkaDataLogsDiskUsed` | P0: 必須 | KafkaデータログがBrokerストレージを使用している割合 | 全Brokerで`85%未満`。試験データ投入後も十分な空き容量がある | ストレージ枯渇が近い。Produce/Consume性能の悪化や、最終的にはBrokerの可用性低下につながる。ConsumeしてもKafkaログは直ちには削除されない |
| `FetchConsumerTotalTimeMsMean` | P1: 重要 | ConsumerのFetch要求をBrokerが受けてから応答するまでの平均所要時間 | 試験中に右肩上がりで増え続けず、Lag減少が止まらない。試験後にベースラインへ戻る。絶対値の閾値は事前測定と要求性能から決める | Broker内部処理、リクエストキュー、レスポンスキュー、ネットワーク送信のどこかでFetch応答が遅延している。ただし設定されたFetch待機時間の影響も含むため、単独では原因を確定できない |
| `BytesOutPerSec` | P1: 重要 | Brokerからクライアントへ送信したデータ量。Broker単位およびTopic単位で確認できる | Lagがある間は想定した読み出し量が観測され、Lag減少と対応する。Lagが残っているのに継続して`0`にならず、一部Brokerだけに極端に偏らない | `0`または急減ならConsumerのFetch停止、接続問題、Brokerのボトルネックが疑われる。Broker間の差が大きければLeader配置、partition、key分布の偏りが疑われる |
| `NetworkProcessorAvgIdlePercent` | P1: 重要 | Brokerのnetwork processor threadがidleだった時間の割合。低いほどネットワーク要求処理に余裕がない | 試験中に`0%`付近へ張り付かず、試験後にベースラインへ戻る。試験用の暫定目安として、継続して`20%未満`にならないことを確認する | 低値が継続する場合、network threadが飽和している。Fetch要求の受付や応答処理が遅れ、リクエストキュー増加やレイテンシ上昇につながる |
| `RequestHandlerAvgIdlePercent` | P1: 重要 | Brokerのrequest handler、すなわちI/O threadがidleだった時間の割合。低いほど要求処理の余裕がない | 試験中に`0%`付近へ張り付かず、試験後にベースラインへ戻る。試験用の暫定目安として、継続して`20%未満`にならないことを確認する | 低値が継続する場合、Brokerの要求処理が飽和している。Fetch処理、ディスクI/O、その他のKafka要求が滞留している可能性がある |
| `VolumeQueueLength` | P1: 重要 | Brokerストレージで完了待ちになっているread/write処理数 | 試験中に増え続けず、Fetch時間や`CpuIoWait`の継続的悪化を伴わず、試験後にベースラインへ戻る | 高止まりまたは増加傾向なら、ストレージI/Oが要求に追いついていない可能性がある。キャッシュにない過去データの一括読み出しで顕在化しやすい |
| `CpuIoWait` | P1: 重要 | CPUがストレージI/O完了を待っている時間の割合 | 一時的な上昇だけで判定せず、ベースラインからの継続的上昇がなく、`VolumeQueueLength`やFetch時間の悪化を伴わない | 高値が継続する場合、Broker処理がディスクI/O待ちになっている。ストレージ性能または大量read/writeがボトルネックの可能性がある |

### 暫定20%基準の扱い

`NetworkProcessorAvgIdlePercent`と`RequestHandlerAvgIdlePercent`の20%は、AWSがすべてのMSK Standard構成に対して保証する公式閾値ではなく、この試験で余力を判断するための暫定値である。これらのKafka由来メトリクスがCloudWatch上で`0`～`1`の比率として表示される環境では、20%は`0.2`と読み替える。

本試験では次の順序で最終基準を決める。

1. 試験前の通常負荷におけるBrokerごとのベースラインを記録する
2. 50,000件試験中の最小値と継続時間を記録する
3. Fetchレイテンシ、Consumer Lag、エラーへの影響を確認する
4. 実測結果と本番の必要余力を基に、監視閾値を確定する

## 異常時だけ追加確認するメトリクス

主メトリクスで異常が見つかった場合、次のメトリクスで原因箇所を切り分ける。

| Metrics名 | 重要度 | Metricsの説明 | 何をもって正常と定義するか | 異常から分かること |
|---|---|---|---|---|
| `FetchConsumerRequestQueueTimeMsMean` | P2: 切り分け | Consumer Fetch要求がBrokerのrequest queueで待った平均時間 | ベースラインから継続的に増加しない | 増加していればnetwork threadからI/O threadへ渡した後の処理待ちが発生している |
| `FetchConsumerLocalTimeMsMean` | P2: 切り分け | Leader Broker内でConsumer Fetch要求を処理した平均時間 | ベースラインから継続的に増加しない | 増加していればBroker内部処理またはディスク読み出しが遅い可能性がある |
| `FetchConsumerResponseQueueTimeMsMean` | P2: 切り分け | Fetch応答がresponse queueで送信待ちになった平均時間 | ベースラインから継続的に増加しない | 増加していればnetwork threadによる応答送信が追いついていない可能性がある |
| `FetchConsumerResponseSendTimeMsMean` | P2: 切り分け | Fetch応答をConsumerへ送信するために要した平均時間 | ベースラインから継続的に増加しない | 増加していればBrokerからConsumerまでのネットワーク送信がボトルネックの可能性がある |
| `PpsAllowanceExceeded` | P2: 切り分け | Brokerの双方向packet-per-second上限超過によってtraffic shapingされたパケット数 | カウンタの増加がない | 増加していればデータ量ではなく、小さい要求の多発などによってパケット数上限へ達している |
| `BwOutAllowanceExceeded` | P2: 切り分け | Brokerの外向きネットワーク帯域上限超過によってtraffic shapingされたパケット数 | カウンタの増加がない | 増加していればConsumerへの送信を含むBrokerの外向き帯域が上限へ達している |
| `VolumeReadBytes` | P2: 切り分け | 指定期間中にBrokerストレージから読み取ったbytes数 | 値の大小だけでは異常判定しない。想定データ量と対応し、`VolumeQueueLength`や`CpuIoWait`の悪化を伴わない | 増加はストレージからの読み出し発生を示す。キューやI/O待ちも悪化していればストレージボトルネックを疑う |

## 最小構成で確認する場合

画面や試験成績表の項目数をさらに絞る場合は、次の7項目を最低限確認する。

| 順位 | Metrics名 | 確認目的 |
|---:|---|---|
| 1 | `OfflinePartitionsCount` | 利用不能partitionがないこと |
| 2 | `UnderReplicatedPartitions` | レプリケーションが正常であること |
| 3 | `UnderMinIsrPartitionCount` | データ保護水準を維持していること |
| 4 | `CpuUser + CpuSystem` | Brokerの処理余力があること |
| 5 | `TrafficShaping` | ネットワーク上限へ達していないこと |
| 6 | `FetchConsumerTotalTimeMsMean` | Fetch応答が劣化していないこと |
| 7 | `BytesOutPerSec` | 想定したConsumeトラフィックが出ていること |

ただし、試験データ投入後に`KafkaDataLogsDiskUsed`が85%へ近づく場合は、同メトリクスを必須項目へ追加する。

## 試験結果の総合判定

MSK側を正常と判定する条件は次のとおり。

```text
1. P0メトリクスがすべて正常範囲である
2. Consumer Lagが要求時間内に解消する
3. Fetch時間が継続的に悪化しない
4. BrokerのCPU、network thread、I/O thread、ストレージに余力が残る
5. Broker間で許容できない負荷偏りがない
6. 試験後に各メトリクスがベースラインへ戻る
7. 同じクラスタを利用する他のProducer、Consumer、Topicへ許容外の影響がない
```

瞬間的なスパイクだけで不合格にせず、値の継続時間、Consumer Lagの推移、Fetch時間、クライアントエラーとの相関を記録する。ただし、`OfflinePartitionsCount`、`UnderMinIsrPartitionCount`、`TrafficShaping`については、試験中に発生した時点で原因確認を必須とする。

## 参考資料

- [Amazon MSK metrics for monitoring Standard brokers with CloudWatch](https://docs.aws.amazon.com/msk/latest/developerguide/metrics-details.html)
- [Amazon MSK best practices for Standard brokers](https://docs.aws.amazon.com/msk/latest/developerguide/bestpractices.html)
- [Amazon MSK storage throughput](https://docs.aws.amazon.com/msk/latest/developerguide/msk-provision-throughput-management.html)
- [Amazon MSK: Monitor consumer lags](https://docs.aws.amazon.com/msk/latest/developerguide/consumer-lag.html)
