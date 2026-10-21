# Grading packet: PR 1

## Expected result for this PR

| PR branch | Language | Planted bug | Class | Severity | A good review must say |
|---|---|---|---|---|---|
| `test/pr-review-lab-pr1-py-mean-word-length` | Python | `mean_word_length("")` or whitespace-only text divides by zero | Unhandled edge case | High: called on every user comment, so an empty comment crashes the request | Empty or whitespace-only input raises `ZeroDivisionError`; handle it (e.g. return 0) and add a test |


---

## Review R-Z

结论：需要先改 1 条阻断再合入：空文本或纯空白文本会让 `mean_word_length` 抛出 `ZeroDivisionError`。

---

**等级**：阻断
- **位置**：`labs/pr-review/textkit/py/textkit.py` 第 21 行（`return sum(len(w) for w in words) / len(words)`）
- **问题**：`text` 为 `""` 或只有空白（如 `"   "`、`"\n"`）时，`words` 是空列表，`len(words) == 0`，函数抛出 `ZeroDivisionError`。
- **为什么**：违反 2.1。PR 描述说 dashboard 会对用户提交的每条评论调用它，空评论或只有空白的评论是很现实的输入，这时 "reading difficulty" 提示会直接崩掉。README 要求 Python 和 TypeScript 两版行为一致；TS 版如果照搬同样的写法，会静默返回 `NaN`（0/0），比报错更危险。所以空输入的行为应该现在就定下来，后续的 TS PR 照着实现。
- **建议**：没有词时返回 `0.0`，这和 `word_count("") == 0` 是一致的。例如：
  ```python
  words = text.split()
  if not words:
      return 0.0
  return sum(len(w) for w in words) / len(words)
  ```
  如果团队更想对空输入抛出明确的 `ValueError`（像 `truncate` 那样），也可以。但不管选哪种，都要在 docstring 里写明，并通知写 TS PR 的人保持一致。

**等级**：建议
- **位置**：`labs/pr-review/textkit/py/test_textkit.py` 第 17–19 行（`test_mean_word_length`）
- **问题**：测试只覆盖了正常句子和多余空白，没有覆盖空串和纯空白输入。
- **为什么**：违反 2.1 中「只覆盖正常路径的测试，不能说明改动是对的」。正是这个缺口让上面的除零问题没被发现。
- **建议**：增加 `mean_word_length("")` 和 `mean_word_length("   ")` 的断言，期望值按上面选定的行为写（例如 `0.0`）。可以顺便加一个单词的用例，如 `mean_word_length("hello") == 5.0`。

**等级**：nit
- **位置**：`labs/pr-review/textkit/py/textkit.py` 第 19 行（docstring）
- **问题**：docstring 没有说明标点也算进词长（`"hi,"` 长度为 3），也没有说明空输入返回什么。
- **为什么**：2.3：不明显的约束应该写下来。这两点会影响 dashboard 显示的值，也影响 TS 版能否做到行为一致。
- **建议**：用一句话说明「words are whitespace-separated, punctuation included; returns 0.0 for text with no words」（或者写成你们选定的行为）。

---

## Review R-T

## PR Review：Add mean_word_length to Python textkit

按严重程度从高到低排列。

### 1. 空输入或纯空白输入会抛 ZeroDivisionError
- **位置**：`py/textkit.py:20-21`
- **问题**：`text` 为 `""` 或只有空白时，`words` 是空列表，`len(words)` 为 0，函数抛出 `ZeroDivisionError`。
- **为什么**：PR 描述说仪表盘会对用户提交的每条评论调用它，空评论或只含空格的评论会直接让调用方报错。这一条超出了 skill 列出的两条原则，但后果最严重。它同时违反 2.2：空输入该怎么处理是一个关键决策，代码和 docstring 都没说明。相邻的 `word_count` 有 `""` 的测试（`py/test_textkit.py:9`），新测试却没覆盖这种情况，和周边写法也不一致。
- **建议**：明确约定空输入的行为，例如 `if not words: return 0.0`；如果要按 `truncate` 的做法抛 `ValueError`，也要在 docstring 里写清楚。再补上 `mean_word_length("")` 和 `mean_word_length("   ")` 的测试。

### 2. 只加了 Python 版，没有对应的 TypeScript 实现
- **位置**：`ts/textkit.ts`（没有改动），`ts/textkit.test.ts`
- **问题**：README 写着 "Both implementations must behave the same"，这个 PR 只给 `py/` 加了函数，`ts/` 没有 `meanWordLength`。
- **为什么**：违反 2.1 中「和仓库已有写法一致」这一条。两套实现从此不再一致，以后再补 TS 版时，很容易在空输入等边界上定出不同的行为。
- **建议**：在同一个 PR 里加上 `meanWordLength(text: string): number`，分词方式和 `wordCount` 保持一致（`split(/\s+/).filter(Boolean)`），空输入的行为和 Python 版相同，并补上相同的测试用例。如果确实要分开做，就在 PR 描述里说明原因和后续计划。

### 3. docstring 没说明「词」是怎么定义的
- **位置**：`py/textkit.py:19`
- **问题**：docstring 写的是 "the words in text"，实际是按空白切分，标点也算进词长（`"there."` 算 6 个字符）。
- **为什么**：违反 2.2：不明显的约束应该写出来。这个函数要用来提示「阅读难度」，标点会把结果抬高，调用方从 docstring 看不出来。同文件的 `word_count` 已经写成 "whitespace-separated words"，这里的写法也不一致。
- **建议**：改成 "Return the average length of the whitespace-separated words in text (punctuation included)."，并在里面写上空输入时返回什么（见第 1 条）。

---

## Review R-M

结论：需要先改 1 条阻断（空输入会崩溃），然后再合入。

**阻断**
- **位置**：`labs/pr-review/textkit/py/textkit.py` 第 20–21 行（`mean_word_length`）
- **问题**：`text` 为空字符串或只有空白时，`words` 是空列表，`len(words)` 为 0，函数会抛出 `ZeroDivisionError`。
- **为什么**：违反 2.1（输入缺失或为空时的情况）。PR 描述说 dashboard 会对用户提交的每条评论调用它，用户提交空评论或只含空白的评论是真实会出现的场景，这会导致 dashboard 渲染这条提示时直接报错。
- **建议**：先决定空文本的约定行为并写进 docstring，例如 `if not words: return 0.0`。如果团队更倾向调用方自己处理，就显式抛 `ValueError`，和同文件里 `truncate` 的写法保持一致。TS 版本的 PR 要用同一个约定，因为 README 要求两种实现行为一致。

**建议**
- **位置**：`labs/pr-review/textkit/py/test_textkit.py` 第 17–19 行（`test_mean_word_length`）
- **问题**：测试只覆盖了正常句子和多余空白，没有覆盖空字符串和只含空白的输入。
- **为什么**：违反 2.1（只覆盖正常情况的测试，不能说明改动是对的）。正是缺了这个用例，上面的崩溃才没被发现。
- **建议**：为 `""` 和 `"   "` 各加一个断言，断言内容按上面选定的约定写（返回 `0.0`，或 `assertRaises(ValueError)`）。

**nit**
- **位置**：`labs/pr-review/textkit/py/textkit.py` 第 20 行
- **问题**：标点会算进单词长度，比如 `"hi, there."` 里 `"hi,"` 按 3 算。
- **为什么**：用它来做「阅读难度」提示时，标点多的评论平均词长会偏大。这里按空白切词和 `word_count` 是一致的，不一定要改。
- **建议**：如果打算保留现在的做法，在 docstring 里写一句「按空白切词，含标点」，免得以后 TS 版本或调用方理解成别的意思。
