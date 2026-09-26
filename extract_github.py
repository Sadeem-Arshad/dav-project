"""
GitHub extractor for the DAV medallion-pipeline project.

Usage:
  # Small sample of the full load (2 pages per repo/entity)
  python extract_github.py full --max-pages 2

  # Real full load: bounded 12-month baseline
  python extract_github.py full --from-date 2025-09-26T00:00:00Z

  # Incremental load: only records created/updated after --since
  python extract_github.py incremental --since 2026-09-19T00:00:00Z

Full load semantics with --from-date:
  commits : commits authored since the date
  issues  : issues/PRs UPDATED since the date (GitHub's `since` filter is on updated_at)
  pulls   : PRs CREATED since the date (client-side cutoff, newest first)
Without --from-date, the full load fetches all history (can be very large).

Set GITHUB_TOKEN in your environment (5,000 req/hr instead of 60).
Output: <out>/<load_type>/<owner>__<repo>__<entity>.json
"""
import argparse
import json
import os
import time
from pathlib import Path

import requests

REPOS = [
    "pandas-dev/pandas",
    "numpy/numpy",
    "scikit-learn/scikit-learn",
    "matplotlib/matplotlib",
    "scipy/scipy",
    "fastapi/fastapi",
    "pallets/flask",
    "pytest-dev/pytest",
]

# entity -> API path suffix
ENTITIES = {
    "commits": "commits",
    "issues": "issues",   # note: this endpoint also returns pull requests
    "pulls": "pulls",
}

PER_PAGE = 100


def headers():
    h = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def build_params(entity, load_type, since, from_date):
    p = {"per_page": PER_PAGE}
    if entity in ("issues", "pulls"):
        p["state"] = "all"
    if load_type == "full":
        if entity == "commits":
            p["since"] = from_date            # None -> all history
        elif entity == "issues":
            p.update({"sort": "created", "direction": "asc", "since": from_date})
        else:  # pulls: no 'since'; with a cutoff go newest-first and stop early
            if from_date:
                p.update({"sort": "created", "direction": "desc"})
            else:
                p.update({"sort": "created", "direction": "asc"})
    else:  # incremental
        if entity == "commits":
            p["since"] = since
        elif entity == "issues":
            p.update({"since": since, "sort": "updated", "direction": "desc"})
        else:  # pulls has no 'since'; sort by updated and filter client-side
            p.update({"sort": "updated", "direction": "desc"})
    return {k: v for k, v in p.items() if v is not None}


def fetch(repo, entity, load_type, since, max_pages, from_date=None):
    url = f"https://api.github.com/repos/{repo}/{ENTITIES[entity]}"
    params = build_params(entity, load_type, since, from_date)
    rows, page = [], 1
    while True:
        params["page"] = page
        r = requests.get(url, headers=headers(), params=params, timeout=60)
        if r.status_code in (403, 429) and r.headers.get("X-RateLimit-Remaining") == "0":
            wait = max(int(r.headers.get("X-RateLimit-Reset", 0)) - time.time(), 1)
            print(f"  rate limited, sleeping {int(wait)}s")
            time.sleep(wait + 1)
            continue
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break

        # Client-side cutoffs for the PR endpoint (it has no `since` parameter)
        cutoff_hit = False
        if entity == "pulls" and load_type == "incremental":
            kept = [b for b in batch if b["updated_at"] >= since]
            cutoff_hit = len(kept) < len(batch)
            batch = kept
        elif entity == "pulls" and load_type == "full" and from_date:
            kept = [b for b in batch if b["created_at"] >= from_date]
            cutoff_hit = len(kept) < len(batch)
            batch = kept

        rows.extend(batch)
        if cutoff_hit or len(batch) < PER_PAGE or (max_pages and page >= max_pages):
            break
        page += 1
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("load_type", choices=["full", "incremental"])
    ap.add_argument("--since", help="incremental only: ISO timestamp, e.g. 2026-09-19T00:00:00Z")
    ap.add_argument("--from-date", help="full only: start of the baseline window, e.g. 2025-09-26T00:00:00Z")
    ap.add_argument("--max-pages", type=int, default=0, help="0 = no limit")
    ap.add_argument("--out", default="data/samples")
    args = ap.parse_args()

    if args.load_type == "incremental" and not args.since:
        ap.error("incremental requires --since")

    out_dir = Path(args.out) / args.load_type
    out_dir.mkdir(parents=True, exist_ok=True)

    total_rows, total_mb = 0, 0.0
    for repo in REPOS:
        for entity in ENTITIES:
            rows = fetch(repo, entity, args.load_type, args.since,
                         args.max_pages, args.from_date)
            path = out_dir / f"{repo.replace('/', '__')}__{entity}.json"
            path.write_text(json.dumps(rows, indent=2))
            mb = path.stat().st_size / 1e6
            total_rows += len(rows)
            total_mb += mb
            print(f"{args.load_type:11} {repo:28} {entity:8} {len(rows):6} rows  {mb:7.2f} MB")
    print(f"{'TOTAL':11} {'':28} {'':8} {total_rows:6} rows  {total_mb:7.2f} MB")


if __name__ == "__main__":
    main()
