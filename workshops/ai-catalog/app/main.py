"""AI活用事例カタログ 閲覧画面（読み取り専用）。

- 一覧: 絞り込み（サイドバー）＋見出し付きの行リスト（各行に「詳細」ボタン）。confirmed_at 降順
- 詳細: 別画面（URL の ?case=<id>）。全項目＋関連事例（同じ困りごと → 同じ部署 → 共有する基盤 の順で辿る）
"""
import os

import psycopg
import streamlit as st
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]
SUMMARY_CHARS = 80
RELATED_LIMIT = 6

LABELS = {
    "department": "部署・役割",
    "who_and_problem": "誰が、何に困っていたか",
    "problem_types": "困りごとの型",
    "ai_and_system": "AIと周辺の仕組みが、何をしているか",
    "platforms": "使っている基盤",
    "requirements": "必要なデータ・基盤・運用体制",
    "confirmed_effects": "確認できた効果",
    "hypothesized_effects": "まだ仮説の効果",
    "source_url": "出典URL",
    "confirmed_at": "確認日",
}
SELECT_COLUMNS = """id, title, department, who_and_problem, problem_types, ai_and_system, platforms, requirements,
                    confirmed_effects, hypothesized_effects, source_url, confirmed_at"""


# ---------- データ取得 ----------

@st.cache_data(ttl=30)
def fetch_facets() -> tuple[list[tuple[str, int]], list[str], list[tuple[str, int]]]:
    with psycopg.connect(DATABASE_URL) as conn:
        ptypes = conn.execute(
            "SELECT t, count(*) FROM cases, unnest(problem_types) t GROUP BY t ORDER BY count(*) DESC, t").fetchall()
        depts = [r[0] for r in conn.execute(
            "SELECT department FROM cases GROUP BY department ORDER BY count(*) DESC, department")]
        plats = conn.execute(
            "SELECT p, count(*) FROM cases, unnest(platforms) p GROUP BY p ORDER BY count(*) DESC, p").fetchall()
    return ptypes, depts, plats


@st.cache_data(ttl=30)
def fetch_cases(keyword: str, problem_type: str, department: str, platforms: list[str]) -> list[dict]:
    sql = f"""
        SELECT {SELECT_COLUMNS}
        FROM cases
        WHERE (%(kw)s = '' OR title ILIKE %(like)s
               OR who_and_problem ILIKE %(like)s OR ai_and_system ILIKE %(like)s)
          AND (%(ptype)s = '' OR %(ptype)s = ANY(problem_types))
          AND (%(dept)s = '' OR department = %(dept)s)
          AND (%(plats)s::text[] = '{{}}' OR platforms @> %(plats)s::text[])
        ORDER BY confirmed_at DESC, id
    """
    params = {"kw": keyword, "like": f"%{keyword}%", "ptype": problem_type, "dept": department, "plats": platforms}
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


@st.cache_data(ttl=30)
def fetch_case(case_id: str) -> dict | None:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(f"SELECT {SELECT_COLUMNS} FROM cases WHERE id = %s", (case_id,)).fetchone()


@st.cache_data(ttl=30)
def fetch_related(case_id: str) -> list[dict]:
    """同じ困りごと → 同じ部署 → 基盤を共有 の順で関連づける。事例→困りごと・部署・基盤→事例 の2ホップを SQL で辿る。"""
    cols = ", ".join("o." + c.strip() for c in SELECT_COLUMNS.split(","))
    sql = f"""
        SELECT {cols},
               ARRAY(SELECT unnest(o.problem_types) INTERSECT SELECT unnest(c.problem_types)) AS shared_problem_types,
               ARRAY(SELECT unnest(o.platforms) INTERSECT SELECT unnest(c.platforms)) AS shared_platforms,
               (o.department = c.department) AS same_department
        FROM cases o, cases c
        WHERE c.id = %(id)s AND o.id <> c.id
          AND (o.problem_types && c.problem_types OR o.department = c.department OR o.platforms && c.platforms)
        ORDER BY cardinality(ARRAY(SELECT unnest(o.problem_types) INTERSECT SELECT unnest(c.problem_types))) DESC,
                 (o.problem_types[1] = c.problem_types[1]) DESC,
                 same_department DESC,
                 cardinality(ARRAY(SELECT unnest(o.platforms) INTERSECT SELECT unnest(c.platforms))) DESC,
                 o.confirmed_at DESC
        LIMIT %(limit)s
    """
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(sql, {"id": case_id, "limit": RELATED_LIMIT}).fetchall()


# ---------- 表示部品 ----------

def summary(text: str, limit: int = SUMMARY_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def badge_line(case: dict, limit: int | None = None) -> str:
    plats = case["platforms"]
    shown = plats if limit is None else plats[:limit]
    line = " ".join(f":gray-badge[{p}]" for p in shown)
    if limit is not None and len(plats) > limit:
        line += f" :gray-badge[他{len(plats) - limit}件]"
    return line


def problem_badges(types: list[str]) -> str:
    return " ".join(f":orange-badge[{t}]" for t in types)


def go_detail(case_id: str) -> None:
    st.query_params["case"] = case_id
    st.rerun()


def go_list() -> None:
    st.query_params.clear()
    st.rerun()


LIST_COLUMNS = [
    ("title", "タイトル", 2.8),
    ("department", "部署・役割", 2.0),
    ("platforms", "使っている基盤", 2.3),
    ("who_and_problem", "誰が、何に困っていたか", 2.9),
    ("confirmed_effects", "確認できた効果", 2.5),
    ("confirmed_at", "確認日", 1.3),
    ("_detail", "", 1.4),
]
PLATFORMS_ON_ROW = 3


def render_list_header() -> None:
    cols = st.columns([w for _, _, w in LIST_COLUMNS], vertical_alignment="bottom")
    for col, (_, label, _) in zip(cols, LIST_COLUMNS):
        if label:
            col.markdown(f"**{label}**")
    st.divider()


def render_row(case: dict) -> None:
    cols = st.columns([w for _, _, w in LIST_COLUMNS], vertical_alignment="center")
    for col, (key, _, _) in zip(cols, LIST_COLUMNS):
        with col:
            if key == "title":
                st.markdown(f"**{case['title']}**")
            elif key == "department":
                st.markdown(f":blue-badge[{case['department']}]")
            elif key == "platforms":
                st.markdown(badge_line(case, PLATFORMS_ON_ROW))
            elif key == "who_and_problem":
                st.markdown(problem_badges(case["problem_types"]))
                st.caption(summary(case["who_and_problem"], 55))
            elif key == "confirmed_effects":
                if case["confirmed_effects"]:
                    st.caption(summary(case["confirmed_effects"], 50))
                else:
                    st.caption("（まだ仮説段階）")
            elif key == "confirmed_at":
                st.caption(str(case["confirmed_at"]))
            elif key == "_detail":
                if st.button("詳細", key=f"detail-{case['id']}"):
                    go_detail(case["id"])


def related_reason(rel: dict) -> str:
    parts = []
    if rel["shared_problem_types"]:
        parts.append("同じ困りごと " + problem_badges(rel["shared_problem_types"]))
    if rel["same_department"]:
        parts.append(f"同じ部署 :blue-badge[{rel['department']}]")
    if rel["shared_platforms"]:
        parts.append("共有する基盤 " + " ".join(f":gray-badge[{p}]" for p in rel["shared_platforms"]))
    return "　".join(parts)


def related_graph_dot(case: dict, related: list[dict]) -> str:
    """左: 中心の事例、中: 困りごとの型・部署・基盤、右: 関連事例 の3層。事例 → 困りごと・部署・基盤 → 事例 と辿る絵。"""
    def node_id(prefix: str, name: str) -> str:
        return f'"{prefix}:{name}"'

    def wrap(text: str, width: int = 14) -> str:
        return "\\n".join(text[i:i + width] for i in range(0, len(text), width))

    center = node_id("case", case["id"])
    dept = node_id("dept", case["department"])
    lines = ["graph G {", "  rankdir=LR; nodesep=0.25; ranksep=1.2; splines=true;",
             '  node [fontname="sans-serif", fontsize=11];', '  edge [color="#9a9a9a"];']
    lines.append(f'  {center} [label="{wrap(case["title"])}", shape=box, style="filled,bold", fillcolor="#ffe8a3"];')
    lines.append(f'  {dept} [label="{case["department"]}", shape=ellipse, style=filled, fillcolor="#cfe3ff"];')
    used_types: list[str] = []
    used_platforms: list[str] = []
    for rel in related:
        for t in rel["shared_problem_types"]:
            if t not in used_types:
                used_types.append(t)
        # 基盤の線は、困りごとでも部署でも繋がらない事例にだけ描く（図を読める密度に保つ）
        if not rel["shared_problem_types"] and not rel["same_department"]:
            for p in rel["shared_platforms"]:
                if p not in used_platforms:
                    used_platforms.append(p)
    for t in used_types:
        lines.append(f'  {node_id("type", t)} [label="{wrap(t, 10)}", shape=ellipse, style="filled,bold", fillcolor="#ffd9b3"];')
    for p in used_platforms:
        lines.append(f'  {node_id("plat", p)} [label="{p}", shape=ellipse, style=filled, fillcolor="#e6e6e6"];')
    for rel in related:
        lines.append(f'  {node_id("case", rel["id"])} [label="{wrap(rel["title"])}", shape=box, style=filled, fillcolor="#f4f4f4"];')
    lines.append(f"  {{ rank=same; {' '.join(node_id('type', t) for t in used_types)} {dept}; {' '.join(node_id('plat', p) for p in used_platforms)} }}")
    lines.append(f"  {{ rank=same; {' '.join(node_id('case', r['id']) for r in related)} }}")
    for t in used_types:
        lines.append(f'  {center} -- {node_id("type", t)} [color="#e08a2e", penwidth=2];')
    lines.append(f"  {center} -- {dept};")
    for p in used_platforms:
        lines.append(f"  {center} -- {node_id('plat', p)};")
    for rel in related:
        for t in rel["shared_problem_types"]:
            lines.append(f'  {node_id("type", t)} -- {node_id("case", rel["id"])} [color="#e08a2e", penwidth=2];')
        if rel["same_department"]:
            lines.append(f'  {dept} -- {node_id("case", rel["id"])} [color="#5b8def"];')
        if not rel["shared_problem_types"] and not rel["same_department"]:
            for p in rel["shared_platforms"]:
                lines.append(f"  {node_id('plat', p)} -- {node_id('case', rel['id'])};")
    lines.append("}")
    return "\n".join(lines)


# ---------- 画面 ----------

def render_detail(case_id: str) -> None:
    case = fetch_case(case_id)
    if case is None:
        st.error("その事例は見つかりません。")
        if st.button("← 一覧へ"):
            go_list()
        return

    if st.button("← 一覧へ"):
        go_list()
    st.title(case["title"])
    st.markdown(f"**{LABELS['department']}**　:blue-badge[{case['department']}]　　"
                f"**{LABELS['problem_types']}**　{problem_badges(case['problem_types'])}")
    st.markdown(f"**{LABELS['platforms']}**　{badge_line(case)}")
    for key in ("who_and_problem", "ai_and_system", "requirements"):
        st.markdown(f"**{LABELS[key]}**")
        st.write(case[key])
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**{LABELS['confirmed_effects']}**")
        if case["confirmed_effects"]:
            st.success(case["confirmed_effects"])
        else:
            st.caption("記載なし")
    with col2:
        st.markdown(f"**{LABELS['hypothesized_effects']}**")
        if case["hypothesized_effects"]:
            st.info(case["hypothesized_effects"])
        else:
            st.caption("記載なし")
    st.markdown(f"**{LABELS['source_url']}**　[{case['source_url']}]({case['source_url']})　"
                f"**{LABELS['confirmed_at']}**　{case['confirmed_at']}")

    st.divider()
    st.subheader("関連事例")
    st.caption("同じ困りごとの型を最優先に、同じ部署、基盤の共有の順で辿っている（事例 → 困りごと・部署・基盤 → 事例）。")
    related = fetch_related(case_id)
    if not related:
        st.info("関連する事例はまだありません。")
        return
    graph_col, list_col = st.columns([1, 1])
    with graph_col:
        st.graphviz_chart(related_graph_dot(case, related), use_container_width=True)
    with list_col:
        for rel in related:
            with st.container(border=True):
                st.markdown(f"**{rel['title']}**")
                st.markdown(related_reason(rel))
                st.caption(summary(rel["who_and_problem"], 60))
                if st.button("この事例を見る", key=f"rel-{rel['id']}"):
                    go_detail(rel["id"])


def render_list() -> None:
    st.title("AI活用事例カタログ")
    ptypes, depts, plats = fetch_facets()
    with st.sidebar:
        st.header("絞り込み")
        keyword = st.text_input("キーワード（タイトル・困りごと・仕組み）", "")
        problem_type = st.selectbox(
            "困りごとの型", [""] + [t for t, _ in ptypes],
            format_func=lambda t: f"{t} ({dict(ptypes)[t]})" if t else "（すべて）")
        department = st.selectbox("部署・役割", [""] + depts, format_func=lambda d: d or "（すべて）")
        platforms = st.multiselect(
            "使っている基盤（すべて含む）",
            [p for p, _ in plats],
            format_func=lambda p: f"{p} ({dict(plats)[p]})",
        )
    cases = fetch_cases(keyword.strip(), problem_type, department, platforms)
    st.caption(f"{len(cases)} 件")
    if not cases:
        st.info("該当する事例がありません。")
        return
    render_list_header()
    for case in cases:
        render_row(case)


st.set_page_config(page_title="AI活用事例カタログ", layout="wide")
selected = st.query_params.get("case")
if selected:
    render_detail(selected)
else:
    render_list()
