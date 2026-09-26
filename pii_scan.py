"""
PII scan of the sample files. Run from the project folder:
  python pii_scan.py
Reads data/samples/**/*.json and prints counts you can quote in the proposal.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "data/samples")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def is_noreply(email):
    return email.lower().endswith("@users.noreply.github.com")


def get(d, *path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


commit_emails, commit_names, logins = set(), set(), set()
text_emails, text_ips = set(), set()
coauthor_lines = 0
counts = {"commits": 0, "issues": 0, "pulls": 0}

for f in sorted(ROOT.rglob("*.json")):
    entity = f.stem.split("__")[-1]
    if entity not in counts:
        continue
    for row in json.loads(f.read_text(encoding="utf-8")):
        counts[entity] += 1
        if entity == "commits":
            for who in ("author", "committer"):
                e = get(row, "commit", who, "email")
                n = get(row, "commit", who, "name")
                if e:
                    commit_emails.add(e)
                if n:
                    commit_names.add(n)
            for who in ("author", "committer"):
                l = get(row, who, "login")
                if l:
                    logins.add(l)
            msg = get(row, "commit", "message") or ""
            coauthor_lines += len(re.findall(r"(?im)^co-authored-by:", msg))
            text_emails.update(EMAIL_RE.findall(msg))
            text_ips.update(IPV4_RE.findall(msg))
        else:
            l = get(row, "user", "login")
            if l:
                logins.add(l)
            body = row.get("body") or ""
            text_emails.update(EMAIL_RE.findall(body))
            text_ips.update(IPV4_RE.findall(body))

real = {e for e in commit_emails if not is_noreply(e)}
print("Rows scanned:", counts)
print(f"Distinct commit author/committer emails : {len(commit_emails)}")
print(f"  of which GitHub noreply (masked)       : {len(commit_emails) - len(real)}")
print(f"  of which real/personal-looking         : {len(real)}")
print(f"Distinct commit author/committer names   : {len(commit_names)}")
print(f"Distinct GitHub logins (all entities)    : {len(logins)}")
print(f"'Co-authored-by' lines in commit messages: {coauthor_lines}")
print(f"Emails found inside free text (msg/body) : {len(text_emails)}")
print(f"IPv4-looking strings in free text        : {len(text_ips)} (may include version numbers)")
