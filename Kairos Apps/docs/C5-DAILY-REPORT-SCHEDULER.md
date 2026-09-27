# C5 — Daily Report Scheduler

## Behavior

Frappe Scheduler runs `kairos.scheduler.generate_daily_draft` at **18:30** every day. It derives
the report date using `Asia/Ho_Chi_Minh`, then creates or refreshes that day's Timeline.

The job deliberately does **not** call an LLM. This prevents automatic provider cost and avoids
creating a final summary before late-day work has arrived. A user can still select **Generate
Summary** on Desk when ready.

If the Timeline did not change, a `ready` Day Report remains ready. If new or changed Event data
alters the Timeline, the report returns to `draft`, signalling that its summary is stale.

## Server requirements

The Bench host clock/timezone must be `Asia/Ho_Chi_Minh` because the cron expression is evaluated by
the server scheduler. Confirm it in WSL/Linux:

```bash
timedatectl | grep "Time zone"
```

After updating the app:

```bash
cd ~/frappe-bench
bench --site kairos.local migrate
bench --site kairos.local enable-scheduler
bench --site kairos.local scheduler status
```

`bench start` must keep the scheduler process running in development. On production, make sure
Bench supervisor/systemd services include the scheduler worker.

## Manual verification

Run the same function without waiting until 18:30:

```bash
cd ~/frappe-bench
bench --site kairos.local execute kairos.scheduler.generate_daily_draft
```

Then open **Kairos Day Report** in Desk. The report for today must exist, have the current Timeline,
and be `draft` unless an unchanged ready report already existed.

Inspect scheduler logs if no report appears:

```bash
tail -n 100 logs/scheduler.log
```
