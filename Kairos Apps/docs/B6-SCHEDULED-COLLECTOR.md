# B6 — Scheduled Codex Collector

This setup runs the Codex collector from Windows Task Scheduler through WSL. It uses the same
Frappe URL and token as manual sync, but keeps them outside the repository.

## 1. Configure the WSL runner

Create `~/.config/kairos/collector.env` in WSL. The session directory is
required because Codex stores this user's sessions on the Windows drive.

```bash
KAIROS_FRAPPE_URL="http://127.0.0.1:8002"
KAIROS_FRAPPE_TOKEN="<api_key>:<api_secret>"
KAIROS_CODEX_SESSIONS_DIR="/mnt/c/Users/cuong.nguyen.e/.codex/sessions"
KAIROS_CODEX_BATCH_SIZE=100
KAIROS_CODEX_TIMEOUT=120
```

### Session source on a new machine

`collector.env` is a **per-user WSL configuration file**, not a file under
`collectors/codex/` and not a file committed to Git. Create it once on each machine at
`~/.config/kairos/collector.env`. It holds both the Frappe connection values and the path to
that machine's local Codex data.

Always set `KAIROS_CODEX_SESSIONS_DIR` explicitly. Without it, the runner falls back to
`$HOME/.codex/sessions`, which is the WSL home directory. That fallback is often stale when
Codex runs on Windows and writes sessions under the Windows profile instead.

For a Windows Codex installation accessed through WSL, use:

```bash
KAIROS_CODEX_SESSIONS_DIR="/mnt/c/Users/<windows-user>/.codex/sessions"
```

For a native Linux Codex installation, use:

```bash
KAIROS_CODEX_SESSIONS_DIR="$HOME/.codex/sessions"
```

Before enabling the scheduled task, confirm that the selected directory really contains recent
`rollout-*.jsonl` files:

```bash
source ~/.config/kairos/collector.env
ls -ltR "$KAIROS_CODEX_SESSIONS_DIR" | head -40
```

If the newest file is older than the activity the user expects to see, the collector cannot create
new events: Codex has not written that activity to this local source. Check whether the user is
working in a different Codex runtime or profile. Do not delete the incremental checkpoint just to
solve this symptom; doing so replays all discovered sessions.

Protect the file and test the runner once:

```bash
chmod 600 ~/.config/kairos/collector.env
bash "/mnt/c/Projects/Kairos Apps/collectors/codex/scripts/run_kairos_codex_sync.sh"
tail -n 30 ~/.local/state/kairos/codex-sync-$(date +%F).log
```

The runner appends stdout and errors to one log file per day. It sends a normal incremental sync
once: files unchanged since the last successful run are skipped, and changed-file events are sent in
100-event requests by default. The checkpoint is
`~/.local/state/kairos/codex-sync-state.json`. Do not schedule `--verify-idempotency`, which
intentionally sends every batch twice.

## 2. Create the Windows task

Open **Task Scheduler** → **Create Task**. Choose the Windows account that owns the WSL
distribution, then create a trigger: *Daily*, repeat task every **30 minutes**, for a duration of
*Indefinitely*. Use this action:

```text
Program/script: powershell.exe
Arguments: -NoProfile -ExecutionPolicy Bypass -File "C:\Projects\Kairos Apps\collectors\codex\scripts\run_kairos_codex_sync.ps1"
Start in: C:\Projects\Kairos Apps\collectors\codex\scripts
```

If the WSL distro has another name, add `-Distro "<name>"` to Arguments. Find its name with
`wsl -l -q` in PowerShell. Select *Run only when user is logged on* for the initial test, save,
then use **Run** in Task Scheduler.

## 3. Verify

Inspect the latest WSL log after manually running the task. A successful run contains a
`Frappe accepted events` line and finishes with exit code `0`. The log also reports skipped
unchanged sessions and each accepted batch. Re-running can update an actively changing session;
stable event IDs prevent duplicate records.

When events look stale, inspect the log before changing data:

```bash
tail -n 80 ~/.local/state/kairos/codex-sync-$(date +%F).log
```

| Log result | Meaning and action |
| --- | --- |
| `Sessions directory: /home/.../.codex/sessions` unexpectedly | Add or correct `KAIROS_CODEX_SESSIONS_DIR` in `collector.env`, then rerun the task. |
| `skipped N unchanged`, `Parsed 0`, `Mapped 0` | The scheduler ran, but no local session file changed. Check the actual Codex session directory and its newest file timestamp. |
| `Parsed > 0`, `Mapped 0` | Codex wrote data, but the current mapper did not consider it a user message or task-completion event. |
| `Frappe accepted ...` but Desk is old | The data reached Frappe; check the event's `Occurred At` and Desk sorting/filtering. |
