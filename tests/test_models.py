import contextlib
import json
import threading
import time
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import openai
import pytest
from pydantic import SecretStr

from review_agents.config import ModelEndpoint
from review_agents.db import connect, migrate
from review_agents.models import (
    BudgetExceededError,
    TokenBudget,
    UsageMeter,
    chat_model,
    review_usage,
)


@dataclass
class FakeService:
    """A minimal OpenAI-compatible /chat/completions endpoint."""

    url: str = ""
    # One entry per request: (status, delay seconds); the last entry repeats.
    script: list[tuple[int, float]] = field(default_factory=lambda: [(200, 0.0)])
    requests: list[dict[str, str]] = field(default_factory=list)
    # Sent with error responses; the default keeps retries in tests fast.
    retry_headers: dict[str, str] = field(default_factory=lambda: {"retry-after-ms": "1"})


def completion(model: str) -> bytes:
    return json.dumps(
        {
            "id": "c1",
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "no findings"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        }
    ).encode()


@pytest.fixture
def service() -> Iterator[FakeService]:
    fake = FakeService()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            fake.requests.append({"path": self.path, "auth": self.headers.get("Authorization", "")})
            status, delay = fake.script[min(len(fake.requests), len(fake.script)) - 1]
            time.sleep(delay)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if status != 200:
                for name, value in fake.retry_headers.items():
                    self.send_header(name, value)
            self.end_headers()
            with contextlib.suppress(BrokenPipeError):  # the client gave up after its timeout
                self.wfile.write(completion(body["model"]) if status == 200 else b'{"error": {}}')

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    fake.url = f"http://127.0.0.1:{server.server_port}/v1"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield fake
    server.shutdown()


@pytest.fixture
def db(tmp_path: Path) -> tuple[Path, int]:
    path = tmp_path / "db.sqlite3"
    with closing(connect(path)) as conn:
        migrate(conn)
        review_id = conn.execute(
            "INSERT INTO reviews (repo, pr, base_sha, head_sha, mode)"
            " VALUES ('o/r', 1, 'a', 'b', 'standard') RETURNING id"
        ).fetchone()["id"]
    return path, int(review_id)


def endpoint(service: FakeService, key: str | None = "sk-test") -> ModelEndpoint:
    return ModelEndpoint.model_validate(
        {"base_url": service.url, "model": "finder-model", "api_key": key and SecretStr(key)}
    )


def usage_rows(db_path: Path) -> list[tuple[str, str, int, int]]:
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT agent, model, input_tokens, output_tokens FROM usage ORDER BY id"
        ).fetchall()
    return [tuple(row) for row in rows]


@pytest.mark.parametrize(
    ("key", "auth"), [("sk-test", "Bearer sk-test"), (None, "Bearer not-needed")]
)
def test_a_call_reaches_the_service_and_records_its_usage(
    service: FakeService, db: tuple[Path, int], key: str | None, auth: str
) -> None:
    budget = TokenBudget(500_000)
    meter = UsageMeter(budget, review_usage(db[0], db[1], "security"))

    reply = chat_model(endpoint(service, key)).invoke("review", config={"callbacks": [meter]})

    assert reply.content == "no findings"
    assert service.requests == [{"path": "/v1/chat/completions", "auth": auth}]
    assert usage_rows(db[0]) == [("security", "finder-model", 11, 7)]
    assert budget.used == 18


def test_no_call_is_made_once_the_budget_is_used_up(
    service: FakeService, db: tuple[Path, int]
) -> None:
    budget = TokenBudget(20)
    meter = UsageMeter(budget, review_usage(db[0], db[1], "security"))
    model = chat_model(endpoint(service))

    model.invoke("first", config={"callbacks": [meter]})
    model.invoke("second", config={"callbacks": [meter]})  # 18 < 20: still allowed
    with pytest.raises(BudgetExceededError, match="token budget of 20"):
        model.invoke("third", config={"callbacks": [meter]})

    assert len(service.requests) == 2
    assert budget.used == 36


def test_agents_of_one_review_share_its_budget(service: FakeService, db: tuple[Path, int]) -> None:
    budget = TokenBudget(18)
    model = chat_model(endpoint(service))

    model.invoke(
        "a", config={"callbacks": [UsageMeter(budget, review_usage(db[0], db[1], "security"))]}
    )
    with pytest.raises(BudgetExceededError):
        model.invoke(
            "b",
            config={"callbacks": [UsageMeter(budget, review_usage(db[0], db[1], "edge_cases"))]},
        )

    assert [row[0] for row in usage_rows(db[0])] == ["security"]


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_errors_are_retried(
    service: FakeService, db: tuple[Path, int], status: int
) -> None:
    service.script = [(status, 0.0), (status, 0.0), (200, 0.0)]
    meter = UsageMeter(TokenBudget(500_000), review_usage(db[0], db[1], "security"))

    chat_model(endpoint(service)).invoke("review", config={"callbacks": [meter]})

    assert len(service.requests) == 3
    assert len(usage_rows(db[0])) == 1


@pytest.mark.parametrize("status", [400, 401, 403])
def test_request_and_permission_errors_are_not_retried(
    service: FakeService, db: tuple[Path, int], status: int
) -> None:
    service.script = [(status, 0.0)]
    meter = UsageMeter(TokenBudget(500_000), review_usage(db[0], db[1], "security"))

    with pytest.raises(openai.APIStatusError):
        chat_model(endpoint(service)).invoke("review", config={"callbacks": [meter]})

    assert len(service.requests) == 1
    assert usage_rows(db[0]) == []


def test_a_slow_service_times_out_after_the_retries(
    service: FakeService, db: tuple[Path, int]
) -> None:
    service.script = [(200, 2.0)]
    meter = UsageMeter(TokenBudget(500_000), review_usage(db[0], db[1], "security"))

    started = time.monotonic()
    with pytest.raises(openai.APITimeoutError):
        chat_model(endpoint(service), timeout=0.3).invoke("review", config={"callbacks": [meter]})

    assert len(service.requests) == 3
    assert time.monotonic() - started < 10


def test_the_client_waits_as_long_as_retry_after_asks(
    service: FakeService, db: tuple[Path, int]
) -> None:
    # The client's own backoff for two retries stays under about 1.5 seconds.
    service.script = [(429, 0.0), (429, 0.0), (200, 0.0)]
    service.retry_headers = {"Retry-After": "2"}
    meter = UsageMeter(TokenBudget(500_000), review_usage(db[0], db[1], "security"))

    started = time.monotonic()
    chat_model(endpoint(service)).invoke("review", config={"callbacks": [meter]})

    assert len(service.requests) == 3
    assert time.monotonic() - started >= 3.5
