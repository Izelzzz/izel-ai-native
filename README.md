# review-lab

一个用来评测和改进 **PR review agent** 的实验室：用一组埋好 bug 的 PR 反复测试 review skill，按答案打分，根据错误改规则，再测。

> ⚠️ `test/pr-review-lab-*` 分支里的代码**故意埋了 bug 和安全漏洞**（包括路径穿越），只用于评测。不要把那里的代码复制到真实项目。

## 仓库结构

`main` 只有这份说明。内容都在分支里：

```
main                                  本说明
 ├── docs/pr-review-lab               skill、评测记录、答案表
 └── test/pr-review-lab-base          被 review 的 textkit 代码（所有 PR 的起点）
       ├── test/pr-review-lab-pr1-…   每个分支 = base + 1 个 commit
       ├── …
       └── test/pr-review-lab-pr6-…
```

### 题目：`test/pr-review-lab-*`

`test/pr-review-lab-base` 从 `main` 拉出，加入一个小的文本工具库 `labs/pr-review/textkit/`，Python 与 TypeScript 各一份，自带测试。

6 个 PR 分支各从 base 拉出，**各加 1 个 commit**：改动就是 PR 的 diff，commit message 就是 PR 描述。它们不是 GitHub 上的 Pull Request，只是分支。

| 分支 | 语言 | 内容 |
|---|---|---|
| [`pr1-py-mean-word-length`](https://github.com/Izelzzz/review-lab/compare/test/pr-review-lab-base...test/pr-review-lab-pr1-py-mean-word-length) | Python | 埋了 bug |
| [`pr2-ts-mean-word-length`](https://github.com/Izelzzz/review-lab/compare/test/pr-review-lab-base...test/pr-review-lab-pr2-ts-mean-word-length) | TypeScript | 埋了 bug（与 PR 1 同类） |
| [`pr3-py-render-template`](https://github.com/Izelzzz/review-lab/compare/test/pr-review-lab-base...test/pr-review-lab-pr3-py-render-template) | Python | 埋了安全漏洞 |
| [`pr4-ts-render-template`](https://github.com/Izelzzz/review-lab/compare/test/pr-review-lab-base...test/pr-review-lab-pr4-ts-render-template) | TypeScript | 埋了安全漏洞（与 PR 3 同类） |
| [`pr5-py-has-prefix`](https://github.com/Izelzzz/review-lab/compare/test/pr-review-lab-base...test/pr-review-lab-pr5-py-has-prefix) | Python | 干净，用来测误报 |
| [`pr6-ts-has-prefix`](https://github.com/Izelzzz/review-lab/compare/test/pr-review-lab-base...test/pr-review-lab-pr6-ts-has-prefix) | TypeScript | 干净，用来测误报 |

点分支名可以看它相对 base 的 diff。所有分支的测试都能通过：埋的 bug 正是测试没覆盖到的那种。同一类 bug 在两种语言里各埋一份，用来检验 skill 的原则是否与语言无关。

### 结果：[`docs/pr-review-lab`](https://github.com/Izelzzz/review-lab/tree/docs/pr-review-lab/labs/pr-review)

都在 `labs/pr-review/` 下：

| 路径 | 内容 |
|---|---|
| `README.md` | lab 说明与每一轮的跑法 |
| `skill/pr-review/SKILL.md` | 当前版本的 review skill |
| `answer-key.md` | 每个 PR 埋了什么、怎么打分、每一轮的分数 |
| `runs/v1/`、`runs/v2/`、`runs/v2.1/` | 每一轮的 skill 快照与记录 |
| [`runs/blind-grading-1/`](https://github.com/Izelzzz/review-lab/blob/docs/pr-review-lab/labs/pr-review/runs/blind-grading-1/README.md) | v1 / v2 / v2.1 的盲评对比，**建议从这里看起** |
| `tools/check-leaks.sh` | 检查 skill 里有没有写进题目答案 |

答案表只在这个分支，PR 分支里没有，所以 reviewer 拿到 PR 分支时是盲测。

## 怎么跑一轮

review 不在 GitHub 上跑，而是在本地或云端机器上，由 agent 执行：

1. 改完 skill，先跑 `tools/check-leaks.sh`，有泄露就不跑。
2. 每个 PR 分支建一个**独立 clone**，只含这一个分支，让 reviewer 碰不到答案表。
3. 每个 PR 交给一个全新上下文的 reviewer agent：读 SKILL.md，看 `git diff test/pr-review-lab-base...HEAD`，输出 review。提示里不提有埋的 bug。
4. **盲评**：把各版本的 review 打乱、换成随机编号，交给不知道有版本之分的打分 agent（用另一个模型），按答案表打分，最后再揭开编号。
5. 每个 PR、每个版本至少跑 3 次再比较，否则分不清改进和随机波动。
6. 记录写进 `runs/`，分数写进 `answer-key.md`。

## 提交规范与检查

提交说明使用 `<type>(<scope>): <summary>`，例如 `docs(pr-review-lab): add run 4 results`。`type` 为 `feat`、`fix`、`refactor`、`docs`、`test`、`chore`、`perf`、`build`、`ci`，`scope` 可省略。`update`、`fix bug` 这类笼统的摘要会被拒绝。git 自己生成的 `Merge`、`Revert`、`fixup!`、`squash!` 直接放行。

检查分两层：本地 git hook 让问题尽早暴露，CI 负责兜底。hook 可以用 `--no-verify` 跳过，也可能根本没装，所以规则以 CI 为准。

### 本地 hook

clone 之后在任意分支执行一次（`.githooks/` 改动后也要重新执行）：

    git show main:scripts/install-hooks.sh | bash

它把 `main` 的 `.githooks/` 装进 `.git/review-lab-hooks/`，所以对**所有分支**生效，切换分支也不会变。`test/` 分支是考题，不放 hook 文件。

| hook | 时机 | 检查 |
|---|---|---|
| `commit-msg` | 每次提交 | 提交说明格式 |
| `pre-commit` | 每次提交，只做几秒内的检查 | 空白错误和冲突标记；超过 1 MiB 的文件；`.env`、私钥等凭据文件；暂存内容里像密钥的字符串；在 `test/*` 上禁止提交答案表、`runs/`、`skill/`、`tools/`；在 `docs/*` 上改动 skill 时运行 `check-leaks.sh` |
| `pre-push` | 推送前 | 拦截改写已发布历史的推送（force-push）；重新检查每个新提交的说明；推送的提交改动了 textkit 时跑它的测试 |

确实要 force-push 时，需要点名分支：`ALLOW_FORCE_PUSH=<分支名> git push --force-with-lease ...`。故意写进代码的假密钥，在那一行加上 `secret-scan: allow`。

提交说明检查来自 [`izel-skill`](https://github.com/Izelzzz/izel-skill) 0.1.0 的 `team-git-workflow`（`.githooks/lib/validate-commit-msg.sh`）。

### CI

`.github/workflows/checks.yml` 在推送到 `main`、PR、每天一次和手动触发时运行，检查**所有分支**：

- 每个提交的说明格式
- `test/*` 分支里没有答案文件
- 当前 skill 没有写进题目答案
- 每个 `test/*` 分支的 textkit 测试都通过
- 用 gitleaks 扫描全部历史里的密钥

push 触发的 workflow 用的是被推送分支自己的那份 workflow 文件，而 `test/*`、`docs/*` 分支里没有这个文件，所以由 `main` 定时检查全部分支。本地也可以跑同样的检查：`bash scripts/ci-checks.sh`。

## 目前进度

| 版本 | 改了什么 | 抓到 bug | 误判阻断 | 合入结论正确 |
|---|---|---|---|---|
| v1 | 只有可读性、注释两条原则 | 4/4（多数是越出原则报的） | 3 | 3/6 |
| v2 | 加入「正确与安全」为第一原则，加严重程度分级 | 4/4 | 3 | 5/6 |
| v2.1 | v2 去掉泄露答案的词 | 4/4 | 1 | 5/6 |

（盲评，每个 PR 每个版本只跑了 1 次。v2 到 v2.1 误判数的变化很可能是随机波动，详见盲评报告。）

下一步：

- 修复干净的 PR 5 被误判为阻断的问题。
- 每个 PR 跑 3 次再比较。
- 加入从真实项目撤回修复得到的 bug，并留出一部分作为不参与调参的考试题。
