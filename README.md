# Session Trader

A personal, single-account system for bounded-window intraday trading of
listed US stocks priced between $1 and $5. It produces ranked trade
recommendations, optionally executes them, and is flat when deactivated.

Project name is a working title.

- `docs/design.md`: system and operational design (source of truth while in design phase)
- `docs/backtester.md`: fill, spread, halt and fee models, validation protocol
- `docs/data-layer.md`: storage layout, schema, vendor adapters, ingestion jobs
- `scripts/phase0/measure_universe.py`: phase 0 measurements against an Alpaca paper account (not yet executed)

## Running phase 0

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .
cp .env.example .env   # fill in Alpaca paper keys
python scripts/phase0/measure_universe.py --out data/phase0 --delisted SYM1,SYM2
```

Status: design phase plus the phase 0 measurement script. See `docs/design.md` section 10 for the roadmap.
