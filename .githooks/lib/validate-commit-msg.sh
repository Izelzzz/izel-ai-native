#!/usr/bin/env bash
# Validate the default commit subject: <type>(<scope>): <summary>
# 校验默认提交主题行：<type>(<scope>): <summary>。scope 可省略。
# Rejects empty subjects and vague summaries (update / fix bug / changes).
# 拒绝空主题和笼统摘要。仓库另有约定时，以仓库约定为准。
# Usage:
#   validate-commit-msg.sh <message-file>
#   validate-commit-msg.sh -m "subject"
#   printf '%s\n' "subject" | validate-commit-msg.sh
# Exit: 0 accepted; 1 rejected.
set -euo pipefail

usage() {
  cat <<'EOF'
用法 / usage:
  validate-commit-msg.sh <消息文件>
  validate-commit-msg.sh -m "说明"
  printf '%s\n' "说明" | validate-commit-msg.sh

退出码 / exit: 0 通过机械检查；1 拒绝。
默认格式 / default: <type>(<scope>): <imperative summary>
type: feat, fix, refactor, docs, test, chore, perf, build, ci
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

message=""
if [[ $# -eq 0 ]]; then
  if [[ -t 0 ]]; then
    usage >&2
    exit 1
  fi
  message="$(cat)"
elif [[ "$1" == "-m" ]]; then
  if [[ $# -ne 2 ]]; then
    echo "validate-commit-msg: -m 之后需要一段说明。 (-m requires a message)" >&2
    exit 1
  fi
  message="$2"
elif [[ $# -eq 1 ]]; then
  if [[ ! -f "$1" ]]; then
    echo "validate-commit-msg: 找不到文件: $1 (file not found)" >&2
    exit 1
  fi
  message="$(cat -- "$1")"
else
  usage >&2
  exit 1
fi

subject=""
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  if [[ "$line" =~ ^[[:space:]]*# ]]; then
    continue
  fi
  if [[ -z "${line//[[:space:]]/}" ]]; then
    continue
  fi
  subject="$line"
  break
done <<< "$message"

COMMIT_SUBJECT="$subject" python3 - <<'PY'
import os
import re
import sys

subject = os.environ.get("COMMIT_SUBJECT", "").strip()
match = re.match(
    r"^(feat|fix|refactor|docs|test|chore|perf|build|ci)"
    r"(?:\(([A-Za-z0-9._/-]+)\))?(!)?:[ \t]+(\S.*?)\s*$",
    subject,
)
if not match:
    print(
        "validate-commit-msg: 主题行需为 <type>(<scope>): <summary>。"
        "类型为 feat、fix、refactor、docs、test、chore、perf、build、ci；scope 可省略。"
        " (subject does not match conventional commit)",
        file=sys.stderr,
    )
    sys.exit(1)

summary = re.sub(r"[.\!。！]+\s*$", "", match.group(4)).strip()
norm = re.sub(r"\s+", " ", summary).strip().lower()

exact = {
    "update",
    "updates",
    "updated",
    "updating",
    "fix",
    "fixed",
    "fixes",
    "fixing",
    "fixup",
    "change",
    "changes",
    "changed",
    "changing",
    "bug",
    "bugs",
    "bugfix",
    "bug fix",
    "fix bug",
    "fix bugs",
    "wip",
    "tmp",
    "misc",
    "stuff",
    "typo",
    "typos",
    "minor fix",
    "small fix",
    "quick fix",
    "minor changes",
    "small changes",
    "various fixes",
    "update code",
    "update files",
    "update docs",
    "update readme",
    "fix code",
    "fix issue",
    "fix issues",
    "fix typo",
    "typo fix",
    "更改",
    "更新",
    "修复",
    "改动",
    "修改",
    "调整",
    "优化",
    "变更",
    "小修",
    "修bug",
    "修复bug",
    "更新代码",
    "修改代码",
    "更新文档",
    "修改文档",
    "改一下",
    "修复一下",
    "更新一下",
}
if norm in exact:
    print(
        "validate-commit-msg: 摘要过于笼统（update / fix bug / changes）。写明改动对象和做了什么。"
        " (vague summary)",
        file=sys.stderr,
    )
    sys.exit(1)

hollow_words = {
    "update",
    "updates",
    "updated",
    "updating",
    "fix",
    "fixed",
    "fixes",
    "fixing",
    "fixup",
    "change",
    "changes",
    "changed",
    "changing",
    "bug",
    "bugs",
    "bugfix",
    "code",
    "files",
    "docs",
    "readme",
    "stuff",
    "typo",
    "typos",
    "various",
    "issue",
    "issues",
    "minor",
    "small",
    "quick",
    "wip",
    "tmp",
    "misc",
}
stopwords = {"a", "an", "the", "of", "to", "for", "and", "or", "in", "on"}
words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", norm)
content_words = [word for word in words if word not in stopwords]
cjk = "".join(re.findall(r"[\u4e00-\u9fff]", summary))
for token in ("更新", "修复", "修改", "改动", "调整", "优化", "变更", "小修", "一下"):
    cjk = cjk.replace(token, "")

vague_latin = bool(content_words) and all(word in hollow_words for word in content_words)
if vague_latin and len(cjk) < 2:
    print(
        "validate-commit-msg: 摘要过于笼统（update / fix bug / changes）。写明改动对象和做了什么。"
        " (vague summary)",
        file=sys.stderr,
    )
    sys.exit(1)

if not content_words and len(cjk) < 2:
    print(
        "validate-commit-msg: 摘要没有写明改动。 (summary lacks a specific change)",
        file=sys.stderr,
    )
    sys.exit(1)

sys.exit(0)
PY
