#!/usr/bin/env node
// Adds/updates `last_verified: <date>` in the front matter of EVERY routed docs page.
// Targeted edit: only that one front-matter line is inserted or replaced; each file is re-read
// immediately before writing so concurrent content edits to the body are never overwritten.
// Usage: node scripts/add-last-verified.mjs [--date 2026-10-12] [--dry-run]
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';
import { loadDocs } from './check-content.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Returns new text with last_verified set, or null when no change is needed. */
export function setLastVerified(text, date) {
  const m = /^---\n([\s\S]*?)\n---(?:\n|$)/.exec(text);
  if (!m) throw new Error('no front matter');
  const line = `last_verified: ${date}`;
  const re = /^last_verified:.*$/m;
  const body = re.test(m[1]) ? m[1].replace(re, line) : `${m[1]}\n${line}`;
  if (body === m[1]) return null;
  return `---\n${body}\n---${m[0].endsWith('\n') ? '\n' : ''}${text.slice(m[0].length)}`;
}

function main(argv) {
  const di = argv.indexOf('--date');
  const date = di >= 0 ? argv[di + 1] : '2026-10-12';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error(`invalid date ${date}`);
  const dry = argv.includes('--dry-run');
  let changed = 0;
  for (const rel of [...loadDocs().keys()].filter((p) => !p.includes('/_shared/')).sort()) {
    const abs = join(root, rel);
    const next = setLastVerified(readFileSync(abs, 'utf8'), date); // fresh read per file
    if (next === null) continue;
    if (!dry) writeFileSync(abs, next);
    changed++;
    console.log(`${dry ? 'would update' : 'updated'} ${rel}`);
  }
  console.log(`${changed} page(s) ${dry ? 'would change' : 'changed'}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main(process.argv.slice(2));
