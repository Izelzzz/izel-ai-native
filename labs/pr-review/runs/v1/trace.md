# Run 1 — skill v1 (readability + comments only)

Six reviewers, one per PR, fresh context, same neutral prompt. No hint of planted bugs.

| PR | Planted bug | Caught? | How the reviewer justified it | Other findings |
|---|---|---|---|---|
| 1 py mean_word_length | empty input → ZeroDivisionError | ✅ ranked #1 | "Outside the skill's two principles, but the most serious" | TS parity missing; docstring should define "word" |
| 2 ts meanWordLength | empty input → NaN | ✅ ranked #1 | Framed under §2.2: "no-word behavior is an undocumented constraint" | Python parity missing; explain code-point counting; extract `words()` helper |
| 3 py render_template | path traversal | ✅ ranked #1 | "Outside the skill's two principles, but serious enough to report" | TS parity missing; comment says what, not why |
| 4 ts renderTemplate | path traversal | ✅ ranked #1 | "Outside the skill's two principles, but too serious to leave out" | "Python version doesn't exist"; comment says what, not why |
| 5 py has_prefix (clean) | — | n/a | — | TS parity missing; document case-sensitivity / empty-prefix rule |
| 6 ts hasPrefix (clean) | — | n/a | — | Python parity missing (**rated High**); document case-sensitivity / empty-prefix rule |

## What this run shows

1. **Bugs were caught by the model's instincts, not by the skill.** Three of four reviewers said so explicitly. The skill never asks for correctness or security, so this depends on the model choosing to step outside the rules.
2. **The skill bent one reviewer's reasoning.** PR 2's crash-free `NaN` bug was justified as "a missing comment" because that was the only principle available.
3. **Every PR got a "the other language is missing" finding.** That is a flaw in the lab, not the reviewer: the README says both languages must match, but each PR changes only one.
4. **Severity drifted.** PR 6 rated the parity note *High*, the same level as real bugs elsewhere.
5. **Your comment principle produced consistent, specific notes** ("says what, not why", "reason only lives in the commit message"). This is the part the skill clearly added.
