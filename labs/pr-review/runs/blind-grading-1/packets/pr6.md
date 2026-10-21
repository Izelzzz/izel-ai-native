# Grading packet: PR 6

## Expected result for this PR

| PR branch | Language | Planted bug | Class | Severity | A good review must say |
|---|---|---|---|---|---|
| `test/pr-review-lab-pr6-ts-has-prefix` | TypeScript | None (clean) | — | — | No real findings. Any finding here counts as a false positive |


---

## Review R-K

## Review: PR 6, "Add hasPrefix to TypeScript textkit"

### 1. (High) The Python version this PR says it matches does not exist
- **Location**: `ts/textkit.ts`, lines 19-22 (the new `hasPrefix`), together with `py/textkit.py`
- **Problem**: The PR description says "matching the Python version", but neither `main` nor this branch has a `has_prefix` in `py/textkit.py`. The PR only adds the TypeScript side.
- **Why**: This breaks consistency with repo conventions (2.1). `README.md` says "Both implementations must behave the same." After this merges, the two implementations have different APIs. The description also points readers to something that isn't there, so a later Python version has no shared spec to follow, and edge cases like the empty list and the empty prefix can easily diverge.
- **Suggestion**: Add `has_prefix(text, prefixes)` to `py/textkit.py` in this same PR (e.g. `any(text.startswith(p) for p in prefixes)`). Add a test in `py/test_textkit.py` covering the same four cases as the TS test. Then fix the "matching the Python version" wording in the description.

### 2. (Low) Two non-obvious behaviours have no comment
- **Location**: `ts/textkit.ts`, line 19 (the doc comment)
- **Problem**: The doc comment only restates what the function does ("Return true if text starts with any of the given prefixes"). It leaves out two constraints you can't see in the code:
  - Matching is case-sensitive. The stated use case is reply and forward subjects, and `"Re: meeting"` and `"Fw: x"` will not match `["RE:", "FW:"]`.
  - An empty-string prefix matches any text.
- **Why**: Comments should explain constraints and trade-offs that aren't obvious (2.2). A caller who misses these will think `"Re:"` is being detected when it isn't, or will put `""` in the list and match everything.
- **Suggestion**: Change it to one short line, for example: `/** Case-sensitive; an empty prefix matches any text, an empty list matches nothing. */`. If the inbox should ignore case, make the caller normalise case explicitly or add a separate option. Don't quietly change the semantics, and make the Python version behave the same way.

Nothing else to report. The implementation is a single `some(startsWith)` line, which is about as simple as it gets. The naming and test style match the existing `wordCount` and `truncate`.

---

## Review R-Z

结论：可以合入。没有阻断项，也没有建议项，只有下面两条 nit。

`hasPrefix` 直接用 `Array.prototype.some` 加 `String.prototype.startsWith`，写法和文件里已有的函数一致。按 PR 描述的场景推了一遍输入：
- 空列表返回 `false`。
- 空文本配非空前缀返回 `false`。
- 空串前缀返回 `true`。
- 参数类型由 TS 签名约束。

这几种都和 Python 的 `str.startswith(tuple)` 行为一致。区分大小写是标准库的常规行为，不需要注释。只改 TS 的 PR 符合团队约定。

---

- **等级**：nit
- **位置**：`labs/pr-review/textkit/ts/textkit.test.ts`，第 21 行（`hasPrefix("", [""])`）
- **问题**：空串前缀的测试只用了空文本，没覆盖「空串前缀能匹配任意非空文本」这个更容易出意外的情况。
- **为什么**：2.1 要求测试覆盖边界值。inbox 的前缀配置里如果混进一个 `""`，所有主题都会被判成回复或转发。现在的测试看不出作者是否有意接受这个行为。
- **建议**：补一条 `assert.equal(hasPrefix("meeting", [""]), true);`，把这个行为固定下来。如果这个行为不想要，就改实现。

- **等级**：nit
- **位置**：PR 描述（commit message）中「matching the Python version」一句；`labs/pr-review/textkit/py/textkit.py`
- **问题**：描述说和 Python 版行为一致，但这个分支上还没有 Python 的 `has_prefix`，这一句现在没法核对。
- **为什么**：README 要求两种实现行为一致。Python 那边有个容易踩的差异：`str.startswith` 只接受 str 或 tuple，传 list 会抛 `TypeError`，空 tuple 则返回 `False`。
- **建议**：在描述里链接对应的 Python PR。Python 版用 `text.startswith(tuple(prefixes))`，并补上同样的四条测试，让两边的边界行为对得上。

---

## Review R-Q

结论：可以合入。没有阻断或建议级问题，下面一条是 nit。

我核对过的内容：
- 实现和 PR 描述一致。`prefixes.some((p) => text.startsWith(p))` 对空列表返回 false，对空前缀返回 true，和配套的 Python PR（c97c7bc，`any(text.startswith(p) for p in prefixes)`）在已测的这些情况下行为一样，符合 README 里"两种实现行为必须一致"的要求。
- 测试覆盖了 PR 描述里列出的四种情况：命中、不命中、空列表、空前缀。两边的测试用例逐条对应。
- 只改 TS 符合团队按语言拆 PR 的做法。函数命名和单行文档注释与文件里已有的写法一致。

---

- **等级**：nit
- **位置**：labs/pr-review/textkit/ts/textkit.ts:19（文档注释）
- **问题**：匹配区分大小写，也不会去掉开头的空格，但文档注释没写这一点。
- **为什么**：属于 2.1 / 2.3。PR 说调用方是收件箱，用来识别回复和转发的主题。真实邮件里常见 "Re:"、"Fwd:" 这类写法，按描述里的 `["RE:", "FW:"]` 去调用，`hasPrefix("Re: meeting", ["RE:", "FW:"])` 会静默返回 false。函数作为通用的 hasPrefix 本身没错，Python 版也是一样的行为，所以这不是本 PR 的缺陷。但调用方容易误以为不区分大小写。
- **建议**：在注释里加半句"区分大小写"，或者请收件箱的调用方自己处理大小写和要传的前缀列表。如果确实要改成不区分大小写，需要在 Python 和 TS 两个 PR 里一起改，保持一致。
