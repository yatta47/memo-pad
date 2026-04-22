#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<EOF
Usage: $(basename "$0") <module-dir>

Dump a Terraform module directory and its local-source references into a
single text stream (stdout) formatted for pasting into an AI chat.

Includes: *.tf in the given dir, plus *.tf in any locally-sourced
module (source = "./..." or "../..."), recursively.

Excludes: .tfvars, .tfstate, .terraform/, registry and Git sources
(listed by name only, not expanded).
EOF
  exit 1
}

[ $# -eq 1 ] || usage
case "$1" in -h|--help) usage ;; esac

ROOT="$(cd "$1" 2>/dev/null && pwd)" || { echo "Not a directory: $1" >&2; exit 1; }

declare -A VISITED=()
declare -a ORDER=()
declare -a EXTERNAL=()

# Extract `source = "..."` values only from inside `module "name" { ... }`
# blocks. Ignores sources in `required_providers`, `locals`, etc.
extract_module_sources() {
  awk '
    BEGIN { in_module = 0; depth = 0 }
    {
      if (!in_module) {
        if (match($0, /^[[:space:]]*module[[:space:]]+"[^"]+"[[:space:]]*\{/)) {
          in_module = 1
          depth = 1
        }
        next
      }
      if (match($0, /^[[:space:]]*source[[:space:]]*=[[:space:]]*"[^"]+"/)) {
        s = substr($0, RSTART, RLENGTH)
        sub(/^[[:space:]]*source[[:space:]]*=[[:space:]]*"/, "", s)
        sub(/".*/, "", s)
        print s
      }
      t = $0; no = gsub(/\{/, "", t)
      t = $0; nc = gsub(/\}/, "", t)
      depth += no - nc
      if (depth <= 0) in_module = 0
    }
  ' "$1"
}

collect() {
  local dir abs src target
  dir="$1"
  abs="$(cd "$dir" && pwd)"
  [ -n "${VISITED[$abs]:-}" ] && return
  VISITED[$abs]=1
  ORDER+=("$abs")

  shopt -s nullglob
  for tf in "$abs"/*.tf; do
    while IFS= read -r src; do
      [ -z "$src" ] && continue
      case "$src" in
        ./*|../*)
          if target="$(cd "$abs" && cd "$src" 2>/dev/null && pwd)"; then
            collect "$target"
          else
            EXTERNAL+=("$src (unresolved local path)")
          fi
          ;;
        *)
          EXTERNAL+=("$src")
          ;;
      esac
    done < <(extract_module_sources "$tf")
  done
  shopt -u nullglob
}

collect "$ROOT"

rel_to_root() {
  local p="$1"
  if [ "$p" = "$ROOT" ]; then
    echo "."
  else
    realpath --relative-to="$ROOT" "$p" 2>/dev/null || echo "$p"
  fi
}

printf '===== Terraform Module Dump =====\n'
printf 'Root: %s\n' "$ROOT"
printf 'Generated: %s\n' "$(date -Iseconds)"
printf 'Local modules expanded: %d\n' "${#ORDER[@]}"
printf '\n'

printf '===== LOCAL MODULES =====\n'
for m in "${ORDER[@]}"; do
  printf -- '- %s\n' "$(rel_to_root "$m")"
done
printf '\n'

if [ ${#EXTERNAL[@]} -gt 0 ]; then
  mapfile -t EXTERNAL < <(printf '%s\n' "${EXTERNAL[@]}" | sort -u)
  printf '===== EXTERNAL SOURCES (not expanded) =====\n'
  for e in "${EXTERNAL[@]}"; do
    printf -- '- %s\n' "$e"
  done
  printf '\n'
fi

shopt -s nullglob
for m in "${ORDER[@]}"; do
  for tf in "$m"/*.tf; do
    rel="$(realpath --relative-to="$ROOT" "$tf" 2>/dev/null || echo "$tf")"
    printf '===== FILE: %s =====\n' "$rel"
    cat -- "$tf"
    printf '\n'
  done
done
shopt -u nullglob
