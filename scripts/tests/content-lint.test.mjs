import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  findModelIds, legacyRanges, legacySectionRanges, lintModelIds, lintDeprecations, parseDeprecations,
  lintLastVerified, lintContent, MODELS_PARTIAL,
} from '../lib/content-lint.mjs';
import { setLastVerified } from '../add-last-verified.mjs';
import { loadDocs, pythonCheckErrors } from '../check-content.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const TODAY = '2026-10-12';
const page = (body, extra = 'last_verified: 2026-10-12') => `---\ntitle: T\n${extra}\n---\n\n${body}\n`;
const ids = (text) => findModelIds(text).map((h) => h.id);

// ------------------------------------------------------------ model-ID recognition

test('recognizes model IDs across vendors', () => {
  const text = [
    'gpt-4o-mini gpt-4.1 chatgpt-4o-latest gpt-5.2-pro o1 o3-mini o1-preview',
    'claude-3-5-sonnet-20241022 claude-sonnet-4-5 claude-opus-4 claude-fable-5-1',
    'text-embedding-3-small gemini-embedding-001 gemini-1.5-pro gemini-2.5-flash',
    'llama3.2:3b llama-3.1-70b meta-llama/Llama-3.1-8B-Instruct',
    'mistral-large-latest mixtral-8x7b open-mistral-nemo codestral-2501',
    'qwen2.5-coder qwen3-32b qwen-max Qwen/Qwen2.5-7B-Instruct deepseek-chat deepseek-r1',
  ].join('\n');
  const found = new Set(ids(text));
  for (const want of [
    'gpt-4o-mini', 'gpt-4.1', 'chatgpt-4o-latest', 'gpt-5.2-pro', 'o1', 'o3-mini', 'o1-preview',
    'claude-3-5-sonnet-20241022', 'claude-sonnet-4-5', 'claude-opus-4', 'claude-fable-5-1',
    'text-embedding-3-small', 'gemini-embedding-001', 'gemini-1.5-pro', 'gemini-2.5-flash',
    'llama3.2:3b', 'llama-3.1-70b', 'meta-llama/Llama-3.1-8B-Instruct',
    'mistral-large-latest', 'mixtral-8x7b', 'open-mistral-nemo', 'codestral-2501',
    'qwen2.5-coder', 'qwen3-32b', 'qwen-max', 'Qwen/Qwen2.5-7B-Instruct', 'deepseek-chat', 'deepseek-r1',
  ]) assert.ok(found.has(want), `missing ${want}; got ${[...found]}`);
});

test('does not flag product names, packages, URLs or placeholders', () => {
  const text = [
    'The Claude Agent SDK and claude-agent-sdk and Claude Code (claude-code) are products.',
    'LlamaIndex, llama-index-core, llama_index and the LlamaIndex tokenizer.',
    'Gemini, Mistral AI, Qwen, DeepSeek, Gemma, Phi, Grok, Kimi, Titan, Sonar and o1-style reasoning words.',
    'See https://platform.claude.com/docs/en/claude-sonnet-4-5 and [x](./gpt-4o-notes.md).',
    'AGENT_MODEL=<your-model-id> and `os.environ["AGENT_MODEL"]`; version 2026-10-12.',
  ].join('\n');
  assert.deepEqual(ids(text), []);
});

test('matching is case-insensitive and numbered prose model names are flagged', () => {
  assert.deepEqual(ids('GPT-4o and Claude-Sonnet-4-5 and GEMINI-2.5-FLASH and Llama3.2:3b'),
    ['GPT-4o', 'Claude-Sonnet-4-5', 'GEMINI-2.5-FLASH', 'Llama3.2:3b']);
});

test('recognizes OpenAI image/realtime/audio/oss IDs', () => {
  assert.deepEqual(ids('gpt-image-1 gpt-realtime gpt-audio gpt-oss-120b GPT-OSS-20B whisper-1 dall-e-3'),
    ['gpt-image-1', 'gpt-realtime', 'gpt-audio', 'gpt-oss-120b', 'GPT-OSS-20B', 'whisper-1', 'dall-e-3']);
});

test('recognizes other vendor families (Grok, Cohere, Gemma, Phi, Nova, Sonar, Titan, Jamba, Kimi, GLM, Yi)', () => {
  const want = ['grok-4', 'grok-code-fast-1', 'command-r-plus', 'command-a-03-2025', 'gemma-3-27b', 'gemma2:9b',
    'phi-4', 'phi3:mini', 'amazon.nova-pro-v1:0', 'us.amazon.nova-lite-v1:0', 'sonar-pro', 'sonar-deep-research',
    'titan-text-express-v1', 'amazon.titan-embed-text-v2:0', 'jamba-1.5-large', 'kimi-k2', 'moonshot-v1-8k',
    'glm-4.5', 'glm4', 'yi-34b', 'yi-lightning'];
  const got = new Set(ids(want.join('\n')));
  for (const w of want) assert.ok(got.has(w), `missing ${w}; got ${[...got]}`);
});

test('Hugging Face / sentence-transformer style names are detected; plain words and repo names are not', () => {
  const want = ['sentence-transformers/all-MiniLM-L6-v2', 'all-MiniLM-L6-v2', 'cross-encoder/ms-marco-MiniLM-L-6-v2',
    'BAAI/bge-reranker-v2-m3', 'bge-large-en-v1.5', 'intfloat/e5-large-v2', 'google/gemma-2-9b-it',
    'microsoft/Phi-3-mini-4k-instruct', 'openai/gpt-oss-20b', 'cross-encoder/nli-deberta-v3-base'];
  const got = new Set(ids(want.join('\n')));
  for (const w of want) assert.ok(got.has(w), `missing ${w}; got ${[...got]}`);
  assert.deepEqual(ids('microsoft/autogen, google/adk-python, the phi coefficient, a command-line tool, yi and kimi'), []);
});

test('link targets are ignored in prose but not inside code fences or inline code', () => {
  assert.deepEqual(ids('See [notes](./gpt-4o-notes.md) and [x](claude-3-opus.md).\n\n[ref]: ./gemini-2.5-flash.md\n'), []);
  assert.deepEqual(ids('```python\nregistry["x"](model="gpt-4o")\n```'), ['gpt-4o']);
  assert.deepEqual(ids('Call `registry["x"](model="gpt-4o")` here.'), ['gpt-4o']);
  assert.deepEqual(ids('```\n[ref]: ./gemini-2.5-flash.md\n```'), ['gemini-2.5-flash.md']);
});

// ------------------------------------------------------------ legacy bounds

const legacy = (inner, summary = 'Legacy: old ids') =>
  `<details>\n<summary>${summary}</summary>\n\n${inner}\n\n</details>`;

test('model IDs are allowed in the shared partial and inside real Legacy details', () => {
  assert.deepEqual(lintModelIds(MODELS_PARTIAL, 'gpt-4o and claude-3-5-sonnet').errors, []);
  assert.deepEqual(lintModelIds('docs/a.md', page(legacy('Used `gpt-4o` and `claude-3-opus`.'))).errors, []);
  assert.deepEqual(lintModelIds('docs/a.md', page(legacy('`o1`', 'Legacy <code>x</code>'))).errors, []);
});

test('model IDs outside the partial or Legacy details fail, with file:line', () => {
  const { errors } = lintModelIds('docs/a.md', page('Use gpt-4o here.'));
  assert.equal(errors.length, 1);
  assert.match(errors[0], /^docs\/a\.md:\d+: model ID "gpt-4o"/);
});

test('no whole-page loophole: only the bounded details block is exempt', () => {
  const text = page(`before gpt-4o-mini\n\n${legacy('inside claude-3-opus')}\n\nafter claude-3-haiku`);
  const found = lintModelIds('docs/a.md', text).errors.join('\n');
  assert.match(found, /gpt-4o-mini/);
  assert.match(found, /claude-3-haiku/);
  assert.doesNotMatch(found, /claude-3-opus/);
});

test('non-Legacy details do not exempt model IDs', () => {
  const text = page('<details>\n<summary>Answer</summary>\n\ngpt-4o\n\n</details>');
  assert.equal(lintModelIds('docs/a.md', text).errors.length, 1);
});

test('legacy markup inside a code fence or inline code is not a real block', () => {
  const fenced = page('```html\n<details><summary>Legacy</summary>\n```\n\ngpt-4o\n\n</details>');
  assert.ok(lintModelIds('docs/a.md', fenced).errors.some((e) => /gpt-4o/.test(e)));
  const inline = page('Write `<details><summary>Legacy</summary>` then gpt-4o.\n');
  assert.ok(lintModelIds('docs/a.md', inline).errors.some((e) => /gpt-4o/.test(e)));
  assert.deepEqual(legacyRanges(fenced).ranges, []);
});

test('an unclosed Legacy block is an error and never extends to the end of the page', () => {
  const text = page('<details>\n<summary>Legacy</summary>\n\ngpt-4o');
  const { errors } = lintModelIds('docs/a.md', text);
  assert.ok(errors.some((e) => /unclosed <details>/.test(e)));
  assert.ok(errors.some((e) => /model ID "gpt-4o"/.test(e)));
});

test('nested details: Legacy covers inner blocks; inner Legacy does not cover the outer', () => {
  const outer = page(legacy('<details>\n<summary>Why</summary>\n\ngpt-4o\n\n</details>'));
  assert.deepEqual(lintModelIds('docs/a.md', outer).errors, []);
  const inner = page(`<details>\n<summary>Q</summary>\n\ngpt-4o\n\n${legacy('claude-3-opus')}\n\n</details>`);
  const msg = lintModelIds('docs/a.md', inner).errors.join('\n');
  assert.match(msg, /gpt-4o/);
  assert.doesNotMatch(msg, /claude-3-opus/);
});

// ------------------------------------------------------------ deprecations

const rulesYaml = `
deprecations:
  - id: old-thing
    pattern: '\\bOldThing\\b'
    hint: use NewThing
    allow_in:
      - docs/hist.md
  - id: budget
    pattern: 'budget_tokens'
    hint: use adaptive thinking
    allow_in_legacy_details: true
`;
const rules = () => {
  const r = parseDeprecations(rulesYaml);
  assert.deepEqual(r.errors, []);
  return r.rules;
};

test('deprecated API on a non-allowed page fails with its hint; allow_in page passes', () => {
  const files = new Map([
    ['docs/hist.md', page('Historically `OldThing` was used.')],
    ['docs/cur.md', page('Call OldThing().')],
  ]);
  const { errors } = lintDeprecations(files, rules());
  assert.equal(errors.length, 1);
  assert.match(errors[0], /^docs\/cur\.md:\d+: deprecated "OldThing" \[old-thing\].*use NewThing/);
});

test('allow_in must name an existing page and still match (no stale or phantom allowances)', () => {
  const files = new Map([['docs/hist.md', page('nothing deprecated here')]]);
  const stale = lintDeprecations(files, rules()).errors.join('\n');
  assert.match(stale, /stale allow_in "docs\/hist\.md"/);
  const phantom = lintDeprecations(new Map([['docs/other.md', page('x')]]), rules()).errors.join('\n');
  assert.match(phantom, /allow_in path "docs\/hist\.md" is not an existing routed page/);
});

test('allow_in rejects globs and bad rules are reported', () => {
  const bad = parseDeprecations("deprecations:\n  - id: a\n    pattern: 'x'\n    hint: h\n    allow_in: ['docs/*.md']\n  - id: b\n    pattern: '('\n    hint: h\n  - id: c\n");
  assert.equal(bad.errors.length, 3);
});

const budgetRules = () => rules().filter((r) => r.id === 'budget');

test('budget_tokens is allowed only inside a real Legacy details block', () => {
  const ok = new Map([['docs/a.md', page(legacy('`budget_tokens`'))]]);
  assert.deepEqual(lintDeprecations(ok, budgetRules()).errors, []);
  const outside = new Map([['docs/a.md', page(`budget_tokens\n\n${legacy('fine')}\n\nbudget_tokens again`)]]);
  assert.equal(lintDeprecations(outside, budgetRules()).errors.length, 2);
  const faked = new Map([['docs/a.md', page('```\n<details><summary>Legacy</summary>\n```\nbudget_tokens\n</details>')]]);
  assert.equal(lintDeprecations(faked, budgetRules()).errors.length, 1);
});

// ------------------------------------------------------------ allow_in = prose only; Legacy sections

const reactRules = () => {
  const r = parseDeprecations(`
deprecations:
  - id: create-react-agent
    pattern: '\\bcreate_react_agent\\b'
    hint: use create_agent
    allow_in:
      - docs/hist.md
    allow_in_legacy_details: true
`);
  assert.deepEqual(r.errors, []);
  return r.rules;
};
const fenced = (code) => '```python\n' + code + '\n```';
const depErrors = (rel, body, extra = []) =>
  lintDeprecations(new Map([[rel, page(body)], ['docs/hist.md', page('create_react_agent is replaced.')], ...extra]), reactRules()).errors
    .filter((e) => e.startsWith(rel + ':'));

test('create_react_agent is forbidden in every import/call format on a non-allowed page', () => {
  const formats = {
    single: 'from langgraph.prebuilt import create_react_agent',
    'single with others': 'from langgraph.prebuilt import ToolNode, create_react_agent',
    multiline: 'from langgraph.prebuilt import (\n    ToolNode,\n    create_react_agent,\n)',
    alias: 'from langgraph.prebuilt import create_react_agent as make_agent\nagent = make_agent(model, tools)',
    'module alias': 'import langgraph.prebuilt as p\nagent = p.create_react_agent(model, tools)',
    'backslash continuation': 'from langgraph.prebuilt import \\\n    create_react_agent',
    'bare call': 'agent = create_react_agent(model, tools)',
    'dotted path': 'agent = langgraph.prebuilt.create_react_agent(model, tools)',
  };
  for (const [name, code] of Object.entries(formats)) {
    assert.ok(depErrors('docs/cur.md', fenced(code)).length >= 1, `not caught: ${name}`);
  }
});

test('allow_in exempts historical prose on the exact page but never code there', () => {
  const prose = 'It replaces the older `langgraph.prebuilt.create_react_agent`.\n\nThe old create_react_agent is gone.';
  assert.deepEqual(lintDeprecations(new Map([['docs/hist.md', page(prose)]]), reactRules()).errors, []);
  const codeOnAllowed = (code) => lintDeprecations(new Map([['docs/hist.md', page(`create_react_agent history.\n\n${code}`)]]), reactRules()).errors;
  assert.equal(codeOnAllowed(fenced('from langgraph.prebuilt import create_react_agent')).length, 1);
  assert.equal(codeOnAllowed(fenced('from langgraph.prebuilt import (\n    create_react_agent as cra,\n)')).length, 1);
  assert.equal(codeOnAllowed('Use `from langgraph.prebuilt import create_react_agent` today.').length, 1);
  assert.equal(codeOnAllowed('Use `create_react_agent(model, tools)` today.').length, 1);
  assert.equal(depErrors('docs/other.md', 'The old create_react_agent is gone.').length, 1);
});

test('Legacy details blocks and explicit Legacy heading sections allow code automatically', () => {
  const code = fenced('from langgraph.prebuilt import create_react_agent');
  assert.deepEqual(depErrors('docs/cur.md', legacy(code)), []);
  assert.deepEqual(depErrors('docs/cur.md', `## Legacy: \`create_react_agent\`\n\n${code}\n\n### Sub heading\n\n${code}`), []);
});

test('a Legacy heading section is bounded by the next heading of the same or higher level', () => {
  const code = fenced('agent = create_react_agent(m, t)');
  const text = page(`## Legacy: old\n\n${code}\n\n### detail\n\n${code}\n\n## Current\n\n${code}\n`);
  const errs = lintDeprecations(new Map([['docs/cur.md', text], ['docs/hist.md', page('create_react_agent')]]), reactRules()).errors;
  assert.equal(errs.length, 1);
  assert.match(errs[0], /^docs\/cur\.md:\d+/);
  const lines = text.split('\n');
  assert.ok(Number(/:(\d+):/.exec(errs[0])[1]) > lines.findIndex((l) => l === '## Current'));
});

test('a Legacy heading inside a code fence is not a Legacy section', () => {
  const text = page('```md\n## Legacy: x\n```\n\n' + fenced('agent = create_react_agent(m, t)'));
  assert.deepEqual(legacySectionRanges(text), []);
  assert.equal(depErrors('docs/cur.md', '```md\n## Legacy: x\n```\n\n' + fenced('agent = create_react_agent(m, t)')).length, 1);
});

// ------------------------------------------------------------ last_verified

test('last_verified: missing and malformed and future are errors', () => {
  assert.match(lintLastVerified('p', '---\ntitle: T\n---\nbody', TODAY).errors[0], /missing last_verified/);
  assert.match(lintLastVerified('p', page('x', 'last_verified: 2026-13-40'), TODAY).errors[0], /not a valid/);
  assert.match(lintLastVerified('p', page('x', 'last_verified: yesterday'), TODAY).errors[0], /not a valid/);
  assert.match(lintLastVerified('p', page('x', 'last_verified: 2026-10-13'), TODAY).errors[0], /future/);
  assert.match(lintLastVerified('p', 'no front matter', TODAY).errors[0], /missing/);
});

test('last_verified: >120 days warns but never errors; 120 days and fresh are clean', () => {
  const old = lintLastVerified('p', page('x', 'last_verified: 2026-06-12'), TODAY); // 122 days
  assert.deepEqual(old.errors, []);
  assert.match(old.warnings[0], /122 days old/);
  const edge = lintLastVerified('p', page('x', 'last_verified: 2026-06-14'), TODAY); // 120 days
  assert.deepEqual([edge.errors, edge.warnings], [[], []]);
  assert.deepEqual(lintLastVerified('p', page('x'), TODAY), { errors: [], warnings: [] });
});

// ------------------------------------------------------------ orchestration + metadata script

test('lintContent ignores _shared for routing checks but requires the partial', () => {
  const files = new Map([['docs/a.md', page('hello')]]);
  const missing = lintContent({ files, deprecationsYaml: rulesYaml.replace(/allow_in:\n\s+- docs\/hist.md/, ''), today: TODAY });
  assert.ok(missing.errors.some((e) => /shared model reference is missing/.test(e)));
  files.set(MODELS_PARTIAL, 'gpt-4o claude-3-opus (no front matter needed)');
  const ok = lintContent({ files, deprecationsYaml: rulesYaml.replace(/allow_in:\n\s+- docs\/hist.md/, ''), today: TODAY });
  assert.deepEqual(ok.errors, []);
});

test('setLastVerified: targeted insert/replace, idempotent, body untouched', () => {
  const src = '---\ntitle: "A: b"\nslug: /x\n---\n\n# Body\n---\nkept\n';
  const once = setLastVerified(src, '2026-10-12');
  assert.equal(once, '---\ntitle: "A: b"\nslug: /x\nlast_verified: 2026-10-12\n---\n\n# Body\n---\nkept\n');
  assert.equal(setLastVerified(once, '2026-10-12'), null);
  assert.equal(setLastVerified(once, '2026-11-01'), once.replace('2026-10-12', '2026-11-01'));
  assert.throws(() => setLastVerified('# no fm', '2026-10-12'));
});

// ------------------------------------------------------------ the real repository

test('real deprecations.yaml is valid and every allowance is genuine', () => {
  const parsed = parseDeprecations(readFileSync(join(root, 'scripts/deprecations.yaml'), 'utf8'));
  assert.deepEqual(parsed.errors, []);
  const files = loadDocs(root);
  files.delete(MODELS_PARTIAL);
  const allowanceErrors = lintDeprecations(files, parsed.rules).errors.filter((e) => /allow_in/.test(e));
  assert.deepEqual(allowanceErrors, []);
});

test('real shared model partial exists as .md and the old .mdx is gone', () => {
  const files = loadDocs(root);
  assert.ok(files.has(MODELS_PARTIAL));
  assert.ok(![...files.keys()].some((p) => p.endsWith('_shared/models.mdx')));
});

// ------------------------------------------------------------ python fence helper

test('python --syntax-only fails on a bad fence and passes on a good one', { skip: spawnSync('python3', ['-V']).error }, () => {
  const dir = mkdtempSync(join(tmpdir(), 'fences-'));
  const bad = join(dir, 'bad.md');
  const good = join(dir, 'good.md');
  writeFileSync(bad, '# t\n\n```python\ndef broken(:\n    pass\n```\n');
  writeFileSync(good, '# t\n\n```python\nprint("ok")\ns = """\n    ```\n"""\n```\n');
  const run = (f) => spawnSync('python3', [join(root, 'examples/langchain-v1/check_doc_imports.py'), '--syntax-only', f], { encoding: 'utf8' });
  const b = run(bad);
  assert.equal(b.status, 1);
  assert.match(b.stdout, /SYNTAX .*bad\.md:4/);
  assert.equal(run(good).status, 0);
});

// ------------------------------------------------------------ python checker status handling

test('pythonCheckErrors: nonzero child without SYNTAX/FENCE lines is an error with stderr/status/signal', () => {
  assert.deepEqual(pythonCheckErrors({ status: 0, stdout: 'done', stderr: '' }), []);
  const crashed = pythonCheckErrors({ status: 1, stdout: '', stderr: 'Traceback\nboom' });
  assert.equal(crashed.length, 1);
  assert.match(crashed[0], /exited with status 1/);
  assert.match(crashed[0], /boom/);
  const silent = pythonCheckErrors({ status: 2, stdout: '', stderr: '' });
  assert.match(silent[0], /status 2.*stderr was empty/);
  const killed = pythonCheckErrors({ status: null, signal: 'SIGKILL', stdout: '', stderr: '' });
  assert.match(killed[0], /signal SIGKILL/);
  assert.match(pythonCheckErrors({ error: new Error('ENOENT') })[0], /python3 is required.*ENOENT/);
});

test('pythonCheckErrors: SYNTAX/FENCE/READ lines are passed through', () => {
  const out = 'SYNTAX  a.md:4 (block 1): bad\nFENCE   b.md: unclosed\nREAD    c.md: nope\nnoise\ndone, 3 failure(s)\n';
  assert.deepEqual(pythonCheckErrors({ status: 1, stdout: out, stderr: '' }), [
    'SYNTAX  a.md:4 (block 1): bad', 'FENCE   b.md: unclosed', 'READ    c.md: nope',
  ]);
});

const hasPython = !spawnSync('python3', ['-V']).error;

test('CLI on a temporary docs tree: undecodable UTF-8 page fails with a READ error, no traceback', { skip: !hasPython }, () => {
  const dir = mkdtempSync(join(tmpdir(), 'content-root-'));
  try {
    mkdirSync(join(dir, 'docs', '_shared'), { recursive: true });
    writeFileSync(join(dir, 'docs', '_shared', 'models.md'), 'models');
    writeFileSync(join(dir, 'rules.yaml'), 'deprecations: []\n');
    writeFileSync(join(dir, 'docs', 'good.md'), page('# fine\n\n```python\nprint(1)\n```'));
    writeFileSync(join(dir, 'docs', 'bad.md'), Buffer.concat([
      Buffer.from(page('# corrupt\n\n')), Buffer.from([0xff, 0xfe, 0xfd]), Buffer.from('\n'),
    ]));
    const run = spawnSync('node', [join(root, 'scripts/check-content.mjs'), '--root', dir, '--rules', join(dir, 'rules.yaml'), '--today', TODAY], { encoding: 'utf8' });
    assert.equal(run.status, 1, run.stdout + run.stderr);
    assert.match(run.stderr, /ERROR READ\s+docs\/bad\.md: not valid UTF-8/);
    assert.doesNotMatch(run.stderr, /Traceback/);
    assert.doesNotMatch(run.stderr, /good\.md/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('python --syntax-only: unreadable path reports READ (exit 1), stdout/stderr have no traceback', { skip: !hasPython }, () => {
  const run = spawnSync('python3', [join(root, 'examples/langchain-v1/check_doc_imports.py'), '--syntax-only', join(tmpdir(), 'definitely-missing-page.md')], { encoding: 'utf8' });
  assert.equal(run.status, 1);
  assert.match(run.stdout, /^READ .*definitely-missing-page\.md/m);
  assert.doesNotMatch(run.stderr, /Traceback/);
});

test('GITHUB_STEP_SUMMARY receives warnings without failing the run', { skip: !hasPython }, () => {
  const dir = mkdtempSync(join(tmpdir(), 'content-summary-'));
  try {
    mkdirSync(join(dir, 'docs', '_shared'), { recursive: true });
    writeFileSync(join(dir, 'docs', '_shared', 'models.md'), 'models');
    writeFileSync(join(dir, 'rules.yaml'), 'deprecations: []\n');
    writeFileSync(join(dir, 'docs', 'old.md'), page('# old', 'last_verified: 2026-01-01'));
    const summary = join(dir, 'summary.md');
    const run = spawnSync('node', [join(root, 'scripts/check-content.mjs'), '--root', dir, '--rules', join(dir, 'rules.yaml'), '--today', TODAY], {
      encoding: 'utf8', env: { ...process.env, GITHUB_STEP_SUMMARY: summary, GITHUB_ACTIONS: 'true' },
    });
    assert.equal(run.status, 0, run.stdout + run.stderr);
    assert.match(run.stderr, /WARN\s+docs\/old\.md: last_verified 2026-01-01/);
    assert.match(run.stderr, /::warning title=Content freshness::docs\/old\.md: last_verified/);
    assert.match(readFileSync(summary, 'utf8'), /Warnings.*\n- docs\/old\.md: last_verified/s);
    assert.match(run.stdout, /NOT live certification/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
