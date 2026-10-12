#!/usr/bin/env node
// Content lint: model IDs, deprecation denylist, last_verified, python fence syntax.
// Usage: node scripts/check-content.mjs [--today YYYY-MM-DD] [--no-python] [--root DIR] [--rules FILE]
// --root DIR reads docs/ from DIR instead of the repository (used by the CLI integration test with
// a temporary tree; the real docs are never written); --rules FILE overrides scripts/deprecations.yaml.
// Exit 1 on any error; stale last_verified (> 120 days) only warns (stderr + GitHub job summary).
import { appendFileSync, readdirSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { lintContent } from './lib/content-lint.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

export function loadDocs(rootDir = root) {
  const files = new Map();
  const walk = (dir) => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, e.name);
      if (e.isDirectory()) walk(full);
      else if (/\.mdx?$/.test(e.name)) files.set(relative(rootDir, full).split(sep).join('/'), readFileSync(full, 'utf8'));
    }
  };
  walk(join(rootDir, 'docs'));
  return files;
}

const PAGE_LINE = /^(SYNTAX|FENCE|READ)\b/;

/**
 * Turn a finished python checker child (spawnSync result shape) into error strings.
 * A nonzero exit/signal that printed no SYNTAX/FENCE/READ line must NOT pass silently: report the
 * status or signal plus stderr (and stdout, if any) so a crashed checker fails the run.
 */
export function pythonCheckErrors(py) {
  if (py.error) return [`python3 is required for the python fence syntax check: ${py.error.message}`];
  if (py.status === 0 && !py.signal) return [];
  const stdout = (py.stdout ?? '').toString();
  const lines = stdout.split('\n').filter((l) => PAGE_LINE.test(l));
  if (lines.length) return lines;
  const how = py.signal ? `was killed by signal ${py.signal}` : `exited with status ${py.status}`;
  const stderr = (py.stderr ?? '').toString().trim();
  const out = stdout.trim();
  return [
    `python fence syntax check ${how} without reporting any SYNTAX/FENCE/READ line` +
      (stderr ? `; stderr: ${stderr.split('\n').slice(-5).join(' | ')}` : '; stderr was empty') +
      (out ? `; stdout: ${out.split('\n').slice(-3).join(' | ')}` : ''),
  ];
}

function main(argv) {
  const ti = argv.indexOf('--today');
  const today = ti >= 0 ? argv[ti + 1] : process.env.CONTENT_TODAY ?? new Date().toISOString().slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(today)) {
    console.error(`invalid --today "${today}"`);
    return 2;
  }
  const ri = argv.indexOf('--root');
  const docsRoot = ri >= 0 ? argv[ri + 1] : root;
  if (!docsRoot) {
    console.error('--root needs a directory');
    return 2;
  }
  const rulesFile = argv.indexOf('--rules') >= 0 ? argv[argv.indexOf('--rules') + 1] : join(root, 'scripts/deprecations.yaml');
  const files = loadDocs(docsRoot);
  const { errors, warnings } = lintContent({
    files,
    deprecationsYaml: readFileSync(rulesFile, 'utf8'),
    today,
  });
  const pages = [...files.keys()].filter((p) => !p.includes('/_shared/')).sort();
  if (!argv.includes('--no-python')) {
    const py = spawnSync('python3', [join(root, 'examples/langchain-v1/check_doc_imports.py'), '--syntax-only', ...pages], {
      cwd: docsRoot,
      encoding: 'utf8',
    });
    errors.push(...pythonCheckErrors(py));
  }
  for (const w of warnings) {
    console.warn(`WARN  ${w}`);
    if (process.env.GITHUB_ACTIONS === 'true') {
      const message = w.replaceAll('%', '%25').replaceAll('\r', '%0D').replaceAll('\n', '%0A');
      console.warn(`::warning title=Content freshness::${message}`);
    }
  }
  for (const e of errors) console.error(`ERROR ${e}`);
  const summary =
    `content check: ${pages.length} pages, ${errors.length} error(s), ${warnings.length} warning(s). ` +
    'last_verified = date of the last audit-scoped content review of the page (per-page unverified APIs ' +
    'are listed in reports/); it is NOT live certification and does not mean every claim was re-checked ' +
    'against current vendor sources. Python examples are only syntax-checked (and, via ' +
    'check_doc_imports.py, import-checked for tracked pages) -- not executed.';
  console.log(summary);
  if (process.env.GITHUB_STEP_SUMMARY) {
    const md = [
      '### Content check',
      summary,
      ...(errors.length ? ['', '**Errors**', ...errors.map((e) => `- ${e}`)] : []),
      ...(warnings.length ? ['', '**Warnings** (do not fail the run)', ...warnings.map((w) => `- ${w}`)] : []),
      '',
    ].join('\n');
    try {
      appendFileSync(process.env.GITHUB_STEP_SUMMARY, md);
    } catch (e) {
      console.error(`could not write GITHUB_STEP_SUMMARY: ${e.message}`);
    }
  }
  return errors.length ? 1 : 0;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) process.exit(main(process.argv.slice(2)));
