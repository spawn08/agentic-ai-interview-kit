# Batch 3 – Tier 3 Interoperability Report

Date of verification: 2026-10-12 (curl). No commits.

## File
| File | Change |
|---|---|
| `docs/core-concepts/agent-interop-protocols.md` | Minimal edits: v1.0 verification banner, AAIF stewardship, three bindings, v1.0 Agent Card (`supportedInterfaces`), `SendMessage`/`ROLE_USER`/unified `Part`, `A2A-Version` header, ACP now merged, task-state note, Official Sources. Structure, tables, interview section preserved. |

## Sources (curl)
- `a2a-protocol.org/latest/specification/` (latest released 1.0.0), `/latest/whats-new-v1/`, `/latest/blog/2026/08/27/a-new-chapter-for-a2a-joining-the-agentic-ai-foundation/` (Growth Stage project at AAIF), `github.com/a2aproject/A2A/releases` (latest tag v1.0.1), `aaif.io/about` (lists A2A), `lfaidata.foundation/.../acp-joins-forces-with-a2a-...` (ACP merging into A2A, team winding down).

## Migrations (v0.3 → v1.0 shown in page)
`message/send` → `SendMessage`; lowercase states/roles → `TASK_STATE_*`/`ROLE_*`; `kind`-discriminated parts → unified `Part`; top-level `url`/`preferredTransport` → `supportedInterfaces[]` (binding + version); `A2A-Version` header.

## Unverified
- A2A origin/donation dates and the AGNTCY row (not re-fetched); stated as unverified in the page.
- Exact task-state transitions (diagram shows common path only); required Agent Card fields in the sample.
- Version discrepancy: spec page says 1.0.0, GitHub latest tag is v1.0.1 (patch); both noted.
- Code not executed.
