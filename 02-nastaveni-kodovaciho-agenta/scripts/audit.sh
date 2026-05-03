#!/usr/bin/env bash
# audit.sh - Conformance check for Claude Code project setup.
#
# Emits machine-readable lines:
#   [PASS|WARN|FAIL] <category> <message>
# Ends with a summary line:
#   [SUMMARY] pass=<n> warn=<n> fail=<n>
#
# Always exits 0 (consumer classifies). Run from any cwd.
#
# Usage:
#   scripts/audit.sh                    # audits this task dir
#   scripts/audit.sh /path/to/project   # audits a different dir

set -uo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PASS=0; WARN=0; FAIL=0

emit() {
  local level="$1" cat="$2" msg="$3"
  printf '[%s] %s %s\n' "$level" "$cat" "$msg"
  case "$level" in
    PASS) PASS=$((PASS+1));;
    WARN) WARN=$((WARN+1));;
    FAIL) FAIL=$((FAIL+1));;
  esac
}

has_cmd() { command -v "$1" >/dev/null 2>&1; }

# JSON validate via node (already required by hooks ecosystem).
json_valid() {
  local f="$1"
  if has_cmd node; then
    node -e "JSON.parse(require('fs').readFileSync('$f','utf8'))" 2>/dev/null
  else
    python3 -c "import json,sys; json.load(open('$f'))" 2>/dev/null
  fi
}

# YAML frontmatter present? (between leading --- lines)
has_frontmatter() {
  awk 'NR==1 && /^---$/ {found=1} NR>1 && found && /^---$/ {print "ok"; exit} END{exit}' "$1" | grep -q ok
}

# Extract a frontmatter scalar field. Naive but sufficient for required fields.
fm_field() {
  local file="$1" field="$2"
  awk -v f="$field" '
    NR==1 && /^---$/ {in_fm=1; next}
    in_fm && /^---$/ {exit}
    in_fm && $1==f":" { $1=""; sub(/^ +/,""); print; exit }
  ' "$file"
}

cd "$ROOT" || { emit FAIL bootstrap "cannot cd into $ROOT"; printf '[SUMMARY] pass=0 warn=0 fail=1\n'; exit 0; }

# --- .mcp.json ---------------------------------------------------------------
if [[ -f .mcp.json ]]; then
  if json_valid .mcp.json; then
    emit PASS mcp ".mcp.json is valid JSON"
    if grep -q '"mcpServers"' .mcp.json; then
      emit PASS mcp "lists mcpServers key"
    else
      emit FAIL mcp ".mcp.json missing 'mcpServers' object"
    fi
  else
    emit FAIL mcp ".mcp.json is not valid JSON"
  fi
else
  emit WARN mcp ".mcp.json not present (no project-scoped MCP servers)"
fi

# --- .claude/settings.json ---------------------------------------------------
if [[ -f .claude/settings.json ]]; then
  if json_valid .claude/settings.json; then
    emit PASS settings "settings.json is valid JSON"
  else
    emit FAIL settings "settings.json is not valid JSON"
  fi
else
  emit WARN settings ".claude/settings.json missing"
fi

if [[ -f .claude/settings.local.json ]]; then
  if json_valid .claude/settings.local.json; then
    emit PASS settings "settings.local.json is valid JSON"
  else
    emit FAIL settings "settings.local.json is not valid JSON"
  fi
fi

# --- .claude/hooks/*.js -----------------------------------------------------
if [[ -d .claude/hooks ]]; then
  shopt -s nullglob
  hooks=(.claude/hooks/*.js)
  if (( ${#hooks[@]} == 0 )); then
    emit WARN hooks ".claude/hooks/ exists but has no .js files"
  fi
  for h in "${hooks[@]}"; do
    if has_cmd node; then
      if node --check "$h" 2>/dev/null; then
        emit PASS hooks "$h syntax ok"
      else
        emit FAIL hooks "$h failed node --check"
      fi
    else
      emit WARN hooks "node not in PATH; cannot syntax-check $h"
    fi
  done
  # Cross-check: every hook referenced in settings.json must exist on disk.
  if [[ -f .claude/settings.json ]] && has_cmd node; then
    refs=$(node -e '
      const s = JSON.parse(require("fs").readFileSync(".claude/settings.json","utf8"));
      const out = [];
      for (const ev of Object.values(s.hooks || {})) {
        for (const grp of ev) for (const h of (grp.hooks || []))
          if (h.command) out.push(h.command);
      }
      console.log(out.join("\n"));
    ' 2>/dev/null)
    while IFS= read -r cmd; do
      [[ -z "$cmd" ]] && continue
      path=$(echo "$cmd" | grep -oE '\.claude/hooks/[A-Za-z0-9._-]+\.js' | head -n1)
      if [[ -n "$path" && ! -f "$path" ]]; then
        emit FAIL hooks "settings.json references missing hook: $path"
      fi
    done <<<"$refs"
  fi
else
  emit WARN hooks ".claude/hooks/ directory missing"
fi

# --- .claude/agents/*.md ----------------------------------------------------
if [[ -d .claude/agents ]]; then
  shopt -s nullglob
  agents=(.claude/agents/*.md)
  if (( ${#agents[@]} == 0 )); then
    emit WARN agents ".claude/agents/ exists but has no .md files"
  fi
  for a in "${agents[@]}"; do
    if has_frontmatter "$a"; then
      name=$(fm_field "$a" name)
      desc=$(fm_field "$a" description)
      if [[ -n "$name" ]]; then
        emit PASS agents "$a frontmatter ok (name=$name)"
      else
        emit FAIL agents "$a missing 'name' field in frontmatter"
      fi
      if [[ -z "$desc" ]] && ! grep -q '^description: *>' "$a"; then
        emit WARN agents "$a missing 'description' field"
      fi
    else
      emit FAIL agents "$a missing YAML frontmatter (--- ... ---)"
    fi
  done
else
  emit WARN agents ".claude/agents/ directory missing"
fi

# --- .claude/skills/*/SKILL.md ----------------------------------------------
if [[ -d .claude/skills ]]; then
  shopt -s nullglob
  skill_dirs=(.claude/skills/*/)
  for d in "${skill_dirs[@]}"; do
    f="${d}SKILL.md"
    if [[ -f "$f" ]]; then
      if has_frontmatter "$f"; then
        emit PASS skills "$f frontmatter ok"
      else
        emit FAIL skills "$f missing YAML frontmatter"
      fi
    else
      emit FAIL skills "$d missing SKILL.md"
    fi
  done
else
  emit WARN skills ".claude/skills/ directory missing"
fi

# --- .claude/commands/*.md --------------------------------------------------
if [[ -d .claude/commands ]]; then
  shopt -s nullglob
  cmds=(.claude/commands/*.md)
  for c in "${cmds[@]}"; do
    if has_frontmatter "$c"; then
      emit PASS commands "$c frontmatter ok"
    else
      emit WARN commands "$c missing YAML frontmatter (optional but recommended)"
    fi
  done
fi

# --- README.md --------------------------------------------------------------
if [[ -f README.md ]]; then
  emit PASS readme "README.md present"
  for kw in "MCP" "subagent" "hook"; do
    if grep -qi "$kw" README.md; then
      emit PASS readme "README mentions '$kw'"
    else
      emit WARN readme "README does not mention '$kw'"
    fi
  done
else
  emit FAIL readme "README.md missing"
fi

printf '[SUMMARY] pass=%d warn=%d fail=%d\n' "$PASS" "$WARN" "$FAIL"
