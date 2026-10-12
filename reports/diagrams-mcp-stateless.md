# Diagram report: MCP 2026-07-28 stateless tool call

- Source: `diagrams/mcp-stateless-request.json` (Archify `sequence`, showcase, no animation)
- Output: `static/diagrams/mcp-stateless-request.html`
- Participants (5): Host, MCP client, Authorization server (token source), MCP server, Tool API

## Flow shown
1. Host asks the client to call a tool.
2. Optional, only for protected tools: client gets an access token from the authorization server (dashed).
3. Client sends HTTPS JSON-RPC `tools/call` with per-request `_meta` and the Bearer token in the `Authorization` header.
4. Server validates token, audience, scopes and schema, then runs the tool against the Tool API (`validated: run tool`).
5. Result returns with `_meta` `io.modelcontextprotocol/serverInfo`, then to the host.

Scope: success path only. There is no alt/branch in the sequence; the former trailing message `alt: 401/403 invalid, stop` was removed because it appeared after a successful tool result, which is chronologically wrong.

Auth failure (footer card, not a message): `401 unauthenticated / 403 insufficient scope: no tool execution`. 401 means the caller is unauthenticated (missing/invalid token); 403 means the token is valid but lacks scope. Either way the server rejects before running the tool, so the Tool API is never called.

Header `tools/call + _meta + Bearer` is shorthand for two separate things: `_meta` holds protocolVersion, clientCapabilities, clientInfo; the Bearer token travels in the `Authorization` header, not in `_meta`. The card states this explicitly.

Deliberately omitted: `initialize`, `Mcp-Session-Id`, any model or agent decision logic, Tasks, Apps, `server/discover`, `tools/list`.

## Source citations
- `docs/core-concepts/model-context-protocol.md`
  - "Connecting a Client" example: `tools/call` body with `params._meta` keys `io.modelcontextprotocol/protocolVersion`, `clientCapabilities`, `clientInfo`. Headers `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`.
  - Protocol-version paragraph: servers SHOULD identify themselves in result `_meta` via `io.modelcontextprotocol/serverInfo`.
  - Version table: 2026-07-28 has no `initialize` / `notifications/initialized` and no `Mcp-Session-Id`.
  - Security section: servers must enforce caller authorization on every operation; OAuth changes (RFC 9207 `iss`, DCR deprecated).
- `reports/batch-1-protocol-reasoning.md`: confirms the `serverInfo` key correction and the per-request `_meta` model.

## Claims to treat carefully
- The page now explicitly documents `Authorization: Bearer`, 401 unauthenticated and 403 insufficient-scope behavior alongside the authorization-spec link. This reconciles the initial diagram handoff's missing-page-evidence note; see `reports/update-pass.md` for the integration amendment.
- Token acquisition is simplified to dashed get/return token messages. No authorization-code flow or API parameters are shown.
- Token audience and scope checks were confirmed against `https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization` on 2026-10-12: servers MUST validate intended audience; insufficient scope SHOULD produce HTTP 403; missing/invalid authorization produces HTTP 401. The HTTPS fetch used curl after Python's default CA bundle failed verification; TLS validation was never disabled.
- Authorization is shown as optional and dashed. Anonymous tools are possible and OAuth is not universal.
- The docs page's client example is illustrative and not SDK-tested.
- The Mcp-* HTTP headers are not drawn. They are in the source example.

## Verification
- Revision: factual chronology repair of the previous diagram (removed `m10`, shortened/clarified `_meta` wording, added auth-failure card).
- `archify validate` and `archify deliver sequence ... --quality showcase`: 9/9 checks, 0 errors, 0 warnings.
  - Spec `diagrams/mcp-stateless-request.json` sha256 `6c977d3757af5fcdaaaa703fe94cd8c3eda2c4f86a028e683f8c3a88a1f4b517` (2705 bytes).
  - Artifact `static/diagrams/mcp-stateless-request.html` sha256 `800c375767714465d249243abe11555e7accab5c5485663cff4fcc83c8073599` (803170 bytes).
- `archify visual-check`: status pass, 0 diagnostics. Containment: 1440x900, 1600x1000, 1920x1080, 2048x1320 (light), no overflow. Screenshot captures: 1440x900 and 2048x1320, light and dark, no overflow. Dark at 1600 and 1920 was not recorded by the tool.
- Perceptual visual review: **pending**. No image-capable reviewer was used.

## Side files
Final browser sidecars and all four generated light/dark PNGs are retained under `reports/diagrams-browser/mcp-stateless-request.visual-check.*`, not shipped in `static/`. The immutable JSON records the artifact's original absolute path; the sibling screenshot filenames still resolve in the moved HTML report. No perceptual image review was performed.

## Integration
The page embeds `/diagrams/mcp-stateless-request.html` through the base-URL-aware `DiagramEmbed` component. The caption discloses that this is a success path and the authorization token does not live in `_meta`.
