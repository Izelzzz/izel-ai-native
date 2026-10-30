"""Split a pull request too large for one review into groups of related changes.

A group is only made when the whole PR does not fit (decision D-008). Changes that
must be read together stay together:

- strong ties, never separated: one file is never split; files that use names another
  changed file defines; a test and the code it tests;
- a weaker tie, separated only when a group would not fit otherwise: files in the same
  module.

Each group still sees the PR's full intent and file list, plus the definitions every
other group changes, so a contract changed in one group is visible to the others.
"""

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import replace
from pathlib import PurePosixPath

from review_agents.context.pr_layer import DEFINITION, TEST_PATH, PrLayer, names_in_patch
from review_agents.context.tokens import estimate_tokens

_IDENTIFIER = re.compile(r"[A-Za-z_]\w{2,}")


class _UnionFind:
    def __init__(self, items: list[str]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: str, b: str) -> None:
        self.parent[self.find(a)] = self.find(b)

    def groups(self) -> list[list[str]]:
        found: dict[str, list[str]] = defaultdict(list)
        for item in self.parent:
            found[self.find(item)].append(item)
        return [sorted(members) for members in found.values()]


def _identifiers(patch: str) -> set[str]:
    return set(_IDENTIFIER.findall(patch))


def _definitions(patch: str) -> list[str]:
    """Definition lines a patch adds, removes or changes inside, as `+`/`-`/` ` lines."""
    lines = []
    for line in patch.splitlines():
        if line.startswith(("+++", "---", "@@")) or line[:1] not in "+- ":
            continue
        if DEFINITION.search(line[1:]):
            lines.append(line.rstrip())
    return lines


def _tested_stem(path: str) -> str | None:
    """`test_refund.py`, `refund_test.go` and `refund.spec.ts` all test `refund`."""
    if not TEST_PATH.search(path):
        return None
    stem = PurePosixPath(path).name.split(".")[0]
    return stem.removeprefix("test_").removesuffix("_test")


def core_units(layer: PrLayer) -> list[list[str]]:
    """Files joined by strong ties: shared changed names, and tests with their code."""
    paths = sorted(layer.diffs)
    union = _UnionFind(paths)
    defined = {path: names_in_patch(patch) for path, patch in layer.diffs.items()}
    used = {path: _identifiers(patch) for path, patch in layer.diffs.items()}
    for a in paths:
        for b in paths:
            if a < b and (defined[a] & used[b] or defined[b] & used[a]):
                union.union(a, b)
    sources = {PurePosixPath(p).name.split(".")[0]: p for p in paths if not TEST_PATH.search(p)}
    for path in paths:
        stem = _tested_stem(path)
        if stem in sources:
            union.union(path, sources[stem])
    return union.groups()


def _unit_tokens(layer: PrLayer, unit: list[str]) -> int:
    names = set().union(*(names_in_patch(layer.diffs[p]) for p in unit))
    excerpt_text = "".join(e.text for e in layer.excerpts if e.name in names)
    return sum(estimate_tokens(layer.diffs[p]) for p in unit) + estimate_tokens(excerpt_text)


def group_changes(
    layer: PrLayer, module_of: Callable[[str], str], capacity_tokens: int
) -> list[list[str]]:
    """Partition the changed files into groups that each fit in `capacity_tokens`.

    Returns one group holding every file when the whole PR fits. A strongly tied unit
    larger than the capacity becomes a group of its own rather than being split.
    """
    units = core_units(layer)
    if sum(_unit_tokens(layer, u) for u in units) <= capacity_tokens:
        return [sorted(layer.diffs)] if layer.diffs else []
    by_module: dict[str, list[list[str]]] = defaultdict(list)
    for unit in units:
        by_module[module_of(unit[0])].append(unit)
    # Merge units of one module while they fit, then pack the rest first-fit decreasing.
    merged: list[list[str]] = []
    for module_units in by_module.values():
        current: list[str] = []
        for unit in sorted(module_units, key=lambda u: -_unit_tokens(layer, u)):
            if current and _unit_tokens(layer, current + unit) > capacity_tokens:
                merged.append(current)
                current = []
            current = current + unit
        if current:
            merged.append(current)
    groups: list[list[str]] = []
    for unit in sorted(merged, key=lambda u: -_unit_tokens(layer, u)):
        for group in groups:
            if _unit_tokens(layer, group + unit) <= capacity_tokens:
                group.extend(unit)
                break
        else:
            groups.append(list(unit))
    return [sorted(g) for g in groups]


def grouped_layers(
    layer: PrLayer, module_of: Callable[[str], str], capacity_tokens: int
) -> list[PrLayer]:
    """One PR layer per group; the original layer when the whole PR fits."""
    groups = group_changes(layer, module_of, capacity_tokens)
    if len(groups) <= 1:
        return [layer]
    layers = []
    for index, group in enumerate(groups, start=1):
        members = set(group)
        names = set().union(*(names_in_patch(layer.diffs[p]) for p in group))
        elsewhere = []
        for path in sorted(set(layer.diffs) - members):
            definitions = _definitions(layer.diffs[path])
            if definitions:
                elsewhere.append(f"{path}:\n" + "\n".join(f"  {d}" for d in definitions))
        oversized = _unit_tokens(layer, group) > capacity_tokens
        layers.append(
            replace(
                layer,
                diffs={p: layer.diffs[p] for p in group},
                excerpts=[e for e in layer.excerpts if e.name in names],
                group=(
                    f"Group {index} of {len(groups)}: this group reviews {len(group)} of the"
                    f" {len(layer.diffs)} changed files; the others are reviewed in parallel."
                    + (" This group is larger than one review window." if oversized else "")
                ),
                signatures_elsewhere=elsewhere,
            )
        )
    return layers
