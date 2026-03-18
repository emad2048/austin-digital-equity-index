"""
State 4 website content check for the DII scoring pipeline.

Visits each reachable business website (state 3 records) and detects whether
contact information is present: phone number, email address, and business hours.

A record qualifies for state 4 if at least 2 of the 3 signals are detected.

This script only detects — it does not score. The scorer (src/score/dii_scorer.py)
reads the output file and assigns points.

Input:
  data/processed/master_businesses.json  (filters to dii_website_score == 16)

Output:
  data/processed/website_content.json
  {
    "<google_id>": {
      "url": "https://example.com",
      "phone_detected": true,
      "email_detected": false,
      "hours_detected": true,
      "state4_qualified": true,
      "state4_attempted": true
    },
    ...
  }

Resumability:
  Progress is saved every 50 records. Re-running skips already-checked google_ids.

Rate limiting:
  0.3 second delay between requests — no session cap.

Usage:
  python src/collect/pull_website_content.py
"""

import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MASTER_PATH = os.path.join(REPO_ROOT, "data", "processed", "master_businesses.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "data", "processed", "website_content.json")

RATE_LIMIT_DELAY = 0.3   # seconds between requests
SAVE_INTERVAL = 50       # save progress every N records
REQUEST_TIMEOUT = 10     # seconds per request

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

PHONE_RE = re.compile(
    r'\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}'  # (512) 555-1234 / 512.555.1234 / 512-555-1234
    r'|\b\d{10}\b',                           # 5125551234
    re.ASCII,
)

EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.ASCII,
)

HOURS_TIME_RE = re.compile(
    r'\b\d{1,2}(:\d{2})?\s*[aApP][mM]\b'  # 9am, 9:00 AM, 10:30am
    r'|\b\d{1,2}:\d{2}\b'                  # 9:00, 17:30
    r'|\b\d{1,2}\s+to\s+\d{1,2}\b',       # 9 to 5, 8 to 8
    re.IGNORECASE,
)

HOURS_DAY_RE = re.compile(
    r'\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun'
    r'|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday'
    r'|hours|open|closed)\b',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_master() -> list[dict]:
    with open(MASTER_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_progress() -> dict:
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_output(results: dict) -> None:
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------

def extract_text(html: str) -> str:
    """Strip tags and return visible page text."""
    soup = BeautifulSoup(html, "html.parser")
    # Remove script and style content before extracting text
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator=" ")


def detect_signals(text: str) -> dict:
    phone = bool(PHONE_RE.search(text))
    email = bool(EMAIL_RE.search(text))
    hours = bool(HOURS_TIME_RE.search(text) and HOURS_DAY_RE.search(text))
    qualified = sum([phone, email, hours]) >= 2
    return {
        "phone_detected": phone,
        "email_detected": email,
        "hours_detected": hours,
        "state4_qualified": qualified,
        "state4_attempted": True,
    }


def check_url(url: str) -> dict:
    """
    Fetch URL and run signal detection.
    On any exception, return all signals as False with state4_attempted True.
    """
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ADEI-research-bot/1.0)"},
        )
        resp.raise_for_status()
        text = extract_text(resp.text)
        return detect_signals(text)
    except Exception:
        return {
            "phone_detected": False,
            "email_detected": False,
            "hours_detected": False,
            "state4_qualified": False,
            "state4_attempted": True,
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    records = load_master()

    # Filter to state 3 records (dii_website_score == 16) with a google_id and url
    state3 = [r for r in records if r.get("dii_website_score") == 16]
    candidates = [
        r for r in state3
        if r.get("google_place_id") and r.get("website_url")
    ]
    excluded = len(state3) - len(candidates)
    print(
        f"Queue: {len(state3):,} candidates — "
        f"{len(candidates):,} queued, {excluded:,} excluded (missing url or id)"
    )

    # Load any existing progress
    results = load_progress()
    already_checked = set(results.keys())
    if already_checked:
        print(f"Resuming — {len(already_checked)} already checked, skipping.")

    # Build queue from unchecked candidates
    queue = [r for r in candidates if r["google_place_id"] not in already_checked]
    print(f"Remaining to check: {len(queue)}")

    if not queue:
        print("Nothing to do — all records already checked.")
        return

    checked = 0
    qualified = 0

    for record in queue:
        google_id = record["google_place_id"]
        url = record["website_url"]

        signals = check_url(url)
        results[google_id] = {"url": url, **signals}

        if signals["state4_qualified"]:
            qualified += 1
        checked += 1

        if checked % SAVE_INTERVAL == 0:
            save_output(results)
            print(
                f"  [{checked}/{len(queue)}] checked — "
                f"{qualified} qualified for state 4 so far"
            )

        time.sleep(RATE_LIMIT_DELAY)

    # Final save
    save_output(results)

    # Summary
    total_checked = len(results)
    total_qualified = sum(1 for v in results.values() if v.get("state4_qualified"))
    rate = total_qualified / total_checked * 100 if total_checked else 0

    print(f"\n--- Summary ---")
    print(f"Total checked     : {total_checked}")
    print(f"Total qualified   : {total_qualified} ({rate:.1f}%)")

    # Breakdown by neighborhood (join back to master on google_place_id)
    id_to_neighborhood = {
        r["google_place_id"]: r.get("neighborhood", "unknown")
        for r in records
        if r.get("google_place_id")
    }
    by_neighborhood: dict[str, dict[str, int]] = {}
    for gid, v in results.items():
        n = id_to_neighborhood.get(gid, "unknown")
        if n not in by_neighborhood:
            by_neighborhood[n] = {"checked": 0, "qualified": 0}
        by_neighborhood[n]["checked"] += 1
        if v.get("state4_qualified"):
            by_neighborhood[n]["qualified"] += 1

    print(f"\nBy neighborhood:")
    for n, counts in sorted(by_neighborhood.items()):
        n_rate = counts["qualified"] / counts["checked"] * 100 if counts["checked"] else 0
        print(
            f"  {n}: {counts['qualified']}/{counts['checked']} qualified "
            f"({n_rate:.1f}%)"
        )

    print(f"\nOutput saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
