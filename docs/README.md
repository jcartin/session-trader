# Documentation index

Start with `design.md`. It holds the goals, the constraints register, the
architecture overview, costs, roadmap and the phase 0 verification log. Each
component then has its own document at implementation depth. Where two
documents disagree, the component document is more recent and wins until
`design.md` is updated.

| Document | Covers |
|---|---|
| `design.md` | System and operational design overview; constraints register; cost tiers; roadmap and phase exit criteria; OTC as future work; verification log |
| `regulatory-and-constraints.md` | Legal status, manipulation rules and conduct invariants, broker and margin terms, market data licensing, market structure risks, taxes and records, OTC rules, pending changes, required design deltas, professional consultations |
| `research/` | The three underlying research reports with every source: R1 legal status and manipulation, R2 broker and data terms, R3 tax, records and OTC |
| `data-layer.md` | Storage layout, Parquet and DuckDB schema, point-in-time attributes, vendor adapter protocol, adjustment, quality flags, ingestion jobs, phase 0 measurements |
| `screener.md` | Universe filter pipeline, ranking score, pump-detection score, point-in-time guarantee, output tables |
| `signal-engine.md` | Strategy protocol, MarketContext and look-ahead guard, Candidate and ExitSignal schemas, conflict resolution, three starter strategies |
| `risk-manager.md` | Rule chain, sizing math with worked examples, loss limits and what they force, config split and change path, invariants and tests |
| `execution.md` | Broker protocol and models, order lifecycle, entry pricing, exit ladder, protective stops, reconciliation, Alpaca adapter, error taxonomy, FakeBroker |
| `session-controller.md` | State machine including LOCKED and HALTED_EXPOSURE, transition table, timers, PREFLIGHT checklist, operator commands, crash recovery, tests |
| `journal-and-reporting.md` | Append-only event schema and payloads, metric definitions, reconciliation, tax lot export, agent read-only role |
| `backtester.md` | Event replay, fill and impact models, spread sources, halt simulation, date-ranged fees, validation protocol, backtest-to-live equivalence |
| `operations.md` | Daily, weekly and monthly runbooks, monitoring thresholds, three-layer kill switch, change management, secrets, deployment, incident playbooks, phase gates |
| `agent-operating-model.md` | Agent roles and access matrix, pre-session note and post-session review templates, tuning proposal format, calibration loop, repository conventions |
| `incidents/` | One record per incident, `YYYY-MM-DD-<slug>.md`, template in `operations.md` |
| `phase0-results.md` | Measured spreads, halt rates, universe size and data coverage, once the phase 0 script has been run |

Reading order for a newcomer: `design.md` sections 1 to 3, then
`regulatory-and-constraints.md`, then `operations.md`, then whichever
component you are working on.
