#!/usr/bin/env bash
# PostToolUse guard: lint edited backend Python files with ruff.
# Deterministic, zero LLM tokens. On a violation it exits 2 and prints ruff's
# output to stderr, which Claude Code feeds back so the agent fixes it before
# continuing. Keeps mechanical style (docstrings D1, imports, unused vars)
# enforced on every edit without spending model tokens.
set -uo pipefail

input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.path // empty')
[ -n "$file" ] || exit 0
[ "${file%.py}" != "$file" ] || exit 0            # only Python files

root=$(git -C "$(dirname "$file")" rev-parse --show-toplevel 2>/dev/null) || exit 0
case "$file" in
  "$root"/backend/*) rel=${file#"$root"/backend/} ;;
  *) exit 0 ;;                                     # only backend/ carries the ruff D config
esac

if out=$(cd "$root/backend" && uv run ruff check --force-exclude -- "$rel" 2>&1); then
  exit 0
fi
{ echo "▸ ruff style check failed for backend/$rel — fix before continuing:"; echo "$out"; } >&2
exit 2
