# Diagram receipt: Model + Harness

- Type: Archify `workflow` (schema v2), `meta.quality_profile: showcase`, animation `none`, default preset.
- Deliverable: `static/diagrams/model-and-harness.html`
- Spec: `diagrams/model-and-harness.json` (sha256 `84e9db1fa26f98f03971e39a8bfa499a990830b97363e580c4943bcbc1bac903`, 4255 bytes)
- Artifact sha256 `d77f1e26b3eec2eecb960f0d689ad0228c84051a7f04a7c3d4aec9463bd9a235` (810638 bytes)
- Parent integration is complete: `DiagramEmbed` embeds the artifact with base-URL-aware routing on `docs/core-concepts/what-are-agents.md`.

## Source ranges
- `docs/core-concepts/what-are-agents.md` L12, L55-89 (observe-act loop), L180-192 (Agent = Model + Harness; harness owns loop, tool execution, memory/state, permissions, approval gates, observability; measure with evals).
- `docs/core-concepts/context-engineering.md` L10, L128-132 (context assembly; notes/memory outside the window).
- `docs/core-concepts/guardrails-and-safety.md` L66-78 (privilege separation, approval gates), L494-496, L556-558 (approval for high-risk actions).
- There is no `core-concepts` security page; `guardrails-and-safety.md` is the security source used.

## Diagram facts (9 nodes)
Main path: User request -> Harness -> Model -> Policy / approval gate -> Tool runtime -> Environment -> Observation -> (next iteration) Harness. Off-path dashed branch from Harness: Memory & checkpoints, Eval trace. The model only proposes actions; its sole outgoing edge goes to the gate, so it has no direct edge to tools.

Interpretation: the gate is drawn in the "Model & policy gate" lane for layout; the docs place approval gates in the harness.

## Validation
- `validate` (first candidate, 6 lanes): 9/9 checks, 0 errors, 0 warnings.
- `visual-check` on that artifact failed: viewport overflow (scrollHeight 1617 at 1440x900). Fix: merged lanes 6 -> 4, dropped one card.
- That layout failed delivery on one crossing (`harness-trace` x `model-to-gate`). Fix: moved `eval-trace` to col 0 and `memory-checkpoints` to col 2.
- Final `deliver`: 9/9 checks, showcase pass, 0 errors, 0 warnings.
- Final `visual-check`: status pass. Chrome automated. 1440x900, 1600x1000, 1920x1080, 2048x1320 (light) reported scrollWidth/scrollHeight equal to the viewport (no overflow). Light and dark screenshots at 1440x900 and 2048x1320, with their JSON/HTML sidecars, are retained under `reports/diagrams-browser/model-and-harness.visual-check.*` (not shipped in `static/`).
- Perceptual visual review: not performed. No image was viewed.
