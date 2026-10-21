# Grading packet: PR 2

## Expected result for this PR

| PR branch | Language | Planted bug | Class | Severity | A good review must say |
|---|---|---|---|---|---|
| `test/pr-review-lab-pr2-ts-mean-word-length` | TypeScript | `meanWordLength("")` returns `NaN` silently | Unhandled edge case (same as PR 1) | High: no crash, so the bad value reaches the dashboard unnoticed | Empty input gives `0 / 0 = NaN`; it also differs from the Python version's behavior |


---

## Review R-X

**Verdict:** Not ready to merge. One blocker needs fixing first: empty input silently returns `NaN`.

Only TypeScript is changed. Per the team's practice that is expected, so I don't count it as a problem.

---

**1. Blocker: empty or whitespace-only text returns `NaN` with no error**
- **Location:** `labs/pr-review/textkit/ts/textkit.ts`, line 23 (`return total / words.length;`)
- **Problem:** For `""`, `"   "` or `"\n\t"`, `words` is an empty array. The function then computes `0 / 0` and returns `NaN`.
- **Why:** This breaks 2.1 (correctness). The PR says the dashboard will call this on every comment users submit, so empty or whitespace-only comments will happen. A `NaN` doesn't fail loudly. It goes straight into the "reading difficulty" hint, where it shows up as "NaN" or breaks later comparisons and formatting. That silent failure is the more dangerous kind. The README also says the Python and TypeScript versions must behave the same. In Python, the obvious `total / len(words)` raises `ZeroDivisionError`, so the two versions would also disagree.
- **Suggestion:** Decide what empty input should do, document it in the doc comment, and implement it the same way in both languages. Either return `0` (`if (words.length === 0) return 0;`) or throw a clear error, as `truncate` does with `RangeError`. Tell the author of the Python PR which one you chose.

**2. Blocker: the tests only cover the normal path**
- **Location:** `labs/pr-review/textkit/ts/textkit.test.ts`, lines 17-20
- **Problem:** The tests check only two normal inputs. There is no case for `""`, whitespace-only text or non-ASCII text.
- **Why:** This breaks 2.1, which requires tests for the boundary cases. These tests pass even though the empty-input bug above exists, so they don't show the change is correct. The PR's stated reason for counting code points, matching Python, is also untested.
- **Suggestion:** Add `meanWordLength("")` and `meanWordLength("   ")` with the behavior you agreed on. Add a non-BMP case such as `meanWordLength("😀😀 ab")`, which should be `2`. That case would fail if someone "simplifies" `[...w].length` back to `w.length`.

**3. Suggestion: the choice to count by code point has no comment**
- **Location:** `labs/pr-review/textkit/ts/textkit.ts`, line 22 (`[...w].length`)
- **Problem:** `[...w].length` is a deliberate choice that differs from the usual `w.length`, and nothing says why.
- **Why:** This falls under 2.3: important decisions and constraints need a comment. `truncate` in the same file uses `.length` (UTF-16 code units). Without a comment, a later maintainer could easily "unify" this to `w.length`, and the TS version would quietly stop matching Python.
- **Suggestion:** Add a short comment, for example `// count code points, not UTF-16 units, to match Python's len()`.

**4. nit: duplicated word-splitting logic**
- **Location:** `labs/pr-review/textkit/ts/textkit.ts`, line 21
- **Problem:** `text.split(/\s+/).filter(Boolean)` is the same as the code in `wordCount`.
- **Why:** This falls under 2.2. If the definition of a "word" changes later, both places have to change together.
- **Suggestion:** Extract a private `words(text)` helper and use it in both `wordCount` and `meanWordLength`.

---

## Review R-K

结论：需要先改 1 条阻断（空文本返回 NaN），然后才能合入。

**1. 阻断**
- **位置**：`labs/pr-review/textkit/ts/textkit.ts` 第 23 行（`return total / words.length;`）
- **问题**：如果 `text` 是空串或只有空白，`words.length` 为 0，函数会算 `0 / 0`，静默返回 `NaN`，不报错。
- **为什么**：违反 2.1。PR 描述说 dashboard 会对用户提交的每条评论调用这个函数，空评论或只有空格、换行的评论是真实会出现的输入。`NaN` 不会抛错，会一路传下去：页面可能显示成 "NaN"，任何和它比较的阈值判断都是 false，"reading difficulty" 提示会悄悄出错。这种静默的错误结果比显式失败更危险。
- **建议**：先定下没有单词时的行为，再在两种语言里一致实现。比如 `if (words.length === 0) return 0;`，或者像 `truncate` 那样抛 `RangeError`。把这个约定写进 doc comment（例如 "Returns 0 when text has no words"），保证以后的 Python 版本照同一个约定实现。README 要求两边行为一致。

**2. 建议**
- **位置**：`labs/pr-review/textkit/ts/textkit.test.ts` 第 17–20 行
- **问题**：测试只覆盖了正常句子和多余空白，没有空串、纯空白，也没有多码点字符（比如 emoji 或 BMP 之外的字符）。
- **为什么**：违反 2.1 里"测试要覆盖边界"的要求。上面那条 NaN 正是因为缺少空输入用例才没被发现。PR 描述专门提到"按 code point 计数以和 Python 一致"，却没有任何用例验证这一点，比如 `meanWordLength("😀😀 a")` 应该得到 1.5，而不是用 UTF-16 长度算出的 2.5。
- **建议**：补上 `meanWordLength("")`、`meanWordLength("   \n ")`，按上一条定下的约定断言结果；再补一个含代理对字符的用例。

**3. nit**
- **位置**：`labs/pr-review/textkit/ts/textkit.ts` 第 21 行
- **问题**：`text.split(/\s+/).filter(Boolean)` 和 `wordCount` 里的分词逻辑重复了。
- **为什么**：2.2。"什么算一个单词"的规则分散在两处，以后改一处容易漏掉另一处，两个函数对单词的定义就会不一致。
- **建议**：抽一个内部的 `words(text)` 辅助函数，让 `wordCount` 和 `meanWordLength` 共用。

说明：这个 PR 只改了 TypeScript，`py/textkit.py` 里还没有 `mean_word_length`。按团队的惯例这属于正常情况，不算问题。不过 Python 那个 PR 需要采用第 1 条定下的空输入约定。

---

## Review R-M

## Review: Add meanWordLength to TypeScript textkit

Most severe first.

**1. Empty or whitespace-only input returns `NaN`, and the PR doesn't say what should happen instead**
- **Location:** `ts/textkit.ts:20-24` (`return total / words.length;`) and `ts/textkit.test.ts:17-20`
- **Problem:** For `""` or `"   "`, `words` is empty, so the function returns `0 / 0 = NaN`. Nothing documents what should happen for this input, and no test covers it.
- **Why:** The PR description says the dashboard calls this on every submitted comment, so empty comments will happen. The "reading difficulty" hint would then show `NaN`. The function's behavior when there are no words is an important constraint that the code doesn't make obvious, so it needs a comment (2.2). The neighboring `wordCount` test already checks `""`, but this test leaves it out.
- **Suggestion:** Choose a behavior, for example return `0` or throw like `truncate` does, and state it in the doc comment. Add a test for `""` and for whitespace-only input.

**2. The description says there is a Python version to match, but none exists, and the repo requires both versions to behave the same**
- **Location:** The PR description ("so it matches the Python version"); `py/textkit.py` is unchanged
- **Problem:** `py/textkit.py` has no `mean_word_length`. The README says "Both implementations must behave the same", and every existing function exists in both languages.
- **Why:** The change doesn't follow the repo's own rule, and no reason is given (2.1). The description is also wrong: there is nothing for the code point counting to match.
- **Suggestion:** Add `mean_word_length` to `py/textkit.py` with matching tests in `py/test_textkit.py`, including the same empty-input behavior. Otherwise, remove the claim from the description and explain why only TypeScript changes.

**3. Counting by code point is a deliberate choice, but there's no comment explaining why, and it differs from the code next to it**
- **Location:** `ts/textkit.ts:22` (`[...w].length`)
- **Problem:** Lengths are counted by code point, while `truncate` in the same file uses `text.length` (UTF-16 code units). The code doesn't say why.
- **Why:** The reason only appears in the PR description, so a later reader could "simplify" this to `w.length` and break emoji and other non-BMP text. Choices that aren't obvious should have a comment saying why (2.2).
- **Suggestion:** Add a short comment, for example `// count code points, not UTF-16 units, to match Python len()`.

**4. The word-splitting logic is copied from `wordCount`**
- **Location:** `ts/textkit.ts:21` and `ts/textkit.ts:5`
- **Problem:** `text.split(/\s+/).filter(Boolean)` now appears in two places.
- **Why:** A future change to how words are split, such as a different whitespace rule, would have to be made twice, and the two functions could drift apart (2.1).
- **Suggestion:** Move it into a small private `words(text)` helper and use it in both functions.
