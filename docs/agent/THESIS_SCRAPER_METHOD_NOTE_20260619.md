# Thesis Scraper Method Note - 2026-06-19

## Status

Completed a thesis-facing explanation for how to describe and include scraping based on `services/scraper/scraper.ipynb`.

## Output

- `docs/thesis/SCRAPER_METHOD_AND_EVIDENCE.md`

## Validation

- Source notebook inspected: `services/scraper/scraper.ipynb`.
- Production scraper service inspected for alignment: `services/scraper/main.py`.
- Continuous scraper context inspected: `services/pipeline/continuous_scraper.py`.

## Claim Boundary

The notebook uses sample local HTML, so it proves parser, field extraction, text cleaning, and deduplication logic. It does not prove current live database counts or that every configured job-board source was reachable.
