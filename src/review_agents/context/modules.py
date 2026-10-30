"""Split a repository into modules and keep a model-written summary of each.

Every module is summarised, with no cap on how many: the review needs the whole
structure to judge module boundaries (decision D-007). A summary is cached by the
content of the module's files (their git blob ids), so only modules whose files
changed are summarised again; a change to a skipped file, such as a lockfile, does
not count.
"""

import hashlib
import json
import logging
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath

from review_agents.context.git import Entry, Snapshot
from review_agents.context.tokens import estimate_tokens, head_tokens
from review_agents.models import BudgetExceededError

log = logging.getLogger(__name__)

MAX_MODULE_FILES = 50
# A directory holding one of these starts its own module, whatever its size.
PACKAGE_MARKERS = frozenset(
    {
        "package.json",
        "pyproject.toml",
        "setup.py",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "composer.json",
        "Gemfile",
        "mix.exs",
        "CMakeLists.txt",
    }
)
_ENTRY_NAMES = (
    "__init__.py",
    "__main__.py",
    "main.py",
    "index.js",
    "index.ts",
    "main.go",
    "lib.rs",
    "main.rs",
    "mod.rs",
)
_SAMPLE_TOKENS = 6_000
_LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
    ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".c": "C", ".h": "C", ".cc": "C++",
    ".cpp": "C++", ".hpp": "C++", ".swift": "Swift", ".scala": "Scala", ".ex": "Elixir",
    ".sh": "Shell", ".sql": "SQL",
}  # fmt: skip

SUMMARY_VERSION = "1"


@dataclass(frozen=True)
class Module:
    path: str  # "" for files at the repository root
    files: tuple[Entry, ...]

    @property
    def language(self) -> str:
        counts = Counter(_LANGUAGES.get(PurePosixPath(f.path).suffix, "") for f in self.files)
        counts.pop("", None)
        return counts.most_common(1)[0][0] if counts else "-"

    @property
    def entry(self) -> str | None:
        here = PurePosixPath(self.path or ".")
        own = {
            PurePosixPath(f.path).name: f.path
            for f in self.files
            if PurePosixPath(f.path).parent == here
        }
        return next((own[name] for name in _ENTRY_NAMES if name in own), None)

    def stats(self) -> str:
        entry = f" · entry {self.entry}" if self.entry else ""
        return f"{self.path or '.'}/ · {len(self.files)} files · {self.language}{entry}"


def split_modules(files: Iterable[Entry]) -> list[Module]:
    """Directories become modules once their subtree has at most MAX_MODULE_FILES files.

    Larger directories are split into their subdirectories; files directly inside a
    split directory form a module of their own. A package marker always starts a module.
    """
    by_dir: dict[str, list[Entry]] = defaultdict(list)
    children: dict[str, set[str]] = defaultdict(set)
    for entry in files:
        parent = str(PurePosixPath(entry.path).parent)
        parent = "" if parent == "." else parent
        by_dir[parent].append(entry)
        parts = PurePosixPath(parent).parts
        for depth in range(len(parts)):
            above = "/".join(parts[:depth])
            children[above].add("/".join(parts[: depth + 1]))

    def subtree(path: str) -> list[Entry]:
        found = list(by_dir.get(path, []))
        for child in sorted(children.get(path, ())):
            found.extend(subtree(child))
        return found

    def has_marker(path: str) -> bool:
        return any(PurePosixPath(f.path).name in PACKAGE_MARKERS for f in by_dir.get(path, []))

    def marked_below(path: str) -> bool:
        return any(has_marker(c) or marked_below(c) for c in children.get(path, ()))

    modules: list[Module] = []

    def visit(path: str, is_root: bool) -> None:
        all_files = subtree(path)
        if not is_root and len(all_files) <= MAX_MODULE_FILES and not marked_below(path):
            modules.append(Module(path, tuple(all_files)))
            return
        own = by_dir.get(path, [])
        if own:
            modules.append(Module(path, tuple(own)))
        for child in sorted(children.get(path, ())):
            visit(child, is_root=False)

    visit("", is_root=True)
    return sorted(modules, key=lambda m: m.path)


@dataclass(frozen=True)
class ModuleSummary:
    path: str
    stats: str
    summary: str | None  # None until a summary exists; the stats stand in for it

    def render(self) -> str:
        if self.summary is None:
            return f"- {self.stats}"
        return f"- {self.stats}\n  {self.summary}"


Summarize = Callable[[str, str], str]
"""Takes a module's path and its sampled source; returns a 3-5 sentence summary."""


def sample_module(snapshot: Snapshot, module: Module) -> str:
    """What the model reads for a summary: the file list, then the entry and largest files."""
    listing = "\n".join(f.path for f in module.files)
    parts = [f"Files:\n{listing}"]
    used = estimate_tokens(parts[0])
    ordered = sorted(module.files, key=lambda f: (f.path != module.entry, -f.size))
    for entry in ordered:
        text = snapshot.read_text(entry.path)
        if not text:
            continue
        remaining = _SAMPLE_TOKENS - used
        if remaining <= 200:
            break
        excerpt = head_tokens(text, remaining)
        parts.append(f"--- {entry.path} ---\n{excerpt}")
        used += estimate_tokens(excerpt)
    return "\n\n".join(parts)


def _cache_key(module: Module) -> str:
    content = hashlib.sha256("\n".join(f"{f.path}={f.blob}" for f in module.files).encode())
    return f"module:{SUMMARY_VERSION}:{module.path or '.'}:{content.hexdigest()}"


def module_summaries(
    conn: sqlite3.Connection,
    repo: str,
    snapshot: Snapshot,
    summarize: Summarize | None,
) -> list[ModuleSummary]:
    """Summaries for every module, generating the missing ones when `summarize` is given.

    A failed summary falls back to the module's git stats and does not stop the others.
    """
    results = []
    for module in split_modules(snapshot.files()):
        key = _cache_key(module)
        row = conn.execute(
            "SELECT content FROM context_cache WHERE repo = ? AND layer = 'repo' AND cache_key = ?",
            (repo, key),
        ).fetchone()
        summary: str | None = json.loads(row["content"])["summary"] if row else None
        if summary is None and summarize is not None:
            try:
                summary = summarize(module.path or ".", sample_module(snapshot, module)).strip()
            except BudgetExceededError:
                log.warning(
                    "summary budget used up; %s and later modules keep their stats",
                    module.path or ".",
                )
                summarize = None
            except Exception:
                log.exception("summarising module %s of %s failed", module.path or ".", repo)
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO context_cache (repo, layer, cache_key, content, tokens)"
                    " VALUES (?, 'repo', ?, ?, ?)",
                    (repo, key, json.dumps({"summary": summary}), estimate_tokens(summary)),
                )
        results.append(ModuleSummary(module.path, module.stats(), summary))
    return results


def to_json(summaries: list[ModuleSummary]) -> list[dict[str, str | None]]:
    return [asdict(s) for s in summaries]
