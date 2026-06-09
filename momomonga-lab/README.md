# momomonga-lab

`momomonga-lab` は、実レビューをもとに「暮らしのなりたい状態」から商品を選べるようにする Next.js サイトです。

## Stack

- Next.js
- TypeScript
- MDX / JSON content
- Cloudflare deploy

## Content Model

- `content/articles`
  - 記事本文
- `content/products`
  - 商品台帳
- `content/states`
  - 目指す状態の定義

## Local Development

```bash
npm install
npm run dev
```

## Cloudflare

無料で始める前提では、まず GitHub 連携 + Cloudflare Pages/Workers を想定。

- static 寄りなら Pages
- SSR や route handlers を使うなら Workers

## Next Steps

1. 記事一覧 / 詳細の整備
2. 状態ページから記事・商品への逆引き
3. HTML ベースのカルーセルテンプレート
4. Cloudflare deploy 設定
5. 独自ドメイン接続
