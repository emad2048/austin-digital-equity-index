"""
apply_review_decisions.py

Applies completed human review decisions from merge_review_queue.csv to
master_businesses.json. Run after all reviewer_decision values are filled.

Logic:
  confirmed  → google record becomes matched (or stays matched with updated
               match_confidence + yelp_id); the yelp record (if it exists as
               a separate record) is marked superseded_by_review.
  rejected_* → google record stays google_only with match_confidence set to
               human_rejected and a rejection_reason field added.

Halts before touching any file if:
  - Any reviewer_decision is blank
  - Any master record has a null geoid
"""

import csv
import json
import sys
from pathlib import Path

QUEUE_PATH = Path("data/processed/merge_review_queue.csv")
MASTER_PATH = Path("data/processed/master_businesses.json")

VALID_DECISIONS = {
    "confirmed",
    "rejected_yelp_duplicate",
    "rejected_shared_phone",
    "rejected_low_confidence",
    "rejected_low_confidence_cross_tract",
}


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_queue() -> list[dict]:
    with open(QUEUE_PATH, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_master() -> list[dict]:
    with open(MASTER_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Pre-flight checks  (halt before touching any file)
# ---------------------------------------------------------------------------

def preflight_queue(queue: list[dict]) -> None:
    blanks = [
        i + 2  # row number (1-indexed header + 1 for 0-index)
        for i, row in enumerate(queue)
        if not row.get("reviewer_decision", "").strip()
    ]
    if blanks:
        print(f"HALT: {len(blanks)} row(s) have empty reviewer_decision: {blanks}")
        sys.exit(1)

    unknown = [
        (i + 2, row["reviewer_decision"])
        for i, row in enumerate(queue)
        if row["reviewer_decision"].strip() not in VALID_DECISIONS
    ]
    if unknown:
        print(f"HALT: Unrecognised reviewer_decision values: {unknown}")
        sys.exit(1)

    print(f"Queue OK — {len(queue)} rows, all reviewer_decision values valid.")


def preflight_master(master: list[dict]) -> None:
    null_geoid = [
        r.get("master_id", f"index-{i}")
        for i, r in enumerate(master)
        if not r.get("geoid")
    ]
    if null_geoid:
        print(f"HALT: {len(null_geoid)} master record(s) have null geoid: {null_geoid[:10]}")
        sys.exit(1)
    print(f"Master OK — {len(master)} records, all geoids present.")


# ---------------------------------------------------------------------------
# Apply decisions
# ---------------------------------------------------------------------------

def apply_decisions(queue: list[dict], master: list[dict]) -> dict:
    # Build lookup indexes
    by_gid: dict[str, dict] = {}
    by_yid: dict[str, dict] = {}
    for rec in master:
        gid = rec.get("google_place_id")
        yid = rec.get("yelp_id")
        if gid:
            by_gid[gid] = rec
        if yid:
            by_yid[yid] = rec

    stats = {
        "confirmed_new_link": 0,       # google_only → matched (new yelp link)
        "confirmed_same_already": 0,   # already matched to same yelp, mc updated
        "confirmed_relink": 0,         # already matched to different yelp, re-linked
        "superseded": 0,               # yelp records marked superseded_by_review
        "rejected": 0,
        "google_not_found": 0,
        "yelp_not_found_warn": 0,
    }

    # Group rows by google_place_id so we can determine the outcome per google
    # before touching any record. A google with a confirmed row always wins —
    # rejected rows for the same google represent other yelp candidates that
    # were ruled out; they must NOT overwrite the confirmed result.
    from collections import defaultdict
    by_gid_queue: dict[str, list[dict]] = defaultdict(list)
    for row in queue:
        by_gid_queue[row["google_place_id"]].append(row)

    # Separate into confirmed and all-rejected groups
    confirmed_rows: list[dict] = []
    rejected_only_gids: set[str] = set()

    for gid, rows in by_gid_queue.items():
        confirmed = [r for r in rows if r["reviewer_decision"].strip() == "confirmed"]
        if confirmed:
            # Exactly one confirmed row per google (validation already passed)
            confirmed_rows.append(confirmed[0])
        else:
            rejected_only_gids.add(gid)

    # ------------------------------------------------------------------ #
    # Pass 1 — Apply confirmed decisions
    # ------------------------------------------------------------------ #
    for row in confirmed_rows:
        gid = row["google_place_id"]
        q_yid = row["yelp_id"]
        q_mc = row["match_confidence"]

        g_rec = by_gid.get(gid)
        if g_rec is None:
            print(f"  WARN: google_place_id {gid} not found in master — skipping.")
            stats["google_not_found"] += 1
            continue

        current_yid = g_rec.get("yelp_id")

        if g_rec.get("source") == "matched" and current_yid == q_yid:
            # Already paired correctly by auto-confirm — update match_confidence only
            g_rec["match_confidence"] = q_mc
            stats["confirmed_same_already"] += 1

        elif g_rec.get("source") == "matched" and current_yid != q_yid:
            # Human overrides auto-match: re-point to the correct yelp
            g_rec["match_confidence"] = q_mc
            g_rec["yelp_id"] = q_yid
            stats["confirmed_relink"] += 1

            y_rec = by_yid.get(q_yid)
            if y_rec and y_rec is not g_rec:
                y_rec["source"] = "yelp_only"
                y_rec["match_confidence"] = "superseded_by_review"
                stats["superseded"] += 1
            elif y_rec is None:
                print(f"  WARN: yelp_id {q_yid} (re-link) not found in master.")
                stats["yelp_not_found_warn"] += 1

        else:
            # google_only → new confirmed match
            g_rec["source"] = "matched"
            g_rec["match_confidence"] = q_mc
            g_rec["yelp_id"] = q_yid
            stats["confirmed_new_link"] += 1

            y_rec = by_yid.get(q_yid)
            if y_rec and y_rec is not g_rec:
                y_rec["source"] = "yelp_only"
                y_rec["match_confidence"] = "superseded_by_review"
                stats["superseded"] += 1
            elif y_rec is None:
                print(f"  WARN: yelp_id {q_yid} (new link) not found in master.")
                stats["yelp_not_found_warn"] += 1

    # ------------------------------------------------------------------ #
    # Pass 2 — Apply rejected decisions (only for all-rejected googles)
    # ------------------------------------------------------------------ #
    for gid in rejected_only_gids:
        rows = by_gid_queue[gid]
        g_rec = by_gid.get(gid)
        if g_rec is None:
            print(f"  WARN: google_place_id {gid} not found in master — skipping.")
            stats["google_not_found"] += 1
            continue

        # Use the first rejection reason; all rows here are rejected_*
        decision = rows[0]["reviewer_decision"].strip()
        g_rec["source"] = "google_only"
        g_rec["match_confidence"] = "human_rejected"
        g_rec["rejection_reason"] = decision
        # Clear any stale yelp link that may have been set by an auto-pass
        g_rec["yelp_id"] = None
        stats["rejected"] += 1

    return stats


# ---------------------------------------------------------------------------
# Post-write geoid guard
# ---------------------------------------------------------------------------

def postflight_geoid(master: list[dict]) -> None:
    null_geoid = [
        r.get("master_id", f"?")
        for r in master
        if not r.get("geoid")
    ]
    if null_geoid:
        print(f"HALT: {len(null_geoid)} record(s) have null geoid after applying decisions.")
        print("  Master file NOT written.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== apply_review_decisions.py ===\n")

    # Load
    queue = load_queue()
    master = load_master()

    # Pre-flight (halt before touching files)
    preflight_queue(queue)
    preflight_master(master)
    print()

    # Apply
    print("Applying decisions...")
    stats = apply_decisions(queue, master)
    print(f"  confirmed (same, mc updated):  {stats['confirmed_same_already']}")
    print(f"  confirmed (new link):          {stats['confirmed_new_link']}")
    print(f"  confirmed (re-link):           {stats['confirmed_relink']}")
    print(f"  yelp records superseded:       {stats['superseded']}")
    print(f"  rejected:                      {stats['rejected']}")
    if stats["google_not_found"]:
        print(f"  WARN google_place_id not found: {stats['google_not_found']}")
    if stats["yelp_not_found_warn"]:
        print(f"  WARN yelp_id not found:         {stats['yelp_not_found_warn']}")

    # Post-flight geoid guard (before writing)
    postflight_geoid(master)

    # Write
    with open(MASTER_PATH, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(master)} records to {MASTER_PATH}")

    # Final composition summary
    from collections import Counter
    source_counts = Counter(r["source"] for r in master)
    mc_counts = Counter(r["match_confidence"] for r in master)

    print("\n=== Final composition ===")
    print(f"  matched:      {source_counts['matched']}")
    print(f"  google_only:  {source_counts['google_only']}")
    print(f"  yelp_only:    {source_counts['yelp_only']}")
    print(f"  Total:        {len(master)}")

    print("\n=== match_confidence breakdown ===")
    for mc, count in sorted(mc_counts.items(), key=lambda x: -x[1]):
        print(f"  {mc:<40} {count}")


if __name__ == "__main__":
    main()
