# Session Trader

Personal, single-account, bounded-window intraday trading system for listed
US stocks priced $1 to $5. Design phase; see `docs/README.md`.

Read first: `docs/README.md`, then `docs/design.md` sections 1 to 3 and 5.4,
then the component document for the area you are touching.

Must:
- Keep docs and code in agreement in the same PR. A `file:line` or default
  cited in a doc is a contract with the code.
- Run `pytest` and `ruff` before opening a PR; attach a reference backtest
  run id if behavior could change.
- Open PRs from `agent/*` branches. Never push to `main`.
- Record config hashes before and after any change under `config/`.
- Say in the first line of a PR if any value in `config/risk.yaml` is loosened.

Never:
- Place, modify or cancel an order, or call any broker endpoint that can.
- Read or write broker credentials; none exist in the agent's environment.
- Write to the journal; the agent's database role is read-only.
- Skip, disable or weaken a test to make CI pass.
- Touch the live host or run migrations against it.
- Put model identifiers, keys, account numbers or P&L figures in commits.

Conventions: Python 3.12; polars and duckdb for data; pydantic for config and
schemas; UTC in storage, ET for display; YAML under `config/` is
operator-owned; docs in plain Markdown with a Status line and a changelog.
