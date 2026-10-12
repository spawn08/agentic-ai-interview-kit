"""Offline regression tests for pricing, routing and cost code published in the docs.

The doc snippets themselves are extracted and executed (no network, no API keys, no real
third-party SDKs: unavailable or heavy modules are stubbed), so the pages cannot drift from
tested code. Covers: llm-gateway config (pricing validation, provider-map merge, lazy embedding
model), tool-calling-agent cost tracking, the evaluation harness, design-principles router
fields, hallucination-mitigation lazy constructors, and a scan for hardcoded tariffs.

Run: pytest examples/langchain-v1/test_pricing.py
"""
import ast
import importlib
import json
import math
import re
import sys
import types
from pathlib import Path

import pytest

from check_doc_imports import python_blocks

DOCS = Path(__file__).resolve().parents[2] / "docs"
GATEWAY = DOCS / "projects/llm-gateway.md"

ROLE_ENV = {
    "AGENT_MODEL": "std-model",
    "AGENT_MODEL_FAST": "fast-model",
    "AGENT_MODEL_REASONING": "reason-model",
    "AGENT_MODEL_ALT": "alt-model",
    "AGENT_MODEL_ALT_FAST": "alt-fast-model",
}
PRICING_OK = {
    "openai": {"in_per_1m": 1.5, "out_per_1m": 6},
    "anthropic": {"in_per_1m": "2.5", "out_per_1m": 12},
    "azure_openai": {"in_per_1m": 1.5, "out_per_1m": 6},
}
PLACEHOLDER = "<from vendor pricing page>"


def _block(path: Path, marker: str) -> str:
    for _, code in python_blocks(path.read_text(encoding="utf-8")):
        if marker in code:
            return code
    raise AssertionError(f"no python block containing {marker!r} in {path}")


def _stub_modules(monkeypatch, names):
    """Replace modules with MagicMock-free stubs when not importable (or when heavy)."""
    for name in names:
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            mod = ".".join(parts[:i])
            stub = types.ModuleType(mod)
            stub.__getattr__ = lambda attr: type(attr, (), {})  # any `from x import Y` works
            monkeypatch.setitem(sys.modules, mod, stub)


@pytest.fixture
def gateway_ns(monkeypatch, tmp_path):
    """Factory: exec the gateway Step 1 block with a given env and pricing file content."""
    code = _block(GATEWAY, "def load_pricing")
    for third_party in ("httpx", "numpy", "redis.asyncio", "tiktoken", "opentelemetry.trace"):
        try:
            importlib.import_module(third_party)
        except ImportError:
            _stub_modules(monkeypatch, [third_party])
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *a, **k: False  # never read a developer's real .env
    monkeypatch.setitem(sys.modules, "dotenv", dotenv)
    _stub_modules(monkeypatch, ["opentelemetry.trace"])
    sys.modules["opentelemetry.trace"].StatusCode = type("StatusCode", (), {})

    def build(pricing=PRICING_OK, env=None, pricing_text=None, set_pricing_env=True):
        for key in list(ROLE_ENV) + ["GATEWAY_PRICING_FILE", "AGENT_EMBEDDING_MODEL"]:
            monkeypatch.delenv(key, raising=False)
        for key, value in {**ROLE_ENV, **(env or {})}.items():
            monkeypatch.setenv(key, value)
        pricing_file = tmp_path / "pricing.json"
        pricing_file.write_text(
            pricing_text if pricing_text is not None else json.dumps(pricing), encoding="utf-8"
        )
        if set_pricing_env:
            monkeypatch.setenv("GATEWAY_PRICING_FILE", str(pricing_file))
        ns: dict = {"__name__": "__doc_example__"}
        exec(compile(code, "llm-gateway.md:step1", "exec"), ns)
        return ns

    return build


# --- pricing validation ---------------------------------------------------------------


def test_valid_pricing_reaches_provider_configs(gateway_ns):
    ns = gateway_ns()
    assert ns["PRICING"]["anthropic"] == {"in_per_1m": 2.5, "out_per_1m": 12.0}
    cfg = ns["PROVIDER_CONFIGS"]
    assert cfg["openai"].price_in_per_1m == 1.5 and cfg["openai"].price_out_per_1m == 6.0
    assert cfg["anthropic"].price_in_per_1m == 2.5


def test_zero_is_a_valid_explicit_rate_but_never_a_fallback(gateway_ns):
    zero = {k: {"in_per_1m": 0, "out_per_1m": 0} for k in PRICING_OK}
    assert gateway_ns(zero)["PRICING"]["openai"] == {"in_per_1m": 0.0, "out_per_1m": 0.0}
    missing_key = {**PRICING_OK, "openai": {"in_per_1m": 1}}
    with pytest.raises(SystemExit, match=r"openai\.out_per_1m"):
        gateway_ns(missing_key)


def test_documented_placeholders_exit_with_clear_message_not_valueerror(gateway_ns):
    placeholders = {k: {"in_per_1m": PLACEHOLDER, "out_per_1m": PLACEHOLDER} for k in PRICING_OK}
    with pytest.raises(SystemExit) as exc:
        gateway_ns(placeholders)
    message = str(exc.value)
    assert "not numeric" in message and "pricing page" in message


@pytest.mark.parametrize(
    "bad",
    [-1, "-0.5", float("nan"), float("inf"), "nan", "inf", True, None, [], {}, ""],
    ids=repr,
)
def test_invalid_rates_rejected(gateway_ns, bad):
    pricing = {**PRICING_OK, "openai": {"in_per_1m": bad, "out_per_1m": 1}}
    # json.dumps writes NaN/Infinity tokens, which Python's json reads back as floats.
    with pytest.raises(SystemExit, match=r"openai\.in_per_1m"):
        gateway_ns(pricing)


def test_missing_provider_entry_rejected(gateway_ns):
    pricing = {k: v for k, v in PRICING_OK.items() if k != "azure_openai"}
    with pytest.raises(SystemExit, match="azure_openai"):
        gateway_ns(pricing)


@pytest.mark.parametrize("text", ["{not json", "[]", '"x"', "null"])
def test_malformed_pricing_file_rejected(gateway_ns, text):
    with pytest.raises(SystemExit):
        gateway_ns(pricing_text=text)


def test_missing_file_and_unset_env_rejected(gateway_ns, tmp_path):
    with pytest.raises(SystemExit, match="GATEWAY_PRICING_FILE is not set"):
        gateway_ns(set_pricing_env=False)
    ns_code = _block(GATEWAY, "def load_pricing")
    # load_pricing() itself, given a path that does not exist
    ns = gateway_ns()
    with pytest.raises(SystemExit, match="Cannot read pricing file"):
        ns["load_pricing"](str(tmp_path / "nope.json"))
    assert "def load_pricing" in ns_code


# --- provider map ----------------------------------------------------------------------


def test_distinct_models_keep_declared_routes(gateway_ns):
    pm = gateway_ns()["MODEL_PROVIDER_MAP"]
    assert pm["std-model"] == ["openai", "azure_openai"]
    assert pm["reason-model"] == ["openai"]
    assert pm["alt-model"] == ["anthropic"]


def test_duplicate_model_id_keeps_azure_fallback(gateway_ns):
    # reasoning role reuses the standard model's ID: the later entry used to overwrite
    # the earlier one and drop the azure_openai fallback.
    pm = gateway_ns(env={"AGENT_MODEL_REASONING": "std-model"})["MODEL_PROVIDER_MAP"]
    assert pm["std-model"] == ["openai", "azure_openai"]
    assert "reason-model" not in pm


def test_duplicate_model_id_across_providers_merges_unique(gateway_ns):
    ns = gateway_ns(env={"AGENT_MODEL_ALT": "std-model", "AGENT_MODEL_FAST": "std-model"})
    assert ns["MODEL_PROVIDER_MAP"]["std-model"] == ["openai", "azure_openai", "anthropic"]
    merged = ns["build_model_provider_map"]([("m", ["a", "b"]), ("m", ["b", "a", "c"])])
    assert merged == {"m": ["a", "b", "c"]}


def test_registry_resolves_merged_fallbacks_in_order(gateway_ns, monkeypatch):
    for key in ("OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(key, "k")
    ns = gateway_ns(env={"AGENT_MODEL_REASONING": "std-model"})
    registry = ns["ProviderRegistry"]()
    assert [p.name for p in registry.resolve("std-model")] == ["openai", "azure_openai"]


# --- embedding model is lazy ------------------------------------------------------------


def test_gateway_starts_without_embedding_model(gateway_ns):
    ns = gateway_ns()  # AGENT_EMBEDDING_MODEL deliberately unset
    assert "EMBEDDING_MODEL" not in ns


def test_get_embedding_model_reads_env_on_call(monkeypatch):
    tree = ast.parse(_block(GATEWAY, "def get_embedding_model"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "get_embedding_model")
    ns: dict = {"os": importlib.import_module("os")}
    exec(compile(ast.Module([fn], []), "get_embedding_model", "exec"), ns)
    monkeypatch.delenv("AGENT_EMBEDDING_MODEL", raising=False)
    with pytest.raises(SystemExit, match="AGENT_EMBEDDING_MODEL"):
        ns["get_embedding_model"]()
    monkeypatch.setenv("AGENT_EMBEDDING_MODEL", "emb-1")
    assert ns["get_embedding_model"]() == "emb-1"


def test_gateway_page_has_no_duplicate_imports_or_module_level_embedding_constant():
    seen: dict[str, int] = {}
    text = GATEWAY.read_text(encoding="utf-8")
    module_text = text[: text.index("## How to Run")]  # later blocks are standalone client scripts
    for _, code in python_blocks(module_text):
        for node in ast.parse(code).body:
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                assert "EMBEDDING_MODEL" not in names
            if isinstance(node, ast.Import):
                for alias in node.names:
                    key = alias.asname or alias.name
                    seen[key] = seen.get(key, 0) + 1
    assert seen.get("os") == 1, "import os should appear once across the gateway module blocks"


def test_gateway_quickstart_env_lists_every_role_and_sources_it_safely():
    text = GATEWAY.read_text(encoding="utf-8")
    run = text[text.index("## How to Run"):]
    for var in (*ROLE_ENV, "AGENT_EMBEDDING_MODEL", "GATEWAY_PRICING_FILE", "AZURE_OPENAI_API_KEY"):
        assert var in run, var
    for command in ("set -a", "source .env", "set +a"):
        assert re.search(rf"^{re.escape(command)}$", run, re.M), f"{command} must be its own line"
    assert "&&" not in run[run.index("set -a"):run.index("set +a")]


# --- tool cost calculation --------------------------------------------------------------


@pytest.fixture(scope="module")
def usage_tracker():
    ns: dict = {"__name__": "__doc_example__"}
    code = _block(DOCS / "implementations/tool-calling-agent.md", "class UsageTracker")
    exec(compile(code, "tool-calling-agent.md:UsageTracker", "exec"), ns)
    return ns["UsageTracker"]


def test_usage_tracker_cost_is_per_million(usage_tracker):
    t = usage_tracker(
        prompt_tokens=2_000, completion_tokens=500, price_in_per_million=3.0, price_out_per_million=15.0
    )
    assert math.isclose(t.estimated_cost, (2_000 * 3.0 + 500 * 15.0) / 1_000_000)


def test_usage_tracker_requires_prices_and_rejects_negatives(usage_tracker):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        usage_tracker(prompt_tokens=1)
    with pytest.raises(ValidationError):
        usage_tracker(price_in_per_million=1.0)
    with pytest.raises(ValidationError):
        usage_tracker(price_in_per_million=-1.0, price_out_per_million=1.0)


def test_evaluation_harness_requires_prices(monkeypatch):
    code = _block(DOCS / "implementations/evaluation-harness.md", "def evaluate_repeated")
    ns: dict = {"__name__": "__doc_example__"}
    monkeypatch.setitem(sys.modules, "__doc_example__", types.SimpleNamespace(__dict__=ns))
    exec(compile(code, "evaluation-harness.md", "exec"), ns)
    with pytest.raises(TypeError):
        ns["evaluate_repeated"](lambda t: None, {"q": ["a"]}, n=1)


def test_design_principles_model_config_has_no_default_prices():
    code = _block(DOCS / "architecture-design/design-principles.md", "class ModelConfig")
    cls = next(
        n for n in ast.walk(ast.parse(code)) if isinstance(n, ast.ClassDef) and n.name == "ModelConfig"
    )
    fields = {n.target.id: n for n in cls.body if isinstance(n, ast.AnnAssign)}
    for name in ("price_in_per_million", "price_out_per_million"):
        assert name in fields and fields[name].value is None
    assert "cost_per_1k_input" not in fields


# --- lazy constructors (no env read at import / def time) --------------------------------


@pytest.fixture
def hallucination_ns(monkeypatch):
    calls: dict[str, list[str]] = {"ST": [], "CE": []}

    class SentenceTransformer:
        def __init__(self, name):
            calls["ST"].append(name)

    class CrossEncoder:
        def __init__(self, name):
            calls["CE"].append(name)

    st = types.ModuleType("sentence_transformers")
    st.SentenceTransformer, st.CrossEncoder = SentenceTransformer, CrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", st)
    for key in ("AGENT_LOCAL_EMBEDDING_MODEL", "AGENT_RERANKER_MODEL", "AGENT_EMBEDDING_MODEL"):
        monkeypatch.delenv(key, raising=False)
    path = DOCS / "architecture-design/hallucination-mitigation.md"

    def load(marker):
        ns: dict = {"__name__": "__doc_example__"}
        exec(compile(_block(path, marker), f"hallucination-mitigation.md:{marker}", "exec"), ns)
        return ns

    return load, calls


def test_grounding_checker_defers_env_read_to_constructor(hallucination_ns, monkeypatch):
    load, calls = hallucination_ns
    ns = load("class SemanticGroundingChecker")  # import time: env unset must not raise
    with pytest.raises(KeyError, match="AGENT_LOCAL_EMBEDDING_MODEL"):
        ns["SemanticGroundingChecker"]()
    monkeypatch.setenv("AGENT_LOCAL_EMBEDDING_MODEL", "local-emb")
    ns["SemanticGroundingChecker"]()
    ns["SemanticGroundingChecker"](model_name="explicit")
    assert calls["ST"] == ["local-emb", "explicit"]


def test_reranker_defers_env_read_to_constructor(hallucination_ns, monkeypatch):
    load, calls = hallucination_ns
    ns = load("class RerankedRetriever")
    with pytest.raises(KeyError, match="AGENT_RERANKER_MODEL"):
        ns["RerankedRetriever"](vector_store=object())
    monkeypatch.setenv("AGENT_RERANKER_MODEL", "rerank-1")
    ns["RerankedRetriever"](vector_store=object())
    assert calls["CE"] == ["rerank-1"]


# --- scan: no hardcoded tariffs, no env reads in default arguments -----------------------

_FORBIDDEN_TARIFF = [
    r"cost_per_1k",
    r"cost_per_1m_\w+\s*[:=]\s*[0-9]",
    r"\*\s*0\.0\d+\s*/\s*1000",
    r"Field\(default=0\.01\)",
    r"\$6,000-30,000",
    r"in_price:\s*float\s*=\s*0",
    r"out_price:\s*float\s*=\s*0",
]


def _routed_docs():
    return [p for p in DOCS.rglob("*.md") if "_shared" not in p.parts]


@pytest.mark.parametrize("pattern", _FORBIDDEN_TARIFF)
def test_no_hardcoded_decimal_tariffs_in_docs(pattern):
    hits = [
        f"{p.relative_to(DOCS)}:{i}"
        for p in _routed_docs()
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(pattern, line)
    ]
    assert not hits, hits


def test_no_python_function_default_reads_the_environment():
    """`def f(x=os.environ[...])` reads env at import time; defaults must be None + lazy."""

    def reads_env(node: ast.AST) -> bool:
        return any(
            isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == "os"
            and n.attr in {"environ", "getenv"}
            for n in ast.walk(node)
        )

    offenders = []
    for path in _routed_docs():
        for line, code in python_blocks(path.read_text(encoding="utf-8")):
            try:
                tree = ast.parse(code)
            except SyntaxError:
                continue
            for fn in ast.walk(tree):
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defaults = fn.args.defaults + [d for d in fn.args.kw_defaults if d is not None]
                    if any(reads_env(d) for d in defaults):
                        offenders.append(f"{path.relative_to(DOCS)}:{line + fn.lineno - 1}")
    assert not offenders, offenders
