#!/usr/bin/env bash
# dir-dump.sh
# 指定ディレクトリ配下の全テキストファイルを 1 つの Markdown ストリームに連結する。
# LLM への貼り付け・コンテキスト渡しを想定。
#
# 使い方:
#   ./dir-dump.sh                # カレントディレクトリ
#   ./dir-dump.sh <dir>          # 指定ディレクトリ
#   ./dir-dump.sh <dir> > out.md # ファイルに保存
#
# 出力フォーマット:
#   # Dump: <abs-path>
#
#   ## file: relative/path/to/file.ext
#
#   ```ext
#   <content>
#   ```
#
# オプション:
#   --max-bytes N    1ファイルあたりの上限バイト数（default: 1048576 = 1MB）
#                    超過分は中身省略でパスだけ表示
#   --include-hidden 隠しファイル/ディレクトリも含める（default: 除外）

set -euo pipefail

MAX_BYTES=1048576
INCLUDE_HIDDEN=0
TARGET="."

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
      sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    --max-bytes)
      MAX_BYTES="$2"
      shift 2
      ;;
    --include-hidden)
      INCLUDE_HIDDEN=1
      shift
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
    *)
      TARGET="$1"
      shift
      ;;
  esac
done

ROOT="$(cd "$TARGET" 2>/dev/null && pwd)" || {
  echo "Not a directory: $TARGET" >&2
  exit 1
}

# ─── 除外設定 ──────────────────────────────────
# ディレクトリ名（パスの任意セグメント）
EXCLUDE_DIRS=(
  ".git" ".terraform" "node_modules" "__pycache__"
  ".venv" "venv" ".mypy_cache" ".pytest_cache" ".ruff_cache"
  ".idea" ".vscode" "dist" "build" ".next" ".cache"
)

# 拡張子（小文字比較）
EXCLUDE_EXT_REGEX='\.(png|jpe?g|gif|bmp|svg|ico|webp|tiff?|psd|ai)$|\.(mp3|wav|ogg|flac|m4a|aac)$|\.(mp4|mov|avi|mkv|webm|wmv|flv)$|\.(zip|tar|tar\.gz|tgz|gz|bz2|xz|7z|rar)$|\.(pdf|docx?|xlsx?|pptx?|odt|ods)$|\.(class|jar|war|ear|so|dll|dylib|exe|bin|o|a|obj)$|\.(pyc|pyo)$|\.(woff2?|ttf|otf|eot)$|\.(db|sqlite3?|sqlitedb)$'

# 個別ファイル名
EXCLUDE_FILES_REGEX='(^|/)(\.DS_Store|Thumbs\.db|package-lock\.json|yarn\.lock|pnpm-lock\.yaml|Cargo\.lock|poetry\.lock|uv\.lock|composer\.lock|Gemfile\.lock)$'

# ─── find コマンド組み立て ──────────────────────
build_find_args() {
  local args=("$ROOT")

  if [ "$INCLUDE_HIDDEN" -eq 0 ]; then
    args+=(-not -path "*/.*")
  fi

  # 除外ディレクトリ
  for d in "${EXCLUDE_DIRS[@]}"; do
    args+=(-not -path "*/${d}/*")
  done

  args+=(-type f)
  printf '%s\n' "${args[@]}"
}

# ─── 言語ヒント（fence用）─────────────────────
lang_hint() {
  local ext="${1##*.}"
  case "${ext,,}" in
    sh|bash) echo "bash" ;;
    py)      echo "python" ;;
    js|mjs)  echo "javascript" ;;
    ts|tsx)  echo "typescript" ;;
    go)      echo "go" ;;
    rs)      echo "rust" ;;
    rb)      echo "ruby" ;;
    java)    echo "java" ;;
    kt)      echo "kotlin" ;;
    swift)   echo "swift" ;;
    yaml|yml) echo "yaml" ;;
    json)    echo "json" ;;
    toml)    echo "toml" ;;
    md|markdown) echo "markdown" ;;
    tf|tfvars|hcl) echo "hcl" ;;
    dockerfile) echo "dockerfile" ;;
    sql)     echo "sql" ;;
    html)    echo "html" ;;
    css|scss|sass) echo "css" ;;
    xml)     echo "xml" ;;
    *)       echo "" ;;
  esac
}

# ─── テキストファイル判定 ──────────────────────
# file --mime-encoding で binary 判定。
# 空ファイルはテキスト扱い、NULバイトを含むファイルはbinary。
is_text_file() {
  local f="$1"
  [ -s "$f" ] || return 0
  local enc
  enc=$(file -b --mime-encoding "$f" 2>/dev/null || echo "unknown")
  [ "$enc" != "binary" ]
}

# ─── ファイル選別（除外パターン適用） ───────────
# 拡張子・ファイル名除外を適用して最終リストを作る。
# 結果は TARGET_RELS（相対パス）にもファイルとして使うので、
# 一度配列に確定させてからツリー出力とコンテンツ出力で再利用する。
should_include() {
  local rel="$1"
  if [[ "${rel,,}" =~ $EXCLUDE_EXT_REGEX ]]; then return 1; fi
  if [[ "$rel" =~ $EXCLUDE_FILES_REGEX ]]; then return 1; fi
  return 0
}

# ─── ディレクトリツリー出力 ─────────────────────
# 含まれるファイルの相対パス一覧から ASCII ツリーを生成する。
# 中間ディレクトリは初回出現時のみ表示。
print_tree() {
  printf '%s\n' "${TARGET_RELS[@]}" | awk -F/ '
    {
      n = NF
      # 中間ディレクトリ
      path = ""
      for (i = 1; i < n; i++) {
        path = (path == "") ? $i : path "/" $i
        if (!seen[path]++) {
          indent = ""
          for (j = 1; j < i; j++) indent = indent "  "
          print indent $i "/"
        }
      }
      # ファイル本体
      indent = ""
      for (j = 1; j < n; j++) indent = indent "  "
      print indent $n
    }
  '
}

# ─── 本体 ──────────────────────────────────────
printf '# Dump: %s\n\n' "$ROOT"
printf '_Generated: %s_\n\n' "$(date -Iseconds)"

mapfile -t FIND_ARGS < <(build_find_args)

# 1パス目: 含めるファイル一覧を確定
TARGET_RELS=()
TARGET_ABS=()
while IFS= read -r f; do
  rel="${f#$ROOT/}"
  should_include "$rel" || continue
  TARGET_RELS+=("$rel")
  TARGET_ABS+=("$f")
done < <(find "${FIND_ARGS[@]}" 2>/dev/null | LC_ALL=C sort)

# ツリー表示（含めるファイルがある場合のみ）
if [ "${#TARGET_RELS[@]}" -gt 0 ]; then
  printf '## Tree\n\n'
  printf '```\n'
  print_tree
  printf '```\n\n'
fi

# 2パス目: ファイル内容を出力
for i in "${!TARGET_ABS[@]}"; do
  f="${TARGET_ABS[$i]}"
  rel="${TARGET_RELS[$i]}"

  # サイズ取得
  size=$(stat -c%s "$f" 2>/dev/null || echo 0)

  printf '## file: %s\n\n' "$rel"

  if [ "$size" -gt "$MAX_BYTES" ]; then
    printf '_skipped: size %s bytes exceeds limit %s bytes_\n\n' "$size" "$MAX_BYTES"
    continue
  fi

  if ! is_text_file "$f"; then
    printf '_skipped: binary file_\n\n'
    continue
  fi

  lang="$(lang_hint "$rel")"

  # ファイル内の最大連続バッククォート数 + 1 を fence 長にする
  # (Markdown 内のコードブロックがネストしても壊れないようにする)
  # grep が0件マッチで非0終了する pipefail 影響を抑えるため || true で吸収
  max_bt=$( { grep -oE '`+' "$f" 2>/dev/null || true; } | awk '{ print length }' | sort -n | tail -1)
  max_bt=${max_bt:-0}
  fence_len=$((max_bt + 1))
  [ $fence_len -lt 3 ] && fence_len=3
  fence=$(printf '%*s' "$fence_len" '' | tr ' ' '`')

  printf '%s%s\n' "$fence" "$lang"
  cat "$f"
  # ファイル末尾に改行がない場合に備える
  [ -z "$(tail -c1 "$f")" ] || printf '\n'
  printf '%s\n\n' "$fence"
done
