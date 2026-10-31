import threading
import time
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest
from gitrepo import Upstream

from review_agents.context.cache import prune, repo_layer_for_review
from review_agents.db import connect, migrate
from review_agents.mirror import MirrorStore


class Setup:
    def __init__(self, tmp_path: Path) -> None:
        self.upstream = Upstream(tmp_path, "octo/shop")
        self.upstream.commit({"README.md": "# Shop\n", "payments/refund.py": "x = 1\n"}, "init")
        self.store = MirrorStore(tmp_path / "repos", remote_base=str(self.upstream.base))
        self.db_path = tmp_path / "db.sqlite3"
        with closing(connect(self.db_path)) as conn:
            migrate(conn)
        self.sync()

    def sync(self) -> Path:
        return self.store.sync("octo/shop", ["refs/heads/main"], [], token=None)

    def review(self) -> int:
        with closing(connect(self.db_path)) as conn:
            row = conn.execute(
                "INSERT INTO reviews (repo, pr, base_sha, head_sha, mode)"
                " VALUES ('octo/shop', 1, 'a', 'b', 'standard') RETURNING id"
            ).fetchone()
        return int(row["id"])

    def build(self, review_id: int, summarize=None):  # type: ignore[no-untyped-def]
        with closing(connect(self.db_path)) as conn:
            return repo_layer_for_review(
                conn,
                review_id,
                "octo/shop",
                self.store.git_dir("octo/shop"),
                "main",
                [],
                summarize=summarize,
            )

    def steps(self, review_id: int) -> list[str]:
        with closing(connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT node, status FROM steps WHERE review_id = ? ORDER BY id", (review_id,)
            ).fetchall()
        return [f"{row['node']}:{row['status']}" for row in rows]


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    return Setup(tmp_path)


def test_a_second_review_of_the_repository_records_the_cache_hit(setup: Setup) -> None:
    first, second = setup.review(), setup.review()

    setup.build(first)
    setup.build(second)

    assert setup.steps(first) == ["context.repo_layer:ok"]
    assert setup.steps(second) == ["context.repo_layer.cache_hit:ok"]


def test_concurrent_reviews_of_one_repository_build_its_layer_once(setup: Setup) -> None:
    calls: list[str] = []
    lock = threading.Lock()

    def slow_summary(path: str, source: str) -> str:
        with lock:
            calls.append(path)
        time.sleep(0.2)
        return "summary"

    reviews = [setup.review() for _ in range(3)]
    threads = [threading.Thread(target=setup.build, args=(r, slow_summary)) for r in reviews]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(calls) == [".", "payments"]  # each module summarised once, not per review
    hits = [step for r in reviews for step in setup.steps(r)]
    assert sorted(hits).count("context.repo_layer:ok") == 1


def test_pruning_keeps_the_latest_layers_and_only_current_module_summaries(setup: Setup) -> None:
    for i in range(5):
        setup.upstream.commit({"README.md": f"# Shop {i}\n"}, f"edit {i}")
        setup.sync()
        setup.build(setup.review(), summarize=lambda path, source: "summary")
    with closing(connect(setup.db_path)) as conn:
        conn.execute(
            "INSERT INTO context_cache (repo, layer, cache_key, content, tokens)"
            " VALUES ('octo/shop', 'repo', 'module:1:old:abc', '{}', 1)"
        )
        conn.execute(
            "INSERT INTO context_cache (repo, layer, cache_key, content, tokens)"
            " VALUES ('octo/other', 'repo', 'layer:keep-me', '{}', 1)"
        )
        layer = setup.build(setup.review())

        prune(conn, "octo/shop", layer, keep_layers=2)

        keys = [
            (row["repo"], row["cache_key"].split(":")[0])
            for row in conn.execute("SELECT repo, cache_key FROM context_cache")
        ]
    assert keys.count(("octo/shop", "layer")) == 2
    assert keys.count(("octo/shop", "module")) == 2  # "." and "payments" at the current commit
    assert ("octo/other", "layer") in keys


def test_pruning_spares_module_summaries_when_a_key_is_unknown(setup: Setup) -> None:
    layer = setup.build(setup.review(), summarize=lambda path, source: "summary")
    unknown = replace(layer, modules=[replace(m, cache_key="") for m in layer.modules])

    with closing(connect(setup.db_path)) as conn:
        prune(conn, "octo/shop", unknown)
        rows = conn.execute("SELECT cache_key FROM context_cache WHERE cache_key LIKE 'module:%'")
        assert len(rows.fetchall()) == 2
