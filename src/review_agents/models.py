"""Model access: OpenAI-compatible chat models, usage records and the token budget."""

import threading
import time
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from review_agents.config import ModelEndpoint
from review_agents.db import connect

REQUEST_TIMEOUT_SECONDS = 120.0
CONNECT_TIMEOUT_SECONDS = 10.0
# The client retries timeouts, connection errors, 408, 409, 429 and 5xx with
# exponential backoff and honours Retry-After; 400, 401 and 403 fail at once.
MAX_RETRIES = 2
# Local model servers ignore the key, but the client refuses to start without one.
_NO_KEY = "not-needed"


class BudgetExceededError(RuntimeError):
    """The review has used its token budget; no further model call is made."""


def chat_model(
    endpoint: ModelEndpoint,
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
    max_retries: int = MAX_RETRIES,
) -> ChatOpenAI:
    """A chat model for any OpenAI-compatible service: OpenRouter, Anthropic, Ollama, ..."""
    api_key = endpoint.api_key or SecretStr(_NO_KEY)
    return ChatOpenAI(
        base_url=str(endpoint.base_url),
        api_key=api_key,
        model=endpoint.model,
        timeout=httpx.Timeout(timeout, connect=min(CONNECT_TIMEOUT_SECONDS, timeout)),
        max_retries=max_retries,
    )


class TokenBudget:
    """Input plus output tokens one review may use. Shared by all of its agents."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._used = 0
        self._lock = threading.Lock()

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit

    def charge(self, tokens: int) -> None:
        with self._lock:
            self._used += tokens


RecordUsage = Callable[[str, int, int, int], None]
"""Stores one call's usage: model, input tokens, output tokens, duration in ms."""


def review_usage(db_path: Path, review_id: int, agent: str) -> RecordUsage:
    """Records into `usage`, the per-review table."""

    def record(model: str, input_tokens: int, output_tokens: int, duration_ms: int) -> None:
        # Callbacks run on the model call's thread, so each record opens its own connection.
        with closing(connect(db_path, create=False)) as conn:
            conn.execute(
                "INSERT INTO usage (review_id, agent, model, input_tokens, output_tokens,"
                " duration_ms) VALUES (?, ?, ?, ?, ?, ?)",
                (review_id, agent, model, input_tokens, output_tokens, duration_ms),
            )

    return record


def summary_usage(db_path: Path, repo: str) -> RecordUsage:
    """Records into `summary_usage`, for module summaries that belong to no single review."""

    def record(model: str, input_tokens: int, output_tokens: int, duration_ms: int) -> None:
        with closing(connect(db_path, create=False)) as conn:
            conn.execute(
                "INSERT INTO summary_usage (repo, model, input_tokens, output_tokens, duration_ms)"
                " VALUES (?, ?, ?, ?, ?)",
                (repo, model, input_tokens, output_tokens, duration_ms),
            )

    return record


class UsageMeter(BaseCallbackHandler):
    """Refuses model calls once the budget is spent and records every call's usage.

    The budget is checked before each call, so a review overshoots it by at most the
    calls already in flight when it ran out.
    """

    # Exceptions raised here must reach the caller, not be logged and swallowed.
    raise_error = True

    def __init__(
        self,
        budget: TokenBudget,
        record: RecordUsage,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._budget = budget
        self._record = record
        self._clock = clock
        self._started: dict[UUID, float] = {}

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        if self._budget.exhausted:
            raise BudgetExceededError(
                f"token budget of {self._budget.limit} used up ({self._budget.used} tokens)"
            )
        self._started[run_id] = self._clock()

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        started = self._started.pop(run_id, self._clock())
        duration_ms = int((self._clock() - started) * 1000)
        input_tokens = output_tokens = 0
        for generations in response.generations:
            for generation in generations:
                usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
                if usage:
                    input_tokens += usage["input_tokens"]
                    output_tokens += usage["output_tokens"]
        model = (response.llm_output or {}).get("model_name", "")
        # Charged before the record is written: if writing fails, the budget still holds.
        self._budget.charge(input_tokens + output_tokens)
        self._record(model, input_tokens, output_tokens, duration_ms)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._started.pop(run_id, None)
