# Task Definition Template Diff Check

`modules/container_base/main.tf` の `container_definitions` 相当だけを切り出した最小検証用 root module。

目的:

- `templatefile()` で TaskDefinition JSON を読む
- `image_tag` だけを可変にする
- テンプレートの空白や key 順が違っても、`jsondecode -> jsonencode` で正規化すれば差分が安定することを確認する

このディレクトリでは AWS provider を使わず、Terraform 内の文字列比較だけに絞る。
そのため「レンダリング結果が安定か」は確認できるが、「AWS provider が state とどう比較するか」の最終確認は別途 `aws_ecs_task_definition` で行う。

## Files

- `taskdef.pretty.json.tftpl`
  - 読みやすく整形したテンプレート
- `taskdef.messy.json.tftpl`
  - 空白と key 順をわざと崩したテンプレート
- `main.tf`
  - `container_base` と同じ shape の `container_definitions` を組み立てる
  - `jsonencode(jsondecode(templatefile(...)))` で正規化する

## Run

```bash
terraform init
terraform apply -auto-approve
terraform plan
```

期待値:

- 2回目の `terraform plan` は `No changes` になる

次にテンプレートを切り替える:

```bash
terraform plan -var='template_variant=messy'
terraform apply -auto-approve -var='template_variant=messy'
terraform plan -var='template_variant=messy'
```

期待値:

- `pretty` と `messy` で raw JSON の見た目は違う
- ただし正規化後の `container_definitions` は同一なので、resource 差分は出ない

## Console Check

raw 文字列の hash は違うが、正規化後の hash は一致することを確認する:

```bash
terraform console
```

```hcl
sha256(templatefile("${path.module}/taskdef.pretty.json.tftpl", local.template_vars))
sha256(templatefile("${path.module}/taskdef.messy.json.tftpl", local.template_vars))
sha256(jsonencode(jsondecode(templatefile("${path.module}/taskdef.pretty.json.tftpl", local.template_vars))))
sha256(jsonencode(jsondecode(templatefile("${path.module}/taskdef.messy.json.tftpl", local.template_vars))))
```

## Next Step

provider レベルまで確認したい場合は、`modules/container_base/main.tf` の `aws_ecs_task_definition.main.container_definitions` に同じ正規化パターンを適用し、検証用 AWS 環境で次を確認する。

1. `terraform apply`
2. `image_tag` を変えずに `terraform plan`
3. テンプレートの空白や key 順だけ変えて `terraform plan`

この3で `No changes` なら、今回の懸念に対する実運用寄りの確認になる。
