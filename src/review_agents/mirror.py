"""One bare git mirror per reviewed repository, fetched incrementally."""

import base64
import fcntl
import os
import re
import subprocess
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

_REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


class GitError(RuntimeError):
    pass


class MissingCommitError(GitError):
    pass


def check_repo_name(repo: str) -> str:
    if not _REPO_NAME.fullmatch(repo) or ".." in repo.split("/"):
        raise ValueError(f"not an owner/name repository: {repo!r}")
    return repo


def git_env(token: str | None = None, remote_prefix: str = "") -> dict[str, str]:
    """Environment for every git call: no user or system config, no prompts.

    The token goes into an HTTP header through `GIT_CONFIG_*` variables, so it is
    never written to the mirror's config, a remote URL or the process arguments.
    """
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    }
    if token:
        credentials = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env |= {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"http.{remote_prefix}.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {credentials}",
        }
    return env


def run_git(
    git_dir: Path,
    *args: str,
    env: dict[str, str] | None = None,
    secret: str | None = None,
    ok_codes: tuple[int, ...] = (0,),
) -> bytes:
    result = subprocess.run(  # noqa: S603 - fixed git binary, arguments are not shell-parsed
        ["git", f"--git-dir={git_dir}", *args],  # noqa: S607
        capture_output=True,
        env=env or git_env(),
        check=False,
    )
    if result.returncode not in ok_codes:
        message = result.stderr.decode("utf-8", "replace").strip()
        if secret:
            message = message.replace(secret, "***")
        raise GitError(f"git {args[0]} failed: {message}")
    return result.stdout


class MirrorStore:
    """Bare mirrors under `root`, one per repository, reused across reviews."""

    def __init__(self, root: Path, remote_base: str = "https://github.com") -> None:
        self._root = root
        self._remote_base = remote_base.rstrip("/")

    def git_dir(self, repo: str) -> Path:
        owner, name = check_repo_name(repo).split("/")
        return self._root / owner / f"{name}.git"

    def remote_url(self, repo: str) -> str:
        return f"{self._remote_base}/{check_repo_name(repo)}.git"

    @contextmanager
    def _locked(self, repo: str) -> Iterator[Path]:
        # Two reviews of the same repository must not fetch into one mirror at once.
        git_dir = self.git_dir(repo)
        git_dir.parent.mkdir(parents=True, exist_ok=True)
        with open(git_dir.parent / f"{git_dir.name}.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield git_dir
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def sync(
        self, repo: str, refs: Sequence[str], commits: Sequence[str], token: str | None
    ) -> Path:
        """Fetch `refs` into the mirror, creating it on first use; return its git dir.

        Later syncs only transfer objects the mirror does not have yet. Every commit in
        `commits` must be present afterwards.
        """
        for ref in refs:
            if not ref.startswith("refs/") or any(c in ref for c in " :^~?*[\\"):
                raise ValueError(f"not a full ref name: {ref!r}")
        for sha in commits:
            if not _SHA.fullmatch(sha):
                raise ValueError(f"not a full commit sha: {sha!r}")
        url = self.remote_url(repo)
        env = git_env(token, remote_prefix=self._remote_base)
        with self._locked(repo) as git_dir:
            if not (git_dir / "HEAD").exists():
                run_git(git_dir, "init", "--bare", "--quiet")
            refspecs = [f"+{ref}:{ref}" for ref in refs]
            run_git(git_dir, "fetch", "--quiet", "--no-tags", url, *refspecs, env=env, secret=token)
            for sha in commits:
                if not self.has_commit(git_dir, sha):
                    raise MissingCommitError(f"{repo} has no commit {sha} after fetching")
        return git_dir

    @staticmethod
    def has_commit(git_dir: Path, sha: str) -> bool:
        try:
            run_git(git_dir, "cat-file", "-e", f"{sha}^{{commit}}")
        except GitError:
            return False
        return True
