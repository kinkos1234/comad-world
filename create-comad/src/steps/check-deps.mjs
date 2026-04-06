import { spawnSync } from 'node:child_process';
import pc from 'picocolors';

const isWin = process.platform === 'win32';

export function has(cmd) {
  const lookup = isWin ? 'where' : 'which';
  const result = spawnSync(lookup, [cmd], { stdio: 'ignore' });
  return result.status === 0;
}

function version(cmd, flag = '--version') {
  try {
    const result = spawnSync(cmd, [flag], { encoding: 'utf8', stdio: 'pipe' });
    if (result.status !== 0) return null;
    return (result.stdout || '').trim().split('\n')[0] || null;
  } catch {
    return null;
  }
}

export function checkDeps(scope) {
  const results = { git: false, docker: false, dockerCompose: false, bun: false };

  // Git — always required
  if (has('git')) {
    results.git = true;
    console.log(`  ${pc.green('+')} git ${pc.dim(version('git') || '')}`);
  } else {
    console.log(`  ${pc.red('x')} git — ${pc.dim('https://git-scm.com')}`);
  }

  // Docker — required for full/lite
  if (scope !== 'minimal') {
    if (has('docker')) {
      results.docker = true;
      console.log(`  ${pc.green('+')} docker ${pc.dim(version('docker', '--version') || '')}`);
    } else {
      console.log(`  ${pc.red('x')} docker — ${pc.dim('https://docs.docker.com/get-docker/')}`);
    }

    // Docker Compose
    const composeResult = spawnSync('docker', ['compose', 'version'], { stdio: 'ignore' });
    if (composeResult.status === 0) {
      results.dockerCompose = true;
      console.log(`  ${pc.green('+')} docker compose`);
    } else {
      console.log(`  ${pc.red('x')} docker compose — ${pc.dim('included with Docker Desktop')}`);
    }
  }

  // Bun
  if (has('bun')) {
    results.bun = true;
    console.log(`  ${pc.green('+')} bun ${pc.dim(version('bun') || '')}`);
  } else {
    console.log(`  ${pc.yellow('!')} bun — ${pc.dim('will install via: curl -fsSL https://bun.sh/install | bash')}`);
  }

  return results;
}

export function suggestFallback(deps, scope) {
  if (scope !== 'minimal' && !deps.docker) {
    console.log();
    console.log(
      `  ${pc.yellow('!')} Docker not found. Switching to ${pc.bold('Minimal')} mode (MCP only, no Neo4j container).`
    );
    console.log(`    Install Docker later: ${pc.cyan('https://docs.docker.com/get-docker/')}`);
    return 'minimal';
  }
  if (scope !== 'minimal' && deps.docker && !deps.dockerCompose) {
    console.log();
    console.log(
      `  ${pc.yellow('!')} Docker Compose not found. Switching to ${pc.bold('Minimal')} mode (MCP only, no Neo4j container).`
    );
    console.log(`    Docker Compose is included with Docker Desktop: ${pc.cyan('https://docs.docker.com/compose/install/')}`);
    return 'minimal';
  }
  return scope;
}
