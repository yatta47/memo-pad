"""catalog/*.json が docs/case-schema.md の形に合っているか検査する。"""
import json, re, sys
from pathlib import Path

KEYS = ["id", "title", "department", "who_and_problem", "problem_types", "ai_and_system", "platforms",
        "requirements", "confirmed_effects", "hypothesized_effects", "source_url", "confirmed_at"]
LIST_KEYS = {"platforms", "problem_types"}
PROBLEM_TYPES = {
    "情報検索・参照に時間がかかる", "手入力・転記・記録の負荷", "文書・資料作成の負荷", "問い合わせ・対応の負荷",
    "属人化・スキル差", "調査・分析・原因究明に時間", "開発・運用の速度と統制", "監視・見守りの限界",
}

def check(path: Path) -> list[str]:
    errs = []
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"json parse error: {e}"]
    if list(d.keys()) != KEYS:
        errs.append(f"keys mismatch: {list(d.keys())}")
    for k in KEYS:
        if k in LIST_KEYS:
            v = d.get(k)
            if not isinstance(v, list) or not v or not all(isinstance(x, str) and x.strip() for x in v):
                errs.append(f"{k}: must be a non-empty list of strings")
        elif not isinstance(d.get(k), str):
            errs.append(f"{k}: not a string")
    if d.get("id") != path.stem:
        errs.append(f"id '{d.get('id')}' != filename '{path.stem}'")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.get("confirmed_at", "")):
        errs.append("confirmed_at: not YYYY-MM-DD")
    if not d.get("source_url", "").startswith("http"):
        errs.append("source_url: not a URL")
    for k in ["title", "department", "who_and_problem", "ai_and_system", "requirements"]:
        if not d.get(k, "").strip():
            errs.append(f"{k}: empty")
    if len(d.get("title", "")) > 40:
        errs.append("title: over 40 chars")
    if len(d.get("department", "")) > 10:
        errs.append("department: over 10 chars")
    pts = d.get("problem_types")
    if isinstance(pts, list):
        if len(pts) > 2:
            errs.append("problem_types: more than 2")
        for t in pts:
            if t not in PROBLEM_TYPES:
                errs.append(f"problem_types: unknown type '{t}'")
    return errs

def main():
    files = sorted(Path("catalog").glob("*.json"))
    bad = 0
    for f in files:
        errs = check(f)
        if errs:
            bad += 1
            print(f"NG {f.name}: " + "; ".join(errs))
    print(f"{len(files)} files, {bad} NG")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
