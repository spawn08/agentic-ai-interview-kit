"""Extract python code fences from docs, parse with ast, and try every import.

Usage: python check_doc_imports.py [--syntax-only] [docs/a.md docs/b.md ...]
(default pages: TIER2_PAGES, run from repo root)
Reports syntax errors, unreadable/undecodable pages (READ) and failing imports exactly; exit code 1
if any fail. Tier 1 pages (TIER1_PAGES) are checked one page per environment (examples/tier1/requirements-<framework>.txt), because
the frameworks' dependencies conflict with each other and with requirements.txt; pass the page explicitly.
--syntax-only parses every python fence (no imports, no third-party packages needed); it is what
`npm run check:content` uses on all routed docs. Neither mode executes the examples.
"""
import ast
import importlib
import re
import sys
import warnings

warnings.filterwarnings("ignore")

# Every Tier 2 page changed in batch 2; used when no paths are given.
TIER2_PAGES = [
    "docs/frameworks/langchain-overview.md",
    "docs/frameworks/langgraph-deep-dive.md",
    "docs/design-patterns/react-pattern.md",
    "docs/core-concepts/planning-and-reasoning.md",
    "docs/core-concepts/agent-architectures.md",
    "docs/core-concepts/tools-and-function-calling.md",
    "docs/foundations/rag-basics.md",
    "docs/foundations/prompting-techniques.md",
    "docs/implementations/rag-agent-with-tools.md",
    "docs/implementations/basic-react-agent.md",
    "docs/interview-questions/coding-challenges.md",
    "docs/interview-questions/framework-qa.md",
    "docs/interview-questions/agent-architecture-qa.md",
    "docs/projects/customer-support-agent.md",
    "docs/projects/research-agent.md",
    "docs/implementations/multi-agent-crew.md",
    "docs/core-concepts/guardrails-and-safety.md",
    "docs/core-concepts/memory-systems.md",
    "docs/core-concepts/what-are-agents.md",
    "docs/design-patterns/chain-of-thought.md",
    "docs/design-patterns/human-in-the-loop.md",
    "docs/design-patterns/multi-agent-pattern.md",
    "docs/design-patterns/plan-and-execute.md",
    "docs/design-patterns/reflection-pattern.md",
    "docs/design-patterns/self-refinement.md",
    "docs/design-patterns/tool-use-pattern.md",
    "docs/implementations/langgraph-workflow.md",
    "docs/implementations/tool-calling-agent.md",
    "docs/implementations/evaluation-harness.md",
]

# New-API pages; each needs its own environment (examples/tier1/requirements-<framework>.txt).
# Run: python check_doc_imports.py <one page>. Not part of the default page list.
TIER1_PAGES = [
    "docs/frameworks/openai-responses-and-agents-sdk.md",
    "docs/frameworks/llamaindex-agents.md",
    "docs/frameworks/microsoft-agent-framework.md",
    "docs/frameworks/crewai-guide.md",
]

# Exact, per-page exclusions. Nothing else is ever skipped: every other import
# (including third-party packages) must resolve in the environment built from
# requirements.txt. Each entry is a top-level module that the page itself defines
# as a file in a multi-file tutorial layout (the page must mention "<module>.py"),
# so it is intentionally not importable here. Unused entries fail the run.
PAGE_LOCAL_MODULES = {
    "docs/implementations/basic-react-agent.md": {"state", "tools", "nodes", "graph"},
    "docs/implementations/rag-agent-with-tools.md": {"state", "nodes", "routing", "vectorstore", "graph"},
    "docs/projects/research-agent.md": {"state", "tools", "nodes", "graph"},
    "docs/implementations/multi-agent-crew.md": {"state", "agents", "supervisor", "graph"},
    "docs/implementations/langgraph-workflow.md": {"state", "nodes", "routing", "graph"},
    "docs/implementations/tool-calling-agent.md": {"state", "tools", "nodes", "graph"},
    "docs/implementations/evaluation-harness.md": {
        "schema", "scorers", "runner", "test_suite", "report", "tracing",
    },
}
OPEN = re.compile(r"^( {0,3})(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)")


def python_blocks(text: str):
    """Yield (first_code_line_number, code) for each python fence, CommonMark-style.

    A closing fence uses the same character (backtick or tilde) at least as many
    times as its opener, indented <= 3 spaces. Opener indentation is stripped from
    the body. A naive "```" regex wrongly ends a block at an *indented* ``` that sits
    inside a Python string literal (e.g. stripping markdown fences from LLM output).
    """
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = OPEN.match(lines[i])
        if not m:
            i += 1
            continue
        fence, lang, start = m.group(2), m.group(3).lower(), i + 1
        indent = len(m.group(1))
        close = re.compile(r"^ {0,3}%s{%d,}\s*$" % (re.escape(fence[0]), len(fence)))
        i += 1
        body = []
        while i < len(lines) and not close.match(lines[i]):
            line = lines[i]
            remove = min(indent, len(line) - len(line.lstrip(" ")))
            body.append(line[remove:])
            i += 1
        if i >= len(lines):
            raise ValueError(f"unclosed code fence opened at line {start}")
        if lang in ("python", "python3", "py", "py3"):
            yield start + 1, "\n".join(body) + "\n"
        i += 1


def page_key(path: str) -> str:
    """Normalise a path to the docs/... form used in PAGE_LOCAL_MODULES."""
    norm = path.replace("\\", "/")
    return norm[norm.index("docs/"):] if "docs/" in norm else norm


def read_page(path: str) -> str | None:
    """Return the page text, or print a READ failure line and return None.

    A single undecodable (UnicodeDecodeError) or unreadable (OSError) page must be reported as a
    failure for that page, not crash the whole run with a traceback.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except UnicodeDecodeError as exc:
        print(f"READ    {path}: not valid UTF-8 ({exc.reason} at byte {exc.start})")
    except OSError as exc:
        print(f"READ    {path}: {type(exc).__name__}: {exc.strerror or exc}")
    return None


def check_syntax(paths: list[str]) -> int:
    """Parse (never import or run) every python fence in each page; return the failure count.

    Reuses python_blocks so fence handling is identical to the import check. An unclosed fence is
    reported as a failure instead of raising.
    """
    failures = 0
    for path in paths:
        text = read_page(path)
        if text is None:
            failures += 1
            continue
        try:
            blocks = list(python_blocks(text))
        except ValueError as exc:
            print(f"FENCE   {path}: {exc}")
            failures += 1
            continue
        for n, (line, code) in enumerate(blocks, 1):
            try:
                ast.parse(code)
            except SyntaxError as exc:
                print(f"SYNTAX  {path}:{line} (block {n}): {exc.msg} (block line {exc.lineno})")
                failures += 1
    return failures


def main(paths: list[str]) -> int:
    failures = 0
    for path in paths:
        text = read_page(path)
        if text is None:
            failures += 1
            continue
        local = PAGE_LOCAL_MODULES.get(page_key(path), set())
        used: set[str] = set()
        for mod in sorted(local):
            if f"{mod}.py" not in text:
                print(f"EXCLUDE {path}: '{mod}' is excluded but the page never mentions {mod}.py")
                failures += 1
        for n, (line, code) in enumerate(python_blocks(text), 1):
            tag = f"{path}:{line} (block {n})"
            try:
                tree = ast.parse(code)
            except SyntaxError as exc:
                print(f"SYNTAX  {tag}: {exc.msg} (block line {exc.lineno})")
                failures += 1
                continue
            for node in ast.walk(tree):
                top = node.module.split(".")[0] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else None
                if top in local:
                    used.add(top)
                    continue
                try:
                    if isinstance(node, ast.Import):
                        for a in node.names:
                            importlib.import_module(a.name)
                    elif isinstance(node, ast.ImportFrom) and node.level == 0:
                        mod = importlib.import_module(node.module)
                        for a in node.names:
                            if not hasattr(mod, a.name):
                                importlib.import_module(f"{node.module}.{a.name}")
                except Exception as exc:  # report exactly
                    print(f"IMPORT  {tag}: {ast.unparse(node)} -> {type(exc).__name__}: {exc}")
                    failures += 1
        for mod in sorted(local - used):
            print(f"EXCLUDE {path}: stale exclusion '{mod}' (no import of it on the page)")
            failures += 1
    print(f"done, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--syntax-only" in args:
        args = [a for a in args if a != "--syntax-only"]
        bad = check_syntax(args or TIER2_PAGES)
        print(f"done, {bad} syntax failure(s)")
        sys.exit(1 if bad else 0)
    sys.exit(main(args or TIER2_PAGES))
