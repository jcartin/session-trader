# Session Trader

A personal, single-account system for bounded-window intraday trading of
listed US stocks priced between $1 and $5. It produces ranked trade
recommendations, optionally executes them, and is flat when deactivated.

Project name is a working title.

Scope, deliberately: one person, one account in that person's own name, their
own money only. No other people's money, no publishing or selling of
signals, no pooled vehicle. Each of those would change the legal status of
the activity (see `docs/regulatory-and-constraints.md` section 2) and is a
decision to take with counsel, not a feature to add.

- `docs/README.md`: index of the design document set (eleven documents covering every component, operations and the agent's role)
- `CLAUDE.md`: rules for an AI agent working in this repository

## Running phase 0

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .
cp .env.example .env   # fill in Alpaca paper keys
python scripts/phase0/measure_universe.py --out data/phase0 --delisted SYM1,SYM2
```

Status: design phase plus the phase 0 measurement script. See `docs/design.md` section 10 for the roadmap.
