import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { has, checkDeps, suggestFallback } from '../src/steps/check-deps.mjs';

describe('has()', () => {
  it('returns true when command exists (node)', () => {
    assert.equal(has('node'), true);
  });

  it('returns false for nonexistent command', () => {
    assert.equal(has('__nonexistent_command_xyz__'), false);
  });

  it('returns true for git (expected in dev env)', () => {
    // git is expected in any dev environment
    assert.equal(has('git'), true);
  });
});

describe('checkDeps()', () => {
  it('always checks git', () => {
    const deps = checkDeps('minimal');
    assert.equal(typeof deps.git, 'boolean');
  });

  it('skips docker check for minimal scope', () => {
    const deps = checkDeps('minimal');
    assert.equal(deps.docker, false);
    assert.equal(deps.dockerCompose, false);
  });

  it('returns an object with all expected keys', () => {
    const deps = checkDeps('full');
    assert.ok('git' in deps);
    assert.ok('docker' in deps);
    assert.ok('dockerCompose' in deps);
    assert.ok('bun' in deps);
  });

  it('checks docker for full scope', () => {
    const deps = checkDeps('full');
    assert.equal(typeof deps.docker, 'boolean');
    assert.equal(typeof deps.dockerCompose, 'boolean');
  });

  it('checks docker for lite scope', () => {
    const deps = checkDeps('lite');
    assert.equal(typeof deps.docker, 'boolean');
  });
});

describe('suggestFallback()', () => {
  it('returns minimal when docker is missing for full scope', () => {
    const result = suggestFallback({ docker: false, dockerCompose: false }, 'full');
    assert.equal(result, 'minimal');
  });

  it('returns minimal when docker exists but compose is missing', () => {
    const result = suggestFallback({ docker: true, dockerCompose: false }, 'full');
    assert.equal(result, 'minimal');
  });

  it('returns minimal when docker exists but compose is missing for lite scope', () => {
    const result = suggestFallback({ docker: true, dockerCompose: false }, 'lite');
    assert.equal(result, 'minimal');
  });

  it('keeps scope when both docker and compose exist', () => {
    const result = suggestFallback({ docker: true, dockerCompose: true }, 'full');
    assert.equal(result, 'full');
  });

  it('keeps lite scope when both docker and compose exist', () => {
    const result = suggestFallback({ docker: true, dockerCompose: true }, 'lite');
    assert.equal(result, 'lite');
  });

  it('keeps minimal scope unchanged regardless of deps', () => {
    const result = suggestFallback({ docker: false, dockerCompose: false }, 'minimal');
    assert.equal(result, 'minimal');
  });

  it('downgrades lite scope when docker is missing', () => {
    const result = suggestFallback({ docker: false, dockerCompose: false }, 'lite');
    assert.equal(result, 'minimal');
  });
});
