# GitHub Open-Source Project Health Analytics

**Course:** Data Analysis and Visualization (DAV), FAST-NUCES Lahore
**Team:** Hamza Sheikh (24L-2500), Sadeem Arshad (24L-2502)

An end-to-end data engineering pipeline on Apache Spark (Databricks) using the
Medallion Architecture (Bronze, Silver, Gold), ending in a BI dashboard.

## Business question
Which open-source Python projects are healthy and active, who contributes to them,
and how quickly are issues and pull requests handled?

## Data source
GitHub REST API (`https://api.github.com`), for 8 repositories:
`pandas-dev/pandas`, `numpy/numpy`, `scikit-learn/scikit-learn`,
`matplotlib/matplotlib`, `scipy/scipy`, `fastapi/fastapi`, `pallets/flask`,
`pytest-dev/pytest`.

| Entity | Endpoint | Full load | Incremental load |
|---|---|---|---|
| Commits | `/repos/{repo}/commits` | 12-month baseline (`since`) | `since` timestamp |
| Issues | `/repos/{repo}/issues?state=all` | 12-month baseline (`since`) | `since` on `updated_at` |
| Pull requests | `/repos/{repo}/pulls?state=all` | PRs created in last 12 months | `updated_at` filter |

Note: the issues endpoint also returns pull requests. These are deduplicated in Silver.

## Sample data (Phase 1)
| Sample | Rows | Size |
|---|---|---|
| `data/samples/full/` | 4,800 | 45.18 MB |
| `data/samples/incremental/` (since 2026-09-19) | 2,426 | 29.70 MB |

Estimated volume: full load about 1.5 GB raw JSON; incremental about 30 MB per week.

## Repository contents
```
data/samples/full/          sample full-load JSON files
data/samples/incremental/   sample incremental-load JSON files
extract_github.py           extraction script (full and incremental loads)
pii_scan.py                 scans the samples for PII and reports counts
```
Planned for Phase 2: `notebooks/` (Databricks notebooks), `docs/` (proposal).

## How to run
```
pip install requests
set GITHUB_TOKEN=your_token          # Windows CMD. Never commit the token.
python extract_github.py full --max-pages 2
python extract_github.py incremental --since 2026-09-19T00:00:00Z
python extract_github.py full --from-date 2025-09-26T00:00:00Z   # real 12-month baseline
python pii_scan.py
```

## PII handling
The data contains author names, emails and GitHub logins. Raw data is kept only in
Bronze. In Silver, names and emails are dropped, identities are replaced with a salted
SHA-256 hash, and emails in free text are redacted.

## Architecture
GitHub API -> Bronze (raw JSON, Delta) -> Silver (cleaned, deduplicated, PII removed)
-> Gold (star schema and aggregates) -> Power BI dashboard.

## Status
- [x] Phase 1: proposal, sample data, extraction scripts
- [ ] Phase 2 (due 10 Oct 2026)
- [ ] Phase 3 (due 24 Oct 2026)
