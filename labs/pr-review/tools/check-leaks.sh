#!/usr/bin/env bash
# Fail if a skill file mentions words specific to the lab's planted bugs.
# A skill must teach general review principles, not this test set's answers.
# Usage: check-leaks.sh <SKILL.md>
set -u
skill="$1"
# Each line: a term tied to a specific fixture (bug, symptom, or clean-PR edge case).
terms=(
  'NaN' 'None' '空串' '除零' 'ZeroDivision' 'division by zero' '0 / 0'
  '文件路径' '路径' 'path' 'traversal' '穿越' '模板' 'template'
  '前缀' 'prefix' '大小写' 'case-sensitiv' '区分大小写'
  '平均' 'mean' 'word' '词' '评论' 'comment 场景' '邮件' 'inbox'
)
hits=0
for t in "${terms[@]}"; do
  if grep -n -i -F -- "$t" "$skill" >/dev/null; then
    grep -n -i -F -- "$t" "$skill" | sed "s/^/  [$t] /"
    hits=$((hits + 1))
  fi
done
if [ "$hits" -gt 0 ]; then echo "LEAK: $hits term(s) found in $skill"; exit 1; fi
echo "clean: no fixture-specific terms in $skill"
