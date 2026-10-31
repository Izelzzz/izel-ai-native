"""The repository layer as a review gets it: built once per repository, recorded, pruned.

Reviews of one repository can run side by side (decision D-011). A per-repository lock
lets the first build the layer and its summaries while the others wait, then read them
from the cache instead of building them again.
"""

import json
import sqlite3
import threading
from collections import defaultdict
from pathlib import Path

from review_agents.context.modules import Summarize
from review_agents.context.repo_layer import RepoLayer, build_repo_layer

_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()
KEEP_LAYERS = 3


def repo_lock(repo: str) -> threading.Lock:
    with _locks_guard:
        return _locks[repo]


def _now(conn: sqlite3.Connection) -> str:
    return str(conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')").fetchone()[0])


def repo_layer_for_review(
    conn: sqlite3.Connection,
    review_id: int,
    repo: str,
    git_dir: Path,
    default_branch: str,
    skip_paths: list[str],
    summarize: Summarize | None = None,
    memories: list[str] | None = None,
    memory_version: str = "",
) -> RepoLayer:
    """The repository layer, built under the repository's lock and recorded in `steps`.

    The step is `context.repo_layer.cache_hit` when the layer came from the cache, so a
    review's steps show whether it reused another review's work.
    """
    started = _now(conn)
    try:
        with repo_lock(repo):
            layer = build_repo_layer(
                conn,
                repo,
                git_dir,
                default_branch,
                skip_paths,
                summarize,
                memories,
                memory_version,
            )
            prune(conn, repo, layer)
    except Exception as exc:
        _step(conn, review_id, "context.repo_layer", started, f"{type(exc).__name__}: {exc}")
        raise
    node = "context.repo_layer.cache_hit" if layer.cache_hit else "context.repo_layer"
    _step(conn, review_id, node, started, None)
    return layer


def _step(
    conn: sqlite3.Connection, review_id: int, node: str, started: str, error: str | None
) -> None:
    conn.execute(
        "INSERT INTO steps (review_id, node, started_at, finished_at, status, error)"
        " VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?, ?)",
        (review_id, node, started, "error" if error else "ok", error),
    )


def prune(
    conn: sqlite3.Connection, repo: str, current: RepoLayer, keep_layers: int = KEEP_LAYERS
) -> None:
    """Drop what no review of `repo` will read again.

    The newest `keep_layers` layers stay, so a review that started on the previous tip of
    the default branch still finds its layer. Module summaries stay only for the modules
    of the current tip; a module that changes again is summarised again either way.
    """
    conn.execute(
        "DELETE FROM context_cache WHERE repo = ? AND layer = 'repo' AND cache_key LIKE 'layer:%'"
        " AND cache_key NOT IN (SELECT cache_key FROM context_cache WHERE repo = ?"
        "   AND layer = 'repo' AND cache_key LIKE 'layer:%'"
        "   ORDER BY created_at DESC, rowid DESC LIMIT ?)",
        (repo, repo, keep_layers),
    )
    keep = [m.cache_key for m in current.modules]
    if not all(keep):  # a summary that does not know its key cannot protect its row
        return
    conn.execute(
        "DELETE FROM context_cache WHERE repo = ? AND layer = 'repo' AND cache_key LIKE 'module:%'"
        " AND cache_key NOT IN (SELECT value FROM json_each(?))",
        (repo, json.dumps(keep)),
    )
