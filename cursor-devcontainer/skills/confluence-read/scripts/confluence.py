#!/usr/bin/env python3
"""Confluence Cloud reader/writer — タスク管理ページの閲覧と進捗コメント追記。

会社PCの Cursor / Claude Code から Confluence Cloud を:
  - 読む（CQL検索 / ページ本文を Markdown 取得 / スペース・ページ一覧）
  - 書く（タスク管理ページに「進捗ログ」を footer コメントとして追記）
ための最小ツール。atlassian-python-api ベース。

依存（devcontainer 内で実施）:
  pip install atlassian-python-api

認証（環境変数。コードに固有情報は持たない）:
  CONFLUENCE_BASE_URL   例: https://your-org.atlassian.net   （末尾に /wiki は付けない）
  CONFLUENCE_EMAIL      Atlassian アカウントのメール
  CONFLUENCE_API_TOKEN  https://id.atlassian.com/manage-profile/security/api-tokens で発行

━━ 安全装置（書き込み）━━
  * comment はデフォルト dry-run。--save を付けて初めて実投稿する。
  * dry-run / 投稿いずれも、先に対象ページのタイトルを取得して表示し、
    page_id 取り違えによる誤爆を防ぐ。
  * 書くのは footer コメント追記のみ。タスク表（本文）は一切変更しない。
  * 取消: 投稿したコメントの削除は Confluence Web UI から行う（本ツールは削除しない）。

使い方（CLI フラグは内部実装。Cursor/CC からは自然言語で呼ぶ想定）:
  検索:        confluence.py search "デプロイ 手順" [--space KEY] [--limit 10]
  検索(CQL):   confluence.py search --cql 'space = DEV AND text ~ "ECS"'
  ページ取得:  confluence.py page 123456 [--raw]
  スペース一覧 confluence.py spaces
  ページ一覧:  confluence.py pages --space DEV
  進捗コメント confluence.py comment 123456 --text "Issue#42 着手。設計レビュー完了"        # dry-run
               confluence.py comment 123456 --text "...進捗..." --save                       # 実投稿
"""
import argparse
import html
import os
import sys
from html.parser import HTMLParser

try:
    from atlassian import Confluence
except ImportError:
    sys.exit(
        "[error] atlassian-python-api が未インストールです。\n"
        "  devcontainer 内で: pip install atlassian-python-api"
    )


def _env(name):
    v = os.environ.get(name)
    if not v:
        sys.exit(
            f"[error] 環境変数 {name} が未設定です。\n"
            "  CONFLUENCE_BASE_URL / CONFLUENCE_EMAIL / CONFLUENCE_API_TOKEN を設定してください。"
        )
    return v


def client():
    return Confluence(
        url=_env("CONFLUENCE_BASE_URL").rstrip("/"),
        username=_env("CONFLUENCE_EMAIL"),
        password=_env("CONFLUENCE_API_TOKEN"),
        cloud=True,
    )


# --- storage(XHTML) → Markdown 簡易変換（表対応）-----------------------------
class _StorageToMarkdown(HTMLParser):
    """Confluence storage format(XHTML) を雑に Markdown 化する。
    MVP のため完璧は狙わない。マクロ・添付・ネスト表は簡易/欠落あり（README 参照）。
    タスク管理が「1ページに表で集約」なので、表は | 区切りで読めるよう優先対応。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._list_depth = 0
        self._in_code = False
        self._href = None
        self._in_table = False
        self._row_idx = 0
        self._row_cols = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if not self._in_table:
                self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "p":
            if not self._in_table:        # 表セル内の <p> 改行はテーブルを壊すので抑制
                self.out.append("\n\n")
        elif tag == "br":
            self.out.append(" " if self._in_table else "\n")
        elif tag == "li":
            if not self._in_table:
                self.out.append("\n" + "  " * max(0, self._list_depth - 1) + "- ")
        elif tag in ("ul", "ol"):
            self._list_depth += 1
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag == "code":
            self.out.append("`")
            self._in_code = True
        elif tag == "pre":
            self.out.append("\n```\n")
        elif tag == "a":
            self._href = a.get("href")
            self.out.append("[")
        elif tag == "table":
            self._in_table = True
            self._row_idx = 0
            self.out.append("\n\n")
        elif tag == "tr":
            self._row_cols = 0
            self.out.append("\n")
        elif tag in ("td", "th"):
            self._row_cols += 1
            self.out.append("| ")

    def handle_endtag(self, tag):
        if tag in ("ul", "ol"):
            self._list_depth = max(0, self._list_depth - 1)
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag == "code":
            self.out.append("`")
            self._in_code = False
        elif tag == "pre":
            self.out.append("\n```\n")
        elif tag == "a":
            self.out.append(f"]({self._href})" if self._href else "]")
            self._href = None
        elif tag in ("td", "th"):
            self.out.append(" ")
        elif tag == "tr":
            self.out.append("|")
            if self._row_idx == 0 and self._row_cols:
                self.out.append("\n" + "| --- " * self._row_cols + "|")
            self._row_idx += 1
        elif tag == "table":
            self._in_table = False
            self.out.append("\n")

    def handle_data(self, data):
        # 表のセル内改行は崩れるので空白化
        self.out.append(data.replace("\n", " ") if self._in_table else data)

    def text(self):
        md = "".join(self.out)
        lines, blank = [], 0
        for ln in md.splitlines():
            if ln.strip() == "":
                blank += 1
                if blank <= 2:
                    lines.append("")
            else:
                blank = 0
                lines.append(ln.rstrip())
        return "\n".join(lines).strip() + "\n"


def storage_to_markdown(html):
    p = _StorageToMarkdown()
    p.feed(html or "")
    return p.text()


def _page_label(c, page_id):
    """page_id から「タイトル + URL」を取り、取り違え防止に表示する。"""
    try:
        pg = c.get_page_by_id(page_id, expand="space")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"[error] page_id={page_id} の取得に失敗: {e}")
    title = pg.get("title", "(no title)")
    base = _env("CONFLUENCE_BASE_URL").rstrip("/")
    webui = (((pg.get("_links") or {}).get("webui")) or "")
    url = f"{base}{webui}" if webui else "(URL 不明)"
    return title, url


# --- commands ---------------------------------------------------------------
def cmd_search(args):
    c = client()
    if args.cql:
        cql = args.cql
    else:
        cql = f'text ~ "{" ".join(args.query)}"'
        if args.space:
            cql = f'space = "{args.space}" AND {cql}'
    res = c.cql(cql, limit=args.limit) or {}
    results = res.get("results", [])
    if not results:
        print(f"(0 件) CQL: {cql}")
        return
    print(f"# 検索結果 {len(results)} 件  (CQL: {cql})\n")
    for r in results:
        content = r.get("content", {}) or {}
        title = content.get("title") or r.get("title") or "(no title)"
        print(f"- [{content.get('type','')}] {title}  (id={content.get('id','')})")


def cmd_page(args):
    c = client()
    pg = c.get_page_by_id(args.page_id, expand="body.storage,version,space")
    title = pg.get("title", "(no title)")
    body = (((pg.get("body") or {}).get("storage") or {}).get("value")) or ""
    ver = (pg.get("version") or {}).get("number")
    print(f"# {title}\n")
    print(f"<!-- page id: {pg.get('id')}  version: {ver} -->\n")
    print(body if args.raw else storage_to_markdown(body))


def cmd_spaces(args):
    c = client()
    res = c.get_all_spaces(limit=args.limit) or {}
    for s in res.get("results", []):
        print(f"- {s.get('key')}  {s.get('name')}")


def cmd_pages(args):
    if not args.space:
        sys.exit("[error] --space <SPACEKEY> を指定してください。")
    c = client()
    for p in c.get_all_pages_from_space(args.space, limit=args.limit) or []:
        print(f"- {p.get('title')}  (id={p.get('id')})")


def cmd_comment(args):
    """進捗を footer コメントとして追記。デフォルト dry-run、--save で実投稿。"""
    c = client()
    title, url = _page_label(c, args.page_id)            # 取り違え防止に必ず先に表示
    body_html = "<p>" + html.escape(args.text).replace("\n", "<br/>") + "</p>"

    print("─── 投稿対象 ───")
    print(f"  ページ : {title}")
    print(f"  URL    : {url}")
    print(f"  内容   : {args.text}")
    print("────────────────")

    if not args.save:
        print("\n[dry-run] 実投稿していません。問題なければ同じコマンドに --save を付けて再実行してください。")
        return

    result = c.add_comment(args.page_id, body_html)
    cid = (result or {}).get("id")
    if cid:
        print(f"\n[done] コメントを追記しました（comment id={cid}）。")  # 戻り id で完了検証
    else:
        sys.exit(f"\n[error] 投稿レスポンスに id がありません。実際に追記されたか Web UI で確認してください: {result}")


def build_parser():
    ap = argparse.ArgumentParser(description="Confluence Cloud reader/writer (progress comments)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="CQL/キーワード検索")
    s.add_argument("query", nargs="*")
    s.add_argument("--cql")
    s.add_argument("--space")
    s.add_argument("--limit", type=int, default=10)
    s.set_defaults(func=cmd_search)

    p = sub.add_parser("page", help="ページ本文を Markdown 取得")
    p.add_argument("page_id")
    p.add_argument("--raw", action="store_true")
    p.set_defaults(func=cmd_page)

    sp = sub.add_parser("spaces", help="スペース一覧")
    sp.add_argument("--limit", type=int, default=50)
    sp.set_defaults(func=cmd_spaces)

    pg = sub.add_parser("pages", help="スペース内ページ一覧")
    pg.add_argument("--space")
    pg.add_argument("--limit", type=int, default=50)
    pg.set_defaults(func=cmd_pages)

    cm = sub.add_parser("comment", help="進捗を footer コメントとして追記（既定 dry-run）")
    cm.add_argument("page_id")
    cm.add_argument("--text", required=True, help="追記する進捗テキスト")
    cm.add_argument("--save", action="store_true", help="実投稿する（無指定なら dry-run）")
    cm.set_defaults(func=cmd_comment)

    return ap


def main():
    args = build_parser().parse_args()
    try:
        args.func(args)
    except SystemExit:
        raise  # 自前の sys.exit メッセージはそのまま通す
    except Exception as e:  # noqa: BLE001  API/権限/接続エラーをLLM向けに親切表示
        sys.exit(f"[error] API 呼び出しに失敗しました: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
