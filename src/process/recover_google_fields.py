"""
Recover three Google Maps fields dropped at the original merge step and write
them back into data/processed/master_businesses.json.

Fields recovered:
  business_status    str | None  — businessStatus value from Google Places API
                                   e.g. 'OPERATIONAL', 'CLOSED_PERMANENTLY'
  has_opening_hours  bool | None — True if regularOpeningHours is present and non-null
  has_photos         bool | None — True if photos is present and a non-empty array

Join key:
  raw Google record: id
  master record:     google_place_id

Records with no google_place_id (yelp_only) receive null for all three fields.

Usage:
  python src/process/recover_google_fields.py
"""

import json
import os
from collections import Counter

REPO_ROOT   = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW_PATH    = os.path.join(REPO_ROOT, "data", "raw",       "google_all_tracts_raw.json")
MASTER_PATH = os.path.join(REPO_ROOT, "data", "processed", "master_businesses.json")


def main() -> None:
    # Load and index raw Google data by place ID
    with open(RAW_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    raw_index = {r["id"]: r for r in raw if r.get("id")}
    print(f"Raw Google records loaded : {len(raw_index)}")

    # Load master
    with open(MASTER_PATH, encoding="utf-8") as f:
        master = json.load(f)
    print(f"Master records loaded     : {len(master)}")

    # Merge
    matched = 0
    null_count = 0

    for record in master:
        gid = record.get("google_place_id")
        raw_rec = raw_index.get(gid) if gid else None

        if raw_rec is not None:
            record["business_status"]   = raw_rec.get("businessStatus")
            record["has_opening_hours"] = raw_rec.get("regularOpeningHours") is not None
            record["has_photos"]        = bool(raw_rec.get("photos"))
            matched += 1
        else:
            record["business_status"]   = None
            record["has_opening_hours"] = None
            record["has_photos"]        = None
            null_count += 1

    # Print match rate
    print()
    print(f"Records matched (fields recovered) : {matched} ({matched/len(master)*100:.1f}%)")
    print(f"Records unmatched (null)           : {null_count} ({null_count/len(master)*100:.1f}%)")

    # business_status breakdown
    status_counts = Counter(r.get("business_status") for r in master)
    print()
    print("business_status value counts:")
    for val, count in status_counts.most_common():
        print(f"  {str(val):<30} {count:,}")

    # has_opening_hours breakdown
    hours_true  = sum(1 for r in master if r.get("has_opening_hours") is True)
    hours_false = sum(1 for r in master if r.get("has_opening_hours") is False)
    hours_null  = sum(1 for r in master if r.get("has_opening_hours") is None)
    print()
    print("has_opening_hours:")
    print(f"  True  : {hours_true:,}")
    print(f"  False : {hours_false:,}")
    print(f"  None  : {hours_null:,}")

    # has_photos breakdown
    photos_true  = sum(1 for r in master if r.get("has_photos") is True)
    photos_false = sum(1 for r in master if r.get("has_photos") is False)
    photos_null  = sum(1 for r in master if r.get("has_photos") is None)
    print()
    print("has_photos:")
    print(f"  True  : {photos_true:,}")
    print(f"  False : {photos_false:,}")
    print(f"  None  : {photos_null:,}")

    # Save
    with open(MASTER_PATH, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)
    print()
    print(f"master_businesses.json updated — {len(master):,} records.")


if __name__ == "__main__":
    main()
