# Protocol and reasoning verification amendment

Checked: 2026-10-12. Companion to `batch-1-protocol-reasoning.md`.

- The installed Anthropic SDK (1.13.0, `/tmp/lcv-b2`) declares `thinking` and `output_config` in `MessageCreateParamsNonStreaming`; `OutputConfigParam.effort` declares low/medium/high/xhigh/max. This resolves the earlier keyword-type uncertainty, **not** per-model acceptance or live inference behavior.
- The MCP authorization specification (`https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization`, HTTPS fetched with curl, 2026-10-12) confirms per-request `Authorization: Bearer`, audience validation, 401 for missing/invalid authorization and 403 for insufficient scope. These are reflected in the page and diagram caption.
- Python's default HTTPS CA bundle failed verification on the supplemental fetch; curl succeeded with its normal trust store. TLS verification was not weakened.
- The final page embeds the stateless sequence diagram; `initialize`/session descriptions remain historical. SDK support for the full 2026-07-28 revision and live provider calls are still unverified.
