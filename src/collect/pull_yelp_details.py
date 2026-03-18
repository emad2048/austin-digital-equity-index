"""
Pull Yelp business details (is_claimed) for all matched/yelp_only records.

The Yelp search endpoint does not return is_claimed. This script calls the
business details endpoint (GET /v3/businesses/{id}) once per Yelp business
to retrieve that field.

Rate limits:
  - 450 calls maximum per session
  - 0.5 second delay between calls

Resumability:
  - Progress is saved to data/processed/yelp_details_progress.json every 50 calls.
  - Re-running the script skips already-fetched IDs.

Output:
  data/processed/yelp_details.json
    {"<yelp_id>": {"is_claimed": true|false|null}, ...}

Usage:
  python src/collect/pull_yelp_details.py
"""

import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

load_dotenv()

YELP_API_KEY = os.getenv("YELP_API_KEY")
YELP_DETAILS_URL = "https://api.yelp.com/v3/businesses/{yelp_id}"

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MASTER_PATH = os.path.join(REPO_ROOT, "data", "processed", "master_businesses.json")
PROGRESS_PATH = os.path.join(REPO_ROOT, "data", "processed", "yelp_details_progress.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "data", "processed", "yelp_details.json")

RATE_LIMIT_DELAY = 0.5   # seconds between calls
RETRY_DELAY = 10         # seconds to wait on 429 before one retry
SAVE_INTERVAL = 50       # save progress every N calls


def load_master() -> list[dict]:
    with open(MASTER_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_progress() -> dict:
    """Load previously saved results, or return empty dict if none."""
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(results: dict) -> None:
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def save_output(results: dict) -> None:
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def fetch_is_claimed(yelp_id: str, headers: dict) -> bool | None:
    """
    Call the Yelp business details endpoint and return is_claimed.
    On 429, waits RETRY_DELAY seconds and retries once.
    Returns None on any error (network, 4xx, missing field).
    """
    url = YELP_DETAILS_URL.format(yelp_id=yelp_id)
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("is_claimed")  # bool or absent
        elif resp.status_code == 429:
            print(f"  [429] {yelp_id}: rate limited — waiting {RETRY_DELAY}s then retrying")
            time.sleep(RETRY_DELAY)
            retry = requests.get(url, headers=headers, timeout=15)
            if retry.status_code == 200:
                return retry.json().get("is_claimed")
            print(f"  [429] {yelp_id}: retry failed (HTTP {retry.status_code})")
            return None
        elif resp.status_code == 404:
            # Business no longer exists on Yelp
            return None
        else:
            print(f"  [WARN] {yelp_id}: HTTP {resp.status_code}")
            return None
    except requests.RequestException as e:
        print(f"  [ERROR] {yelp_id}: {e}")
        return None


def main() -> None:
    if not YELP_API_KEY:
        print("[ERROR] YELP_API_KEY not set in environment.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}

    # Load master dataset and filter to records with a Yelp ID
    records = load_master()
    yelp_records = [
        r for r in records
        if r.get("source") in ("matched", "yelp_only") and r.get("yelp_id")
    ]
    print(f"Records with Yelp ID: {len(yelp_records)}")

    # Load any previously saved progress
    results = load_progress()
    already_fetched = set(results.keys())
    if already_fetched:
        print(f"Resuming — {len(already_fetched)} already fetched, skipping.")

    # Build the work queue (skip already-fetched IDs)
    queue = [r["yelp_id"] for r in yelp_records if r["yelp_id"] not in already_fetched]
    print(f"Remaining to fetch: {len(queue)}")

    # Fetch loop
    calls_this_session = 0
    errors = 0

    for i, yelp_id in enumerate(queue, start=1):
        is_claimed = fetch_is_claimed(yelp_id, headers)
        results[yelp_id] = {"is_claimed": is_claimed}

        if is_claimed is None:
            errors += 1

        calls_this_session += 1

        # Progress report every SAVE_INTERVAL calls
        if calls_this_session % SAVE_INTERVAL == 0:
            save_progress(results)
            claimed_count = sum(
                1 for v in results.values() if v.get("is_claimed") is True
            )
            print(
                f"  [{calls_this_session}/{len(queue)}] saved — "
                f"{claimed_count} claimed so far, {errors} null/errors"
            )

        time.sleep(RATE_LIMIT_DELAY)

    # Final save
    save_progress(results)
    save_output(results)

    total = len(results)
    claimed = sum(1 for v in results.values() if v.get("is_claimed") is True)
    unclaimed = sum(1 for v in results.values() if v.get("is_claimed") is False)
    null_count = sum(1 for v in results.values() if v.get("is_claimed") is None)

    print(f"\n--- Summary ---")
    print(f"Total fetched (all sessions): {total}")
    print(f"  is_claimed = True  : {claimed}")
    print(f"  is_claimed = False : {unclaimed}")
    print(f"  is_claimed = None  : {null_count} (errors / missing field)")
    print(f"Calls this session   : {calls_this_session}")
    remaining = len(yelp_records) - total
    if remaining > 0:
        print(f"[INFO] {remaining} records still unfetched — re-run to continue.")
    else:
        print(f"Output saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
