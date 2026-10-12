"""Offline tests for the evaluation formulas published in the docs (stdlib only, no network).

The doc snippets are extracted and executed, so the pages cannot drift from tested code.
Run: pytest examples/langchain-v1/test_evaluation.py
"""
from math import comb
import sys
import types
from pathlib import Path

import pytest

from check_doc_imports import python_blocks

DOCS = Path(__file__).resolve().parents[2] / "docs"
METRICS = DOCS / "foundations/evaluation-metrics.md"
HARNESS = DOCS / "implementations/evaluation-harness.md"


def _exec_block(path: Path, marker: str) -> dict:
    """Exec the first python fence on a page that contains `marker`; return its namespace."""
    for _, code in python_blocks(path.read_text(encoding="utf-8")):
        if marker in code:
            ns: dict = {"__name__": "__doc_example__"}
            sys.modules["__doc_example__"] = types.SimpleNamespace(__dict__=ns)
            exec(compile(code, f"{path.name}:{marker}", "exec"), ns)
            return ns
    raise AssertionError(f"no python block containing {marker!r} in {path}")


@pytest.fixture(scope="module")
def metrics():
    ns: dict = {}
    for marker in ("def pass_hat_k", "def trajectory_match", "def cost_report"):
        ns.update(_exec_block(METRICS, marker))
    return ns


@pytest.fixture(scope="module")
def harness():
    return _exec_block(HARNESS, "def evaluate_repeated")


def test_pass_hat_k_matches_closed_form(metrics):
    # all runs succeed -> 1; none -> 0; k=1 -> plain success rate
    assert metrics["pass_hat_k"](5, 5, 3) == 1.0
    assert metrics["pass_hat_k"](5, 0, 1) == 0.0
    assert metrics["pass_hat_k"](4, 3, 1) == pytest.approx(0.75)
    assert metrics["pass_hat_k"](4, 3, 2) == pytest.approx(comb(3, 2) / comb(4, 2))


def test_pass_hat_k_is_not_p_to_the_k(metrics):
    # 3/4 successes: naive (c/n)**k says 0.316, the unbiased pass^4 is 0 (never saw 4 straight wins)
    assert (3 / 4) ** 4 == pytest.approx(0.3164, abs=1e-3)
    assert metrics["pass_hat_k"](4, 3, 4) == 0.0


def test_pass_hat_k_converges_to_p_to_the_k_for_large_n(metrics):
    # With many runs the estimator approaches p**k (independent runs, fixed p).
    n, c, p, k = 10_000, 9_000, 0.9, 8
    assert metrics["pass_hat_k"](n, c, k) == pytest.approx(p**k, abs=5e-3)


def test_pass_at_k_vs_pass_hat_k_move_in_opposite_directions(metrics):
    n, c = 10, 6
    at = [metrics["pass_at_k"](n, c, k) for k in range(1, 6)]
    hat = [metrics["pass_hat_k"](n, c, k) for k in range(1, 6)]
    assert at == sorted(at) and hat == sorted(hat, reverse=True)
    assert at[0] == pytest.approx(hat[0])  # both equal the success rate at k=1


@pytest.mark.parametrize("n,c,k", [(3, 4, 1), (3, -1, 1), (3, 1, 0), (3, 1, 4)])
def test_invalid_arguments_rejected(metrics, n, c, k):
    with pytest.raises(ValueError):
        metrics["pass_hat_k"](n, c, k)
    with pytest.raises(ValueError):
        metrics["pass_at_k"](n, c, k)


def test_mean_over_tasks_averages_per_task(metrics):
    runs = {"a": [True, True, True, True], "b": [True, False, False, False]}
    assert metrics["mean_over_tasks"](metrics["pass_hat_k"], runs, 2) == pytest.approx((1.0 + 0.0) / 2)
    with pytest.raises(AssertionError):
        metrics["mean_over_tasks"](metrics["pass_hat_k"], {"a": [True], "b": [True, False]}, 1)


def test_trajectory_modes(metrics):
    tm = metrics["trajectory_match"]
    actual = ["search", "retry", "read", "answer"]
    assert tm(actual, ["search", "read", "answer"], "in_order")
    assert not tm(actual, ["read", "search"], "in_order")
    assert tm(actual, ["read", "search"], "any_order")
    assert not tm(actual, ["search", "read", "answer"], "exact")
    assert tm(["a", "b"], ["a", "b"], "exact")
    with pytest.raises(ValueError):
        tm(actual, [], "bogus")
    p, r = metrics["trajectory_precision_recall"](["a", "x"], ["a", "b"])
    assert (p, r) == (0.5, 0.5)


def test_cost_report_normalizes_by_success(metrics):
    runs = [
        {"success": True, "input_tokens": 1_000_000, "output_tokens": 0},
        {"success": False, "input_tokens": 1_000_000, "output_tokens": 500_000},
    ]
    rep = metrics["cost_report"](runs, input_price_per_mtok=2.0, output_price_per_mtok=4.0)
    assert rep["spend"] == pytest.approx(6.0)  # 2 + (2 + 2): failures still cost money
    assert rep["cost_per_task"] == pytest.approx(3.0)
    assert rep["cost_per_success"] == pytest.approx(6.0)
    assert rep["successes_per_dollar"] == pytest.approx(1 / 6)
    none = metrics["cost_report"]([{"success": False, "input_tokens": 1, "output_tokens": 1}], 1.0, 1.0)
    assert none["cost_per_success"] == float("inf")


def test_harness_step_runs_offline(harness):
    calls = {"i": 0}

    def stub(task):
        calls["i"] += 1
        return harness["Run"](calls["i"] % 4 != 0, ["search", "answer"], 1000, 200)

    rep = harness["evaluate_repeated"](stub, {"q": ["search", "answer"]}, n=4, ks=(1, 4), in_price=1.0, out_price=2.0)
    assert rep["pass^1"] == pytest.approx(0.75)
    assert rep["pass^4"] == 0.0 and rep["pass@4"] == 1.0
    assert rep["trajectory_ok"] == 1.0
    assert rep["cost_per_success"] == pytest.approx((4 * (1000 * 1.0 + 200 * 2.0) / 1e6) / 3)


def test_cost_report_no_wins_and_no_spend(metrics):
    cr = metrics["cost_report"]
    no_wins_no_spend = cr([{"success": False, "input_tokens": 0, "output_tokens": 0}], 1.0, 1.0)
    assert no_wins_no_spend["successes_per_dollar"] == 0.0
    assert no_wins_no_spend["cost_per_success"] == float("inf")
    no_wins_spend = cr([{"success": False, "input_tokens": 10, "output_tokens": 10}], 1.0, 1.0)
    assert no_wins_spend["successes_per_dollar"] == 0.0
    # wins but no cost data: inf is allowed (documented caveat)
    free = cr([{"success": True, "input_tokens": 0, "output_tokens": 0}], 1.0, 1.0)
    assert free["successes_per_dollar"] == float("inf")


def test_cost_report_empty_runs(metrics):
    rep = metrics["cost_report"]([], 1.0, 1.0)
    assert rep["spend"] == 0.0 and rep["cost_per_task"] == 0.0
    assert rep["successes_per_dollar"] == 0.0
    assert rep["cost_per_success"] == float("inf")


def _stub(harness):
    return lambda task: harness["Run"](True, ["a"], 1, 1)


def test_evaluate_repeated_rejects_empty_tasks(harness):
    with pytest.raises(ValueError, match="tasks"):
        harness["evaluate_repeated"](_stub(harness), {}, n=2, ks=(1,), in_price=1.0, out_price=1.0)


@pytest.mark.parametrize("n", [0, -1])
def test_evaluate_repeated_rejects_nonpositive_n(harness, n):
    with pytest.raises(ValueError, match="n must"):
        harness["evaluate_repeated"](_stub(harness), {"q": ["a"]}, n=n, ks=(1,), in_price=1.0, out_price=1.0)


def test_evaluate_repeated_rejects_k_above_n(harness):
    with pytest.raises(ValueError, match="k"):
        harness["evaluate_repeated"](_stub(harness), {"q": ["a"]}, n=2, ks=(1, 3), in_price=1.0, out_price=1.0)


def test_evaluate_repeated_zero_budget_and_no_wins(harness):
    fail = lambda task: harness["Run"](False, [], 0, 0)
    rep = harness["evaluate_repeated"](fail, {"q": ["a"]}, n=2, ks=(1, 2), in_price=0.0, out_price=0.0)
    assert rep["pass^1"] == 0.0 and rep["pass@2"] == 0.0
    assert rep["trajectory_ok"] == 0.0
    assert rep["cost_per_success"] == float("inf")


def test_harness_and_metrics_pages_agree(metrics, harness):
    for n, c, k in [(6, 4, 3), (8, 8, 8), (5, 2, 2)]:
        assert harness["pass_hat_k"](n, c, k) == metrics["pass_hat_k"](n, c, k)
        assert harness["pass_at_k"](n, c, k) == metrics["pass_at_k"](n, c, k)
