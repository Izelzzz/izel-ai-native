# PR review lab — answer key

Keep this file out of the reviewer's reach. The code under review is `labs/pr-review/textkit/` on the `test/pr-review-lab-*` branches.
Each PR is a branch off `test/pr-review-lab-base`; its commit message is the PR description.
All tests pass on every branch: the planted bugs are ones the tests miss.

## Expected findings

| PR branch | Language | Planted bug | Class | Severity | A good review must say |
|---|---|---|---|---|---|
| `test/pr-review-lab-pr1-py-mean-word-length` | Python | `mean_word_length("")` or whitespace-only text divides by zero | Unhandled edge case | High: called on every user comment, so an empty comment crashes the request | Empty or whitespace-only input raises `ZeroDivisionError`; handle it (e.g. return 0) and add a test |
| `test/pr-review-lab-pr2-ts-mean-word-length` | TypeScript | `meanWordLength("")` returns `NaN` silently | Unhandled edge case (same as PR 1) | High: no crash, so the bad value reaches the dashboard unnoticed | Empty input gives `0 / 0 = NaN`; it also differs from the Python version's behavior |
| `test/pr-review-lab-pr3-py-render-template` | Python | `name` comes from the request and is joined to `TEMPLATE_DIR` unchecked | Security: path traversal | Critical | `name="../…"` or an absolute path reads any file the process can read; check the resolved path stays inside `TEMPLATE_DIR` or use an allowlist |
| `test/pr-review-lab-pr4-ts-render-template` | TypeScript | Same, via `path.join(TEMPLATE_DIR, name)` | Security: path traversal (same as PR 3) | Critical | Same as PR 3 |
| `test/pr-review-lab-pr5-py-has-prefix` | Python | None (clean) | — | — | No real findings. Any finding here counts as a false positive |
| `test/pr-review-lab-pr6-ts-has-prefix` | TypeScript | None (clean) | — | — | No real findings. Any finding here counts as a false positive |

Verified on 2026-10-20: `mean_word_length("")` raises `ZeroDivisionError`;
`meanWordLength("")` returns `NaN`; `render_template("../README.md", {})`
and `renderTemplate("../package.json", {})` both read files outside `templates/`.

## Scoring each run

For every PR, record:

- **Caught**: did the review name the planted bug (the right cause, not just "add more tests")?
- **False positives**: findings that are wrong, or so minor they are noise.
- **Severity right?**: was the bug ranked as serious as the table says?

Things that are *not* false positives, if raised as minor notes: suggesting a
test for the clean PRs' edge cases, or noting that Python `len()` and JS
`.length` count characters differently (pre-existing on `main`, in `truncate`).

## What the language pairs test

PRs 1/2 and 3/4 plant the same bug class in two languages. If a review catches
a bug in one language but misses it in the other, the skill's principles depend
on one language's habits, or that language needs a `references/<lang>.md`.

## Results log

| Run | Skill version | PR1 | PR2 | PR3 | PR4 | PR5 FP | PR6 FP | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | v1 (readability + comments only) | ✅ #1 | ✅ #1 (framed as a missing comment, §2.2) | ✅ #1 | ✅ #1 | 1 (TS parity, lab flaw) + 1 low note | 1 (TS parity, rated High) + 1 low note | 3 of 4 catches explicitly said "outside the skill's principles": the model's own instincts found them, not the skill. Parity finding on every PR is a lab design flaw (README says both languages must match, but each PR changes one) |
| 2 | v2 (+ correctness/safety first, severity tiers, standard-behavior comments exempt) | ✅ 阻断 | ✅ 阻断 (+ missing tests as a 2nd 阻断) | ✅ 阻断 (+ missing tests as a 2nd 阻断) | ✅ 阻断 | **1 false 阻断** (empty prefix) + 2 nits | 0 — "可以合入", 2 nits | All 4 bugs caught via §2.1, no more "outside the principles". Reviewer prompt gained one line of team context (languages land in separate PRs): parity noise gone. New problems: PR5 vs PR6 are the same logic but got opposite verdicts (variance); missing tests for a bug sometimes filed as a separate 阻断 |
