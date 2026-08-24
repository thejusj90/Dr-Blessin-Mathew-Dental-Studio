# DentMemo Prospect Engine

An isolated, state-agnostic Python pipeline that turns an authoritative dentist registry into a ranked, evidence-backed prospect database. It **does not scrape Google Maps** or send outreach. Exa Agent is the research layer; SQLite is the resumable source of working state.

## Architecture

`ingestion.py` maps flexible CSV headers, normalizes names, creates stable IDs, and conservatively deduplicates. `enrichment.py` submits batches through the official `exa-py` Agent SDK with `input.data`, an explicit effort, and schema-constrained output. `storage.py` atomically stores dentists, prospects, evidence, Exa runs/cost, clinics, and dentist–clinic relationships. `scoring.py` keeps identity confidence separate from sales score. `exporters.py` builds dentist and clinic views.

Interrupted `processing` rows are reset to `pending` when the database opens. Completed records are skipped unless `--force` is used. Temporary 429/5xx/network failures use bounded exponential backoff; authentication and schema errors fail immediately.

## Install and configure

Requires Python 3.10+.

```bash
cd prospect-engine
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `EXA_API_KEY` in `.env`. **Never commit `EXA_API_KEY`.** The `.env` and working databases/exports are ignored. Effort defaults to cost-controlled `medium`; supported values are `low`, `medium`, `high`, and `auto`.

## Input and import

CSV headers are mapped case-insensitively. A name header (`name`, `dentist_name`, or `doctor_name`) is required. Registration, city, state, district, and address aliases are optional. Source files are read only and never modified.

```bash
python -m dentmemo_prospects.cli import data/input/goa_dentists.csv --state Goa
python -m dentmemo_prospects.cli stats --state Goa
```

IDs use registration number + state when available, otherwise normalized name + city + state. Same-name people are not merged unless that deterministic identity matches.

## Safe enrichment workflow

Always preview first; dry-run makes no Exa calls:

```bash
python -m dentmemo_prospects.cli enrich --state Goa --dry-run
python -m dentmemo_prospects.cli enrich --state Goa --limit 5 --effort medium
python -m dentmemo_prospects.cli enrich --state Goa --limit 50
python -m dentmemo_prospects.cli enrich --state Goa
```

Control requests with `--batch-size`, `--max-cost`, and `--limit`. A new batch is not started after recorded project cost reaches the limit. Each completed batch is persisted before the next begins. Inspect one row with `python -m dentmemo_prospects.cli show DENTIST_ID`.

Only publicly presented business/professional contacts are requested. Ambiguous results are retained with nulls and routed to manual review. Google presence is evidence-based (`confirmed`, `probable`, `not_found`, `unknown`); the engine never fetches Google Maps HTML.

## Export

```bash
python -m dentmemo_prospects.cli export --state Goa
```

This creates `goa_all_prospects.csv`, segment A/B files, `goa_manual_review.csv`, a clinic-level file with all related dentists, and `goa_summary.json` under `data/output`. Segment thresholds are A ≥75, B ≥55, C ≥35, D below 35. Prospect and identity weights are loaded from `config/scoring.yaml`.

## Tests and troubleshooting

```bash
pytest -q
```

Tests use mocked Exa clients and consume no credits. If `EXA_API_KEY` is missing, imports, stats, dry-runs, exports, and tests still work; live enrichment does not. For 401/403 errors check the key without printing it. For schema errors update the integration against the installed `build-with-exa` skill/current official SDK. Failed batches remain retryable. Use `--force` only for an intentional re-check. `refresh --older-than DAYS` is a non-enriching placeholder for the future freshness workflow.
