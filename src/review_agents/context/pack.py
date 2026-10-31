"""The context pack: what each dimension agent of a review reads, in cache-friendly order.

Every dimension gets the same prefix: the shared rules, then the repository layer, then
the pull request layer. Only the last message, the dimension's SKILL.md and its task,
differs, so a model service with prompt caching reuses the prefix across the five
agents and across each agent's turns (context design §5).
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from importlib.resources import files
from pathlib import PurePosixPath

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from review_agents.context.grouping import grouped_layers, signature_tokens
from review_agents.context.pr_layer import PrLayer
from review_agents.context.repo_layer import RepoLayer
from review_agents.context.tokens import estimate_tokens

DIMENSIONS = ("spec_drift", "edge_cases", "security", "maintainability", "verifiability")
_SKILLS = files("review_agents") / "skills"
SHARED_RULES = (_SKILLS / "_shared.md").read_text(encoding="utf-8")
SKILLS = {d: (_SKILLS / d / "SKILL.md").read_text(encoding="utf-8") for d in DIMENSIONS}

# The part of the window kept free for what an agent adds while it works: tool results,
# its reasoning and its findings.
AGENT_SHARE = 0.3
NO_ROOM_NOTE = (
    "The intent, repository layer and file list alone leave no room for the changes in"
    " one review window; each group is larger than the window."
)


def task(dimension: str) -> str:
    return (
        f"{SKILLS[dimension]}\n\n"
        f"Review the pull request above for the {dimension} dimension only. Read more code"
        " with your tools wherever the context is not enough. Report findings in the output"
        " format of the shared rules."
    )


@dataclass(frozen=True)
class ContextPack:
    shared_rules: str
    repo: RepoLayer
    pr: PrLayer

    @property
    def prefix(self) -> str:
        """Everything before the dimension's own message, identical for every dimension."""
        return f"{self.repo.render()}\n\n{self.pr.render()}"

    def messages(self, dimension: str) -> list[BaseMessage]:
        return [
            SystemMessage(self.shared_rules),
            HumanMessage(self.prefix),
            HumanMessage(task(dimension)),
        ]


def fixed_tokens(base: ContextPack, layer: PrLayer) -> int:
    """What every group carries whatever its changes: rules, repository, intent, task."""
    longest_task = max(estimate_tokens(task(d)) for d in DIMENSIONS)
    return (
        estimate_tokens(base.shared_rules)
        + estimate_tokens(base.prefix)
        + signature_tokens(layer)
        + longest_task
    )


def module_finder(repo: RepoLayer) -> Callable[[str], str]:
    """The deepest module of the repository layer holding a path; "" for the root."""
    paths = sorted((m.path for m in repo.modules if m.path), key=len, reverse=True)

    def module_of(path: str) -> str:
        parents = {str(p) for p in PurePosixPath(path).parents}
        return next((m for m in paths if m in parents), "")

    return module_of


def build_packs(repo: RepoLayer, layer: PrLayer, window_tokens: int) -> list[ContextPack]:
    """One pack per group of changes; a single pack when the whole PR fits (decision D-008)."""
    base = ContextPack(SHARED_RULES, repo, replace(layer, diffs={}, excerpts=[], notes=[]))
    room = int(window_tokens * (1 - AGENT_SHARE)) - fixed_tokens(base, layer)
    if room < 1:
        # Every unit then gets a group of its own, flagged as larger than the window.
        layer = replace(layer, notes=[*layer.notes, NO_ROOM_NOTE])
        room = 1
    groups = grouped_layers(layer, module_finder(repo), room)
    return [ContextPack(SHARED_RULES, repo, group) for group in groups]
