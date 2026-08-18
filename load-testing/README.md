# 負荷生成ツールのコマンドライン（oha / vegeta）

「ロードバランサのターゲットを、暖まっていないプロセスへ切り替えたら何が起きるか」を
再現する検証で使ったコマンドラインの記録。ツールの使い分けと、実際に踏んだ罠を残す。

## 使い分け

| ツール | モデル | 使いどころ |
|---|---|---|
| [`oha`](https://github.com/hatoo/oha) | closed-loop（同時数を固定） | コールド状態への**一撃**。「N本同時に来たら詰まるか」 |
| [`vegeta`](https://github.com/tsenart/vegeta) | open-loop（到着レートを固定） | **投げ続けている最中に**切替を起こす。エンドユーザ視点の影響測定 |

**この使い分けが結論を左右する。** closed-loop はサーバが詰まると次のリクエストを
投げなくなる（＝負荷側が勝手に減速する）ので、詰まりの影響が過小評価される。
「切り替えた瞬間にユーザが何秒待たされたか」を測るなら open-loop でなければならない。

導入した版: `oha` 1.15.0 / `vegeta` 12.13.0（`~/.local/bin`）

```bash
cargo install oha      # または brew install oha
go install github.com/tsenart/vegeta/v12@latest
```

## oha — 一撃

```bash
oha -c "$CONC" -n "$CONC" --no-tui "$URL/query"
```

- `-c N -n N` … 同時数 N で、総リクエスト数も N。**1リクエストずつ N 並列で1回だけ**撃つ形。
  `-n` を増やすと「詰まった後に後続が積まれる」条件が混ざるので、一撃の観測には向かない
- `--no-tui` … スクリプトから回すとき必須。付けないと TUI が端末を奪う
- `-q R` … 到着レートを R req/s に絞る。ロードバランサ側でレートを絞る緩和策の
  エミュレーションに使った（`QPS` 環境変数で出し分け）

```bash
# レート制限あり版
oha -c 20 -n 20 -q 2 --no-tui http://localhost:18080/query
```

**2回目以降は再現しない。** プールもスレッドプールも暖まってしまうので、
撃つ前に必ずプロセスを再起動する。対照実験として「暖まった状態に撃つ」を
別途取りたい場合だけ再起動を飛ばす。

## vegeta — 一定レートを流し続ける

vegeta は「ターゲット定義を stdin から受けて `attack` → バイナリ結果 → `report` で集計」の3段。

### ウォームアップ（段階的にレートを上げる）

```bash
for R in 10 25 50 100 150; do
  echo "GET http://localhost:${LB_PORT}/query" \
    | vegeta attack -rate="${R}/1s" -duration=45s -timeout=120s \
        -max-workers=400 -keepalive=true 2>/dev/null \
    | vegeta report 2>/dev/null \
    | awk -F'[][]' '/^Success/{printf "成功率 %s", $2} END{print ""}'
done
```

いきなり目標レートを当てるとサーバ側のスレッドプールが追いつかず、
**測りたい現象ではなくウォームアップ不足を測ってしまう**。段階的に上げて定常状態を作ってから測る。

### 測定本体（バックグラウンドで流し続け、その最中に切替を起こす）

```bash
echo "GET http://localhost:${LB_PORT}/query" \
  | vegeta attack -rate="${RATE}/1s" -duration="${TOTAL}s" -timeout=120s \
      -max-workers=400 -keepalive=true \
      -prometheus-addr=0.0.0.0:8880 \
  > "$OUT/vegeta.bin" &
VEGETA_PID=$!

# ... この裏で切替やプロセス再起動を実行する ...

wait "$VEGETA_PID"
vegeta report "$OUT/vegeta.bin" | tee "$OUT/vegeta-report.txt"
```

- `-rate=N/1s` … 到着レート。**サーバの応答が遅れても投げ続ける**のが open-loop の要点
- `-timeout=120s` … 短いと「詰まった」ではなく「vegeta が諦めた」を測ることになる。
  観測したい最大待ち時間より十分長くする
- `-max-workers=N` … 詰まると in-flight が積み上がる。ここが小さいと
  vegeta 側がボトルネックになり、指定レートを維持できず結果が濁る
- `-keepalive=true` … 毎回 TCP を張り直すと、測りたい対象ではなく接続確立を測る
- 結果は `.bin`（gob 形式）。**集計は必ず後段の `vegeta report`**。ファイルは肥大するので gitignore 推奨

### 到着レートと同時実行数の関係

```
同時実行数 = 到着レート × サービス時間
```

**レートだけ上げても同時実行数は増えない。** サービス時間（サーバ側の保持時間）が短いと、
レートを上げても「同時にリソースを要求している数」は増えず、枯渇系の現象は再現しない。
検証対象の同時数を作りたいなら、サーバ側に保持時間を持たせてこの式で逆算する。

## vegeta + Prometheus の罠（4つとも実際に踏んだ）

1. **vegeta に OTel 出力は無い。** あるのは `-prometheus-addr` だけ。
   OpenTelemetry Collector 経由の構成にはできず、**Prometheus が直接ホストを叩く**形になる。
   Linux の Docker では `host.docker.internal` が既定で解決できないので、
   Prometheus コンテナ側に `extra_hosts: - "host.docker.internal:host-gateway"` が要る
2. **`-prometheus-addr` を複数の vegeta に付けない。** ウォームアップの for ループのように
   複数プロセスが順に起動・終了すると同じポートを奪い合い、
   **カウンタが毎回リセットされてグラフが読めなくなる**。付けるのは測定本体1本だけ
3. **`request_seconds` のバケット上限は 10 秒固定**（`prometheus.DefBuckets`。変更フラグ無し）。
   「10秒超の割合」は出せるが、**p95 が10秒を超えるケースの分位点は Grafana では出せない**。
   分位点は実行後の `vegeta report` を正とする
4. **Prometheus 3 は `le` を正規化して格納する。** exporter の出力は `le="10"` だが、
   クエリは **`le="10.0"`** でないとマッチしない。**エラーは出ず、ただ空になる**ので気づきにくい

## スクリプトに落とすときの注意

- **`| tail` や `| grep` を挟むとパイプ末尾の終了コードを拾う。** ビルド失敗や
  ツールの異常終了を exit 0 と誤認する。`set -o pipefail` を入れるか、
  終了コードを見る箇所ではパイプを挟まない
- **`set -euo pipefail` 下では `grep` の不一致（exit 1）がスクリプトを止める。**
  ログから値を拾うだけの箇所には必ず `|| true` を付ける
- **zsh では `UID` は readonly。** `read -r UID ...` が `failed to change user ID` で落ちる
- 失敗を潰さず区別する。`curl` の `rc=28` はタイムアウト（＝サーバが応答しない）、
  `rc=7` は connection refused（＝プロセスが落ちている）。
  一律 TIMEOUT 扱いにすると、再起動中の停止まで「詰まり」に見えてしまう

```bash
if R=$(curl -s -o /dev/null -w '%{http_code} %{time_total}s' --max-time 5 "$URL/health" 2>/dev/null); then
  echo "[health] $(date +%H:%M:%S) $R"
else
  case "$?" in
    28) echo "[health] $(date +%H:%M:%S) TIMEOUT(>5s)" ;;
    7)  echo "[health] $(date +%H:%M:%S) REFUSED" ;;
    *)  echo "[health] $(date +%H:%M:%S) FAIL(rc=$?)" ;;
  esac
fi
```

## おまけ: 「ALB slow start で緩和できる」は成り立たないことがある

切替シナリオの緩和策として ALB の slow start を測ろうとしたが、
**リスナールールの重み変更では slow start は発火しない**。

- slow start はターゲットが healthy になった時点で発火し、weight 変更では再発火しない
- 空のターゲットグループに一括登録したターゲットは slow start に入らない
  （"Newly registered targets enter slow start mode only when there is at least one
  healthy target that is not in slow start mode."）
- healthy 不足時の fail open では適用されない

なので測れるのは **weight の段階刻み**であって slow start ではない。
これを「slow start の効果」として持ち帰ると、発火しない機能を提案することになる。
