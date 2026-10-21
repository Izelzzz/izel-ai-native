# PR Review Lab

> ⚠️ **`test/pr-review-lab-*` 分支里的代码故意埋了 bug 和安全漏洞（包括路径穿越），只用于评测 review agent。不要把那里的代码复制到真实项目。**

用一组埋好 bug 的 PR 反复评测 `pr-review` skill：写规则 → 跑 review → 对照答案打分 → 改规则 → 再跑。

## 分支

| 分支 | 内容 |
|---|---|
| `docs/pr-review-lab` | 本目录：skill、每一轮的记录、答案表 |
| `test/pr-review-lab-base` | 被 review 的 textkit 库（`labs/pr-review/textkit/`），Python 与 TypeScript 各一份 |
| `test/pr-review-lab-pr1` … `pr6` | 6 个练习 PR，每个是 base 上的一次提交，提交说明即 PR 描述 |

答案表只在本分支，PR 分支里没有，所以 reviewer 拿到 PR 分支时是盲测。

## 本目录

| 路径 | 内容 |
|---|---|
| `skill/pr-review/SKILL.md` | 当前版本的 skill |
| `runs/v<N>/` | 第 N 轮：当时的 SKILL.md 快照与 `trace.md` 记录 |
| `answer-key.md` | 埋了什么、怎么打分、每轮的结果记录 |

## 跑一轮

1. 改 skill 后先跑 `tools/check-leaks.sh skill/pr-review/SKILL.md`，扫描不通过不跑。
2. 为每个 PR 分支建一个**独立 clone**（`git clone --single-branch --branch <PR 分支>`），不要用 `git worktree`：worktree 共用 `.git`，reviewer 能看到本分支和答案表。
3. 每个 PR 交给一个全新上下文的 reviewer，提示只说「按 SKILL.md review 这个 PR」，不提示有埋的 bug。
4. 盲评：把各版本的输出打乱、换成随机编号，交给不知道版本的打分 agent（最好换一个模型），按 `answer-key.md` 打分。每个 PR 每个版本至少跑 3 次再比较。
5. 按 `answer-key.md` 打分，结果写进它的 Results log，记录写进 `runs/v<N>/trace.md`。

被 review 的代码自带测试，在 `labs/pr-review/textkit/` 里运行：

    python3 -m unittest discover -s py
    npm test
