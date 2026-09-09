"""ワークショップ用スライド（Day1 / Day2）を生成する。共通部品を1箇所に持つ。

使い方: python3 build_slides.py → docs/slides/day1-*.html, day2-*.html（本編）と *-appendix.html（講師用カンペ）
図の部品や配置は NODES / ARROWS を直せば全スライドに反映される。
"""
import html
from pathlib import Path

ROOT = Path("/home/yatta47/repos/github/workshop-ai-catalog")
OUT = ROOT / "docs/slides"
PROMPTS = ROOT / "docs/prompts"

HEAD = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {{ theme: {{ extend: {{ fontFamily: {{ sans: ['"Noto Sans JP"', 'system-ui', 'sans-serif'] }} }} }} }}
  </script>
  <style>
    body {{ background: #e5e7eb; margin: 0; }}
    .slide {{
      aspect-ratio: 16 / 9; max-width: 1280px; width: 100%;
      margin: 24px auto; background: #fff; border-radius: 12px;
      box-shadow: 0 4px 24px rgba(0,0,0,.12); padding: 44px 60px;
      box-sizing: border-box; display: flex; flex-direction: column; overflow: hidden;
    }}
    .slide {{ position: relative; }}
    .slide::after {{ content: attr(data-n) " / " attr(data-total); position: absolute; bottom: 14px; right: 22px; font-size: 12px; color: #94a3b8; }}
    .tips {{ display: inline-flex; align-items: center; background: #065f46; color: #fff; border-radius: 8px; padding: 4px 12px; font-weight: 700; font-size: 16px; margin-right: 10px; letter-spacing: .04em; }}
    .tips-step {{ font-size: 13px; color: #64748b; margin-right: 12px; }}
    .step {{ display: inline-flex; align-items: center; background: #0f172a; color: #fff; border-radius: 8px; padding: 4px 12px; font-weight: 700; font-size: 16px; margin-right: 12px; letter-spacing: .02em; }}
    .tag {{ display: inline-block; border-radius: 6px; padding: 1px 8px; font-size: 12px; font-weight: 600; vertical-align: middle; }}
    .tag-info {{ background: #dbeafe; color: #1e40af; }}
    .tag-inst {{ background: #fee2e2; color: #991b1b; }}
    .num {{ display: inline-flex; width: 26px; height: 26px; border-radius: 999px; background: #0f172a; color: #fff; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; margin-right: 8px; flex: none; }}
    pre.cheat {{ background: #0f172a; color: #e2e8f0; border-radius: 10px; padding: 12px 14px; font-size: 11px; line-height: 1.5; white-space: pre-wrap; overflow: hidden; margin: 0; }}
    .fig {{ height: 100%; display: flex; align-items: center; justify-content: center; }}
    .fig svg {{ width: 100%; height: 100%; }}
    @media print {{ body {{ background: #fff; }} .slide {{ break-inside: avoid; page-break-after: always; margin: 0; box-shadow: none; border-radius: 0; }} }}
  </style>
</head>
<body class="font-sans text-slate-800">
"""

FOOT = """
<script>
  const slides = Array.from(document.querySelectorAll('.slide'));
  let current = 0;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting && e.intersectionRatio > 0.5) {
        current = slides.indexOf(e.target);
      }
    });
  }, { threshold: [0.5] });
  slides.forEach((s) => observer.observe(s));
  function go(i) {
    current = Math.max(0, Math.min(slides.length - 1, i));
    slides[current].scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  document.addEventListener('keydown', (e) => {
    if (['ArrowRight', 'ArrowDown', ' ', 'PageDown'].includes(e.key)) { e.preventDefault(); go(current + 1); }
    if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(e.key)) { e.preventDefault(); go(current - 1); }
    if (e.key === 'Home') { e.preventDefault(); go(0); }
    if (e.key === 'End') { e.preventDefault(); go(slides.length - 1); }
  });
</script>
</body>
</html>
"""

# ---------- アーキテクチャ図（以降のスライドでも使い回す） ----------

AI = "fill:#fff4d6;stroke:#f59e0b;stroke-width:2.5"
WH = "fill:#ffffff;stroke:#94a3b8;stroke-width:2"
DB = "fill:#f8fafc;stroke:#94a3b8;stroke-width:2"

# key: (x, y, w, h, ai_made, title, sub, step, group)   group: "local" | "jira"
NODES = {
    "browser":  (30, 140, 110, 70, False, "Web Browser", "", "", "local"),
    "article":  (30, 300, 110, 60, False, "記事URL", "AWS導入事例など", "", "local"),
    "frontend": (210, 140, 200, 70, True, "Web画面", "Frontend + Backend", "STEP 3", "local"),
    "skill":    (210, 300, 140, 60, True, "SKILL", "URL → カード", "STEP 1", "local"),
    "catalog":  (380, 300, 120, 60, False, "Catalog", "JSON 48件", "", "local"),
    "pgmcp":    (540, 140, 150, 70, False, "PostgreSQL MCP", "既製品", "STEP 2", "local"),
    "pg":       (780, 140, 220, 74, False, "PostgreSQL", "cases（＋pgvector, AGE）", "STEP 4", "local"),
    "mymcp":    (540, 262, 150, 70, True, "自作MCP", "読み取り3ツール", "STEP 6", "jira"),
    "sync":     (780, 290, 220, 72, True, "sync application", "バッチ、LLMなし", "STEP 5", "jira"),
    "jira":     (780, 466, 220, 70, False, "Jira", "台帳。他の人もフォームで起票できる", "", "jira"),
}
# (from, to, path, label, label_xy)
ARROWS = [
    ("browser", "frontend", "M140,175 L208,175", "", None),
    ("frontend", "pg", "M310,138 L310,100 L890,100 L890,136", "SQL", (600, 93)),
    ("article", "skill", "M140,330 L208,330", "", None),
    ("skill", "catalog", "M350,330 L378,330", "", None),
    ("catalog", "pgmcp", "M500,330 L520,330 L520,175 L538,175", "", None),
    ("pgmcp", "pg", "M690,175 L778,175", "MCP", (734, 166)),
    ("pg", "sync", "M890,214 L890,288", "片方向・冪等", (905, 256)),
    ("sync", "jira", "M890,362 L890,464", "", None),
    ("mymcp", "jira", "M615,332 L615,494 L776,494", "読むだけ（API token）", (700, 486)),
]


def arch_svg(colored: bool, focus: list[str] | None = None, jira: bool = False) -> str:
    """colored=False: 色分けなしのフラット版。True: AIに作らせる部品を橙で、STEP番号付き。
    focus: 囲んで強調する部品（他は薄く）。jira: Jira 側（sync / 自作MCP / Jira）を描くか。"""
    keys = [k for k, v in NODES.items() if jira or v[8] == "local"]

    def vis(key: str) -> float:
        if focus:
            return 1.0 if key in focus else 0.28
        return 1.0

    height = 560 if jira else 490
    parts = [f"""
<svg viewBox="0 0 1120 {height}" style="font-family:'Noto Sans JP',system-ui,sans-serif" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="ah" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L10,5 L0,10 z" fill="#64748b"/>
    </marker>
  </defs>
  <rect x="10" y="14" width="1100" height="420" rx="14" fill="#fafafa" stroke="#cbd5e1" stroke-width="2" stroke-dasharray="8 6"/>
  <text x="26" y="40" font-size="15" fill="#64748b" font-weight="700">Local PC</text>
  <rect x="170" y="56" width="920" height="360" rx="12" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>
  <text x="186" y="80" font-size="14" fill="#64748b" font-weight="700">Docker Desktop</text>
  <rect x="190" y="96" width="520" height="300" rx="12" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="2"/>
  <text x="206" y="120" font-size="14" fill="#64748b" font-weight="700">Development VM（Cursor / Claude Code が動く場所）</text>
"""]
    parts.append('  <g stroke="#64748b" stroke-width="2" fill="none" marker-end="url(#ah)">')
    for a, b, path, _, _ in ARROWS:
        if a in keys and b in keys:
            parts.append(f'    <path d="{path}" opacity="{min(vis(a), vis(b))}"/>')
    parts.append("  </g>")
    for a, b, _, label, xy in ARROWS:
        if label and a in keys and b in keys:
            anchor = "middle" if xy[0] < 880 else "start"
            parts.append(f'  <text x="{xy[0]}" y="{xy[1]}" font-size="12" fill="#64748b" text-anchor="{anchor}" opacity="{min(vis(a), vis(b))}">{label}</text>')
    for key in keys:
        x, y, w, h, ai_made, title, sub, step, _ = NODES[key]
        style = AI if (colored and ai_made) else (DB if key in ("pg", "jira") else WH)
        sub_text = f"{step}　{sub}" if (colored and step) else sub
        sub_color = "#92400e" if (colored and ai_made) else "#64748b"
        o = vis(key)
        cx = x + w / 2
        if key == "jira":
            parts.append(f"""  <g opacity="{o}">
    <path d="M{x},{y + 12} a{w / 2},12 0 0,1 {w},0 v{h - 24} a{w / 2},12 0 0,1 -{w},0 z" style="{style}"/>
    <path d="M{x},{y + 12} a{w / 2},12 0 0,0 {w},0" fill="none" stroke="#94a3b8" stroke-width="2"/>
    <text x="{cx}" y="{y + 46}" font-size="16" text-anchor="middle" font-weight="700">{title}</text>
    <text x="{cx}" y="{y + h + 14}" font-size="12" text-anchor="middle" fill="{sub_color}">{sub_text}</text>
  </g>""")
            continue
        ty = y + h / 2 + (5 if not sub_text else -4)
        parts.append(f"""  <g opacity="{o}">
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" style="{style}"/>
    <text x="{cx}" y="{ty}" font-size="15" text-anchor="middle" font-weight="700">{title}</text>""")
        if sub_text:
            parts.append(f'    <text x="{cx}" y="{ty + 20}" font-size="12" text-anchor="middle" fill="{sub_color}">{sub_text}</text>')
        parts.append("  </g>")
    if focus:
        xs = [NODES[k][0] for k in focus]; ys = [NODES[k][1] for k in focus]
        xe = [NODES[k][0] + NODES[k][2] for k in focus]; ye = [NODES[k][1] + NODES[k][3] for k in focus]
        pad = 16
        parts.append(f'  <rect x="{min(xs) - pad}" y="{min(ys) - pad}" width="{max(xe) - min(xs) + pad * 2}" height="{max(ye) - min(ys) + pad * 2 + (18 if "jira" in focus else 0)}" rx="14" fill="none" stroke="#dc2626" stroke-width="3" stroke-dasharray="10 7"/>')
    if colored:
        parts.append(f"""  <rect x="26" y="{height - 8 - 40}" width="18" height="14" rx="3" style="{AI}"/>
  <text x="50" y="{height - 8 - 28}" font-size="13" fill="#334155">AIに作らせる部品</text>
  <rect x="26" y="{height - 8 - 14}" width="18" height="14" rx="3" style="{WH}"/>
  <text x="50" y="{height - 8 - 2}" font-size="13" fill="#334155">既製品・データ</text>""")
    parts.append("</svg>")
    return "\n".join(parts)


def slide(inner: str, cls: str = "") -> str:
    return f'<div class="slide {cls}">\n{inner}\n</div>\n'


def title_slide(day: str, title: str, sub: str) -> str:
    return slide(f"""
  <p class="text-lg text-slate-500 mb-4">社内ワークショップ　{day}（30分・全部ライブ）</p>
  <h1 class="text-5xl font-bold leading-tight mb-6">{title}</h1>
  <p class="text-2xl text-slate-700 mb-10">{sub}</p>
  <p class="text-base text-slate-500">yatta47 ／ 2026-09</p>
""", "justify-center items-center text-center")


def arch_slide(title: str, lead: str, colored: bool, jira: bool = False, foot: str = "") -> str:
    return slide(f"""
  <h2 class="text-3xl font-bold mb-1">{title}</h2>
  <p class="text-slate-500 mb-2">{lead}</p>
  <div class="flex-1 min-h-0 fig">{arch_svg(colored, None, jira)}</div>
  {f'<p class="mt-2 text-sm text-slate-500">{foot}</p>' if foot else ''}
""")


def step_slide(step: str, title: str, want: str, focus: list[str], doing: list[str], note: str = "", jira: bool = False) -> str:
    """やりたいこと（1行） → 全体のどこか（図、大きめ）と ここでやること を同じ高さで横並び。"""
    items = "".join(f"<li>{d}</li>" for d in doing)
    return slide(f"""
  <div class="flex items-center mb-2"><span class="step">{step}</span><h2 class="text-3xl font-bold">{title}</h2></div>
  <p class="text-xl font-bold border-l-4 border-slate-800 pl-4 mb-4"><span class="text-xs font-normal text-slate-500 mr-3">やりたいこと</span>{want}</p>
  <div class="grid grid-cols-12 gap-5 flex-1 min-h-0">
    <div class="col-span-3 border rounded-xl p-4 text-sm flex flex-col">
      <p class="text-xs text-slate-500 mb-2">ここでやること</p>
      <ul class="list-disc pl-5 space-y-2 text-slate-800">{items}</ul>
      {f'<p class="mt-auto pt-3 text-xs text-slate-500">{note}</p>' if note else ''}
    </div>
    <div class="col-span-9 border rounded-xl p-2 min-h-0 flex flex-col">
      <p class="text-xs text-slate-500 mb-1">全体のどこか</p>
      <div class="flex-1 min-h-0 fig">{arch_svg(True, focus, jira)}</div>
    </div>
  </div>
""")


def tips_head(step: str, title: str) -> str:
    return f'<div class="flex items-center mb-2"><span class="tips">TIPS</span><span class="tips-step">{step}</span><h2 class="text-3xl font-bold">{title}</h2></div>'


def tips_slide(step: str, title: str, oneliner: str, blocks: list[tuple[str, list[str]]], foot: str = "") -> str:
    """初学者向けの補足。1スライド1内容。ひとことで → 2〜3列（何か／いつ使う／注意 など）。"""
    cols = "".join(
        f'<div class="border rounded-xl p-5 min-h-0"><p class="text-sm text-slate-500 mb-3">{h}</p>'
        f'<ul class="list-disc pl-5 space-y-3 text-slate-800 leading-relaxed">{"".join(f"<li>{i}</li>" for i in items)}</ul></div>'
        for h, items in blocks)
    return slide(f"""
  {tips_head(step, title)}
  <div class="bg-emerald-50 border-l-4 border-emerald-700 text-slate-900 rounded-r-xl px-6 py-3 text-xl font-semibold mb-4">{oneliner}</div>
  <div class="grid grid-cols-{len(blocks)} gap-5 flex-1 min-h-0 text-base">{cols}</div>
  {f'<p class="mt-3 text-base text-slate-600">{foot}</p>' if foot else ''}
""")


def finalize(s: str) -> str:
    """各スライドに n / N を埋め込む（固定の浮きカウンタは使わない。印刷でも出る）。"""
    total = s.count('<div class="slide')
    n = [0]
    def rep(m):
        n[0] += 1
        return f'<div class="slide{m.group(1)}" data-n="{n[0]}" data-total="{total}">'
    import re
    return re.sub(r'<div class="slide([^"]*)">', rep, s)


def cheat_slide(title: str, blocks: list[tuple[str, str]], cols: int = 2) -> str:
    body = "".join(f'<div><p class="font-bold text-sm mb-1">{h}</p><pre class="cheat">{html.escape(t)}</pre></div>' for h, t in blocks)
    return slide(f"""
  <div class="flex items-baseline justify-between mb-2"><h2 class="text-2xl font-bold">{title}</h2><span class="text-xs text-slate-400">講師用カンペ。参加者には見せない</span></div>
  <div class="grid grid-cols-{cols} gap-4 flex-1 overflow-hidden">{body}</div>
""")


def appendix_cover(day: str, items: list[str]) -> str:
    lis = "".join(f"<li>{i}</li>" for i in items)
    return slide(f"""
  <p class="text-lg text-slate-500 mb-3">社内ワークショップ　{day}</p>
  <h1 class="text-4xl font-bold mb-3">付録：講師用カンペ</h1>
  <p class="text-slate-600 mb-6">当日 AI に貼る指示文と発話。参加者には見せない（本編スライドとは別ファイル）</p>
  <ul class="list-disc pl-6 text-lg space-y-2 text-slate-800">{lis}</ul>
""", "justify-center")


def prompt_text(name: str) -> str:
    """区切り線 --- の後ろが本文の形式（01-skill.md, 03-webapp.md）。"""
    t = (PROMPTS / name).read_text(encoding="utf-8")
    body = t.split("---", 1)[1] if "---" in t else t
    return body.strip()


def prompt_before_rule(name: str) -> str:
    """見出し行の後、区切り線 --- の前が本文の形式（01-skill-sloppy.md, 02-insert.md）。"""
    t = (PROMPTS / name).read_text(encoding="utf-8")
    body = t.split("---", 1)[0]
    lines = [l for l in body.splitlines() if not l.startswith("# ")]
    return "\n".join(lines).strip()


SUMMARY = """
  <h2 class="text-3xl font-bold mb-2">まとめ: 今日伝えたかったこと</h2>
  <p class="text-slate-600 mb-4 text-lg">雑に指示しても、作ってはくれる。ただし<strong>手直しが多くなる</strong></p>
  <div class="bg-slate-900 text-white rounded-xl px-8 py-5 text-2xl font-semibold mb-6">
    認識違いを減らすには<br>
    <span class="text-amber-300">正しい情報（コンテキスト）</span> と <span class="text-rose-300">正しい指示（プロンプト）</span> が要る
  </div>
  <div class="grid grid-cols-2 gap-6 text-sm">
    <div class="border-2 border-blue-200 rounded-xl p-4">
      <p class="font-bold text-blue-800 mb-2"><span class="tag tag-info">コンテキスト</span>　人が用意する事実</p>
      <ul class="list-disc pl-5 space-y-1 text-slate-700">
        <li>事例カードのスキーマ（12項目）と困りごとの型、基盤名の辞書</li>
        <li>テーブル名・列名・型、接続文字列</li>
        <li>使うライブラリのバージョン</li>
      </ul>
    </div>
    <div class="border-2 border-rose-200 rounded-xl p-4">
      <p class="font-bold text-rose-800 mb-2"><span class="tag tag-inst">プロンプト</span>　設計判断を言葉にしたもの</p>
      <ul class="list-disc pl-5 space-y-1 text-slate-700">
        <li>記事に無いことを補わない</li>
        <li>MCPだけで、まとめて、重複しても壊れないように</li>
        <li>機能は3つ。書き込みは作らない。確認してから終わる</li>
      </ul>
    </div>
  </div>
  <p class="mt-auto text-sm text-slate-500">手直しの1回1回は「足りなかった情報」か「言っていなかった判断」。それを先に用意するのが人の仕事。今日の事前準備（スキーマ、辞書、指示文）がそのまま証拠</p>
"""

TWIST = """
  <h2 class="text-3xl font-bold mb-1">…という形で説明しましたが</h2>
  <p class="text-slate-600 mb-4 text-lg">今日の進め方は「見せるため」の形。実際に作るときは、<strong>仕様を先に固めて一気に作る</strong>のが主流になった（2026）</p>
  <div class="grid grid-cols-2 gap-6 flex-1 min-h-0">
    <div class="border rounded-xl p-5 flex flex-col">
      <p class="font-bold text-lg mb-3">今日（見せるため）</p>
      <div class="flex items-center gap-2 text-sm mb-4">
        <span class="bg-slate-200 rounded px-3 py-2 font-semibold">STEP 1</span><span>→</span>
        <span class="bg-slate-200 rounded px-3 py-2 font-semibold">STEP 2</span><span>→</span>
        <span class="bg-slate-200 rounded px-3 py-2 font-semibold">STEP 3</span><span>→</span>
        <span class="bg-slate-200 rounded px-3 py-2 font-semibold">…</span>
      </div>
      <ul class="list-disc pl-5 space-y-2 text-base text-slate-800">
        <li>1つずつ積み上げる。前の STEP の結果を見てから次の指示を書く</li>
        <li>エージェントは1つ。会話も1本。ループを回すのは人</li>
        <li>失敗したら「何が足りなかったか」を指して直す</li>
        <li>向く場面: 仕様がまだ無い探索、初めて作るもの</li>
      </ul>
    </div>
    <div class="border-2 border-orange-300 rounded-xl p-5 flex flex-col">
      <p class="font-bold text-lg mb-3 text-orange-800">実際（作るため）: 仕様先行 ＋ 並列</p>
      <div class="flex items-center gap-2 text-sm mb-4">
        <span class="bg-orange-100 rounded px-3 py-2 font-semibold">spec → plan → tasks</span><span>→</span>
        <div class="flex flex-col gap-1">
          <span class="bg-orange-100 rounded px-3 py-1 font-semibold">SKILL</span>
          <span class="bg-orange-100 rounded px-3 py-1 font-semibold">画面</span>
          <span class="bg-orange-100 rounded px-3 py-1 font-semibold">導出処理・MCP</span>
        </div><span>→</span>
        <span class="bg-orange-100 rounded px-3 py-2 font-semibold">検査・統合</span>
      </div>
      <ul class="list-disc pl-5 space-y-2 text-base text-slate-800">
        <li>仕様先行（spec-driven）: スキーマ・機能・やらないこと・確認方法を先に書き、計画とタスクに割ってから書かせる。Spec Kit / Kiro / plan mode はみな同じ3段</li>
        <li>並列: 部品ごとに別のエージェント、別の作業コピー（git worktree）。効くのは<strong>部品が独立し、機械的に検査できるとき</strong>だけ。トークンは体数以上に増える</li>
        <li>人は仕様と検査の設計に時間を使う。途中の会話は見ない</li>
      </ul>
    </div>
  </div>
  <div class="mt-3 border-l-4 border-emerald-700 bg-emerald-50 rounded-r-xl px-5 py-2 text-sm text-slate-800">
    <span class="font-bold mr-2">補足</span>仕様先行＋並列にすると効きが増す2つの設計。<strong>ハーネスエンジニアリング</strong>（モデルの周りに置く型と検査: CLAUDE.md、SKILL、MCP、検査スクリプト）と<strong>ループエンジニアリング</strong>（作る → 検査 → 直す の回し方: 誰が回すか、何で止まるか）。Day 2 で詳しく
  </div>
  <div class="mt-3 bg-slate-900 text-white rounded-xl px-6 py-4 text-lg font-semibold">
    一つずつ直す型は「速く感じるが手直しに時間を食う」（METR の比較試験: 19%遅いのに20%速く感じた）。並列にしても変わらないのは、最初に渡す <span class="text-amber-300">情報</span> と <span class="text-rose-300">指示</span> の質
  </div>
"""

TWIST2 = """
  <h2 class="text-3xl font-bold mb-1">ハーネスエンジニアリングと、ループエンジニアリング</h2>
  <p class="text-slate-600 mb-4 text-lg">「仕様先行で一気に」を成り立たせる2つの設計。どちらも今日の中に実物がある</p>
  <div class="grid grid-cols-2 gap-6 flex-1 min-h-0">
    <div class="border-2 border-blue-200 rounded-xl p-5 flex flex-col">
      <p class="font-bold text-lg mb-2 text-blue-800">ハーネスエンジニアリング</p>
      <p class="text-sm text-slate-600 mb-3">モデルの<strong>周り</strong>を設計する。「そこそこのモデル＋良いハーネス」は「最強のモデル＋悪いハーネス」に勝つ</p>
      <ul class="list-disc pl-5 space-y-2 text-base text-slate-800">
        <li><strong>事前に効くもの（guides）</strong>: CLAUDE.md / AGENTS.md、SKILL、MCP、hooks、権限（渡す鍵）</li>
        <li><strong>事後に効くもの（sensors）</strong>: テスト、lint、検査スクリプト、CI。外れたら自動で戻す</li>
        <li><strong>育て方（ratchet）</strong>: 失敗するたびに1行足す。全ての行が「実際に起きた失敗」に遡れる状態を保つ</li>
        <li>今日の実物: SKILL、スキーマと辞書、検査スクリプト、rw / ro のロール、リハーサルで足した指示文の3行</li>
      </ul>
    </div>
    <div class="border-2 border-emerald-200 rounded-xl p-5 flex flex-col">
      <p class="font-bold text-lg mb-2 text-emerald-800">ループエンジニアリング</p>
      <p class="text-sm text-slate-600 mb-3">「作る → 検査 → 直す」の<strong>回し方</strong>を設計する。誰が回すか、何で止まるか、状態をどこに残すか</p>
      <ul class="list-disc pl-5 space-y-2 text-base text-slate-800">
        <li><strong>誰が回すか</strong>: 今日は人（失敗 → 足りない情報を指す → 再実行）。実際はエージェントに渡す</li>
        <li><strong>何で止まるか</strong>: 「動いた」ではなく「検査が通った」。止まる条件を先に書く</li>
        <li><strong>状態をどこに残すか</strong>: 会話ではなくファイルと Issue。会話が切れても続きから回せる（Ralph loop の型）</li>
        <li>今日の実物: 検査スクリプトを通してから終わる、という指示文の1行。一番小さいループ</li>
      </ul>
    </div>
  </div>
  <div class="mt-4 bg-slate-900 text-white rounded-xl px-6 py-4 text-lg font-semibold">
    今日の積み上げは「仕様を発見するフェーズ」だった。次に同じものを作るなら、この<span class="text-amber-300">スキーマと指示文</span>と<span class="text-blue-300">ハーネス</span>を最初に渡して、並列で回す
  </div>
"""


# ---------- Day 1 ----------

def hw_step(n: int, title: str, file: str, lines: list[str], extra: str = "", hot: bool = False) -> str:
    cls = "border-orange-300 bg-orange-50" if hot else "border-slate-300 bg-white"
    lis = "".join(f"<li>{l}</li>" for l in lines)
    return f"""
    <div class="border-2 {cls} rounded-xl p-3 flex flex-col min-h-0">
      <div class="flex items-center mb-1"><span class="num">{n}</span><span class="font-bold text-lg leading-tight">{title}</span></div>
      <p class="text-xs font-mono text-slate-500 mb-3">{file}</p>
      <ul class="list-disc pl-4 space-y-2 text-sm text-slate-800 leading-snug">{lis}</ul>
      {extra}
    </div>"""


HOMEWORK_FANOUT = """
      <div class="mt-auto pt-3 flex items-stretch gap-1 text-xs">
        <div class="flex flex-col justify-center"><span class="bg-slate-900 text-white rounded px-2 py-1 font-semibold whitespace-nowrap">親</span></div>
        <div class="flex flex-col justify-center text-slate-400">⇉</div>
        <div class="flex flex-col gap-1 flex-1">
          <span class="bg-white border border-orange-300 rounded px-2 py-0.5 font-semibold">子: SKILL</span>
          <span class="bg-white border border-orange-300 rounded px-2 py-0.5 font-semibold">子: DB投入</span>
          <span class="bg-white border border-orange-300 rounded px-2 py-0.5 font-semibold">子: 画面</span>
          <span class="bg-white border border-orange-300 rounded px-2 py-0.5 font-semibold">子: 導出・MCP</span>
        </div>
      </div>"""


def homework_slide() -> str:
    arrow = '<div class="flex items-center justify-center text-2xl text-slate-400">→</div>'
    steps = arrow.join([
        hw_step(1, "環境を整える", "配布物（今日のもの）",
                ["スキーマ文書と正規化辞書", "指示文4本", "seed 47件と検査スクリプト", "compose と .env の雛形"]),
        hw_step(2, "仕様を決める", "SPEC.md", 
                ["plan mode で高機能モデルと会話して固める", "書くのは「何を」。ゴール／機能／やらないこと／制約（版・1ファイル）", "受け入れ条件は<strong>検査として書く</strong>（48行ある、「コールセンター」でコンタクトセンターが出る）"]),
        hw_step(3, "完了条件を書く", "check.sh ＋ CLAUDE.md",
                ["「動いた」ではなく「何が通れば完了か」を先に書く", "できるだけ1コマンドにする。エージェントが自分で判定できる形", "守ってほしい約束事（今日足した行）は CLAUDE.md に置く", "ここが無いと、並列の「完了」を人が全部見直すことになる"]),
        hw_step(4, "タスクに割る", "TASKS.md",
                ["単位は「独立して検査できるか」", "各タスクに入力／出力／検査／<strong>触ってよいファイル</strong>", "画面はスキーマ文書（契約）に対して作れるので、DB投入と並列にできる"]),
        hw_step(5, "オーケストレータに渡す", "1セッション＋サブエージェント",
                ["親が TASKS.md を読み、依存の無いタスクを子に並列で振る", "子は自分の検査が通るまで。2回直して通らなければ止めて報告", "仕様は変えない。疑問は QUESTIONS.md に書いて続ける"],
                HOMEWORK_FANOUT, hot=True),
    ])
    return slide(f"""
  <h2 class="text-3xl font-bold mb-1">宿題: 仕様先行で、もう一度作ってみる</h2>
  <p class="text-slate-600 mb-3 text-base">今日と同じものを、今日の材料を使って「先に決めて、一気に」で作る。worktree は使わず、サブエージェントの並列まで</p>
  <div class="grid gap-2 flex-1 min-h-0" style="grid-template-columns: 1fr 24px 1fr 24px 1fr 24px 1fr 24px 1.25fr;">{steps}</div>
  <div class="mt-3 bg-slate-900 text-white rounded-xl px-6 py-3 text-base"><span class="text-amber-300 font-bold mr-3">最後に</span>全体の check.sh を通し、TASKS.md にチェック。人が見るのは仕様と結果の差分だけ。途中で CLAUDE.md に足すことになった行が「最初に渡せていなかった情報と指示」。並列はトークンを体数以上に使うので、予算を先に決めておく</div>
""")


def day1() -> str:
    s = HEAD.format(title="AIを活用しながら事例カタログを作る（Day 1）")
    s += title_slide("Day 1", "AIを活用しながら、AI活用事例カタログを作る", "URLから事例カードを起こし、DBに入れ、画面で見るところまで")

    s += slide("""
  <h2 class="text-3xl font-bold mb-5">今日やること</h2>
  <div class="bg-slate-900 text-white rounded-xl px-8 py-7 text-3xl font-semibold leading-relaxed mb-6">
    AIを活用しながら、<br>「AI活用事例カタログ」を30分で作る
  </div>
  <div class="border rounded-xl p-5 text-base flex-1">
    <p class="text-xs text-slate-500 mb-2">きっかけ</p>
    <p class="leading-relaxed">OKRの絡みで、AI活用の事例をあちこちから集めていた。ただ、集めたものを<strong>きれいに見られる画面がなかった</strong>。無いなら作ってみよう、というのが発端。</p>
    <p class="leading-relaxed mt-3">事例は「誰が、何に困っていたか」「AIと周辺の仕組みが何をしているか」「確認できた効果と、まだ仮説の効果」の形で揃えたい。溜めるだけでなく、似た事例・つながる事例が見えるところまで。</p>
  </div>
  <p class="mt-4 text-sm text-slate-500">STEP 0 → 1 → 2 → 3 → 4 の順に、その場でAIに作らせながら進める</p>
""")

    s += arch_slide("全体アーキテクチャ", "作るものは以下の構成。手元のPCの中だけで完結する", colored=False)
    s += arch_slide("AIに作らせる部分", "橙の部品を、当日その場でAIに作らせる。白は既製品とデータ", colored=True)

    s += step_slide("STEP 0", "実行環境",
        "手元のPCだけで完結する環境を、あらかじめ用意しておく",
        ["pg"],
        ["Docker Desktop 上で <strong>docker compose</strong> により PostgreSQL 17 を起動している",
         "AIエージェント（Cursor / Claude Code）は Development VM の中で動く",
         "Python 環境（uv）に streamlit / psycopg を入れてある",
         "DBは空。<strong>テーブルはまだ無い</strong>"],
        "環境と事例データ（47件）だけが準備済み。コードはここから")

    s += step_slide("STEP 1", "URLから事例カードを作成する",
        "記事のURLを渡すだけで、決まった形（11項目）に構造化された事例データを作りたい",
        ["article", "skill", "catalog"],
        ["AIに <strong>SKILL</strong>（URL → 事例カードJSON の手順書）を作らせる",
         "SKILL に記事URLを1本渡し、<code>catalog/</code> に JSON が1件できる",
         "まず雑に頼んで出てくるものと、正しく頼んで出てくるものを見比べる",
         "できたカードは検査スクリプトで形式を確認する"],
        "2本目以降は「このURLをカードにして」だけで同じ形が出る")

    s += tips_slide("STEP 1", "SKILLとは",
        "AIに渡す「手順書」。1回書いて置いておくと、同じ形の成果物が何度でも出る",
        [("何か", ["Markdown の手順書（<code>SKILL.md</code>）。入力・出力の形・判断基準・確認方法を書く",
                  "AIエージェントが作業のたびに読み込み、その通りに動く",
                  "チャットのプロンプトとの違いは「毎回貼る」か「置いておく」か"]),
         ("いつ使う", ["同じ作業を何度も頼む（URL → カードを何十回もやる）",
                      "出力の形を揃えたい（JSON の項目名と順番を固定する）",
                      "判断基準を固定したい（困りごとの型は8種から選ぶ）"]),
         ("注意", ["手順が曖昧なら、出力も毎回ぶれる",
                  "SKILL を書くのもAIに任せられる。ただし何を書くかは人が決める",
                  "Cursor / Claude Code で置き場所が違う（同じ内容を両方に置ける）"])],
        "今日は SKILL 自体をAIに書かせる。人が渡すのは「何を、どういう形で、どう確かめるか」")

    s += tips_slide("STEP 1", "雑な指示と正しい指示の差はどこに出るか",
        "指示に書いていないことは、AIがその場で決める。決めてほしくないことを書く",
        [("雑な指示で抜けるもの", ["出力の形: 項目が毎回変わる、日本語と英語が混ざる",
                                  "判断基準: 「効果」に確認済みと見込みが混ざる",
                                  "置き場所と名前: どこに何というファイルで出すか",
                                  "確認方法: できたものが正しいか誰も見ない"]),
         ("正しい指示に入っているもの", ["入力: URL 1本。ログイン不要で読めること",
                                        "出力: 12項目のスキーマ文書（<code>docs/case-schema.md</code>）",
                                        "基準: 困りごとの型は8種、基盤名は正規化辞書に合わせる",
                                        "確認: 検査スクリプトを通してから終わる"])],
        "「正しい情報」＝スキーマと辞書、「正しい指示」＝入力・出力・基準・確認の4点")

    s += tips_slide("STEP 1", "なぜ決まった形（スキーマ）にするのか",
        "自由文のままでは溜まるだけ。決まった項目にすると、入れる・探す・比べる・つなぐができる",
        [("自由文のまま", ["読めば分かるが、機械には1件ずつ違う形",
                          "DB に入れるとき列が決まらない",
                          "「同じ困りごとの事例」を機械的に集められない"]),
         ("スキーマあり", ["<code>problem_types</code> が同じ事例を1行の SQL で引ける",
                          "確認済みの効果と仮説の効果を別の列に分けられる",
                          "STEP 4 の関連（グラフの辺）は、この項目をそのまま使う"]),
         ("設計のコツ", ["項目は「後で何を聞きたいか」から逆算する",
                        "選択肢がある項目は固定リストにする（型8種、部署、基盤名）",
                        "文章のままでよい項目も残す（誰が何に困っていたか）"])])

    s += step_slide("STEP 2", "DBにデータを投入する",
        "catalog/ に溜まった事例カード48件を、SQLを書かずにPostgreSQLへ入れたい",
        ["catalog", "pgmcp", "pg"],
        ["AIがDBを触れるように <strong>PostgreSQL MCP</strong>（既製品）を追加する",
         "AIに「catalog/ を全部DBに入れて」と会話で頼む",
         "AIが MCP を通してテーブルを作り、まとめて INSERT し、件数を確認する",
         "SQL はAIが組み立てる。人はスキーマ文書とテーブル名を伝えるだけ"],
        "48件で約50KBのSQLになる。待つ間にAIのログを見せる")

    s += tips_slide("STEP 2", "MCPとは",
        "AIが外の仕組み（DB、Jira、ブラウザ…）を操作するための共通の接続規格",
        [("何か", ["Model Context Protocol。AI側とツール側の「話し方」を決めた規格",
                  "MCPサーバ = ツールの束。「何ができるか」と「呼び方」をAIに公開する",
                  "AI（Cursor / Claude Code）が、会話の中で必要なツールを選んで呼ぶ"]),
         ("いつ使う", ["AIに手元の外を触らせたいとき。今日は PostgreSQL",
                      "既製品が多い: Postgres、GitHub、Playwright、Confluence など",
                      "既製品が無い、または範囲を絞りたいときは自作する（Day 2）"]),
         ("今日の使い方", ["設定ファイルに1行足すだけで、AIが SQL を実行できるようになる",
                          "人は「catalog/ を全部入れて」と言うだけ。SQL はAIが組む",
                          "スクリプトを書かせずに MCP だけで入れる。差を見せるため"])],
        "USB-C のようなもの。規格が同じなら、AI側もツール側も相手を選ばない")

    s += tips_slide("STEP 2", "AIの権限は、渡した鍵の権限",
        "MCP経由でAIができることの上限は、MCPサーバに渡した接続情報（ユーザー・トークン）で決まる",
        [("仕組み", ["MCPサーバは、渡された DB ユーザーで SQL を実行するだけ",
                    "そのユーザーに CREATE があればテーブルを作れる。無ければ作れない",
                    "AI側の設定（許可モード）とは別の層。DB側で効く"]),
         ("今日の構成", ["<code>aicase_rw</code>: 作成・挿入ができる。STEP 2 で使う",
                        "<code>aicase_ro</code>: SELECT だけ。画面や配布用の MCP に使う",
                        "接続文字列は <code>.env</code> に置き、設定ファイルには書かない"]),
         ("注意", ["「AIに DB を触らせる」＝「そのユーザーの権限を渡す」と思って設計する",
                  "本番相当の DB に unrestricted で繋がない。読み取り専用ユーザーを作る",
                  "MCPサーバの出自も確認する（非推奨の Postgres MCP には未修正の SQL インジェクションがある）"])])

    s += step_slide("STEP 3", "Web画面で事例を見る",
        "DBに入った事例を、人がブラウザで探せる画面が欲しい",
        ["browser", "frontend", "pg"],
        ["AIに <strong>Streamlit</strong> の画面を1ファイルで書かせ、その場で起動する",
         "一覧: キーワード検索と、部署・基盤での絞り込み。各行に「詳細」",
         "詳細: 11項目を全部表示",
         "STEP 1 で作った1件が一覧の先頭に出る"],
        "検索はキーワードの部分一致だけ。「コールセンター」で「コンタクトセンター」の事例は出ない")

    s += tips_slide("STEP 3", "コーディングエージェントとは",
        "チャットで答えるだけでなく、ファイルを書き、コマンドを実行し、結果を見て直すAI",
        [("チャットAIとの違い", ["チャット: 人がコードをコピーして貼って動かす",
                                "エージェント: 自分でファイルを作り、起動し、エラーを読んで直す",
                                "「作って → 動かして → 確認」のループを回すのがエージェント"]),
         ("いつ使う", ["動くものまで一気に欲しいとき（今日の Web 画面）",
                      "エラーの読み直しを任せたいとき",
                      "既存コードを読んで合わせてほしいとき"]),
         ("注意", ["動く場所の権限で動く。環境が触れるものは全部触れる",
                  "指示が曖昧なところは、AIがもっともらしく決めて進む",
                  "「動いた」と「正しい」は別。確認の仕方まで指示に入れる"])],
        "Cursor / Claude Code はどちらもこれ。今日は Development VM の中で動かしている")

    s += tips_slide("STEP 3", "指示は「仕様書」の粒度で書く",
        "機能を並べるだけでは足りない。データの形・やらないこと・起動方法まで書くと一発で動く",
        [("今日の指示文に入っているもの", ["データ: テーブル名、列、配列の列（型・基盤）",
                                          "機能: 一覧（検索・絞り込み）、詳細、行ごとの詳細ボタン",
                                          "やらないこと: 認証、編集、削除、複数ファイル",
                                          "起動: コマンドとアドレス"]),
         ("リハーサルで足した行", ["SQL は placeholder で組む（文字列連結しない）",
                                  "JOIN の列名は別名を付ける（曖昧エラーの再発防止）",
                                  "表示用の分岐は if 文で書く（式のままだと内部オブジェクトが表示される）"])],
        "足した行はどれも「一度失敗して分かったこと」。失敗を指示文に還元すると、次から一発になる")

    s += tips_slide("STEP 3", "なぜ Streamlit か",
        "Python だけで Web 画面が作れる。フロントとバックエンドを分けず、1ファイルで動く",
        [("何か", ["Python の Web 画面フレームワーク。<code>st.dataframe</code> や <code>st.button</code> を並べると画面になる",
                  "上から順に実行し、操作があると再実行する単純なモデル",
                  "DB へは同じファイルから直接 SQL を投げる（MCP は通さない）"]),
         ("ライブに向く理由", ["1ファイルで完結するので、AIの出力が読める量に収まる",
                              "起動が1コマンド。作らせてすぐ見せられる",
                              "見た目の作り込みが要らない。中身の話に集中できる"]),
         ("向かないもの", ["複数人の同時編集、認証、細かい UI",
                          "本番の社内ツールにするなら、React などの前段と API に分ける",
                          "今日の画面は「見られる」ことが目的。作り込まない"])])

    s += step_slide("STEP 4", "検索の精度を上げ、関連を見せる",
        "言い換えを拾える検索と、事例同士のつながりが見える画面にしたい",
        ["frontend", "pg"],
        ["PostgreSQL に <strong>pgvector</strong>（意味）と <strong>AGE</strong>（関連）を足す",
         "意味検索: 困りごとの文章を埋め込み、近い順に並べる。「コールセンター」で「コンタクトセンター」も出る",
         "関連事例: 同じ困りごとの型 → 同じ部署 → 共有する基盤 の順に辿り、詳細の下に図と根拠付きで出す",
         "AIに画面と導出処理を書き換えさせ、同じ検索をやり直して差を見る"],
        "意味で入って、関連で広げる")

    s += tips_slide("STEP 4", "ベクトル検索とは",
        "文章を数値の列（埋め込み）に変え、数値の距離で「意味の近さ」を測る検索",
        [("仕組み", ["埋め込みモデルが文章を1024個の数値に変える。似た意味は近い数値になる",
                    "検索語も同じモデルで数値にし、距離が近い順に並べる",
                    "PostgreSQL では <strong>pgvector</strong> 拡張が距離計算と索引を担う"]),
         ("いつ使う", ["言い換え・表記ゆれを拾いたい（コールセンター／コンタクトセンター）",
                      "「こんな感じの悩み」と文章で探したい",
                      "キーワードが思いつかない入口の検索"]),
         ("注意", ["なぜ近いかは説明できない。根拠を出す用途には向かない",
                  "埋め込みモデルが要る。今日はローカルの Ollama（bge-m3）を使い、外に送らない",
                  "件数が少ないうちは索引不要。まず動かしてから最適化する"])])

    s += tips_slide("STEP 4", "グラフ検索とは",
        "事例・困りごとの型・部署・基盤を「点」、その関係を「線」にして、線を辿って探す検索",
        [("仕組み", ["点（ノード）: 事例、困りごとの型、部署、基盤",
                    "線（辺）: 事例 → 型 HAS_PROBLEM、事例 → 部署 FOR、事例 → 基盤 USES",
                    "「この事例 → 同じ型 → 別の事例」と2段辿ると関連事例になる。<strong>Apache AGE</strong> なら Cypher で書ける"]),
         ("いつ使う", ["「なぜ関連か」を言葉で出したい（同じ困りごと: 情報検索に時間）",
                      "多段の関係（同じ型で、同じ基盤で、別部署）を1つの問いにしたい",
                      "件数が増えても「1件足すと地図が濃くなる」見せ方をしたい"]),
         ("注意", ["線の材料は STEP 1 でAIが判断して埋めた項目。ここの精度がそのまま関連の精度",
                  "型・部署・基盤の値がぶれると線がつながらない。正規化辞書はこのため",
                  "SQL の配列演算でも同じことはできる。グラフは「問いを書きやすい」道具"])])

    s += tips_slide("STEP 4", "なぜ PostgreSQL に足すのか",
        "専用のベクトルDB・グラフDBを立てず、拡張機能で同じ PostgreSQL に載せる",
        [("拡張機能とは", ["PostgreSQL に後から機能を足す仕組み。<code>CREATE EXTENSION</code> 1行で有効になる",
                          "pgvector: ベクトル型と距離演算。AGE: グラフとCypher",
                          "データは同じテーブルの隣にある。JOIN も同じ SQL で書ける"]),
         ("利点", ["運用対象が1つ。バックアップ・権限・接続先が増えない",
                  "意味検索の結果を、そのまま部署や型で絞り込める",
                  "48件規模なら性能の差は出ない"]),
         ("代わりに増えるもの", ["イメージのビルド（AGE と pgvector が両方入った公式イメージは無い）",
                                "埋め込みの導出処理と、グラフの導出処理（どちらもバッチ）",
                                "件数が数十万を超えたら専用製品を検討する。今日はそこではない"])])

    s += slide("""
  """ + tips_head("STEP 4", "意味で入って、関連で広げる") + """
  <p class="text-slate-500 mb-5">「似ている」には2種類ある。担う仕組みも別</p>
  <div class="grid grid-cols-2 gap-6 flex-1 text-sm">
    <div class="border-2 border-violet-200 rounded-xl p-5">
      <p class="text-xl font-bold text-violet-800 mb-2">意味が近い ＝ ベクトル（pgvector）</p>
      <p class="mb-2">「経理が締め日前に残業している。同じ悩みの事例は？」</p>
      <ul class="list-disc pl-5 space-y-1 text-slate-700">
        <li>困りごとの文章を埋め込み、距離で並べる</li>
        <li>言い換え（コールセンター／コンタクトセンター）を吸収</li>
        <li>なぜ近いかは言えない。入口を探すのに向く</li>
      </ul>
    </div>
    <div class="border-2 border-orange-300 rounded-xl p-5">
      <p class="text-xl font-bold text-orange-800 mb-2">関連が近い ＝ グラフ（AGE）</p>
      <p class="mb-2">「同じ困りごとで、うちが持っている基盤で動く事例は？」</p>
      <ul class="list-disc pl-5 space-y-1 text-slate-700">
        <li>事例 → 困りごとの型・部署・基盤 → 事例 と辿る</li>
        <li>根拠が言葉で出る（「同じ困りごと: 情報検索に時間」）</li>
        <li>辺の材料（型・部署・基盤）は STEP 1 でAIが判断して埋めている</li>
      </ul>
    </div>
  </div>
  <p class="mt-4 text-sm text-slate-500">溜めるだけの台帳は件数が増えるほど探しにくい。関連が見えると逆で、1件足すたびに地図が濃くなる</p>
""")


    s += slide(SUMMARY)
    s += slide(TWIST)
    s += homework_slide()
    s += arch_slide("予告: Day 2", "手元のカタログを Jira に載せて、AIとの会話から事例を引けるようにする",
                    colored=True, jira=True,
                    foot="STEP 5: PostgreSQL → Jira の同期（バッチ）。STEP 6: Jira の事例だけを読む自作MCP。人の入口は Web画面、AIの入口は MCP")
    s += FOOT
    return s


def day1_appendix() -> str:
    s = HEAD.format(title="Day 1 付録（講師用カンペ）")
    s += appendix_cover("Day 1", [
        "P.1　STEP 1 の指示文（雑な指示 ／ 正しい指示文）",
        "P.2　STEP 2 の発話 ／ P.3　STEP 3 の指示文（前半）",
        "P.3　STEP 3 の指示文（後半）",
        "P.4　STEP 4 の指示文（案）",
    ])
    s += cheat_slide("付録 P.1　STEP 1 の指示文", [
        ("① 雑な指示（先に貼る）", prompt_before_rule("01-skill-sloppy.md")),
        ("② 正しい指示文（当日貼る版）", prompt_text("01-skill.md")),
    ])
    s += cheat_slide("付録 P.2　STEP 2 の発話 ／ P.3 STEP 3 の指示文（前半）", [
        ("STEP 2（会話で言う。MCP の追加は .mcp.json に1行）", prompt_before_rule("02-insert.md")),
        ("STEP 3（当日貼る版・前半: データ）", prompt_text("03-webapp.md").split("## 機能")[0].strip()),
    ])
    s += cheat_slide("付録 P.3　STEP 3 の指示文（後半）", [
        ("機能 1〜4", "## 機能" + prompt_text("03-webapp.md").split("## 機能")[1].split("## やらないこと")[0]),
        ("やらないこと・起動", "## やらないこと" + prompt_text("03-webapp.md").split("## やらないこと")[1]),
    ])
    s += cheat_slide("付録 P.4　STEP 4 の指示文（案。pgvector / AGE の環境準備後に確定）", [
        ("意味検索（pgvector）", """検索を「言い換えを拾える」ようにしたい。
- 環境: PostgreSQL に pgvector が入っている（CREATE EXTENSION vector 済み）。埋め込みは Ollama の bge-m3（1024次元）をローカルで使う
- cases に embedding vector(1024) 列を足し、who_and_problem ＋ title を埋め込んで全件更新する導出スクリプト（scripts/embed.py）を書く。冪等に
- app/main.py の一覧のキーワード検索を「検索語を埋め込んで <=> で近い順に上位20件」に差し替える。ILIKE は残さない
- 同じ「コールセンター」で検索し直し、コンタクトセンターの事例が上に来ることを確認"""),
        ("関連事例（AGE）", """関連事例を、SQL の配列演算からグラフの探索に差し替えたい。
- 環境: Apache AGE が入っている（LOAD 'age' と search_path は DB 側で設定済み）
- グラフ cases_graph を作り、ノード Case / ProblemType / Department / Platform、辺 HAS_PROBLEM / FOR / USES を cases から導出するスクリプト（scripts/build_graph.py）を書く。冪等に
- app/main.py の fetch_related を Cypher（事例 → 型・部署・基盤 → 事例、共有する型の数 → 同じ部署 → 共有基盤の数 の順）に差し替える。画面の見た目は変えない
- 大成の事例の関連事例が、差し替え前と同じ顔ぶれで出ることを確認"""),
    ])
    s += FOOT
    return s


# ---------- Day 2 ----------

def day2() -> str:
    s = HEAD.format(title="事例カタログをグローバルへ（Day 2）")
    s += title_slide("Day 2", "事例カタログを、AIから引けるようにする", "Jira に同期し、自作MCP で AI の入口を作る")

    s += slide("""
  <h2 class="text-3xl font-bold mb-5">今日やること</h2>
  <div class="bg-slate-900 text-white rounded-xl px-8 py-7 text-3xl font-semibold leading-relaxed mb-6">
    Day 1 で作ったカタログを Jira に載せて、<br>AIとの会話から事例を引けるようにする
  </div>
  <div class="border rounded-xl p-5 text-base flex-1">
    <p class="text-xs text-slate-500 mb-2">なぜ Jira か</p>
    <p class="leading-relaxed">手元の PostgreSQL は自分しか見られない。事例を<strong>他の人も見られて、起票もできる場所</strong>に置きたい。Jira は「ローカルのものをグローバルからアクセスできるようにしただけ」の器で、権限と監査が乗り、手元が消えても残る。</p>
    <p class="leading-relaxed mt-3">最後に Cursor / Claude Code から「経理で請求書処理に困っている。近い事例ある？」と聞くと、Jira の事例が返る。</p>
  </div>
""")

    s += arch_slide("全体アーキテクチャ", "Day 1 の構成に、Jira と、そこへつなぐ2つの部品を足す", colored=False, jira=True)
    s += arch_slide("AIに作らせる部分", "今日作るのは sync application と 自作MCP の2つ", colored=True, jira=True)

    s += step_slide("STEP 5", "Jiraへ同期する",
        "手元のDBにある事例を、他の人も見られて起票もできる場所（Jira）に載せたい",
        ["pg", "sync", "jira"],
        ["AIに <strong>同期スクリプト</strong>（PostgreSQL → Jira、挿入のみ、冪等）を書かせる",
         "実行はバックグラウンドで。48件が Jira の事例プロジェクトに起票される",
         "同期の実行にLLMは関わらない。判断のいらない処理はバッチに置く",
         "Jira 側のフィールドIDの対応表は事前に用意してあり、AIに渡す"],
        "片方向。双方向にすると正本が2つになる", jira=True)

    s += tips_slide("STEP 5", "判断のいらない処理はバッチに置く",
        "「DB の行を Jira に写す」に判断は無い。LLM を通さず、普通のコードで決定的にやる",
        [("バッチとは", ["人の操作なしに、まとめて一方向に処理するプログラム",
                        "入力（cases テーブル）→ 変換（対応表）→ 出力（Jira の起票）",
                        "同じ入力なら同じ結果。再実行しても壊れない（冪等）"]),
         ("なぜ LLM を使わないか", ["写すだけの処理に「解釈」が入ると、写し間違いの原因になる",
                                  "48件で毎回 LLM を呼ぶと遅く、費用もかかる",
                                  "LLM の出番は「読んで判断する」STEP 6 に取っておく"]),
         ("設計の型", ["片方向: PostgreSQL → Jira。逆はやらない。正本を1つにする",
                      "挿入のみ: 同じ id があれば何もしない。更新・削除はしない",
                      "1件ごとに結果を1行出し、最後に件数。人が後から追える"])],
        "AIに書かせるのは「同期スクリプト」。実行時に AI はいない")

    s += tips_slide("STEP 5", "API トークンは「期限と範囲のある鍵」",
        "Jira を外から操作する鍵。読める範囲と期限を絞って発行し、コードには書かない",
        [("Atlassian の場合", ["スコープ付き API トークン: <code>read:jira-work</code> のように範囲を指定する",
                              "期限は最長1年。切れたら作り直す",
                              "スコープ付きは <code>api.atlassian.com/ex/jira/{cloudId}/</code> 経由でしか使えない"]),
         ("置き場所", ["<code>.env</code> に置き、<code>.gitignore</code> で除外する",
                      "コード側は環境変数から読む。ファイルに直書きしない",
                      "AIに指示文を渡すときも、トークンの値は渡さない（変数名だけ）"]),
         ("注意", ["個人のトークンで動かすと、その人の権限で動く。共有用は別に作る",
                  "書き込みトークンは同期にだけ渡す。MCP（STEP 6）には読み取り用を渡す",
                  "漏れたらすぐ失効。失効できる鍵を使うのはそのため"])])

    s += step_slide("STEP 6", "MCPで事例をAIから引く",
        "Cursor / Claude Code との会話の中で、Jira の事例だけを引いて答えてほしい",
        ["mymcp", "jira"],
        ["AIに <strong>自作MCPサーバ</strong>（1ファイル、読み取り3ツール）を書かせる",
         "読める範囲は事例プロジェクトだけ。書き込みツールは無い",
         "Cursor に登録し、「経理で請求書処理に困っている。近い事例ある？」と聞く",
         "MCPが候補を渡し、どれが近いかはLLMが読んで判断する",
         "コードを1画面だけ見せる。「読める範囲が1行、ツールが3つ、対応表が1つ」"],
        "", jira=True)

    s += tips_slide("STEP 6", "自作MCPは「関数 ＋ 説明文」でできる",
        "MCP サーバの中身は、Python の関数に説明文を付けて並べたもの。AI はその説明文を読んで使い方を知る",
        [("作り方", ["SDK（MCP Python SDK 2.x）で <code>MCPServer</code> を作り、関数に <code>@mcp.tool()</code> を付ける",
                    "関数名・引数名・docstring が、そのままAIに見える「ツールの説明書」になる",
                    "起動は標準入出力（stdio）。Cursor / Claude Code が子プロセスとして立ち上げる"]),
         ("説明文が大事な理由", ["AI はコードを読まず、説明文で「いつ呼ぶか」を決める",
                                "「困りごとの文章から候補を返す」と書けば、悩みの相談で呼ばれる",
                                "引数は事例の言葉にする（JQL ではなく「困りごと」）"]),
         ("注意", ["SDK の版で書き方が違う（1.x は FastMCP、2.x は MCPServer）。指示文に版を書く",
                  "ツールは少なく。3本あれば足りる。多いとAIが選び損ねる",
                  "登録は設定ファイルに1行。設定後は再起動が要る"])],
        "「正しい情報」の例: SDK の版。古い情報で書かせると動かないものが出てくる")

    s += tips_slide("STEP 6", "ツールが取ってきて、LLM が選ぶ",
        "自作MCP は候補を渡すだけ。「どれが近いか」は LLM が読んで判断する分業",
        [("役割分担", ["MCP（ツール）: Jira から候補を取ってくる。決定的で速い",
                      "LLM: 候補を読み、相談内容に近いものを選び、理由を添えて答える",
                      "人: 相談を投げ、答えを読んで、事例に当たる"]),
         ("なぜこの分担か", ["Jira は意味検索も関連の辺も持っていない（Day 1 の PostgreSQL とは違う）",
                            "器に無い能力は、持っている側（LLM）に寄せる",
                            "候補が数十件なら、LLM が読んで選ぶ方が実装が軽い"]),
         ("限界と次", ["件数が増えると候補が文脈に入りきらない",
                      "その時は候補の絞り込みを Jira 側（JQL）か DB 側に戻す",
                      "「どこで似ているを判断するか」は、器の能力で決めればよい"])])

    s += slide("""
  """ + tips_head("STEP 6", "汎用MCPと自作MCPの違い") + """
  <p class="text-slate-500 mb-5">コードで見える差。汎用（Confluence / Postgres MCP）は「本人が見られる全部」に届く</p>
  <div class="grid grid-cols-5 gap-5 flex-1 text-sm">
    <div class="col-span-3 bg-slate-900 text-slate-100 rounded-xl p-4 font-mono text-xs leading-relaxed">
      <span class="text-amber-300">PROJECT_KEY = "AICASE"</span>   # 読める範囲はここだけ<br>
      <span class="text-amber-300">FIELDS = {</span> "customfield_10042": "誰が、何に困っていたか", ... <span class="text-amber-300">}</span><br><br>
      mcp = MCPServer("ai-case-catalog")   # MCP Python SDK 2.x<br><br>
      @mcp.tool()<br>
      def <span class="text-emerald-300">find_cases</span>(problem: str): ...        # 困りごとの文章から候補<br>
      @mcp.tool()<br>
      def <span class="text-emerald-300">list_hypothesis_cases</span>(): ...      # 効果がまだ仮説の事例<br>
      @mcp.tool()<br>
      def <span class="text-emerald-300">get_case</span>(key: str): ...            # 1件をカードの形で<br>
    </div>
    <div class="col-span-2 flex flex-col gap-3">
      <div class="border rounded-lg p-3"><p class="font-bold">どこまで届くか</p><p class="text-slate-600">PROJECT_KEY 1行。汎用MCPにはこの行が存在しない</p></div>
      <div class="border rounded-lg p-3"><p class="font-bold">何ができるか</p><p class="text-slate-600">ツール3本。引数は事例の言葉</p></div>
      <div class="border rounded-lg p-3"><p class="font-bold">何ができないか</p><p class="text-slate-600">書き込みなし。汎用MCPは「できないこと」を示せない</p></div>
      <div class="border rounded-lg p-3"><p class="font-bold">人が意味を付けた場所</p><p class="text-slate-600">FIELDS の対応表。AIに渡す前にやる仕事</p></div>
    </div>
  </div>
""")

    s += slide("""
  """ + tips_head("STEP 6", "ローカルとグローバル") + """
  <p class="text-slate-500 mb-6">同じカードに、同じ問いを、器の能力に応じて別の層で解く</p>
  <table class="w-full text-base border-collapse">
    <thead><tr class="bg-slate-100"><th class="p-3 text-left w-1/4"></th><th class="p-3 text-left">ローカル（Day 1）</th><th class="p-3 text-left">グローバル（Day 2）</th></tr></thead>
    <tbody>
      <tr class="border-b"><td class="p-3 font-bold">器</td><td class="p-3">PostgreSQL（＋pgvector、AGE）</td><td class="p-3">Jira</td></tr>
      <tr class="border-b"><td class="p-3 font-bold">関連・類似を担う場所</td><td class="p-3">DB（決定的・速い・再現する）</td><td class="p-3">LLM（自作MCPが候補を渡し、LLMが読んで判断）</td></tr>
      <tr class="border-b"><td class="p-3 font-bold">理由</td><td class="p-3">器が検索機構を持っている</td><td class="p-3">器が持っていないので、持っている側に寄せた</td></tr>
      <tr><td class="p-3 font-bold">限界</td><td class="p-3">埋め込みモデルと辺の導出が要る</td><td class="p-3">件数が増えると候補が入りきらない。育ったらDB側へ戻す</td></tr>
    </tbody>
  </table>
  <p class="mt-6 text-sm text-slate-500">Jira が正本になったら、Day 1 の Web画面は Confluence の Jira Issues マクロに置き換える</p>
""")


    s += slide(SUMMARY.replace("今日伝えたかったこと", "2日間で伝えたかったこと"))
    s += slide(TWIST)
    s += slide(TWIST2)
    s += homework_slide()
    s += FOOT
    return s


def day2_appendix() -> str:
    s = HEAD.format(title="Day 2 付録（講師用カンペ）")
    s += appendix_cover("Day 2", [
        "P.1　STEP 5 の指示文（案。Jira 準備後に確定）",
        "P.2　STEP 6 の指示文（案）",
    ])
    s += cheat_slide("付録 P.1　STEP 5 の指示文（案）／ P.2　STEP 6 の指示文（案）", [
        ("STEP 5（Jira 準備後に確定。渡す材料）", """sync/sync_to_jira.py を作ってください。PostgreSQL の cases テーブルを Jira の事例プロジェクトに起票する片方向のバッチです。

## 接続
- PostgreSQL: .env の DATABASE_URL
- Jira: .env の JIRA_EMAIL / JIRA_TOKEN / JIRA_CLOUD_ID / JIRA_PROJECT_KEY
- エンドポイントは https://api.atlassian.com/ex/jira/{JIRA_CLOUD_ID}/rest/api/3/ （スコープ付きトークンはこれ以外で使えない）

## 対応表（列 → Jira フィールド）
- title → summary
- department → customfield_XXXXX
- （...10項目分。docs/jira-fields.md を貼る）

## 挙動
- 挿入のみ。既に同じ id の Issue があれば何もしない（冪等）
- 双方向にしない。更新・削除はしない
- 1件ごとに結果を1行出力し、最後に件数を表示"""),
        ("STEP 6（渡す材料）", """mcp/server.py を作ってください。Jira の事例プロジェクトだけを読む MCP サーバです。

## 前提
- MCP Python SDK 2.x。from mcp.server.mcpserver import MCPServer（FastMCP ではない）。起動は mcp.run(transport="stdio")
- PROJECT_KEY = "AICASE"。全ての JQL は project = AICASE で括る
- 対応表は sync と同じモジュール（jira_fields.py）から読む

## ツール（3本だけ）
- find_cases(problem: str): 困りごとの文章から候補を返す（JQL の text ~ で絞る）
- list_hypothesis_cases(): 効果がまだ仮説の事例
- get_case(key: str): 1件をカードの形で

## やらないこと
- 書き込みツールを作らない
- JQL を引数で受けない
- PROJECT_KEY 以外のプロジェクトに触れない

作ったら .cursor/mcp.json（と .mcp.json）に登録して、「経理で請求書処理に困っている。近い事例ある？」で試してください。"""),
    ])
    s += FOOT
    return s


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "day1-workshop-ai-catalog.html").write_text(finalize(day1()), encoding="utf-8")
    (OUT / "day2-workshop-ai-catalog.html").write_text(finalize(day2()), encoding="utf-8")
    (OUT / "day1-workshop-ai-catalog-appendix.html").write_text(finalize(day1_appendix()), encoding="utf-8")
    (OUT / "day2-workshop-ai-catalog-appendix.html").write_text(finalize(day2_appendix()), encoding="utf-8")
    print("written")
