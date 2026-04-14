# ADR 0001 — Repository Strategy

- **Status:** Superseded by [ADR 0011](0011-monorepo-reversal.md) (2026-04-14)
- **Date:** 2026-04-14
- **Deciders:** Comad World maintainer (@kinkos1234)
- **Related:** `refact.md`, `scripts/upgrade.sh`, `scripts/comad`, `comad.lock`

> **Note (2026-04-14):** Nested `.git` 전략은 폐기됐다. 이 결정이 내려진 당일 오후 감사에서 (a) 원격 레포가 존재한 적 없고 (b) umbrella가 이미 모듈 소스를 트래킹하고 있었으며 (c) 채택률 관점에서 역효과임이 드러났다. 상세: ADR 0011.

## Context

Today the repository is structurally ambiguous. At the root it looks like a product
(one README, one installer, one global `comad` CLI). Underneath it behaves like
a federation: each module (`brain`, `ear`, `eye`, `photo`, `sleep`, `voice`) carries
its own `.git` directory and pushes to its own GitHub repo. There is no `.gitmodules`.
`refact.md` calls this a "hybrid monorepo" and flags it as the biggest structural
signal blocking further progress.

The friction is concrete:

- Upgrade semantics are unclear (does `comad upgrade` treat each module as a
  first-class unit or as a dependency pinned by `comad.lock`?).
- CI is split across module repos, so the public repo's green badge does not
  imply the system is green.
- Users cannot reason about what "a release" means — there are seven possible
  version identities at any moment.
- Contributors don't know where to file issues.

## Options considered

### A. True monorepo
Remove the nested `.git` directories. `comad-world` becomes the only repo.
Individual modules lose their own GitHub pages, star counts, and `npm/pip`
release identities, but gain a single version, a single CI, a single issue
tracker, and an obvious place to land cross-module PRs.

Pros: simplest model to explain, hardest for a reader to get lost in, CI signal
means what it says, `comad.lock` becomes redundant inside the repo.
Cons: requires a migration (moving each module's history into the umbrella via
`git subtree add`), breaks existing external references to the per-module repos,
and forfeits the "mix-and-match" story where somebody could consume just
`comad-brain` without the rest.

### B. Meta repo with formal submodules
Keep the per-module repos, but declare them as Git submodules in `.gitmodules`,
with `comad.lock` as the pin. `comad upgrade` becomes `git submodule update`.

Pros: respects existing module identities, pins are cryptographically exact,
`git clone --recursive` is the only bootstrap step users learn.
Cons: submodules remain confusing for newcomers (detached HEADs, nested status),
and the umbrella's CI still cannot run per-module tests without manual fan-out.

### C. Keep the current hybrid — but write the contract down (RECOMMENDED)
Nested `.git` directories remain, but the umbrella formalizes two things:
(1) the umbrella treats `comad.lock` as the single source of truth for module
SHAs (already implemented in `scripts/comad lock` / `upgrade.sh --lock`);
(2) any file that lives under a module directory is managed by that module's
CI — the umbrella CI only verifies the *wiring* (install/upgrade smoke, lock
consistency, duplicate-file guard).

Pros: zero migration cost; preserves per-module release independence; matches
what `scripts/upgrade.sh` already does; lets us keep improving without betting
the project on a restructure.
Cons: the hybrid remains unusual and must be documented clearly; the umbrella
CI scope stays narrow by design.

## Decision

**We adopt Option C — "documented hybrid".**

Rationale:

1. Option A's migration cost is real work that produces no new user value today
   and breaks external URLs we already advertise in launch posts.
2. Option B's submodules are a net usability downgrade for a user base that
   installs via `./install.sh`, not `git clone --recursive`.
3. Option C codifies what is *already working*. We have a `VERSION` file, a
   `comad.lock`, an upgrader, and a global CLI. The missing piece is a written
   contract — this ADR — and a few CI guards to keep the boundary honest.

We revisit this ADR if one of these triggers fires:

- A contributor lands the same logical change in two module repos because the
  boundary wasn't clear.
- `comad.lock` drifts out of sync with the nested `.git` HEADs more than twice
  in a quarter.
- External adopters complain that per-module repos are out-of-date relative to
  the umbrella.

## Contract implied by the decision

1. **Root = wiring.** `install.sh`, `scripts/*`, `Makefile`, `VERSION`,
   `comad.lock`, `README.md`, `docs/`, `comad.config.yaml`, and the top-level
   `.github/workflows/` belong to the umbrella. Changes here never require a
   per-module release.
2. **Module directories = owned by their `.git`.** A change that *only* affects
   `brain/` lands in the `comad-brain` repo first, then propagates to the
   umbrella via `comad upgrade --lock`. A change that spans modules lands in
   the umbrella with a per-module follow-up if needed.
3. **`comad.lock` is authoritative.** When the umbrella is tagged, each module
   SHA in `comad.lock` is the *as-released* state. Users who need an exact
   reproducible install must `comad upgrade` against a fixed `comad.lock`, not
   against the per-module `HEAD`.
4. **Umbrella CI scope.** The umbrella pipeline runs:
   - shell syntax + `--dry-run` for upgrader (already in `upgrade-smoke.yml`)
   - duplicate-file guard (planned, ADR 0002 candidate)
   - generated-artifact guard (`.gitignore` drift check)
   - schema validation for `comad.config.yaml` once the contract ships (Phase 3)
   Module-level tests remain the module repos' responsibility.
5. **Release identity.** The umbrella `VERSION` identifies *the combination*.
   Per-module versions remain independent. When the umbrella VERSION bumps,
   `comad.lock` and `CHANGELOG.md` move together.

## Consequences

- `docs/adr/` is established as the permanent home for architectural decisions.
- `scripts/upgrade.sh` is the operational expression of this ADR — changes to
  upgrade semantics must update this doc.
- Future Tier 2 work (config schema, duplicate-file guard, scripts/lib/*)
  inherits clause (4) above as its scope fence.
- Tier 3 work (eye Phase 2 internal reshuffle, apps/services/agents layout) is
  *out of scope* of this ADR — it reshapes the *inside* of a module directory,
  not the boundary between modules and the umbrella.

## Open questions (not blockers)

- Should we publish the nested module repos as a `git subtree push` from the
  umbrella, eliminating the dual-commit ritual? Revisit after duplicate-file
  guard lands.
- Should `comad.lock` move from YAML to TOML to match `Cargo.lock` expectations?
  No strong reason either way; keep YAML until something actually breaks.
