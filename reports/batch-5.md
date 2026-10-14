# Batch 5 report: regression prevention (content lint, last_verified, CI)

Date: 2026-10-12. This report covers prevention integration; batches 1–4 separately document the content changes. No commits or PRs were created. Final-state amendments below supersede the original subtask's handoff blockers and initial counts; complete verification is summarized in `reports/update-pass.md`.

## Files and actions

| File | Action |
|---|---|
| `scripts/deprecations.yaml` | New regex denylist: `id`, `pattern`, `flags`, `hint`, `allow_in` (exact pages), `allow_in_legacy_details`. |
| `scripts/lib/content-lint.mjs` | New pure lint logic: model-ID detection, real `<details><summary>Legacy` bounds, deprecations, `last_verified`. |
| `scripts/check-content.mjs` | New CLI (`npm run check:content`). Also runs the Python fence syntax check. `--today`, `--no-python`. |
| `scripts/add-last-verified.mjs` | New metadata script: inserts/replaces only the `last_verified:` front-matter line, re-reading each file right before writing. |
| `scripts/tests/content-lint.test.mjs` | New `node:test` regression tests (20), run with `npm test`. |
| `examples/langchain-v1/check_doc_imports.py` | Added `check_syntax(paths)` and `--syntax-only`, reusing the existing CommonMark-style `python_blocks` parser. `main(paths)` is unchanged. |
| `package.json`, `package-lock.json` | Scripts `check:content`, `test` (existing `typecheck`/`build` kept); devDependency `js-yaml ^4.1.0`. |
| `docusaurus.config.ts` | `docs.exclude` = Docusaurus defaults (kept) + `**/_shared/**`. |
| `docs/_shared/models.mdx` -> `docs/_shared/models.md` | Renamed (exact name requested). |
| `docs/index.md` | Import line now `./_shared/models.md`; plus `last_verified`. |
| `reports/batch-3.md` | Path mention updated on its one line. |
| `docs/architecture-design/design-principles.md`, `docs/projects/{customer-support-agent,llm-gateway,multi-agent-orchestration}.md` | One-token path fix in an existing "see docs/_shared/models.md" comment (otherwise they would point at a removed file). |
| 84 routed pages under `docs/` | `last_verified: 2026-10-12` added (script-driven, every routed page, none skipped). |
| `.github/workflows/content-check.yml` | PR/push/weekly: `npm test`, `check:content`, typecheck, build, plus pinned Python example tests. `contents: read` only. |
| `.github/workflows/monthly-latest.yml` | Monthly schedule + manual: latest, uncapped installs, example tests; scheduled failure only opens/updates one deduplicated issue. |

## Dependency decision

The `yaml` package is **not** installed (`node_modules/yaml` absent). `js-yaml` 4.2.0 is already in
`node_modules`/`package-lock.json` (transitive via Docusaurus), so it was declared as a direct devDependency
(`^4.1.0`, satisfied by the locked 4.2.0) rather than adding anything new. `npm install` was not possible
offline; the `package.json` and lockfile root entries were edited by hand. Parent: run `npm install` once
to confirm the lockfile is in sync. JSON-as-YAML was not needed. Front matter and the denylist are parsed
with `CORE_SCHEMA` so dates stay strings.

## Rules

- **Model IDs**: flagged anywhere in routed pages (prose, code, front matter) unless the file is
  `docs/_shared/models.md` or the match lies inside a real `<details><summary>Legacy...</summary>` ... `</details>`
  block. Families: OpenAI `gpt-*`/`chatgpt-*`/`o1,o3...`, Claude (`claude-*` with a digit or tier word), embeddings
  (`text-embedding-*`, `gemini-embedding-*`, `voyage-*`, ...), Gemini, Llama (`llama3.2:3b`, `meta-llama/...`),
  Mistral family, Qwen, DeepSeek. Lowercase API identifiers only; URLs and link targets are ignored. Product names
  (Claude Agent SDK, `claude-agent-sdk`, LlamaIndex, `llama-index`, "GPT-4" prose) do not match.
- **Legacy bounds**: tags inside code fences or inline code are ignored, so quoting the markup is not a loophole;
  an unclosed/unmatched `<details>` is an error and never extends to end of page; text after `</details>` is checked
  again. Tests cover each case.
- **Deprecations**: `allow_in` takes exact paths only (globs rejected). A path that does not exist, or has no match
  for its pattern (stale allowance), fails the check. `budget_tokens` (and `"type": "enabled"`) are allowed only inside
  Legacy details. Allowances currently used: `AgentExecutor` (langchain-overview, langgraph-deep-dive, framework-qa:
  "the old AgentExecutor ..." historical prose), `LLMChain` (langchain-overview), `OpenAIAgent` and
  `ReActAgent.from_tools` (llamaindex-agents prose), `beta.assistants` (openai-responses sunset notice). No suppression
  covers a current-API use.
- **last_verified**: missing/invalid/future date = error; older than 120 days = **warning only** (CI stays green;
  warnings go to stderr and, in CI, to the job summary). Meaning: the **date of the last audit-scoped content review**
  of the page (the batch 1-5 audit). It is not live certification and does not say every claim was re-checked against
  current vendor sources; per-page unverified APIs are listed in the per-batch reports under `reports/`. All 84 routed
  pages carry the stamp (stamped by script, not by an independent full re-read of each page's sources). It does **not**
  claim the examples were executed: Python examples are only syntax-checked (`--syntax-only`, all pages) and, for the tracked pages,
  import-checked (`check_doc_imports.py`); no snippet is run against a live API.

## Source / doc URLs and verification dates

No new vendor docs were fetched in this batch. URLs and dates are those already recorded in the pages and in
`reports/batch-3.md` (checked 2026-10-12); `last_verified: 2026-10-12` on every page is the audit review date, not a
fresh re-read of each page in this batch.

## Review-fix amendment (prevention review)

- **Python child failures**: `check-content.mjs` now turns a nonzero exit or signal of the python checker that printed
  no `SYNTAX`/`FENCE`/`READ` line into an error containing status/signal, stderr and stdout (`pythonCheckErrors`, unit
  tested with fake child results). `check_doc_imports.py` reports a per-page `READ` failure for
  `UnicodeDecodeError`/`OSError` instead of a traceback. An integration test runs the real CLI on a temporary docs tree
  (`--root`, `--rules`) containing invalid UTF-8; real docs are never modified.
- **Deprecation allowances**: `allow_in` now exempts historical **prose** on the exact pages only; fenced code, and
  inline code containing an import or a call, still fail there. `allow_in_legacy_details` also accepts an explicit
  `Legacy` heading section (bounded by the next heading of the same/higher level; headings in fences ignored) besides
  real `<details><summary>Legacy` blocks. `langchain-overview.md`'s `LLMChain` fence is now wrapped in a Legacy
  details block. The `OpenAIAgent`/`from_tools` sentence in `llamaindex-agents.md` was reworded so the pattern does
  not appear as an inline call.
- **`create_react_agent`**: one rule matches the bare name, so single-line, multiline/parenthesized, aliased, dotted
  and call forms are all caught. Prose mentions are allowed only on `langchain-overview`, `react-pattern`,
  `basic-react-agent` (each verified to match); code is allowed only in Legacy blocks/sections.
- **Model IDs**: case-insensitive; added `gpt-image/realtime/audio/oss`, Whisper/DALL-E, Grok, Command R/A, Gemma, Phi,
  Amazon Nova/Titan (Bedrock), Sonar, Jamba, Kimi/Moonshot, GLM, Yi, and Hugging Face / sentence-transformer / reranker
  name shapes (`all-MiniLM-*`, `bge-*`, `org/model` for known orgs). Markdown link targets are ignored only outside
  fences and inline code. **Limit**: these are regex families for known vendors, not a universal detector; an unknown
  vendor's ID shape is not caught. Bare product names and prose such as "GPT-4" are not matched (numbered-name prose is
  not an API identifier; the rule is IDs). Newly detected current uses were replaced by env-var placeholders
  (`AGENT_NLI_MODEL`, `AGENT_RERANKER_MODEL` documented in `_shared/models.md`).
- **CI**: `content-check.yml` jobs have `timeout-minutes` 30/40; the pinned job now installs the exact
  `requirements-verified.txt` (a real `pip freeze` of the verified Python 3.12.10 environment `/tmp/lcv-b2`, 191
  packages, no local paths/credentials, macOS-captured). The Tier 1 job installs unpinned `examples/tier1/requirements-<framework>.txt`
  (one env per framework, matrix; so it is **not** called pinned) and is skipped on PRs. `monthly-latest.yml` (45 min) now covers the **tracked
  migrated examples** only: Tier 2 pages in one environment and each Tier 1 page in its own matrix environment. Archived legacy
  pages (`autogen-guide`, `semantic-kernel`) are intentionally not import-checked in CI. Weekly warnings are visible via
  stderr and `GITHUB_STEP_SUMMARY` and never fail the run.
- **Tier 1 imports**: `TIER1_PAGES` (openai-responses-and-agents-sdk, llamaindex-agents, microsoft-agent-framework,
  crewai-guide) are checked with the dedicated CLI by exact page path; `multi-agent-crew.md` joined `TIER2_PAGES` with
  its tutorial-local modules declared in `PAGE_LOCAL_MODULES`. No broad unresolved-import ignore was added.

## Verification run here

- `node --test scripts/tests/` (`npm test`): 35 pass.
- `node scripts/check-content.mjs`: 84 pages, 0 errors, 0 warnings (the earlier `OpenAIAgent` item has landed).
- Tier 2 import check in `/tmp/lcv-b2` (all `TIER2_PAGES`, incl. multi-agent-crew): 0 failures.
- Python syntax check over all 84 pages: 0 failures.

## Final-state reconciliation (2026-10-12)

The original handoff items were resolved as follows:

- `framework-qa.md` uses the current workflow agents; no `OpenAIAgent` allowance was added. Content lint passes.
- The shared model partial now says **no universal default**, distinguishes provider SDKs and prefixed LangChain model strings, and documents embedding/reranker variables.
- Navigation, redirects, `_shared` routing exclusion and the `.md` import compile in the completed repository build.
- `npm install --package-lock-only --ignore-scripts` succeeded without changes to the existing lockfile on 2026-10-12. Its audit reported 63 dependency vulnerabilities; no out-of-scope upgrades or `audit fix` were attempted.
- Tier 1 import/smoke checks now run on PRs as well as push/schedule/manual dispatch. The earlier non-PR description is obsolete.
- No GitHub workflow has been executed from this environment. Linux installation of the macOS-captured freeze remains unverified; local framework tests use isolated Python 3.12 environments. Scheduled issue creation is implemented, not remotely exercised.
- Regex model-ID detection covers known families, not arbitrary unknown vendors. Weekly freshness annotations/job summaries warn after 120 days; monthly failures alone open/update issues.
- The Python fence extractor now supports both backticks and tildes, `python`/`python3`/`py`/`py3`, matching closing-fence characters/lengths and CommonMark opener indentation. Twenty additional parametrized regression cases prevent syntax/import checks from silently skipping these forms.
- Final Node/Python counts and results are in `reports/update-pass.md`; previous counts above describe intermediate runs.

## Revision: Tier 1 CI split (2026-10-12)

`examples/langchain-v1/requirements-tier1.txt` (one resolve of every framework, including the huge umbrella
`agent-framework`) was replaced by four files, each its own environment. Exact coverage:

| Matrix leg | Requirements | Pages import-checked | Offline smoke tests |
|---|---|---|---|
| openai | `examples/tier1/requirements-openai.txt` | `docs/frameworks/openai-responses-and-agents-sdk.md` | `examples/tier1/openai` |
| microsoft | `requirements-microsoft.txt` (`agent-framework-core`, `opentelemetry-sdk`, OTLP gRPC exporter) | `docs/frameworks/microsoft-agent-framework.md` | `examples/tier1/microsoft` |
| llamaindex | `requirements-llamaindex.txt` | `docs/frameworks/llamaindex-agents.md` | `examples/tier1/llamaindex` |
| crewai | `requirements-crewai.txt` (+ `langgraph`, `langchain-openai`) | `docs/frameworks/crewai-guide.md`, `docs/implementations/multi-agent-crew.md` | `examples/tier1/crewai` |

`content-check.yml` (`examples-tier1-imports`, including PRs) and `monthly-latest.yml` (`latest-tier1`) both use
`strategy.fail-fast: false` matrices; the monthly report job fires on `needs.*.result == failure`, so a failure in ANY leg
opens/updates the deduplicated issue. Limits: smoke tests are offline fakes/constructions, not live API checks; Linux CI
has not run these (verified on macOS arm64, Python 3.12.10); the Tier 1 files are unpinned floors, not freezes (a freeze
captured on macOS would risk missing Linux wheels; a freeze can be added later per leg if reproducibility is wanted).
`multi-agent-crew.md` stays in `TIER2_PAGES` as well (default check in the Tier 2 env).
