from review_agents.context.grouping import group_changes, grouped_layers
from review_agents.context.pr_layer import ChangedFile, Excerpt, PrLayer, PrRequest
from review_agents.context.tokens import estimate_tokens

SHA = "a" * 40


def patch(path: str, body: str, size: int = 0) -> str:
    filler = "".join(f"+    pad_{i} = {i}\n" for i in range(size))
    return (
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1,3 +1,4 @@\n{body}{filler}"
    )


def layer(diffs: dict[str, str], excerpts: list[Excerpt] | None = None) -> PrLayer:
    return PrLayer(
        request=PrRequest("octo/shop", 7, "Split orders", "Move orders out.", SHA, SHA),
        issues=[],
        specs=[],
        files=[ChangedFile("M", path) for path in diffs],
        diffs=diffs,
        excerpts=excerpts or [],
        previous_findings=[],
    )


def room_for(units: float, diffs: dict[str, str]) -> int:
    """A capacity that holds `units` of the largest patch."""
    return int(units * max(estimate_tokens(p) for p in diffs.values()))


def module_of(path: str) -> str:
    return path.split("/")[0]


def where(groups: list[list[str]]) -> dict[str, int]:
    return {path: i for i, group in enumerate(groups) for path in group}


def test_a_pr_that_fits_is_reviewed_as_one_group() -> None:
    pr = layer(
        {"a/x.py": patch("a/x.py", "+def alpha():\n"), "b/y.py": patch("b/y.py", "+x = 1\n")}
    )

    assert grouped_layers(pr, module_of, capacity_tokens=100_000) == [pr]


def test_independent_changes_are_packed_into_groups_that_fit() -> None:
    diffs = {p: patch(p, f"+def f_{p[0]}():\n", size=40) for p in ("a/x.py", "b/y.py", "c/z.py")}

    groups = group_changes(layer(diffs), module_of, capacity_tokens=room_for(2.5, diffs))

    assert len(groups) == 2
    assert sorted(p for g in groups for p in g) == sorted(diffs)


def sized(path: str, body: str, tokens: int) -> str:
    """A patch of about `tokens` tokens, so tests can control how files pack."""
    lines = body
    while estimate_tokens(patch(path, lines)) < tokens:
        lines += "+    pad = 0\n"
    return patch(path, lines)


def test_a_caller_stays_with_the_code_it_calls_across_modules() -> None:
    # Packed by size alone, refund (100) and notes (90) would not fit together, so
    # orders (70) would join notes; the reference to `refund` must keep it with refund.
    diffs = {
        "payments/refund.py": sized("payments/refund.py", "+def refund(order):\n", 100),
        "docs/notes.py": sized("docs/notes.py", "+def unrelated_thing():\n", 90),
        "api/orders.py": sized("api/orders.py", "+    return refund(order)\n", 70),
    }

    found = where(group_changes(layer(diffs), module_of, capacity_tokens=165))

    assert found["payments/refund.py"] == found["api/orders.py"]
    assert found["docs/notes.py"] != found["api/orders.py"]


def test_a_test_stays_with_the_code_it_tests() -> None:
    diffs = {
        "payments/refund.py": sized("payments/refund.py", "+x = 1\n", 100),
        "docs/notes.py": sized("docs/notes.py", "+z = 3\n", 90),
        "tests/test_refund.py": sized("tests/test_refund.py", "+y = 2\n", 70),
    }

    found = where(group_changes(layer(diffs), module_of, capacity_tokens=165))

    assert found["payments/refund.py"] == found["tests/test_refund.py"]


def test_a_file_larger_than_a_group_is_never_split() -> None:
    diffs = {
        "big/huge.py": patch("big/huge.py", "+def huge():\n", size=400),
        "a/x.py": patch("a/x.py", "+def alpha():\n"),
    }

    layers = grouped_layers(layer(diffs), module_of, capacity_tokens=500)

    huge = next(g for g in layers if "big/huge.py" in g.diffs)
    assert huge.diffs["big/huge.py"] == diffs["big/huge.py"]
    assert "larger than one review window" in (huge.group or "")


def test_small_changes_in_one_module_are_reviewed_together() -> None:
    # By size alone two of the four orders files would join the big file's group.
    diffs = {f"orders/m{i}.py": sized(f"orders/m{i}.py", f"+v{i} = {i}\n", 40) for i in range(4)}
    diffs["other/big.py"] = sized("other/big.py", "+w = 1\n", 200)

    found = where(group_changes(layer(diffs), module_of, capacity_tokens=290))

    assert len({found[f"orders/m{i}.py"] for i in range(4)}) == 1


def test_each_group_sees_the_whole_pr_and_what_other_groups_change() -> None:
    diffs = {
        "orders/service.py": patch(
            "orders/service.py", "-def cancel(self):\n+def cancel(self, reason):\n", size=40
        ),
        "notify/events.py": patch("notify/events.py", "+def on_paid():\n", size=40),
    }
    excerpts = [Excerpt("usage", "cancel", "api/orders.py", "1: service.cancel()")]

    layers = grouped_layers(layer(diffs, excerpts), module_of, capacity_tokens=room_for(1.5, diffs))

    assert len(layers) == 2
    notify = next(g for g in layers if "notify/events.py" in g.diffs)
    rendered = notify.render()
    assert "M orders/service.py" in rendered  # full file list
    assert "Move orders out." in rendered  # full intent
    assert "+def cancel(self, reason):" in rendered  # the contract another group changes
    assert notify.excerpts == []  # excerpts follow the group whose names they are about
    assert "Group " in rendered
