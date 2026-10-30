import threading
from pathlib import Path

import pytest
from gitrepo import Upstream, git

from review_agents.mirror import (
    GitError,
    MirrorStore,
    MissingCommitError,
    check_repo_name,
    git_env,
    run_git,
)

MAIN = ["refs/heads/main"]


@pytest.fixture
def upstream(tmp_path: Path) -> Upstream:
    return Upstream(tmp_path)


@pytest.fixture
def store(tmp_path: Path, upstream: Upstream) -> MirrorStore:
    return MirrorStore(tmp_path / "repos", remote_base=str(upstream.base))


def object_ids(git_dir: Path) -> set[str]:
    listing = git(git_dir, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)")
    return set(listing.split())


def test_first_sync_creates_a_bare_mirror_with_the_requested_commits(
    store: MirrorStore, upstream: Upstream
) -> None:
    head = upstream.commit({"a.py": "x = 1\n"}, "init")

    git_dir = store.sync("octo/app", MAIN, [head], token=None)

    assert git_dir == store.git_dir("octo/app")
    assert git(git_dir, "rev-parse", "--is-bare-repository") == "true"
    assert store.has_commit(git_dir, head)


def test_a_second_sync_only_fetches_the_new_objects(store: MirrorStore, upstream: Upstream) -> None:
    upstream.commit({f"f{i}.py": f"v = {i}\n" for i in range(20)}, "init")
    git_dir = store.sync("octo/app", MAIN, [], token=None)
    before = object_ids(git_dir)
    (git_dir / "marker").write_text("kept", encoding="utf-8")

    # One changed file: one commit, one root tree and one blob.
    head = upstream.commit({"f0.py": "v = 100\n"}, "change one file")
    store.sync("octo/app", MAIN, [head], token=None)

    after = object_ids(git_dir)
    assert (git_dir / "marker").read_text(encoding="utf-8") == "kept"
    assert before < after
    assert len(after - before) == 3
    assert store.has_commit(git_dir, head)


def test_a_pull_request_ref_is_fetched_next_to_the_default_branch(
    store: MirrorStore, upstream: Upstream
) -> None:
    upstream.commit({"a.py": "x = 1\n"}, "init")
    head = upstream.commit({"a.py": "x = 2\n"}, "pr change", branch="pull/7/head")

    git_dir = store.sync("octo/app", [*MAIN, "refs/heads/pull/7/head"], [head], token=None)

    assert store.has_commit(git_dir, head)


def test_a_commit_missing_after_the_fetch_is_an_error(
    store: MirrorStore, upstream: Upstream
) -> None:
    upstream.commit({"a.py": "x = 1\n"}, "init")

    with pytest.raises(MissingCommitError):
        store.sync("octo/app", MAIN, ["0" * 40], token=None)


@pytest.mark.parametrize("repo", ["octo", "octo/app/x", "../app", "octo/..", "octo/a b", "/etc"])
def test_repository_names_must_be_owner_slash_name(repo: str) -> None:
    with pytest.raises(ValueError, match="owner/name"):
        check_repo_name(repo)


@pytest.mark.parametrize("ref", ["main", "refs/heads/main:refs/x", "refs/heads/a b", "HEAD"])
def test_refs_must_be_full_ref_names(store: MirrorStore, ref: str) -> None:
    with pytest.raises(ValueError, match="full ref"):
        store.sync("octo/app", [ref], [], token=None)


def test_commits_must_be_full_shas(store: MirrorStore) -> None:
    with pytest.raises(ValueError, match="full commit sha"):
        store.sync("octo/app", MAIN, ["HEAD"], token=None)


def test_the_token_travels_only_in_the_environment_and_never_reaches_the_mirror(
    store: MirrorStore, upstream: Upstream
) -> None:
    upstream.commit({"a.py": "x = 1\n"}, "init")
    token = "fake-token-value-123"  # secret-scan: allow

    env = git_env(token, remote_prefix="https://github.com")
    git_dir = store.sync("octo/app", MAIN, [], token=token)

    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com.extraheader"
    assert token not in env["GIT_CONFIG_VALUE_0"]  # base64-encoded in the header
    for path in git_dir.rglob("*"):
        if path.is_file():
            assert token.encode() not in path.read_bytes()


def test_git_errors_never_show_the_token(store: MirrorStore, upstream: Upstream) -> None:
    upstream.commit({"a.py": "x = 1\n"}, "init")
    git_dir = store.sync("octo/app", MAIN, [], token=None)
    token = "fake-token-value-123"  # secret-scan: allow

    with pytest.raises(GitError) as raised:
        run_git(git_dir, "rev-parse", token, secret=token)

    assert token not in str(raised.value)
    assert "***" in str(raised.value)


def test_concurrent_syncs_of_one_repository_both_succeed(
    store: MirrorStore, upstream: Upstream
) -> None:
    head = upstream.commit({f"f{i}.py": "x\n" * 200 for i in range(50)}, "init")
    errors: list[BaseException] = []

    def sync() -> None:
        try:
            store.sync("octo/app", MAIN, [head], token=None)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=sync) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
