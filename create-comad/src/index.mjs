#!/usr/bin/env node

import pc from 'picocolors';
import { selectOptions } from './steps/select-preset.mjs';
import { checkDeps, suggestFallback } from './steps/check-deps.mjs';
import { setupProject } from './steps/setup-project.mjs';

// ── Banner ─────────────────────────────────────────────────────────────
console.log();
console.log(pc.cyan('  comad-world'));
console.log(pc.dim('  Your interests. Your agents. Your knowledge graph.'));
console.log();

// ── Step 1-3: Interactive prompts ──────────────────────────────────────
const result = await selectOptions();
if (!result || !result.projectName) {
  console.log(pc.red('\n  Setup cancelled.'));
  process.exit(1);
}
const { projectName, preset, scope: rawScope } = result;

// ── Step 4: Check dependencies ─────────────────────────────────────────
console.log();
console.log(pc.bold('Checking dependencies...'));
const deps = checkDeps(rawScope);
const scope = suggestFallback(deps, rawScope);

// Bail if git is missing
if (!deps.git) {
  console.log();
  console.log(pc.red('  Git is required. Install it and try again.'));
  console.log(pc.dim('  https://git-scm.com'));
  process.exit(1);
}

// ── Step 5: Setup ──────────────────────────────────────────────────────
await setupProject({ projectName, preset, scope, deps });
