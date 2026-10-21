# Grading packet: PR 4

## Expected result for this PR

| PR branch | Language | Planted bug | Class | Severity | A good review must say |
|---|---|---|---|---|---|
| `test/pr-review-lab-pr4-ts-render-template` | TypeScript | Same, via `path.join(TEMPLATE_DIR, name)` | Security: path traversal (same as PR 3) | Critical | Same as PR 3 |


---

## Review R-M

结论：需要先改 1 条阻断（路径穿越），之后才可以合入。

---

**阻断**
- **位置**：`labs/pr-review/textkit/ts/textkit.ts:30`
- **问题**：`name` 没有校验就拼进了 `join(TEMPLATE_DIR, name)`，可以读到 `templates/` 目录之外的任意文件。
- **为什么**：违反 2.1 的信任边界原则。按 PR 描述，`name` 来自客户在支持门户提交的请求，函数直接拿它去访问文件。下拉框只是界面限制，请求里的值可以随意改。`path.join` 会解析 `..`，所以 `renderTemplate("../../../../etc/passwd", {})` 会读出服务器上的文件，并当作邮件正文返回。这是任意文件读取。
- **建议**：只接受已知的模板名。可以用白名单，也可以要求 `name` 匹配 `/^[\w-]+\.txt$/`。另一种做法是先 `path.resolve(TEMPLATE_DIR, name)`，再确认结果仍以 `TEMPLATE_DIR` 开头，否则抛错。同时在 `textkit.test.ts` 里加测试，断言 `"../package.json"`、`"../../etc/passwd"`、`"/etc/passwd"` 这类输入会抛错。

**建议**
- **位置**：`labs/pr-review/textkit/ts/textkit.test.ts:17-20`
- **问题**：测试只覆盖正常模板，以及占位符缺值的情况。
- **为什么**：违反 2.1。只测正常输入，说明不了改动是对的。模板不存在时目前会抛出 Node 原生的 `ENOENT` 错误，这个行为没有测试，也没有约定，调用方不知道该捕获什么。
- **建议**：补两类用例：模板不存在时的报错，以及非法 `name` 被拒绝。如果希望给调用方一个稳定的错误类型，就在函数里统一包装成一种明确的错误。

**nit**
- **位置**：commit message（"matching the Python version"）
- **问题**：仓库里目前还没有 Python 版的 `render_template`，`py/textkit.py` 里只有 `word_count` 和 `truncate`。
- **为什么**：按团队流程，Python 版会走另一个 PR，所以只改一种语言本身没问题。但 README 要求两边行为一致，「未知占位符保留原样」和占位符语法（`\w+`）现在只在 TS 一侧有定义。
- **建议**：Python 版 PR 要照着这里的规则实现，并且加上同样的名称校验。描述可以改成「Python 版将保持一致」。

---

## Review R-K

**结论：需要先修复 1 条阻断（路径穿越）才能合入。**

---

**1.**
- **等级**：阻断
- **位置**：`labs/pr-review/textkit/ts/textkit.ts` 第 30 行（`readFileSync(join(TEMPLATE_DIR, name), "utf8")`）
- **问题**：`name` 没有任何校验就拼进文件路径。传入 `../../../../etc/passwd` 这类值，就能读到 `templates/` 目录以外的任意文件。
- **为什么**：违反 2.1「外部输入碰到文件路径之前要校验」。PR 描述写明 `name` 来自支持门户的请求，并且会被「原样传给」这个函数。下拉框只是前端限制，攻击者可以直接构造请求。`path.join` 会把 `..` 规范化掉，最终路径就落到模板目录之外。读到的文件内容会被当成模板渲染后返回，造成服务器上任意文件泄露，比如配置文件和密钥。另外，模板名不存在时，`readFileSync` 抛出的 ENOENT 错误里带有服务器的绝对路径。如果调用方把这个错误原样回给前端，内部目录结构也会暴露。
- **建议**：
  - 首选做法：用 `readdirSync(TEMPLATE_DIR)` 得到允许的模板名单，`name` 不在名单里就抛出明确的错误。
  - 另一种做法：先 `path.resolve(TEMPLATE_DIR, name)`，再检查结果以 `TEMPLATE_DIR` 开头（`TEMPLATE_DIR` 本身带结尾的 `/`）。不满足就拒绝，同时拒绝含路径分隔符的 `name`。
  - 未知模板名要抛一个不含内部路径的自定义错误。
  - 在 `textkit.test.ts` 里补用例：`renderTemplate("../package.json", {})`、`renderTemplate("/etc/passwd", {})` 和不存在的模板名都应抛错。现有测试只覆盖正常路径，证明不了这个函数在真实调用场景下是安全的（也是 2.1 的要求）。

**2.**
- **等级**：nit
- **位置**：`labs/pr-review/textkit/ts/textkit.ts` 第 25–28 行（JSDoc）
- **问题**：注释只说了未匹配的占位符会保留原样，没说为什么这样做。
- **为什么**：2.3 要求非显而易见的取舍要写「为什么」。原因（方便一眼看出没填完的模板）目前只写在 commit message 里，读代码的人看不到。
- **建议**：在这句后面加半句，例如「so half-filled templates are easy to spot」。

---

补充说明（不算发现）：commit message 写着与「Python 版本」行为一致，但基线分支的 `py/textkit.py` 里还没有 `render_template`。按团队「两种语言分两个 PR」的惯例，这是正常的。建议在 Python 那个 PR 里做同样的路径校验，并按 README 的要求保持两边行为一致，包括对非法名字的处理。

---

## Review R-Z

## Review: Add renderTemplate to TypeScript textkit

### 1. Path traversal: the template name comes from the user and goes straight into the file path (high)
- **Location**: `ts/textkit.ts`, the `renderTemplate` body, `readFileSync(join(TEMPLATE_DIR, name), "utf8")` (line 30)
- **Problem**: `name` is not checked before it is joined onto `TEMPLATE_DIR`. The PR description says the name is "sent in the request and passed straight to this function". So a request with `name = "../../etc/passwd"` or an absolute path reads any file the process can open and returns it as the rendered template.
- **Why**: This is outside the skill's two principles (simplicity, comments), but it is too serious to leave out. A dropdown in the UI does not limit what a client can send. The design has no limit on which files can be read, and no comment saying this was considered.
- **Suggestion**: Accept only known template names. Either compare `name` against an allowlist (for example `readdirSync(TEMPLATE_DIR)`), or resolve the path and reject it if it is not inside `TEMPLATE_DIR`:
  `const p = resolve(TEMPLATE_DIR, name); if (!p.startsWith(TEMPLATE_DIR)) throw new Error(...)`
  Also add a test for `"../package.json"`.

### 2. "Matching the Python version" is wrong: there is no Python version (high)
- **Location**: the PR description; `py/textkit.py`, which is not changed
- **Problem**: `py/textkit.py` has only `word_count` and `truncate`. There is no `render_template`, so this PR adds a TypeScript-only feature.
- **Why**: The repo's README says "Both implementations must behave the same." This change breaks that rule. The PR description also gives a false reason for the placeholder behaviour, which will mislead reviewers and future maintainers (principle 2.1: follow the repo's existing conventions).
- **Suggestion**: Add `render_template` to `py/textkit.py`, with the same tests in `py/test_textkit.py` (including the path-traversal guard). Or fix the description and explain why the two versions differ on purpose.

### 3. The reason for keeping unknown placeholders is missing from the code (low)
- **Location**: `ts/textkit.ts`, the doc comment of `renderTemplate` (lines 25-28)
- **Problem**: The comment says *what* happens ("left as they are") but not *why*. The reason, "so half-filled templates are easy to spot", appears only in the commit message.
- **Why**: Principle 2.2 says non-obvious choices should be commented. Without the reason, someone may later "fix" this to replace unknown keys with empty strings.
- **Suggestion**: Change the second line to something like: `Unknown placeholders are kept (not blanked) so half-filled output is easy to spot.`

The rest of the change is fine. The regex replacement is short and clear. `Object.hasOwn` correctly avoids matching keys inherited from the prototype. The tests follow the style of the existing tests.
