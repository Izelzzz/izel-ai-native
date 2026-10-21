#!/usr/bin/env bash
# Checks every branch on origin. Local hooks can be skipped (--no-verify) or never installed; this can't.
# Run from a clone that has fetched all branches with full history.
set -uo pipefail
# Relative to this script, not the checked-out branch: test/* and docs/* trees have no .githooks/.
. "$(dirname "$0")/../.githooks/lib/common.sh" || { echo "ci-checks: can't load .githooks/lib/common.sh" >&2; exit 2; }

failures=0
problem() { printf '  ✗ %s\n' "$*"; failures=$((failures + 1)); }
section() { printf '\n== %s\n' "$*"; }

branches="$(git for-each-ref --format='%(refname:short)' refs/remotes/origin | grep -v '^origin$' | grep -v '/HEAD$')"

section "Commit messages on all branches"
for c in $(git rev-list $branches); do
  [ -n "$(git rev-list --parents -n1 "$c" | cut -s -d' ' -f2)" ] || continue   # root commit
  msg="$(git log -1 --format=%B "$c")"
  is_git_generated_subject "$(printf '%s\n' "$msg" | subject_of)" && continue
  printf '%s\n' "$msg" | "$HOOK_LIB_DIR/validate-commit-msg.sh" 2>/dev/null \
    || problem "${c:0:7} $(git log -1 --format=%s "$c")"
done

section "Answer files kept off test branches"
for b in $(printf '%s\n' "$branches" | grep '^origin/test/'); do
  leaked="$(git ls-tree -r --name-only "$b" | grep -E "$LAB_ANSWER_PATHS" || true)"
  [ -z "$leaked" ] || problem "$b contains: $(printf '%s' "$leaked" | tr '\n' ' ')"
done

section "Current skill names no answers"
docs=origin/docs/pr-review-lab
if git cat-file -e "$docs:labs/pr-review/skill/pr-review/SKILL.md" 2>/dev/null; then
  tmp="$(mktemp -d)"
  git show "$docs:labs/pr-review/skill/pr-review/SKILL.md" > "$tmp/SKILL.md"
  git show "$docs:labs/pr-review/tools/check-leaks.sh" > "$tmp/check-leaks.sh"
  bash "$tmp/check-leaks.sh" "$tmp/SKILL.md" || problem "skill on $docs names fixture-specific terms"
fi

section "textkit tests on every test branch"
for b in $(printf '%s\n' "$branches" | grep '^origin/test/'); do
  dir="$(mktemp -d)"
  git worktree add -q --detach "$dir" "$b"
  if (cd "$dir/labs/pr-review/textkit" && python3 -m unittest discover -s py -q && npm test --silent) > "$dir.log" 2>&1; then
    printf '  ✓ %s\n' "$b"
  else
    sed 's/^/    /' "$dir.log"; problem "tests fail on $b"
  fi
  git worktree remove --force "$dir"
done

printf '\n'
[ "$failures" -eq 0 ] && { echo "All checks passed."; exit 0; }
echo "$failures problem(s) found."; exit 1
