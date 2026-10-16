# Operations Runbook

Status: draft v0.1, 2026-10-16
Companion to `design.md` section 6 (operational design), section 5.6 (session
controller states), section 10 (roadmap); `data-layer.md` section 6
(ingestion jobs); `backtester.md` section 9 (calibration loop);
`agent-operating-model.md` (who does what).

This document is written for one operator running one account. Every
procedure assumes nobody else is available to help at the moment it is
needed. Where the design document says what the system does, this one says
what the operator does, in what order, and how to tell it worked.

Terms: "system" means the Session Trader process and its scheduled jobs;
"agent" means the AI agent described in `agent-operating-model.md`;
"operator" means the human account holder.

---

## 1. Daily runbook

All times ET. Trading days only. The checklist is the same in paper and live
mode; only the credentials and the consequences differ.

### 1.1 Before the session

| Time | Step | Who | Done when |
|---|---|---|---|
| 06:00 | `refresh_symbols` job: assets endpoint, listing and delisting dates, broker tradability flags | System | Job log shows success and row counts within 5 percent of yesterday |
| 08:00 | `ingest_daily` catch-up if the 18:00 run failed; screener run; pump filter; watchlist published as `universe_snapshots` for today | System | Watchlist of 20 to 50 names exists with today's date and the current config hash |
| 08:30 | Pre-session note (template in `agent-operating-model.md` section 4.1): watchlist review, filings scan, borderline pump names, overnight incidents, fee or rule changes noticed | Agent | Note posted to the operator channel |
| 09:00 | Read the note. Blacklist any name that feels wrong. Confirm the config hash in the note matches the merged `risk.yaml` and `strategies.yaml` on `main`. Confirm the account mode (paper or live) printed in the note is the one intended | Operator | Operator acknowledges the note; blacklist file committed if changed |
| 09:15 | PREFLIGHT runs: data quality checks, broker connectivity, account snapshot, intraday buying power read, gross exposure must be zero, watchlist loaded, config hash recorded, clock skew under 500 ms | System | PREFLIGHT result pushed to operator: PASS with the hash, or FAIL with the first failing check |
| 09:15 to 09:45 | If PREFLIGHT failed: fix and re-run, or skip the day. Never override a PREFLIGHT failure | Operator | PASS received, or the day is marked skipped in the journal |

### 1.2 During the session

| Time | Step | Who | Done when |
|---|---|---|---|
| 09:45 or later | `activate`. In phase 2 the operator does this by hand each day; scheduled activation (design.md open question 3) is a later decision | Operator | Session state is ACTIVE in the journal and UI |
| Continuous | Heartbeat every 10 seconds; stall detector; fill deviation check; broker error rate | System | Silent when healthy |
| On alert | Follow the matching playbook in section 7. Do not improvise | Operator | Playbook steps complete; incident record opened if the playbook says so |
| In advisory mode | Approve or skip each candidate card. A card not acted on within its time-in-force expires on its own | Operator | Decision journaled as `operator_action` |
| 15:30 | Entry cutoff; state moves to WINDING_DOWN automatically | System | State change in journal |
| 15:45 | Flatten deadline; FLATTENING begins | System | All positions closed, or HALTED_EXPOSURE recorded |
| 16:00 | Market close. Any position still held is an incident | System | CLOSED state reached |

### 1.3 After the session

| Time | Step | Who | Done when |
|---|---|---|---|
| 16:05 | Reconciliation against broker positions and balances; session report; incident list | System | Reconciliation shows zero mismatches, or activation is locked and an incident is open |
| 16:15 | Read the session report. If activation is locked, start the reconciliation playbook (7.6) today, not tomorrow | Operator | Report acknowledged |
| 18:00 | `ingest_daily`, `ingest_halts` | System | Job logs show success |
| 18:30 | `ingest_minutes_watchlist` | System | Minute bars present for every symbol traded today |
| Evening | Post-session review (template in `agent-operating-model.md` section 4.2) | Agent | Review posted; any tuning proposal opened as a PR, never applied |
| Evening | Read the review. Decide nothing about parameters tonight; parameter decisions are weekly | Operator | Nothing to record |

### 1.4 Non-trading days

Market holidays and early closes come from the exchange calendar the system
loads at `refresh_symbols`. On an early-close day the entry cutoff and flatten
deadline move earlier by the same amount as the close (13:00 close means 12:30
cutoff and 12:45 flatten). PREFLIGHT fails if the calendar is older than 30
days.

---

## 2. Weekly and monthly routines

### 2.1 Weekly (Saturday morning, about one hour)

- [ ] Metrics review: expectancy, profit factor, max drawdown, slippage versus
      model, risk rejection mix, halt exposure count, over the last 20 and 60
      sessions, grouped by config hash. The agent prepares the table; the
      operator reads it.
- [ ] Parameter decisions: review any open tuning-proposal PRs. Merge, request
      changes, or close. Merged changes take effect at Monday's PREFLIGHT.
- [ ] Blacklist pruning: remove names older than 90 days unless re-confirmed.
- [ ] Kill-switch drill (section 4.4) in paper mode. Record the time each layer
      took.
- [ ] Calibration review: the agent's backtest-to-live comparison for the week
      (`backtester.md` section 9). Accept or reject proposed changes to
      `impact_coeff`, the spread model, or `stop_gap_factor`.
- [ ] Open incidents: every incident record must have an owner and a next step.
- [ ] Data quality: flag rates per vendor from `reference_daily.quality_flags`.
      A vendor whose flag rate doubled is a ticket.

### 2.2 Monthly (first Saturday)

- [ ] Backup verification: restore last night's Postgres dump and one month of
      parquet into a scratch directory, run the session report for a past day,
      compare to the stored report. Record the restore time.
- [ ] Dependency updates: the agent opens one PR with updated pins and the
      test results. Merge only when tests and a reference backtest match the
      previous run to the cent.
- [ ] Secrets rotation check: keys older than 90 days get rotated (section 5.4).
- [ ] Broker statement reconciliation: compare the broker's monthly statement
      to the journal's month totals for fees, fills and cash movements.
- [ ] Capital review: equity versus the phase budget. If drawdown exceeds the
      phase limit (section 8), the phase-regression rule applies.

### 2.3 Annual and event-driven

- [ ] Each January, and whenever FINRA or the SEC publish a rate change: update
      `fees.yaml` (`backtester.md` section 6). The SEC Section 31 rate changes
      each fiscal year, usually announced in the spring with an April effective
      date; the FINRA TAF changes by notice. Add a dated row, never edit an old
      one.
- [ ] Each January: re-read the broker fee schedule and the market data plan
      terms. Record the check in `design.md` section 15.
- [ ] Whenever the broker announces an API deprecation: open a ticket the same
      day. The July 2026 removal of the day-trade fields is the precedent.
- [ ] Whenever the exchanges change LULD bands or the Nasdaq bid-price rules:
      update the band table and the screener filter.

---

## 3. Monitoring and alerting

### 3.1 Signals

| Signal | Threshold | Action | Channel |
|---|---|---|---|
| Heartbeat missed | 30 seconds without a heartbeat during ACTIVE, WINDING_DOWN or FLATTENING | Supervisor restarts the process; if positions were open, the restarted process enters WINDING_DOWN and alerts | Page |
| Data stall | No bar for the liquid control symbol for 2 minutes during market hours | No new entries. If positions are open and the stall passes 2 minutes, FLATTENING using broker quotes as the price source | Page |
| Fill deviation | Fill price differs from the intended limit by more than the slippage budget (default 0.3 percent) | Alert; the position manager re-evaluates risk on the real fill; three deviations in a session stop new entries | Page |
| Halt exposure | Any held symbol enters a halt | Alert with symbol, position size, halt start time | Page plus SMS |
| Loss limit | Daily loss limit reached (1.5 percent of equity) or weekly (4 percent) | FLATTENING; activation locked for the day or week | Page plus SMS |
| Broker errors | 3 rejected or errored orders within 5 minutes | Stop new entries; alert | Page |
| Broker unreachable | 3 consecutive API failures over 30 seconds | Alert with the layer 3 kill-switch instruction | Page plus SMS |
| Margin state | Broker reports any intraday margin deficit or call | FLATTENING; activation locked; incident (playbook 7.8) | Page plus SMS |
| Reconciliation mismatch | Any difference in positions, cash or fee totals at CLOSED | Activation locked; incident | Page |
| Scheduled job failure | Any `ingest_*`, `refresh_symbols` or `sample_quotes` job exits non-zero | Alert; PREFLIGHT will fail if the data is stale | Log channel plus morning note |
| Disk | Data volume above 85 percent | Alert | Log channel |
| Clock skew | Over 500 ms against the vendor server | PREFLIGHT fails; during a session, alert | Page |

### 3.2 Channels

- **Page**: a push notification to the operator's phone through a service with
  delivery confirmation and an escalation timer. If unacknowledged in 5 minutes
  during ACTIVE, it repeats, then falls through to SMS.
- **SMS**: for the states where the operator may need to act from the broker's
  app without a computer.
- **Log channel**: a chat channel or log view read at the 16:15 and morning
  checkpoints.
- Design.md open question 4 asks which channel is fastest in practice. The
  weekly drill measures it: record the time from alert to acknowledgment.

### 3.3 What is deliberately not alerted

Individual fills, rejections, candidate generation and ordinary state changes
go to the journal only. An alert that fires every day stops being read.

---

## 4. Kill switch

Three independent layers. Each works when the others are broken.

### 4.1 Layer 1: in-app `kill`

Procedure: issue `kill` from the UI or the command line. The process cancels
all open orders, submits exits for every position through the ladder with the
FLATTENING marketable-limit fallback, writes `operator_action: kill` to the
journal, confirms flat against the broker, then stops. Expected time to flat:
under 60 seconds in liquid names. Verify: broker positions page shows none.

### 4.2 Layer 2: standalone liquidation script

A separate script on a separate device (phone shortcut or a second machine)
with its own API key pair, restricted to trading permissions. It calls the
broker's cancel-all and then liquidate-all endpoints, polls positions until
empty or 2 minutes pass, and prints the result. It shares no code with the
main process beyond the broker SDK. Verify: same as layer 1. If positions
remain after 2 minutes, go to layer 3.

### 4.3 Layer 3: broker application

Log in to the broker's web or mobile app. Cancel all open orders first, then
close each position. Do this when the API is unreachable, or when layers 1
and 2 report positions that will not close. Expect a halted symbol to be
unclosable until it resumes.

### 4.4 Drill script (weekly, paper mode)

1. With the paper session ACTIVE and at least one paper position open, start a
   timer.
2. Run layer 1. Record time to flat and any error.
3. Re-enter one paper position by hand. Run layer 2 from the phone. Record time.
4. Re-enter one paper position. Close it through the broker app. Record time.
5. Confirm the journal has three `operator_action` entries and the
   reconciliation for the day is clean.
6. Write the three times into the drill log. A layer that took more than twice
   its previous time, or failed, is an incident.

The drill keeps the layer 2 credentials known to work and the layer 3 login
fresh. Both decay silently otherwise.

---

## 5. Configuration, change management and secrets

### 5.1 Configuration files

| File | Governs | Change path | Takes effect |
|---|---|---|---|
| `risk.yaml` | Every rule in `design.md` section 5.4 | PR; operator approval required; agent may draft but never merge; no backtest can justify loosening a limit, only the operator's explicit decision | Next PREFLIGHT, never mid-session |
| `strategies.yaml` | Strategy parameters, weights, enabled set | PR with attached walk-forward report at three pessimism levels and the parameter count tried (`backtester.md` section 8); operator merges | Next PREFLIGHT |
| `fees.yaml` | Date-ranged fee rates | PR citing the FINRA or SEC notice | Immediately in backtests; next PREFLIGHT live |
| `screener.yaml` | Universe filters and ranking weights | Same as strategies | Next 08:00 screener run |
| `blacklist.yaml` | Names excluded by the operator | Direct commit by the operator, no PR needed | Next screener run |
| `luld_bands.yaml` | Band table | PR citing the exchange notice | Next PREFLIGHT |

Every PR that changes a config file must state the config hash before and
after. PREFLIGHT records the live hash in the journal, and every report groups
results by that hash, so a change can always be evaluated against what came
before it.

### 5.2 Branch protection

`main` requires a pull request. The agent's branches are prefixed `agent/`.
Pushing directly to `main` is disabled for every identity, including the
operator's, so that a hurried fix still leaves a record.

### 5.3 Secrets

| Secret | Where it lives | Who holds it | Rotation |
|---|---|---|---|
| Paper trading keys | Phase 1 and 2 host, OS keychain or `.env` with mode 600 | System process only | 90 days |
| Live trading keys | Phase 3 host only. Never on a machine that also has paper keys | System process only | 90 days, and immediately after any incident in playbook 7.9 |
| Layer 2 kill-switch keys | Operator's phone or second device | Operator | 90 days |
| Market data keys | Same host as the process that uses them | System process | 90 days |
| Database credentials | Host keychain. The agent's role is read-only | System (read-write role), agent (read-only role) | 180 days |
| Alert service tokens | Host | System | 180 days |

Rules:

- Live keys are issued read-only (account and positions, no trading) until the
  phase 3 gate (section 8) is passed. The upgrade to trading permission is the
  gate's final step.
- The agent's environment contains no broker credentials of any kind, in any
  phase. This is enforced by giving the agent its own OS user whose
  environment and keychain hold only the read-only database role and the
  repository credentials.
- Keys never appear in the repository, the journal, logs or alerts. A scanner
  runs in CI on every PR.
- Every rotation is journaled as `operator_action: rotate_secret` with the
  secret's name, not its value.

### 5.4 Rotation procedure

1. Create the new key in the vendor console.
2. Place it in the keychain or `.env` on the correct host.
3. Restart the process outside market hours and confirm PREFLIGHT passes.
4. Revoke the old key in the vendor console.
5. Journal the rotation.

---

## 6. Deployment

### 6.1 Phase 1 and 2: workstation or home server

- Python 3.12 in a virtual environment; Postgres 16 local; parquet on a local
  disk with at least 50 GB free.
- The main process runs under systemd (or a container with `restart:
  unless-stopped`) with a unit that starts it at 09:00 ET on trading days and
  stops it at 16:30 ET. The scheduled jobs in `data-layer.md` section 6 are
  systemd timers or cron entries.
- Clock: `chrony` or `systemd-timesyncd` enabled. PREFLIGHT fails on skew over
  500 ms, so an unsynced machine cannot trade.
- Backups: nightly `pg_dump` and a parquet rsync to an external disk or object
  storage. Phase 2 requires the monthly restore test in section 2.2.
- Power and network: if the workstation is a laptop, it must be on mains power
  and wired or stable wireless during ACTIVE. A dropped connection is a data
  stall and will flatten positions.

### 6.2 Phase 3: VPS

- A small US-East instance (2 vCPU, 4 GB RAM, 80 GB disk) close to the
  broker's endpoints. One container for the process, one for Postgres, or
  Postgres managed by the provider.
- Container restart policy `unless-stopped`; the process itself decides on
  start whether it is inside a session (playbook 7.1).
- `chrony` on the host. Firewall allows outbound to the broker, data vendor and
  alert service only, inbound SSH from the operator's address only.
- Nightly backups: Postgres dump and the day's parquet partitions to object
  storage in a different region, 90-day retention. Monthly restore test.
- No paper keys on this host. The paper environment stays on the workstation
  for the calibration replay and for drills.
- Deployment is a tagged release built by CI, pulled by the operator with a
  single command outside market hours. The agent has no deploy rights.

### 6.3 Upgrade procedure (any phase)

1. Merge to `main`; CI builds and tags.
2. After 16:30 ET, pull the tag, run the database migrations, start the
   process in a dry-run mode that executes PREFLIGHT against the paper or live
   account without activating.
3. Confirm the config hash and code version in the PREFLIGHT output.
4. Leave it stopped; the 09:00 unit starts the real session tomorrow.

Never upgrade between 09:00 and 16:30 ET.

---

## 7. Incident response playbooks

An incident is any event that locked activation, left a position open past its
rules, moved money unexpectedly, or exposed a credential. Every incident gets a
record (section 7.10) the same day.

### 7.1 Process crash with open positions

What the system does: the broker-side protective stops placed at entry remain
live. The supervisor restarts the process within seconds. On start, the
process reads positions and orders from the broker, rebuilds state from the
journal, and if it finds positions or a session that was ACTIVE, enters
WINDING_DOWN and alerts.

Operator steps:

1. Acknowledge the page. Open the broker app and confirm the positions and
   stops the alert lists match what the broker shows.
2. If the process is back and in WINDING_DOWN, let it manage exits to the
   flatten deadline. Do not activate again today.
3. If the process is not back within 2 minutes, run layer 2.
4. Collect the crash log and the last 50 journal events. Open the incident.

### 7.2 Data stall

What the system does: no new entries after 2 minutes without a control-symbol
bar. If positions are open and the stall continues, FLATTENING using broker
quotes.

Operator steps:

1. Check the vendor status page and the broker status page.
2. If the broker is healthy and the vendor is not, let FLATTENING complete.
   Do not switch feeds mid-session.
3. If both are down, go to layer 3.
4. Incident only if positions were flattened or the stall exceeded 10 minutes.

### 7.3 Broker API down

What the system does: alerts with the layer 3 instruction. It cannot cancel or
flatten by itself.

Operator steps:

1. Open the broker app. Cancel all open orders first. Open orders are the
   bigger risk because a resting entry can fill during an outage.
2. Close positions by hand, largest first.
3. When the API returns, the process reconciles and will report mismatches
   against hand-closed positions; resolve them in the 7.6 playbook.
4. Incident record, always.

### 7.4 Halted holding at deactivate or flatten deadline

What the system does: enters HALTED_EXPOSURE, alerts, and on resume exits at
the reopening price if within the slippage budget, otherwise ladders. If still
halted at 16:00, the position carries overnight and an incident is journaled.

Operator steps:

1. Read the halt reason from the exchange halt list. A LULD pause resumes in
   5 to 10 minutes; a news-pending or regulatory halt can last hours or days.
2. For a LULD pause: wait. The process handles the resume.
3. For a news or regulatory halt past 15:55: accept the overnight hold. Set a
   calendar reminder for 09:30 tomorrow. Do not try to sell in the pre-market
   unless the position is large relative to equity and the pre-market quote is
   liquid.
4. Next morning, the process's PREFLIGHT sees a non-zero position and refuses
   to activate until it is closed. Close it by hand or with a one-off exit
   command, then run PREFLIGHT again.
5. Incident record, including the reopen price and realized slippage, which
   feeds the halt simulation's reopen distribution (`backtester.md` section 5).

### 7.5 Exit ladder exhausted

What the system does: inside FLATTENING, a marketable limit at the bid minus
the impact term. Outside FLATTENING, it holds and alerts.

Operator steps:

1. Look at the quote. If the spread has blown out because of a halt, see 7.4.
2. If the spread is wide but the stock is trading, the stop is still live. Let
   the stop or the flatten deadline do the work. Manual market orders in these
   names are how slippage budgets get destroyed.
3. Incident only if the position reached 16:00.

### 7.6 Reconciliation mismatch

What the system does: locks activation and reports the differences in
positions, quantities, cash and fees.

Operator steps, in order of likelihood:

1. Fee rounding: compare the journal's fee per fill to the broker's. A one-cent
   difference per trade is a `fees.yaml` or rounding issue; fix in a PR and
   re-run reconciliation with the corrected table.
2. Partial fill accounting: a fill the stream delivered twice or not at all.
   Pull the broker's order history for the day and match order ids.
3. Hand actions: anything done through the broker app (7.3, 7.4) will not be
   in the journal. Add an `operator_action` event describing it, with the
   broker's order id.
4. A genuinely missed fill: this is a bug. The incident stays open until the
   cause is found in the adapter.
5. Activation unlocks only when reconciliation runs clean.

### 7.7 Suspected erroneous fill

Exchanges can cancel ("bust") trades executed far from the prevailing price
under their clearly erroneous execution rules, usually within 30 minutes of the
trade. A fill that looks too good is the warning sign.

Operator steps:

1. If a fill deviates more than 10 percent from the quote at the time, treat
   the position as provisional for 30 minutes: do not rely on its proceeds for
   new entries. The leverage gate already prevents reuse of unrealized gains,
   so in practice this means not raising sizes manually.
2. Watch for a broker notice of a cancelled trade. If one arrives, the journal
   needs a `fill` reversal event and the reconciliation re-run.
3. Incident record if a trade was busted.

### 7.8 Margin call despite the leverage gate

The leverage gate should make this impossible. If the broker reports an
intraday margin deficit or call anyway, something is wrong in the gate's
reading of the account payload.

Operator steps:

1. The system has already entered FLATTENING and locked activation. Confirm
   flat in the broker app.
2. Meet the call the same day by depositing cash if the broker requires it,
   even if the positions are closed. Repeated unmet calls restrict the account
   for 90 days under the intraday margin rules (design.md C1).
3. Pull the account payload the process read at the time of the last entry
   and compare it to the broker's view. The gate stays locked until the
   discrepancy is explained and the fix is merged.
4. Incident record, always, with the payload attached.

### 7.9 API key compromise

Signs: orders in the broker history the journal does not contain, logins from
unknown locations, a key found in a log or repository.

Operator steps:

1. Revoke every key for that account in the vendor console immediately,
   including the layer 2 key. Do this before investigating.
2. Close any position the journal does not know about through the broker app.
3. Contact the broker's support to flag unauthorized activity.
4. Rotate all remaining secrets in section 5.3.
5. Find how the key leaked before issuing new trading keys. New keys are
   read-only until that is known.
6. Incident record, always.

### 7.10 Incident record template

```
Incident: <short title>
Date / session id:
Detected by: <alert name | operator | reconciliation | agent review>
Phase and mode: <1|2|3>, <paper|live>
Timeline (ET):
  hh:mm  what happened
  hh:mm  what the system did
  hh:mm  what the operator did
Positions affected and realized P&L impact:
Root cause: <known | suspected | unknown>
Fix: <PR link | config change | procedure change | none>
Prevents recurrence? <yes | partly | no>, why:
Follow-ups with owner and date:
Phase regression triggered? <yes | no> (section 8)
```

Incident records live in `docs/incidents/YYYY-MM-DD-<slug>.md` and are
referenced from the journal's `incident` event.

---

## 8. Phase gates

The gates in `design.md` section 10 restated as checklists. A gate is passed
when every item is true on the same day. Regression conditions send the
system back; coming forward again requires passing the gate afresh.

### 8.1 Phase 1 to phase 2 (backtester to paper)

- [ ] Two-year walk-forward backtest runs end to end automatically.
- [ ] At least one strategy meets the go criteria in `backtester.md` section 8.
- [ ] Look-ahead guard tests pass; a deliberately leaking test strategy is
      caught.
- [ ] Reconciliation code tested against synthetic broker statements.
- [ ] Paper keys on the phase 2 host only; agent environment verified to hold
      no broker credentials.
- [ ] Alert channels tested end to end, including SMS.
- [ ] Layer 2 kill-switch script tested against the paper account.

### 8.2 Phase 2 to phase 3 (paper to live small)

- [ ] 40 or more paper sessions completed.
- [ ] Zero reconciliation mismatches in the last 40 sessions.
- [ ] Zero unhandled incidents: every incident has a record with a known root
      cause and a merged fix.
- [ ] Paper expectancy positive after modeled costs, at the realistic
      pessimism level, over the 40 sessions.
- [ ] Backtest-to-paper equivalence: modeled fills within tolerance of paper
      fills for the last 4 weekly comparisons.
- [ ] SIP data subscription active for the whole of the last 20 sessions.
- [ ] Four consecutive weekly kill-switch drills passed on all three layers.
- [ ] Monthly restore test passed at least twice.
- [ ] Live account funded with the phase 3 amount, at least $2,000 and sized so
      total loss is acceptable. Margin enabled, leverage gate verified against
      the live account payload with read-only keys.
- [ ] Operator has read the broker's margin agreement and the intraday margin
      documentation in the last 30 days.
- [ ] Final step: upgrade live keys to trading permission.

### 8.3 Phase 3 review at 60 sessions

- [ ] Net positive expectancy after real fees and real slippage.
- [ ] Max drawdown within the configured weekly and monthly budgets throughout.
- [ ] Live slippage within tolerance of the model for the last 8 weekly
      comparisons.
- [ ] No incident in the last 20 sessions with an unknown root cause.

Passing allows a size increase of at most 50 percent, then another 60-session
review. Failing means stay at the current size, or regress.

### 8.4 Regression conditions

| Condition | Consequence |
|---|---|
| Weekly loss limit hit twice in a rolling 8 weeks (phase 3) | Back to phase 2 for 20 paper sessions |
| Any incident with unknown root cause open for more than 5 trading days (phase 3) | Trading keys downgraded to read-only until closed |
| Reconciliation mismatch with a real missed fill (any phase) | Activation locked until the adapter fix is merged and 5 clean paper sessions follow |
| Slippage outside tolerance for 3 consecutive weekly comparisons (phase 3) | Size halved; back to phase 2 if still outside after 3 more |
| Kill-switch drill failure on any layer | No live activation until the drill passes |
| Margin call event (7.8) | Phase 3 keys read-only until the root cause is fixed; then 10 clean paper sessions |

---

## 9. Changelog

- v0.1: initial runbook, expanding `design.md` section 6 into procedures,
  playbooks, phase gates and regression rules.
