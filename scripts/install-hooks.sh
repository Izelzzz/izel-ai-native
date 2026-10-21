#!/usr/bin/env bash
# Install main's .githooks for this clone, so they run on every branch.
# Works from any branch, even ones without .githooks/:
#   git show main:scripts/install-hooks.sh | bash
# Re-run after .githooks changes on main.
set -euo pipefail

ref="${1:-main}"
git rev-parse -q --verify "$ref:.githooks" >/dev/null || { echo "install-hooks: $ref has no .githooks/" >&2; exit 1; }

# Inside the git dir, not the working tree, so switching branches can't remove or change them.
dest="$(cd "$(git rev-parse --git-common-dir)" && pwd)/review-lab-hooks"
rm -rf "$dest"; mkdir -p "$dest"
git archive "$ref" .githooks | tar -x -C "$dest" --strip-components=1
git rev-parse "$ref:.githooks" > "$dest/.source-tree"
chmod +x "$dest"/commit-msg "$dest"/pre-commit "$dest"/pre-push "$dest"/lib/validate-commit-msg.sh

git config core.hooksPath "$dest"
echo "install-hooks: installed $ref's hooks into $dest"
