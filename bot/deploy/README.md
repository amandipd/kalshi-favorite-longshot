# Running the bot on a Linux server

The bot ran for a while on a small Linux server in Amazon's us-east-2 (Ohio) region, the region Kalshi's API is
served from, under systemd. The unit files here are that setup with placeholder paths: the repository in
`/opt/kalshi-bot`, a virtualenv in `/opt/kalshi-bot/venv`, ledger backups in `/opt/kalshi-bot/backups`, and a service
user called `kalshi`. Change them to suit your machine before you install them.

Only one live bot may trade from a Kalshi account at a time. The one-bot lock (localhost port 47864) only works inside
one machine, so before you enable `kalshi-bot` anywhere, make sure no other copy is trading from the same account.

## Install

1. Clone the repository to `/opt/kalshi-bot`, create the virtualenv and install `bot/requirements.txt` into it.
2. Put `.env` (and the key file it names) in `/opt/kalshi-bot/bot`, readable by the service user only.
3. Copy the unit files to `/etc/systemd/system/`, run `sudo systemctl daemon-reload`, and enable what you want.

```bash
sudo systemctl enable --now kalshi-backup.timer          # the nightly ledger backup
sudo systemctl enable --now kalshi-alerts kalshi-dashboard
sudo systemctl enable --now kalshi-bot                    # real money: only once nothing else trades the account
sudo systemctl enable --now kalshi-watchdog.timer kalshi-stall-alert.timer
```

Keep the clock synced (chrony or systemd-timesyncd): the bot enters at minute 8 of each window on Kalshi's clock.

## The services

| Unit | What it runs | Restarts |
|---|---|---|
| `kalshi-bot` | `bot.py --live --env prod --yes` | on failure, 30 s apart, gives up after 3 in 10 minutes |
| `kalshi-alerts` | `python -m kalshi_bot.notify --log state/notify.log` | always, 60 s apart |
| `kalshi-dashboard` | `dashboard.py --lan` (port 8080) | on failure, 10 s apart |
| `kalshi-watchdog.timer` | `python -m kalshi_bot.watchdog` every minute: pings healthchecks.io | (a timer) |
| `kalshi-stall-alert.timer` | `python -m kalshi_bot.stall_alert` every 10 minutes | (a timer) |
| `kalshi-backup.timer` | a ledger backup at 03:31, 14 days kept | (a timer) |

The bot writes its log to `state/live-prod.log` and `state/live-prod.err.log`, and the dashboard to
`state/dashboard.log` and `state/dashboard.err.log`. `journalctl -u <unit>` shows systemd's own notes for any unit.

`--lan` makes the dashboard listen on every interface. Keep port 8080 closed to the internet and reach it over a
private network you control.

## Halt and resume

```bash
cd /opt/kalshi-bot/bot && ../venv/bin/python bot.py --halt "reason"    # no new orders; open bets still settle
cd /opt/kalshi-bot/bot && ../venv/bin/python bot.py --resume           # back to betting
cd /opt/kalshi-bot/bot && ../venv/bin/python bot.py --status           # halted or not
```

The running bot sees a halt at once. A halt lasts through restarts and reboots: only `--resume` clears it, including
the bot's own automatic halts.

## Restarting safely

A restart in the wrong few minutes can miss a window's entry. `safe_restart.py` waits until the window is clear (3.5
minutes at most) and then returns, so the restart after it only runs once it is safe:

```bash
cd /opt/kalshi-bot/bot && ../venv/bin/python deploy/safe_restart.py && sudo systemctl restart kalshi-bot
```

`--check` just says yes or no and exits 1 when it is not safe. By hand, the unsafe band is 390 to 600 seconds into
each 15-minute window, which covers minutes :08 to :09, :23 to :24, :38 to :39 and :53 to :54 and the prep before each.

The bot binds its lock port without listening, so `ss` and `netstat` don't show it. To check that the new bot holds
it, start a dry run beside it: `timeout 30 ../venv/bin/python bot.py --env prod` must print "another bot is already
running" and exit 1.

## Quick checks

- **Speed to Kalshi:** `../venv/bin/python deploy/probe_latency.py` times Kalshi's public `/exchange/status` from
  this machine (no key needed).
- **Watchdog:** set `HEALTHCHECK_URL` in `.env`. `journalctl -u kalshi-watchdog -n 5` shows each minute's ping. With
  no live bot running it pings `/fail`, so healthchecks.io marks the check down.
- **Backups:** `ls -l /opt/kalshi-bot/backups`. One now: `sudo systemctl start kalshi-backup`.
