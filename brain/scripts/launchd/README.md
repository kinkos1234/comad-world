# Launchd migration

## Why

macOS cron runs outside the user's Aqua session, so `claude -p`
(which reads OAuth from keychain) fails with exit 1. We tested this:

- **cron → claude -p**: `⚠ claude -p exited with code 1: ` (empty stderr)
- **launchd user agent → claude -p**: full authenticated response

LaunchAgents in `gui/<uid>` inherit the GUI session, so the existing
Claude Max OAuth works without any extra API key.

## Install

```sh
zsh brain/scripts/launchd/install.sh
```

Creates 10 plists under `~/Library/LaunchAgents/` and bootstraps them
into the current GUI session. Re-running the script is idempotent.

Installed agents (schedule in local time, Monday = weekday 1):

| Label | Time | Program |
|---|---|---|
| `com.comad.ear-ingest` | 07:00 daily | `ear-ingest.ts --since 1` |
| `com.comad.ear-digest` | 08:00 daily | `ear/generate-digest.js` |
| `com.comad.crawl-arxiv` | 09:00 daily | `crawl-arxiv.sh` |
| `com.comad.ingest-geeknews` | 09:30 daily | `ingest-geeknews.sh` |
| `com.comad.crawl-blogs` | 10:00 daily | `crawl-blogs.sh` |
| `com.comad.crawl-github` | 11:00 Mon | `crawl-github.sh` |
| `com.comad.monitor-upstream` | 11:30 Mon | `monitor-upstream.sh` |
| `com.comad.search-weekly` | 12:00 Mon | `search-weekly.sh` |
| `com.comad.evolution-loop` | 12:30 Mon | `evolution-loop.sh` |
| `com.comad.run-benchmark` | 13:00 Mon | `run-benchmark.sh` |

## Operate

```sh
launchctl list | grep com.comad                  # status
launchctl kickstart gui/$(id -u)/<label>         # trigger one-off
launchctl print gui/$(id -u)/<label>             # details + last exit
tail -f brain/crawl.log                          # runtime log
```

## Uninstall

```sh
zsh brain/scripts/launchd/uninstall.sh
```

Removes plists and bootout the agents. Cron entries were just commented
out with `# MIGRATED_TO_LAUNCHD:` — restore via `crontab -e` if needed.

## Caveats

- User must be logged in (Aqua session) for agents to fire. Overnight
  runs survive sleep as long as Power Nap or the machine is awake; if
  the machine is off at scheduled time, the agent won't catch up —
  launchd doesn't have anacron semantics.
- Keychain unlocks at login and stays unlocked while the session is
  active, so `claude -p` auth keeps working across all runs.
