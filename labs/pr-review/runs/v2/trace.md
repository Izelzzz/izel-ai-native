# Run 2 — skill v2

Changes from v1:

- New §2.1 "correct and safe" placed before readability and comments.
- Severity tiers: 阻断 / 建议 / nit. Only §2.1 can produce 阻断.
- §2.3: standard language/library behavior needs no comment (user's call after run 1: case-sensitivity notes are nits).
- Reviewer prompt gained one line of team context: each feature's Python and TS versions land as separate PRs. Fixes run 1's lab flaw without rewriting the pushed PR branches.

| PR | Planted bug | Caught? | Verdict | Other findings |
|---|---|---|---|---|
| 1 py mean_word_length | empty input → ZeroDivisionError | ✅ 阻断, via §2.1 | 需要先改 | 建议: tests miss empty input · nit: docstring |
| 2 ts meanWordLength | empty input → NaN | ✅ 阻断, called out "silent is more dangerous" | 需要先改 | **阻断**: tests only cover normal path · 建议: comment on code-point counting · nit: duplicated split |
| 3 py render_template | path traversal | ✅ 阻断, incl. absolute-path case | 需要先改 | **阻断**: no tests for bad names · nit: error leaks server path |
| 4 ts renderTemplate | path traversal | ✅ 阻断 | 需要先改 | nit: comment says what, not why |
| 5 py has_prefix (clean) | — | n/a | **需要先改 ❌** | **阻断 (false)**: empty prefix matches everything · nit: case-sensitive · nit: use `startswith(tuple)` |
| 6 ts hasPrefix (clean) | — | n/a | 可以合入 ✅ | nit: test empty prefix on non-empty text · nit: link the Python PR |

## Compared with run 1

| | v1 | v2 |
|---|---|---|
| Bugs caught | 4 / 4, but 3 "outside the skill's principles" | 4 / 4, all via §2.1 |
| Clean PRs | both got a "High"-level parity finding | PR 6 clean; PR 5 got a false 阻断 |
| Parity noise | on all 6 PRs | gone |
| Case-sensitivity comment notes | on both clean PRs | PR 6 explicitly said "no comment needed"; PR 5 kept it as a nit |

## What this run shows

1. **Catching bugs is now the rule, not luck.** Every reviewer cited §2.1.
2. **The new rule overshot on one clean PR.** §2.1 says "push real inputs from the PR's scenario". PR 5's reviewer invented a scenario (a config string with a trailing comma) and rated the result 阻断. The user already ruled this a nit.
3. **Same logic, opposite verdicts.** PR 5 and PR 6 are the same function in two languages. PR 6's reviewer considered the same empty-prefix case and called it a nit. One run per PR is not enough to tell a skill problem from reviewer variance.
4. **"Missing tests" is filed inconsistently.** For the same kind of gap: 建议 on PR 1, a separate 阻断 on PR 2 and PR 3. It should ride along with the bug it fails to catch, not double-count.
