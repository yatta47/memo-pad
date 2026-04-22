# tf-dump

Terraformモジュールを1つのテキストにまとめて、生成AIに貼り付けて解析させるためのシェルスクリプト。

## できること

- 指定したディレクトリ配下の `*.tf` をファイル名ごとに区切ってstdoutに出力
- `module` ブロックの `source` にローカルパス（`./...` / `../...`）があれば、**参照先モジュールも再帰的に展開**
- レジストリやGit source（`hashicorp/aws`等）は「外部参照」として名前だけリスト化（本文は展開しない）
- 循環参照は visited チェックでスキップ

## 使い方

```bash
./tf-dump.sh path/to/terraform/module > dump.txt
```

例: `ecs-deployment-poc` の ecs-platform モジュールをdump

```bash
./tools/tf-dump/tf-dump.sh ~/repos/github/ecs-deployment-poc/src/terraform/infra_modules/ecs-platform > /tmp/ecs-platform-dump.txt
```

出力は以下のような構造:

```
===== Terraform Module Dump =====
Root: /path/to/module
Generated: 2026-04-22T15:49:43+09:00
Local modules expanded: 5

===== LOCAL MODULES =====
- .
- ../../resource_modules/security-group
...

===== EXTERNAL SOURCES (not expanded) =====
- hashicorp/aws

===== FILE: main.tf =====
<本文>

===== FILE: ../../resource_modules/security-group/main.tf =====
<本文>
...
```

## 含まれないもの（意図的に除外）

- `*.tfvars` / `*.tfstate` （機密混入リスク）
- `.terraform/` 配下
- README等の `*.md`
- レジストリ/Git sourceの中身

## 前提

- bash 4以上（連想配列を使用）
- GNU `realpath`（Linux標準）
- `sed` / `shopt`
