// Pure content-lint logic (no filesystem access) so node:test can exercise it on in-memory pages.
// CLI wrapper: scripts/check-content.mjs. Rules: scripts/deprecations.yaml.
import yaml from 'js-yaml';

export const MODELS_PARTIAL = 'docs/_shared/models.md';
export const STALE_AFTER_DAYS = 120;

// ---------------------------------------------------------------- structure helpers

/** Replace every non-newline char in [start,end) with a space, keeping offsets/line numbers. */
function blank(text, start, end) {
  return text.slice(0, start) + text.slice(start, end).replace(/[^\n]/g, ' ') + text.slice(end);
}

/** CommonMark-style fenced code ranges [{start,end}] plus unclosed-fence errors. */
export function fencedRanges(text) {
  const ranges = [];
  const errors = [];
  const lines = text.split('\n');
  let offset = 0;
  let open = null;
  lines.forEach((line, i) => {
    if (!open) {
      const m = /^ {0,3}(`{3,}|~{3,})/.exec(line);
      if (m) open = { char: m[1][0], len: m[1].length, start: offset, line: i + 1 };
    } else {
      const m = /^ {0,3}(`{3,}|~{3,})\s*$/.exec(line);
      if (m && m[1][0] === open.char && m[1].length >= open.len) {
        ranges.push({ start: open.start, end: offset + line.length });
        open = null;
      }
    }
    offset += line.length + 1;
  });
  if (open) {
    ranges.push({ start: open.start, end: text.length });
    errors.push(`unclosed code fence opened at line ${open.line}`);
  }
  return { ranges, errors };
}

export function lineOf(text, index) {
  let n = 1;
  for (let i = 0; i < index; i++) if (text.charCodeAt(i) === 10) n++;
  return n;
}

/**
 * Actual `<details><summary>Legacy...</summary>` blocks, bounded by their matching `</details>`.
 * Tags inside code fences or inline code are ignored, so quoting the markup cannot create a
 * loophole, and an unbalanced block is an error (never "everything to end of page").
 */
export function legacyRanges(text) {
  const errors = [];
  const { ranges: fences, errors: fenceErrors } = fencedRanges(text);
  errors.push(...fenceErrors);
  let scan = text;
  for (const f of fences) scan = blank(scan, f.start, f.end);
  scan = scan.replace(/(`+)[^`\n]*?\1/g, (m) => ' '.repeat(m.length));

  const ranges = [];
  const stack = [];
  const tag = /<details\b[^>]*>(\s*<summary\b[^>]*>([\s\S]*?)<\/summary>)?|<\/details\s*>/gi;
  let m;
  while ((m = tag.exec(scan)) !== null) {
    if (m[0][1] === '/') {
      const top = stack.pop();
      if (!top) {
        errors.push(`unmatched </details> at line ${lineOf(text, m.index)}`);
      } else if (top.legacy) {
        ranges.push({ start: top.start, end: m.index + m[0].length });
      }
    } else {
      const summary = (m[2] ?? '').replace(/<[^>]*>/g, '').trim();
      stack.push({ start: m.index, line: lineOf(text, m.index), legacy: /^legacy\b/i.test(summary) });
    }
  }
  for (const open of stack) errors.push(`unclosed <details> opened at line ${open.line}`);
  return { ranges, errors };
}

const inRanges = (ranges, i) => ranges.some((r) => i >= r.start && i < r.end);

/** Inline code spans (outside fences): [{start,end,text}]. */
export function inlineCodeSpans(text) {
  let scan = text;
  for (const f of fencedRanges(text).ranges) scan = blank(scan, f.start, f.end);
  const spans = [];
  const re = /(`+)[^`\n]*?\1/g;
  let m;
  while ((m = re.exec(scan)) !== null) spans.push({ start: m.index, end: m.index + m[0].length, text: m[0] });
  return spans;
}

/**
 * Explicit Legacy heading sections: an ATX heading whose text starts with "Legacy" (markup and
 * backticks stripped) up to the next heading of the same or a higher level, so a Legacy heading
 * never swallows the rest of the page. Headings inside code fences are ignored.
 */
export function legacySectionRanges(text) {
  const fences = fencedRanges(text).ranges;
  const headings = [];
  let offset = 0;
  for (const line of text.split('\n')) {
    const m = /^ {0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$/.exec(line);
    if (m && !inRanges(fences, offset)) {
      headings.push({ start: offset, level: m[1].length, title: m[2].replace(/[`*_]/g, '').trim() });
    }
    offset += line.length + 1;
  }
  const ranges = [];
  headings.forEach((h, i) => {
    if (!/^legacy\b/i.test(h.title)) return;
    const next = headings.slice(i + 1).find((n) => n.level <= h.level);
    ranges.push({ start: h.start, end: next ? next.start : text.length });
  });
  return ranges;
}

// ---------------------------------------------------------------- front matter

export function parseFrontmatter(text) {
  const m = /^---\n([\s\S]*?)\n---(?:\n|$)/.exec(text);
  if (!m) return null;
  // CORE_SCHEMA keeps dates as strings (no implicit timestamp type).
  const data = yaml.load(m[1], { schema: yaml.CORE_SCHEMA }) ?? {};
  return { data, raw: m[1], length: m[0].length };
}

// ---------------------------------------------------------------- model IDs

const ID = '[A-Za-z0-9._-]*';
const B = '(?<![A-Za-z0-9_])';
// Identifier-shaped tokens only, matched case-insensitively (except the bare `o1` family). These are
// regex FAMILIES for the vendors/model lines we know about, not a universal model-ID detector: an
// unknown vendor's ID shape will not be caught. Product names without an ID shape ("Claude Agent
// SDK", "LlamaIndex", "Gemini", "Phi" as a word) never match.
const fam = (family, src, flags = 'gi', keep) => ({ family, re: new RegExp(src, flags), keep });
const MODEL_PATTERNS = [
  fam('openai-gpt', `${B}(?:chat)?gpt-(?:\\d|oss|image|realtime|audio|codex|[a-z]+\\d)${ID}`),
  fam('openai-media', `${B}(?:whisper-\\d|dall-e-\\d|tts-\\d|sora-\\d|omni-moderation|text-moderation)${ID}`),
  { family: 'openai-o', re: /(?<![A-Za-z0-9_.-])o[1-9](?:-(?:mini|pro|preview|high|low)|-\d{4}-\d{2}-\d{2})*(?![A-Za-z0-9_.-])/g },
  fam('claude', `${B}claude-[A-Za-z0-9._-]+`, 'gi',
    (id) => /\d/.test(id) || /^claude-(?:opus|sonnet|haiku|instant)(?![a-z])/i.test(id)),
  fam('embedding', `${B}(?:text-embedding|gemini-embedding|text-multilingual-embedding|embed-(?:english|multilingual|v\\d)|voyage|nomic-embed|mxbai-embed|snowflake-arctic-embed)-[A-Za-z0-9._-]+`),
  fam('gemini', `${B}gemini-(?:\\d|pro|flash|ultra|nano|exp|embedding)${ID}`),
  fam('llama', `${B}(?:llama-?\\d|llama-(?:guard|vision))[A-Za-z0-9._:-]*`),
  fam('mistral', `${B}(?:open-)?(?:mistral|mixtral|codestral|ministral|pixtral|devstral|magistral)-(?:[a-z]*\\d|large|small|medium|tiny|nemo|latest|instruct|embed|ocr|saba)${ID}`),
  fam('qwen', `${B}qwen(?:\\d|-(?:max|plus|turbo|vl|long|coder|omni))[A-Za-z0-9._:-]*`),
  fam('deepseek', `${B}deepseek-(?:chat|reasoner|coder|r\\d|v\\d|llm|math|vl)${ID}`),
  fam('grok', `${B}grok-?(?:\\d|beta|code|vision|mini)${ID}`),
  fam('cohere-command', `${B}command-(?:r|a)(?![A-Za-z0-9])[A-Za-z0-9._-]*`),
  fam('gemma', `${B}(?:code|pali)?gemma-?\\d[A-Za-z0-9._:-]*`),
  fam('phi', `${B}phi-?\\d[A-Za-z0-9._:-]*`),
  fam('bedrock', `${B}(?:[a-z]{2}\\.)?(?:amazon\\.(?:nova|titan)|ai21\\.jamba|cohere\\.command|meta\\.llama|anthropic\\.claude|mistral\\.(?:mistral|mixtral))[A-Za-z0-9._:-]*`),
  fam('titan', `${B}titan-(?:text|embed|image|multimodal)${ID}`),
  fam('sonar', `${B}sonar-(?:pro|reasoning|deep|small|medium|large|online|huge)${ID}`),
  fam('jamba', `${B}jamba-?(?:\\d|large|mini|instruct)${ID}`),
  fam('kimi', `${B}(?:kimi-(?:k\\d|latest|thinking|dev|vl)|moonshot-v\\d)${ID}`),
  fam('glm', `${B}(?:chat)?glm-?\\d${ID}`),
  fam('yi', `${B}yi-(?:\\d|large|lightning|medium|vision|coder)${ID}`),
  // Hugging Face repo paths for model orgs, plus well-known sentence-transformer / reranker names.
  fam('hf-path', `${B}(?:meta-llama|mistralai|Qwen|deepseek-ai|xai-org|01-ai|THUDM|zai-org|moonshotai|ai21labs|CohereForAI|CohereLabs|sentence-transformers|cross-encoder|BAAI|intfloat|nomic-ai|jinaai)/[A-Za-z0-9._-]+`),
  fam('hf-path', `${B}(?:google|microsoft|openai|amazon|nvidia|allenai|tiiuae|HuggingFaceTB|ibm-granite)/(?:gemma|codegemma|paligemma|phi|gpt-oss|gpt2|flan|t5|mt5|bert|falcon|olmo|llama|nemotron|granite|siglip|vit)${ID}`),
  fam('transformer-name', `${B}(?:all-(?:MiniLM|mpnet|distilroberta)|paraphrase-(?:MiniLM|multilingual|mpnet)|multi-qa-|ms-marco-|msmarco-|bge-(?:small|base|large|m3|reranker)|e5-(?:small|base|large|mistral)|gte-(?:small|base|large|qwen))${ID}`),
];

/**
 * Model-ID-looking tokens outside URLs. Returns [{id, family, index}] sorted by position.
 * Markdown link targets and reference definitions are ignored ONLY outside code fences and inline
 * code, so `registry["x"](model="gpt-4o")` inside code is still caught.
 */
export function findModelIds(text) {
  const code = [...fencedRanges(text).ranges, ...inlineCodeSpans(text)];
  const mask = (re) => (src) =>
    src.replace(re, (m, ...rest) => {
      const index = rest[rest.length - 2];
      return inRanges(code, index) ? m : ' '.repeat(m.length);
    });
  let scan = text.replace(/https?:\/\/[^\s)>\]"'`]+/g, (m) => ' '.repeat(m.length));
  scan = mask(/\]\([^)\n]*\)/g)(scan); // inline link targets
  scan = mask(/^ {0,3}\[[^\]\n]+\]:[ \t]*\S+/gm)(scan); // reference definitions
  const found = [];
  for (const { family, re, keep } of MODEL_PATTERNS) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(scan)) !== null) {
      const id = m[0].replace(/[.:-]+$/, '');
      if (keep && !keep(id)) continue;
      found.push({ id, family, index: m.index });
    }
  }
  return found.sort((a, b) => a.index - b.index);
}

export function lintModelIds(rel, text) {
  if (rel === MODELS_PARTIAL) return { errors: [] };
  const { ranges, errors: structural } = legacyRanges(text);
  const errors = structural.map((e) => `${rel}: ${e}`);
  for (const hit of findModelIds(text)) {
    if (inRanges(ranges, hit.index)) continue;
    errors.push(
      `${rel}:${lineOf(text, hit.index)}: model ID "${hit.id}" (${hit.family}) outside ${MODELS_PARTIAL} and any ` +
        `<details><summary>Legacy...</summary> block; use an env var or a placeholder`,
    );
  }
  return { errors };
}

// ---------------------------------------------------------------- deprecation denylist

export function parseDeprecations(yamlText) {
  const doc = yaml.load(yamlText, { schema: yaml.CORE_SCHEMA });
  const errors = [];
  const rules = [];
  if (!doc || !Array.isArray(doc.deprecations)) {
    return { rules, errors: ['deprecations.yaml: top-level "deprecations" list is required'] };
  }
  const seen = new Set();
  doc.deprecations.forEach((r, i) => {
    const where = `deprecations[${i}]${r?.id ? ` (${r.id})` : ''}`;
    if (!r || typeof r.id !== 'string' || typeof r.pattern !== 'string' || typeof r.hint !== 'string' || !r.hint.trim()) {
      errors.push(`${where}: id, pattern and hint are required strings`);
      return;
    }
    if (seen.has(r.id)) errors.push(`${where}: duplicate id`);
    seen.add(r.id);
    const allowIn = r.allow_in ?? [];
    if (!Array.isArray(allowIn) || allowIn.some((p) => typeof p !== 'string' || /[*?{}[\]]/.test(p))) {
      errors.push(`${where}: allow_in must be a list of exact page paths (no globs)`);
      return;
    }
    try {
      rules.push({
        id: r.id,
        re: new RegExp(r.pattern, `${String(r.flags ?? '').replace(/g/g, '')}g`),
        hint: r.hint.trim(),
        allowIn,
        allowInLegacyDetails: r.allow_in_legacy_details === true,
      });
    } catch (e) {
      errors.push(`${where}: invalid regex: ${e.message}`);
    }
  });
  return { rules, errors };
}

/** Inline code that is really code (an import or a call), not just a name in prose. */
const looksLikeCode = (span) => /\bimport\b|\(/.test(span);

/**
 * files: Map<relPath, text> of routed pages.
 *
 * Allowance semantics:
 *  - `allow_in` exempts PROSE on those exact pages only (text outside code fences; an inline-code
 *    span that is merely a name is prose, one holding an import or a call is code).
 *  - `allow_in_legacy_details` exempts matches (code included) inside a real
 *    <details><summary>Legacy...</summary> block or an explicit "Legacy" heading section.
 */
export function lintDeprecations(files, rules) {
  const errors = [];
  const allowUsed = new Map(); // `${rule}|${page}` -> matched?
  for (const rule of rules) {
    for (const page of rule.allowIn) {
      if (!files.has(page) || page === MODELS_PARTIAL) {
        errors.push(`deprecations.yaml: ${rule.id}: allow_in path "${page}" is not an existing routed page`);
      } else {
        allowUsed.set(`${rule.id}|${page}`, false);
      }
    }
  }
  const cache = new Map();
  const structure = (rel, text) => {
    if (!cache.has(rel)) {
      cache.set(rel, {
        fences: fencedRanges(text).ranges,
        spans: inlineCodeSpans(text),
        legacy: [...legacyRanges(text).ranges, ...legacySectionRanges(text)],
      });
    }
    return cache.get(rel);
  };
  for (const [rel, text] of files) {
    for (const rule of rules) {
      rule.re.lastIndex = 0;
      let m;
      while ((m = rule.re.exec(text)) !== null) {
        if (m[0] === '') rule.re.lastIndex++;
        const st = structure(rel, text);
        let note = '';
        if (rule.allowIn.includes(rel)) {
          allowUsed.set(`${rule.id}|${rel}`, true);
          const span = st.spans.find((x) => m.index >= x.start && m.index < x.end);
          if (!inRanges(st.fences, m.index) && !(span && looksLikeCode(span.text))) continue;
          note = ' (allow_in covers prose only, not code)';
        }
        if (rule.allowInLegacyDetails) {
          if (inRanges(st.legacy, m.index)) continue;
          note += ' (code is allowed only inside a <details><summary>Legacy...</summary> block or a "Legacy" heading section)';
        }
        errors.push(`${rel}:${lineOf(text, m.index)}: deprecated "${m[0]}" [${rule.id}]${note} -- ${rule.hint}`);
      }
    }
  }
  for (const [key, used] of allowUsed) {
    if (!used) {
      const [id, page] = key.split('|');
      errors.push(`deprecations.yaml: ${id}: stale allow_in "${page}" (page has no match for the pattern); remove it`);
    }
  }
  return { errors };
}

// ---------------------------------------------------------------- last_verified

const DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function lintLastVerified(rel, text, today) {
  const errors = [];
  const warnings = [];
  let fm;
  try {
    fm = parseFrontmatter(text);
  } catch (e) {
    return { errors: [`${rel}: invalid front matter YAML: ${e.reason ?? e.message}`], warnings };
  }
  const value = fm?.data?.last_verified;
  if (value === undefined) {
    errors.push(`${rel}: missing last_verified in front matter (run: node scripts/add-last-verified.mjs)`);
    return { errors, warnings };
  }
  const m = typeof value === 'string' ? DATE.exec(value) : null;
  const t = m ? Date.UTC(+m[1], +m[2] - 1, +m[3]) : NaN;
  const valid = m && new Date(t).toISOString().startsWith(value);
  if (!valid) {
    errors.push(`${rel}: last_verified "${value}" is not a valid YYYY-MM-DD date`);
    return { errors, warnings };
  }
  const todayMs = Date.UTC(+today.slice(0, 4), +today.slice(5, 7) - 1, +today.slice(8, 10));
  const age = Math.floor((todayMs - t) / 86400000);
  if (age < 0) errors.push(`${rel}: last_verified ${value} is in the future (today ${today})`);
  else if (age > STALE_AFTER_DAYS) warnings.push(`${rel}: last_verified ${value} is ${age} days old (> ${STALE_AFTER_DAYS}); re-verify the page`);
  return { errors, warnings };
}

// ---------------------------------------------------------------- orchestration

/** files: Map<relPath, text> of every docs/**\/*.md(x) page, including the _shared partial. */
export function lintContent({ files, deprecationsYaml, today }) {
  const errors = [];
  const warnings = [];
  const parsed = parseDeprecations(deprecationsYaml);
  errors.push(...parsed.errors);
  const routed = new Map([...files].filter(([rel]) => !rel.includes('/_shared/')));
  for (const [rel, text] of routed) {
    errors.push(...lintModelIds(rel, text).errors);
    const lv = lintLastVerified(rel, text, today);
    errors.push(...lv.errors);
    warnings.push(...lv.warnings);
  }
  if (!files.has(MODELS_PARTIAL)) errors.push(`${MODELS_PARTIAL}: shared model reference is missing`);
  errors.push(...lintDeprecations(routed, parsed.rules).errors);
  return { errors, warnings };
}
