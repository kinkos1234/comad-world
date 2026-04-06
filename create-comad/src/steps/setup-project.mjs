import { spawnSync } from 'node:child_process';
import { existsSync, copyFileSync, writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import pc from 'picocolors';
import prompts from 'prompts';
import { PRESETS } from '../presets.mjs';

const __dirname = import.meta.dirname ?? dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = resolve(__dirname, '..', '..');

const REPO = 'kinkos1234/comad-world';

/**
 * Safe command runner using spawnSync (array form) to prevent shell injection.
 * @param {string} cmd - Command name
 * @param {string[]} args - Command arguments
 * @param {object} opts - spawnSync options
 * @returns {string} stdout
 */
function run(cmd, args = [], opts = {}) {
  const result = spawnSync(cmd, args, { encoding: 'utf8', stdio: 'pipe', ...opts });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    const err = new Error(result.stderr || `Command failed: ${cmd} ${args.join(' ')}`);
    err.status = result.status;
    throw err;
  }
  return result.stdout;
}

/**
 * Cross-platform synchronous sleep (no external commands).
 * Uses Atomics.wait on a SharedArrayBuffer.
 * @param {number} ms - Milliseconds to wait
 */
function sleepSync(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function step(msg) {
  console.log(`\n${pc.bold(msg)}`);
}

function ok(msg) {
  console.log(`  ${pc.green('+')} ${msg}`);
}

function warn(msg) {
  console.log(`  ${pc.yellow('!')} ${msg}`);
}

function fail(msg) {
  console.log(`  ${pc.red('x')} ${msg}`);
}

// ── Clone ──────────────────────────────────────────────────────────────
function cloneRepo(targetDir) {
  step('[1/4] Downloading comad-world...');

  if (existsSync(targetDir)) {
    fail(`Directory ${pc.bold(targetDir)} already exists.`);
    process.exit(1);
  }

  // Try degit first (faster, no git history), fall back to git clone --depth 1
  try {
    run('npx', ['--yes', 'degit', REPO, targetDir], { stdio: 'inherit' });
    ok('Downloaded via degit');
  } catch {
    try {
      run('git', ['clone', '--depth', '1', `https://github.com/${REPO}.git`, targetDir], {
        stdio: 'inherit',
      });
      ok('Cloned via git');
    } catch (e) {
      fail('Failed to download. Check your network connection and try again.');
      console.log(`    ${pc.dim(e.message)}`);
      process.exit(1);
    }
  }
}

// ── Preset config ──────────────────────────────────────────────────────
function applyPreset(targetDir, preset) {
  step('[2/4] Applying domain preset...');

  const presetDef = PRESETS.find((p) => p.value === preset);
  const configPath = join(targetDir, 'comad.config.yaml');

  if (presetDef && presetDef.file) {
    const presetPath = join(targetDir, 'presets', presetDef.file);
    if (existsSync(presetPath)) {
      copyFileSync(presetPath, configPath);
      ok(`Applied ${pc.bold(presetDef.title)} preset`);
    } else {
      warn(`Preset file not found, using default config`);
    }
  } else {
    // Custom — create a minimal starter config
    const templatePath = join(PKG_ROOT, 'templates', 'comad.config.yaml');
    if (existsSync(templatePath)) {
      copyFileSync(templatePath, configPath);
      ok('Created starter config — edit comad.config.yaml to add your interests');
    } else {
      warn(`Template file not found: ${templatePath}`);
      warn('You will need to create comad.config.yaml manually.');
    }
  }
}

// ── Install dependencies ───────────────────────────────────────────────
async function installDeps(targetDir, deps, scope) {
  step('[3/4] Installing dependencies...');

  const brainDir = join(targetDir, 'brain');

  // Install bun if missing
  if (!deps.bun) {
    console.log();
    console.log(`  ${pc.yellow('!')} bun is not installed. It will be installed via:`);
    console.log(`    ${pc.dim('curl -fsSL https://bun.sh/install | bash')}`);
    const { confirm } = await prompts({
      type: 'confirm',
      name: 'confirm',
      message: 'Allow bun installation?',
      initial: true,
    });
    if (confirm) {
      try {
        console.log(`  ${pc.dim('Installing bun...')}`);
        const curl = run('curl', ['-fsSL', 'https://bun.sh/install']);
        spawnSync('bash', ['-c', curl], { stdio: 'inherit', encoding: 'utf8' });
        ok('Installed bun');
        deps.bun = true;
      } catch {
        warn('Could not auto-install bun. Install manually: https://bun.sh');
      }
    } else {
      warn('Skipping bun installation. Install manually: https://bun.sh');
    }
  }

  // bun install in brain/ (skip for minimal — MCP only, no local deps needed)
  if (scope !== 'minimal' && deps.bun && existsSync(brainDir)) {
    try {
      run('bun', ['install'], { cwd: brainDir, stdio: 'inherit' });
      ok('Installed brain dependencies');
    } catch (e) {
      warn(`bun install failed: ${e.message}`);
    }
  } else if (scope === 'minimal') {
    ok('Minimal mode — skipping brain dependency install');
  }
}

// ── Start services ─────────────────────────────────────────────────────
function startServices(targetDir, deps, scope) {
  step('[4/4] Starting services...');

  if (scope === 'minimal') {
    ok('Minimal mode — no containers needed');
    return;
  }

  if (!deps.docker || !deps.dockerCompose) {
    warn('Docker not available — skipping container start');
    return;
  }

  // Start only brain-neo4j for lite, full docker-compose for full
  try {
    if (scope === 'lite') {
      run('docker', ['compose', 'up', '-d', 'brain-neo4j'], { cwd: targetDir, stdio: 'inherit' });
      ok('Started Neo4j (brain)');
    } else {
      run('docker', ['compose', 'up', '-d'], { cwd: targetDir, stdio: 'inherit' });
      ok('Started all services (Neo4j + Ollama)');
    }
  } catch (e) {
    warn(`docker compose failed: ${e.message}`);
    console.log(`    Run manually: cd ${targetDir} && docker compose up -d`);
  }

  // Run brain schema setup
  const brainDir = join(targetDir, 'brain');
  if (deps.bun && existsSync(brainDir)) {
    try {
      // Give Neo4j a moment to accept connections
      console.log(`  ${pc.dim('Waiting for Neo4j to be ready...')}`);
      let ready = false;
      for (let i = 0; i < 15; i++) {
        try {
          run('docker', ['exec', 'comad-brain-neo4j', 'neo4j', 'status'], { timeout: 5000 });
          ready = true;
          break;
        } catch {
          sleepSync(2000);
        }
      }
      if (ready) {
        run('bun', ['run', 'setup'], { cwd: brainDir, stdio: 'inherit' });
        ok('Brain schema initialized');
      } else {
        warn('Neo4j not ready yet — run later: cd brain && bun run setup');
      }
    } catch {
      warn('Schema setup skipped — run later: cd brain && bun run setup');
    }
  }
}

// ── Success banner ─────────────────────────────────────────────────────
function printSuccess(projectName, scope) {
  const dir = projectName;
  console.log();
  console.log(pc.green('  +  comad-world installed successfully!'));
  console.log();
  console.log('  Next steps:');
  console.log();
  console.log(`    ${pc.cyan('cd')} ${dir}`);

  if (scope !== 'minimal') {
    console.log(`    ${pc.cyan('docker compose up -d')}        ${pc.dim('# Start Neo4j')}`);
  }

  console.log(`    ${pc.cyan('cd brain && bun run crawl:hn')} ${pc.dim('# First crawl')}`);
  console.log(`    ${pc.cyan('cd brain && bun run mcp')}      ${pc.dim('# Start MCP server')}`);
  console.log();
  console.log(`  Then open Claude Code and say: ${pc.bold('dream')}`);
  console.log();

  if (scope === 'full') {
    console.log(pc.dim('  Modules installed:'));
    console.log(pc.dim('    brain/  — Knowledge graph + MCP server'));
    console.log(pc.dim('    ear/    — Discord content curator'));
    console.log(pc.dim('    eye/    — Simulation engine'));
    console.log();
  }
}

// ── Main ───────────────────────────────────────────────────────────────
export async function setupProject({ projectName, preset, scope, deps }) {
  const targetDir = resolve(process.cwd(), projectName);

  cloneRepo(targetDir);
  applyPreset(targetDir, preset);
  await installDeps(targetDir, deps, scope);
  startServices(targetDir, deps, scope);
  printSuccess(projectName, scope);
}
