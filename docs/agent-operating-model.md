# Agent Operating Model

Status: draft v0.1, 2026-10-16
Companion to `design.md` section 8 (roles and guardrails) and section 5.8
(journal); `operations.md` sections 1, 2, 5 and 7; `backtester.md` sections 8
and 9; `data-layer.md` section 5.

This document says how the AI agent (Claude Code, working in this repository
and reading the journal database) takes part in building, running, advising
on and maintaining Session Trader, and how its limits are enforced by
configuration rather than by instruction.

---

## 1. Why the agent is out of the hot path

A large language model call takes seconds, costs money per call, does not
return the same output for the same input, and cannot be replayed in a
backtest. Each of those alone disqualifies it from a component whose decisions
must be reproducible from logged inputs (design.md principle 1). The signal
engine, risk manager, position manager and execution adapter are therefore
deterministic code with versioned parameters, and the agent works on them from
outside: writing them, testing them, reading what they did, and proposing
changes through pull requests. Nothing the agent does during a session can
change what the session does.

---

## 2. Roles

### 2.1 Build

| | |
|---|---|
| Inputs | Design documents, open tickets, test failures, the journal schema, vendor documentation |
| Outputs | Code, tests, migrations, documentation, backtest reports, pull requests on `agent/` branches |
| Autonomous | Create branches, write and run code and tests locally, run backtests on stored data, open PRs, respond to review comments, update documents to match code |
| Needs approval | Merging anything to `main`; adding a dependency; any change under `config/`; any change to the `Broker` interface or the journal schema |
| Never | Push to `main`; push to the release tag the live host pulls; disable or skip a test to get green; store a credential in the repository |
| Enforcement | Branch protection requires a PR for `main`; the agent's git identity has no tag-push permission; CI runs a secret scanner and fails on any match; `CODEOWNERS` routes `config/` and `src/execution/` to the operator |

### 2.2 Run

| | |
|---|---|
| Inputs | Job logs, PREFLIGHT output, alerts, the journal, the exchange calendar |
| Outputs | The morning note, job-failure diagnoses, restart commands for crashed non-trading jobs |
| Autonomous | Re-run a failed `ingest_*` or `refresh_symbols` job; run PREFLIGHT in dry-run mode against the paper account; publish reports; confirm the journal and broker agree after a restart in paper mode |
| Needs approval | Activating any session, paper or live; restarting the trading process during market hours; anything that touches the live host |
| Never | Issue `activate`, `deactivate`, `flatten` or `kill` on a live session; change a running session's configuration; approve or skip an advisory card |
| Enforcement | The agent runs as its own OS user with no broker credentials and no SSH key for the live host; the trading process accepts operator commands only from the operator's authenticated UI session or local socket, which the agent's user cannot reach |

### 2.3 Advise

| | |
|---|---|
| Inputs | The journal (read-only), `universe_snapshots`, `reference_daily`, filings and press releases for watchlist names, backtest outputs, broker statements the operator shares |
| Outputs | Pre-session note, post-session review, weekly metrics table, tuning proposals as PRs, calibration proposals as PRs |
| Autonomous | Read anything in the journal and data layer; run any backtest; draft any proposal |
| Needs approval | Every parameter change, by PR merge; every blacklist suggestion, by the operator editing `blacklist.yaml` |
| Never | Place, modify or cancel an order; hold broker credentials; present a recommendation to anyone but the operator |
| Enforcement | Read-only Postgres role `agent_ro` with `SELECT` on the journal schema and nothing else; no broker SDK configuration in the agent's environment; the advisory UI has no agent-facing endpoint |

### 2.4 Maintain

| | |
|---|---|
| Inputs | Quality flag rates, vendor status, dependency advisories, backtest-to-live comparisons, fee and rule notices |
| Outputs | Data quality tickets, dependency PRs, calibration PRs, `fees.yaml` PRs with the citing notice, documentation drift fixes |
| Autonomous | Run the weekly calibration replay; run regression backtests against a pinned reference run; open PRs |
| Needs approval | Deploying anything; rotating a secret; changing a vendor |
| Never | Alter or delete journal rows; rewrite history on a shared branch; run migrations against the live database |
| Enforcement | `agent_ro` has no write grant; migrations run from the operator's deploy step only (operations.md section 6.3) |

The nevers are enforced by what the agent's user can reach, not by what it is
told. If a never becomes reachable, that is itself an incident.

---

## 3. Access matrix

| Resource | Operator | Trading process | Agent |
|---|---|---|---|
| Broker trading keys | Holds | Reads from keychain | None |
| Broker read-only keys (phase 3 pre-gate) | Holds | Reads | None |
| Layer 2 kill-switch keys | Holds on phone | None | None |
| Market data keys | Holds | Reads | Read-only historical key for backfills |
| Postgres `trader_rw` | Yes | Yes | No |
| Postgres `agent_ro` | Yes | No | Yes |
| Parquet data directory | Read-write | Read-write | Read-only mount, plus a separate scratch directory for backtest outputs |
| Repository | Write, merge, tag | None | Write to `agent/*` branches, open PRs |
| Live host SSH | Yes | n/a | No |
| Alert service | Receives | Sends | Sends to the log channel only |

---

## 4. Specified artifacts

### 4.1 Pre-session note (08:30 ET)

Posted to the operator channel. Must fit on one phone screen above the fold.

```
Pre-session note, <date>, mode=<paper|live>, config=<hash8>, code=<sha8>
Account: equity $X, gross exposure $0 (must be 0), buying power $Y
Overnight: <incidents open | none>; jobs: <all green | failures>
Watchlist: N names. Top 5 by score: SYM (score, ADV $, spread %), ...
Borderline pump flags: SYM: <one line why>; ...
Filings since yesterday for watchlist names: SYM: <8-K item / offering / none>
Blacklist suggestions: SYM: <reason>  (operator decides)
Rule or fee changes noticed: <none | notice id and one line>
Recommendation: <activate as normal | activate with caution on X | skip today because Y>
```

Queries behind it, all against `agent_ro` and the data layer:

- Account line: last `session_state` event of type CLOSED and its account
  snapshot; if any position is non-zero, say so in capitals.
- Watchlist: `universe_snapshots` where `date = today`, joined to
  `reference_daily` for ADV, spread estimate and `pump_score`.
- Borderline: `pump_score` within 20 percent of the threshold, either side.
- Filings: EDGAR full-text search for each watchlist CIK since the previous
  close, filtered to 8-K, 424B (offerings), S-1, S-3 and 6-K.
- Jobs: the job log table for the last 24 hours.

The recommendation line is advisory. The operator activates.

### 4.2 Post-session review (evening)

```
Session review, <date>, mode, config=<hash8>
Result: N trades, W wins, net P&L $X, fees $F, time in market M minutes
Versus model: slippage realized X bps vs modeled Y bps; fills vs expected
What fired: per strategy: candidates, accepted, filled, P&L
What was rejected: per risk rule: count (top 3 rules named)
Notable trades: up to 3, one line each: entry reason, exit reason, outcome
Incidents: <list | none>
Data quality: flagged bars today, vendor flag rate vs 20-day average
Halt exposure: <none | SYM halted hh:mm to hh:mm, outcome>
Observations: up to 3 sentences, each tied to a journal event id
Proposals: <none | PR link(s)>, never applied
```

Queries: `candidate`, `risk_decision`, `order_intent`, `fill`,
`position_close` and `incident` events for the session id; the backtester's
replay of the day for the "versus model" line (`backtester.md` section 9);
`reference_daily.quality_flags` for the data line.

Observations must cite event ids so the operator can check them. An
observation without a citation is removed before posting.

### 4.3 Weekly metrics table (Saturday)

For the last 20 and 60 sessions, grouped by config hash: sessions, trades,
expectancy per trade, profit factor, max drawdown dollars and percent, Sharpe
at session level, slippage versus model, risk rejection mix, halt exposure
incidents. Plus the open PR list and the open incident list with owners.

### 4.4 Tuning proposal (PR to `strategies.yaml` or `screener.yaml`)

PR body, in this order:

1. **Hypothesis.** One sentence: what is believed to be true and why it
   should change a parameter.
2. **Change.** The parameter, old value, new value, and the config hash
   before and after.
3. **Evidence.** Walk-forward out-of-sample results on the same data window,
   old versus new, at all three pessimism levels (`backtester.md` section 2
   and 8). Trade count. Regime slices.
4. **Parameter count tried** to arrive at this proposal, and the deflated
   result.
5. **What would make this wrong.** The observation that should cause a
   revert, and the session count after which to check.
6. **Recommendation.** Merge, merge at reduced weight, or do not merge yet.

A proposal with fewer than 100 out-of-sample trades says "not evaluable" in
the recommendation, and is opened only so the operator can see the direction
of the evidence. The operator merges; the agent never does. Merged changes
take effect at the next PREFLIGHT.

### 4.5 Risk proposal (PR to `risk.yaml`)

Same format, with one difference: evidence can justify a tighter limit but
never a looser one. A proposal to loosen a risk limit states that plainly in
the first line and carries no recommendation; the decision is the
operator's alone.

---

## 5. The weekly calibration loop

The agent's standing maintenance job, run every Friday after the data jobs
finish, is the backtest-to-live equivalence check in `backtester.md`
section 9.

1. For each session this week, replay the journal's stored bars and quotes
   through the backtester with the production config hash.
2. Match modeled fills to actual fills by order id. Report, per strategy and
   per symbol: price difference in basis points, quantity difference, time
   difference, fee difference.
3. Compute the week's systematic bias: the mean signed difference and its
   standard error.
4. If the bias is outside tolerance (default: mean more than 5 bps or fee
   difference more than one cent per trade), open a calibration PR proposing
   a change to `impact_coeff`, the spread model parameters, `stop_gap_factor`
   or `fees.yaml`, with the evidence and the same "what would make this
   wrong" clause.
5. Post the comparison table in the Saturday metrics.

Four consecutive in-tolerance weeks are a phase 2 gate item
(`operations.md` section 8.2). The loop is also the first place a vendor
data problem or a broker behavior change shows up, which is why it is weekly
rather than monthly.

---

## 6. Repository conventions

### 6.1 Branches and commits

- `main` is protected: PR required, status checks required, no direct push
  for anyone.
- Agent branches: `agent/<area>-<short-slug>`, for example
  `agent/backtester-halt-reopen-distribution`. Operator branches:
  `op/<slug>`.
- Commit subject in imperative mood under 72 characters; body says what
  changed and why, not how. One themed change per commit. Attribution lines
  as the harness supplies them.
- No model identifiers, keys, account numbers or P&L figures in commit
  messages.

### 6.2 Pull request template

```
## What
One paragraph.

## Why
The ticket, incident record, or observation that motivated this.

## Config hash
before: <hash8>  after: <hash8>   (or "no config change")

## Evidence
Backtest or calibration report link, with pessimism levels, if any parameter
or model changed. "n/a" for pure code with unchanged behavior.

## Tests
What was run and the result. A reference backtest run id if behavior could
have changed.

## Risk
What breaks if this is wrong, and how to roll back.
```

CI on every PR: ruff, pytest, the secret scanner, a schema check that the
journal event types in code match `design.md` section 5.8, and a reference
backtest whose summary metrics must match the pinned run to the cent unless
the PR says it changes behavior.

### 6.3 CLAUDE.md for this repository

A short file at the repository root. Proposed contents:

```
# Session Trader

Read first: docs/README.md, then docs/design.md sections 1 to 3 and 5.4,
then the component doc for the area you are touching.

Must:
- Keep docs and code in agreement in the same PR.
- Run `pytest` and `ruff` before opening a PR; attach a reference backtest
  run id if behavior could change.
- Open PRs on agent/* branches. Never push to main.
- Record config hashes before and after any change under config/.

Never:
- Place, modify or cancel an order, or call any broker endpoint that can.
- Read or write broker credentials; none exist in your environment.
- Write to the journal; your database role is read-only.
- Loosen a value in config/risk.yaml without saying so in the PR's first line.
- Skip, disable or weaken a test to make CI pass.
- Touch the live host or run migrations against it.

Conventions: Python 3.12, polars and duckdb for data, pydantic config,
ET for display and UTC for storage, .yaml under config/ is operator-owned.
```

### 6.4 docs/README.md index

```
# Documentation

design.md               System and operational design; constraints register;
                        roadmap; verification log. Start here.
backtester.md           Event model, fill and impact models, halt simulation,
                        fee table, validation protocol, equivalence loop.
data-layer.md           Storage layout, schema, vendor adapters, adjustment,
                        quality flags, ingestion jobs, phase 0 measurements.
operations.md           Daily runbook, routines, monitoring, kill switch,
                        change management, secrets, deployment, playbooks,
                        phase gates.
agent-operating-model.md  Agent roles, access matrix, note and review
                        templates, proposal format, calibration loop,
                        repository conventions.
incidents/              One record per incident, YYYY-MM-DD-<slug>.md.
phase0-results.md       Measured spreads, halts, universe size (when run).
```

---

## 7. Cost expectations for agent usage

Assumes one agent session per task, with the journal queries kept narrow.

| Phase | Typical weekly work | Estimated monthly cost |
|---|---|---|
| 1, build | Several multi-hour coding sessions; backtests run locally and cost nothing | $50 to $150 |
| 2, paper | Daily pre-session note and post-session review (short, templated), weekly metrics and calibration, occasional code | $50 to $100 |
| 3, live | Same as phase 2 plus incident analysis | $50 to $150 |

Two habits keep this flat: the notes and reviews are produced from fixed
queries and templates rather than from reading the whole journal, and backtest
reports are summarized by the backtester itself before the agent reads them.
These ranges supersede the "LLM usage" row in `design.md` section 9 where
they differ; the design table should be aligned at its next revision.

---

## 8. Changelog

- v0.1: initial operating model, expanding `design.md` section 8 into roles
  with enforcement, an access matrix, artifact templates, the calibration
  loop and repository conventions.
