# Blind grading 1 — v1 vs v2 vs v2.1

## Why

Until now the same model wrote the bugs, edited the skill and graded the reviews. Two fixes in this round:

1. **v2.1 removes fixture-specific words from the skill.** v2 named the exact symptoms and targets of the planted bugs (`NaN`, `None`, 空串, 文件路径, 模板) and used a clean PR's edge case as an example (区分大小写). v2.1 replaces them with general wording. Everything else, including §3 severity, is identical to v2. `tools/check-leaks.sh` now scans a skill for such words; v2.1 passes.
2. **Blind grading by a different model.** For each PR, the v1, v2 and v2.1 reviews were shuffled and relabelled with random IDs (`mapping.json`). Six grader agents running a different model (Sonnet) scored them against the answer key, without knowing there were versions. The person running the lab did not look at the mapping until all grades were in.

## Leak checks on the reviewers

All 18 reviewers' commands were inspected from their transcripts. None read the answer key. One v2.1 reviewer (PR 6) ran `git log --all` and read the paired Python PR's commit: not the answer key, but it shows the review copies (git worktrees) share one `.git`, so **any reviewer could have reached `docs/pr-review-lab`**. Future runs must give each reviewer a standalone clone containing only its PR branch.

## Results (`grades-unblinded.json`)

| | v1 | v2 | v2.1 |
|---|---|---|---|
| Bugs caught | 4/4 | 4/4 | 4/4 |
| Bug ranked as must-fix | 3/4 | 4/4 | 4/4 |
| False blockers | 3 | 3 | 1 |
| Noise findings | 6 | 0 | 0 |
| Correct merge verdict | 3/6 | 5/6 | 5/6 |

Per PR (FB = false blockers):

| PR | v1 | v2 | v2.1 |
|---|---|---|---|
| 1 py empty input | ✅ | ✅ | ✅ |
| 2 ts empty input | ✅ caught, but framed as a missing comment, not must-fix | ✅ +1 FB (missing tests as blocker) | ✅ |
| 3 py traversal | ✅ +1 FB (missing TS version rated high) | ✅ +1 FB (missing tests as blocker) | ✅ |
| 4 ts traversal | ✅ +1 FB (missing Python version rated high) | ✅ | ✅ |
| 5 py clean | ❌ verdict: asks for TS version | ❌ FB: empty prefix | ❌ FB: empty prefix |
| 6 ts clean | ❌ FB: missing Python version rated High | ✅ mergeable | ✅ mergeable |

## Reading the results

1. **Removing the leaked words did not cost anything.** v2.1 still catches 4/4 and ranks all of them as must-fix. The v2 gains came from the principle, not from naming the answers.
2. **v2.1's lower false-blocker count is probably noise.** The difference is all "missing tests filed as a blocker" (v2, PR 2 and 3). §3 severity rules are identical in v2 and v2.1, so the skill change cannot explain it. One run per PR cannot separate this from reviewer variance.
3. **PR 5's false blocker is consistent, so it is a real skill problem.** Both v2 and v2.1 blocked the clean Python PR over the empty-prefix case; both TS reviews passed the same logic. Two runs each is too few to say whether language matters.
4. **v1's noise is mostly the lab's fault.** Five of v1's six noise findings are "the other language is missing". v1 reviewers were not told the team lands languages in separate PRs; v2 and v2.1 reviewers were. Graders were told for all three.
5. **The grader mostly agrees with the earlier self-grading.** It independently flagged the same v1 PR 2 framing problem and the same PR 5 false blocker.

## Next

- Run each PR at least 3 times per version before comparing versions.
- Standalone clones for reviewers.
- Fix PR 5's false blocker: a 阻断 must be able to happen in the scenario the PR states.
- Harder, human-written bugs (reverted real fixes), with a held-out set.
