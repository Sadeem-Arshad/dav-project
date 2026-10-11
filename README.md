# GitHub Open-Source Project Health Analytics

Course: Data Analysis and Visualization (DAV), FAST-NUCES Lahore
Team: Hamza Sheikh (24L-2500), Sadeem Arshad (24L-2502)

A Spark/Databricks pipeline using the Medallion Architecture (Bronze, Silver,
Gold), ending in a Power BI dashboard.

## Business question
Which open-source Python projects are healthy and active, who contributes to
them, and how fast are issues and pull requests handled?

## Data source
GitHub REST API, for 8 repos: pandas-dev/pandas, numpy/numpy,
scikit-learn/scikit-learn, matplotlib/matplotlib, scipy/scipy,
fastapi/fastapi, pallets/flask, pytest-dev/pytest.

We pull 3 entities per repo: commits, issues, pull requests. Note: GitHub's
issues endpoint also returns pull requests, so these get split apart in
Silver.

## Sample data (Phase 1)
| Sample | Rows | Size |
|---|---|---|
| data/samples/full/ | 4,800 | 45.18 MB |
| data/samples/incremental/ (since 2026-09-19) | 2,426 | 29.70 MB |

## Repo contents
```
data/samples/full/          sample full-load JSON (Phase 1)
data/samples/incremental/    sample incremental JSON (Phase 1)
extract_github.py            Phase 1 extraction script
pii_scan.py                  checks samples for PII
docs/                        proposal doc (Phase 1)
databricks/
  00_setup_and_logging.py    makes the catalog/schema/tables, has shared helper functions
  01_raw_to_bronze.py        GitHub API -> Bronze (full / incremental / backfill)
  02_bronze_to_silver.py     Bronze -> Silver (typed, deduped, PII hashed)
  03_schema_drift_demo.py    shows the pipeline doesn't break on a weird/broken record
```
Phase 3 (not done yet): Gold notebook + Power BI dashboard.

## How the pipeline works
GitHub API -> Bronze (raw JSON as-is) -> Silver (typed, cleaned, PII hashed) ->
Gold (Phase 3) -> dashboard (Phase 3).

Every write to Bronze and Silver uses MERGE INTO, keyed on the commit sha or
the issue/PR id. So running a notebook again doesn't create duplicate rows,
it just adds new stuff and updates anything that changed on GitHub. Every run
writes a row to `pipeline_execution_logs`, pass or fail, so there's always a
record of what happened.

## Bronze tables
`bronze_commits`, `bronze_issues`, `bronze_pulls` all have the same columns:

| Column | Type | What it is |
|---|---|---|
| record_key | string | sha for commits, id for issues/pulls. This is the MERGE key |
| source_repo | string | e.g. pandas-dev/pandas |
| entity_type | string | commits / issues / pulls |
| raw_json | string | the raw GitHub response for this record, kept as text |
| api_params | string | which params we used to fetch it |
| load_type | string | full / incremental / backfill |
| batch_id | string | which run wrote this row |
| run_id | string | id of that notebook run |
| load_timestamp | timestamp | when it was written |

`bronze_quarantine`: records with no usable key (e.g. missing sha) -
source_repo, entity_type, raw_record, reason, batch_id, run_id, load_timestamp.

## Silver tables
Author names/emails are gone here, replaced with a hashed `author_key`.

`silver_commit`: sha (key), repo, author_key, committer_key, committed_at,
message_length, is_merge_commit, load_timestamp.

`silver_issue`: issue_id (key), repo, number, state, author_key, created_at,
updated_at, closed_at, comment_count, time_to_close_hours, load_timestamp.

`silver_pull_request`: pr_id (key), repo, number, state, author_key,
created_at, updated_at, closed_at, merged_at, is_merged, is_draft,
base_branch, time_to_merge_hours, load_timestamp.

`silver_quarantine`: records that failed to parse - entity_type, record_key,
repo, reason, raw_json, batch_id, run_id, load_timestamp.

`pipeline_execution_logs`: one row per run per entity - run_id, layer,
entity, parameters, start_time, end_time, status, rows_inserted,
rows_updated, rows_quarantined, error_message. This is the proof table.

## How to run it
Import all 4 notebooks from `databricks/` into Databricks, same folder, run
in this order:

1. `00_setup_and_logging` - run once, makes everything
2. `01_raw_to_bronze` - pulls from GitHub into Bronze
3. `02_bronze_to_silver` - Bronze into Silver
4. `03_schema_drift_demo` - optional proof, safe to re-run anytime

**Normal run (incremental):** on `01_raw_to_bronze`, set `load_type` =
incremental, leave `since_date`, `until_date`, `batch_id` blank. Then run
`02_bronze_to_silver` with `batch_id` blank too.

**First time ever (full load):** same but `load_type` = full. Blank
`since_date` pulls about the last 12 months.

**Backfill (redo an old date range on purpose):** set `load_type` = backfill,
`since_date` and `until_date` to whatever window you need
(e.g. 2026-09-01T00:00:00Z to 2026-09-08T00:00:00Z), and give `batch_id` a
name so you can find it later. Nothing is hardcoded, it all comes from the
widgets. Re-running a backfill over the same window doesn't duplicate rows.

**GitHub token:** paste it into the `github_token` widget each session. Never
saved anywhere. Works without one too, just with a lower rate limit.

**Checking the proof:** query
`SELECT * FROM workspace.dav_project.pipeline_execution_logs ORDER BY start_time DESC;`
Run 01 or 02 twice with the same inputs - the second run's `rows_inserted`
should be 0 (or close to it), since the data's already there.

## PII handling
Raw names/emails only ever sit inside Bronze's raw_json. Silver drops them
completely and replaces them with a salted SHA-256 hash (`author_key`). The
salt is just a fixed string in the code, not a real secret (repo's public
anyway) - it's there so the same person always hashes the same way, which is
needed for MERGE to recognize repeat authors.

## Schema drift
`03_schema_drift_demo.py` shows what happens with a weird record:
- an unexpected new field -> ignored, doesn't break anything
- a field in the wrong shape -> that one field goes blank, row still works
- a genuinely broken record -> goes to silver_quarantine with a reason,
  doesn't stop the run
- adding a new column to Silver on purpose later -> done with
  `MERGE WITH SCHEMA EVOLUTION INTO`, no rebuilding tables

## Status
- [x] Phase 1: proposal, sample data, extraction scripts
- [x] Phase 2: Bronze + Silver pipeline, MERGE INTO, backfill, schema drift,
      logging, this README (due 10 Oct 2026)
- [ ] Phase 3: Gold layer + Power BI dashboard (due 24 Oct 2026)
