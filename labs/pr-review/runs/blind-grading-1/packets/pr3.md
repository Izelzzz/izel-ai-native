# Grading packet: PR 3

## Expected result for this PR

| PR branch | Language | Planted bug | Class | Severity | A good review must say |
|---|---|---|---|---|---|
| `test/pr-review-lab-pr3-py-render-template` | Python | `name` comes from the request and is joined to `TEMPLATE_DIR` unchecked | Security: path traversal | Critical | `name="../…"` or an absolute path reads any file the process can read; check the resolved path stays inside `TEMPLATE_DIR` or use an allowlist |


---

## Review R-X

## PR Review: Add render_template to Python textkit

I found 3 issues, most severe first. The first is a security bug. It falls outside the skill's two principles (simplicity and comments), but it is serious enough that I'm reporting it anyway.

### 1. Path traversal: the user-supplied `name` can read any file on the server
- **Location**: `py/textkit.py`, in `render_template`: `template = (TEMPLATE_DIR / name).read_text(encoding="utf-8")`
- **Problem**: `name` is joined to `TEMPLATE_DIR` as-is and the file is read with no check. The PR description says `name` comes straight from the support portal's request.
- **Why**: A customer can send `../../etc/passwd` or `../py/textkit.py`. An absolute path like `/etc/passwd` also works, because `Path / "/abs"` throws away the left side. Either way the function reads any file the process can access, and its contents come back in the rendered email. Picking from a dropdown limits nothing, because the request can be forged.
- **Suggestion**: Resolve the path and confirm it is still inside the template directory before reading. Or, simpler, keep an allowlist of template names and reject anything else. For example:
  ```python
  path = (TEMPLATE_DIR / name).resolve()
  if not path.is_relative_to(TEMPLATE_DIR):
      raise ValueError(f"unknown template: {name!r}")
  ```
  Add tests that `../` names and absolute paths raise an error. Also add a one-line comment saying `name` is untrusted input, which is the constraint behind this check (§2.2).

### 2. Python and TypeScript no longer match: there is no TS `renderTemplate`
- **Location**: `ts/textkit.ts` and `ts/textkit.test.ts` (not changed by this PR)
- **Problem**: The function is only added to `py/`.
- **Why**: The README says "Both implementations must behave the same", and every existing function exists in both languages. This PR breaks that rule without giving a reason (§2.1, consistency with repo conventions). The two implementations will drift further over time.
- **Suggestion**: Add an equivalent `renderTemplate` and tests on the TS side, including the same traversal check. If TS is deliberately left out, say why in the PR description.

### 3. The comment says what unknown placeholders do, not why
- **Location**: `py/textkit.py`, the `render_template` docstring: "Placeholders without a matching key are left as they are."
- **Problem**: The docstring describes the behaviour but not the reason for it. The reason ("so half-filled templates are easy to spot") is only in the commit message.
- **Why**: Leaving placeholders in place instead of raising an error or substituting an empty string is a non-obvious choice (§2.2). Without the reason in the code, a later maintainer may "fix" it into raising an error or substituting an empty string.
- **Suggestion**: Change it to something like "Unknown placeholders are left as-is so half-filled templates are easy to spot."

---

## Review R-M

**Verdict:** Not ready to merge. One blocker needs fixing first: path traversal in `render_template`.

The PR only changes Python, which is fine given the team's practice of shipping each language in its own PR. All 3 existing tests pass.

---

**1. Blocker: path traversal lets a request read any file on the server**
- **Location:** `labs/pr-review/textkit/py/textkit.py:28`
- **Problem:** `name` comes from the customer's request, and the code passes it straight into `(TEMPLATE_DIR / name).read_text()` without checking it.
- **Why:** Principle 2.1 says input from outside the trust boundary must be checked before it is used to access a resource. A dropdown in the UI does not stop anyone from sending their own request. I confirmed both attacks work: `render_template("../README.md", {})` returns the README, and `render_template("/etc/hostname", {})` returns the system file, because `Path / "/abs"` throws away the left side. Anyone who sends a request can read any file the process can read, including config and secrets, and gets the contents back as rendered text.
- **Fix:** Resolve the path first, then check it stays inside the templates folder. Raise `ValueError` if it doesn't, which matches how `truncate` reports errors:
  ```python
  path = (TEMPLATE_DIR / name).resolve()
  if not path.is_relative_to(TEMPLATE_DIR) or not path.is_file():
      raise ValueError(f"unknown template: {name!r}")
  ```
  An allowlist works too, such as checking `name` against the file names in `TEMPLATE_DIR`. Note that `TEMPLATE_DIR` already calls `.resolve()`, so the comparison holds.

**2. Suggestion: tests only cover the happy path**
- **Location:** `labs/pr-review/textkit/py/test_textkit.py:17-19`
- **Problem:** The tests check a normal fill and a missing key. Nothing covers bad template names (`../x`, absolute paths, a template that doesn't exist) or what happens when a value itself contains `{...}`.
- **Why:** Principle 2.1 says tests that only cover normal cases don't show the change is correct. Without a test, a later edit could bring the blocker back unnoticed. Per the skill's severity rules, missing tests can't be a blocker, so this is a suggestion.
- **Fix:** Add `assertRaises(ValueError)` cases for `"../README.md"`, `"/etc/passwd"` and `"missing.txt"`. Also add a test that fixes the current one-pass behavior in place: `{"name": "{x}", "x": "y"}` gives `"Hello, {x}!\n"`, not `"Hello, y!\n"`.

**3. nit: the docstring doesn't say which names are allowed**
- **Location:** `labs/pr-review/textkit/py/textkit.py:24-27`
- **Problem:** Once the check is added, the docstring should say `name` must be a file directly inside `templates/` and that anything else raises `ValueError`.
- **Why:** Principle 2.3 says to document constraints the code doesn't make obvious, so callers know what will be rejected.
- **Fix:** Add one sentence saying so.

---

## Review R-Q

结论：需要先改 1 条阻断（模板名的路径穿越）才能合入。

---

**1. 阻断**
- **位置**：`labs/pr-review/textkit/py/textkit.py:28`
- **问题**：`name` 没有校验就直接拼进路径（`TEMPLATE_DIR / name`），客户可以借此读到 `templates/` 之外的任意文件。
- **为什么**：违反 2.1「外部输入碰到文件路径前要校验」。PR 描述写明，`name` 来自客户在支持门户提交的请求，并且"直接传入"本函数。下拉框只限制了界面，请求可以伪造。`"../../../etc/passwd"` 会跳出模板目录。如果传绝对路径 `"/etc/passwd"`，`Path` 的 `/` 运算会直接丢掉 `TEMPLATE_DIR`。文件内容随后作为"渲染结果"返回，可能被发进邮件或回显给客户，等于任意文件读取。
- **建议**：解析后确认路径仍在模板目录内，否则抛 `ValueError`，例如：
  ```python
  path = (TEMPLATE_DIR / name).resolve()
  if not path.is_relative_to(TEMPLATE_DIR) or not path.is_file():
      raise ValueError(f"unknown template: {name!r}")
  ```
  更稳的做法是用白名单：允许的名字限定为 `TEMPLATE_DIR` 下实际存在的文件名，或者用 `^[\w-]+\.txt$` 这类正则匹配。

**2. 阻断**
- **位置**：`labs/pr-review/textkit/py/test_textkit.py:17-19`
- **问题**：测试只覆盖正常路径（模板存在、key 有或没有），没有覆盖非法 `name`。
- **为什么**：违反 2.1「测试只覆盖正常路径，不能说明改动是对的」。上面的穿越问题正是因为缺这类用例才没被发现，修复后也需要用例防止回退。
- **建议**：补充以下几种输入的断言，确认它们都抛出预期的异常：`"../README.md"`、绝对路径（如 `str(Path(__file__).resolve())`）、不存在的模板名。也可以顺带补一个模板里出现多个占位符、只填了部分的用例。

**3. nit**
- **位置**：`labs/pr-review/textkit/py/textkit.py:28`
- **问题**：模板不存在时，抛出的 `FileNotFoundError` 带着服务器上的绝对路径。
- **为什么**：调用方如果把异常信息回给客户，会泄露部署目录。和第 1 条一起改成统一的 `ValueError("unknown template: ...")`，调用方也更容易处理。
- **建议**：并入第 1 条的修复。

---

说明：README 要求 Python 和 TS 两个版本行为一致，但按团队惯例两种语言分两个 PR 合入，所以这个 PR 不改 `ts/` 是预期内的，不算问题。之后的 TS 版本需要做同样的路径校验。
