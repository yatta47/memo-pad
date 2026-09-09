# workshop-ai-catalog

AI活用事例カタログを題材にした社内ワークショップ（30分・全部ライブ）の環境。

- 計画: `docs/workshop-plan.md`
- 環境準備: `docs/step0-setup.md`
- 事例カードのスキーマ: `docs/case-schema.md`
- 当日貼る指示文: `docs/prompts/`

当日AIが作る4部品（`.claude/skills/`, `app/`, `sync/`, `mcp/`）はリポジトリに含めない。`scripts/reset.sh` で消す。

## 起動

```sh
cp .env.example .env   # 値を埋める
docker compose --project-directory . -f infra/compose.yml up -d
uv sync
```
