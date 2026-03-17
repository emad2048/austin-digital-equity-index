"""
Sprint 2 — Cross-source merge pipeline for the Austin Digital Equity Index.

Merges Google Places (google_all_tracts_raw.json) and Yelp Fusion
(yelp_all_tracts_raw.json) records into a single master dataset using a
three-pass strategy:
  Pass 1 — Exact phone match, within-tract
  Pass 2 — Fuzzy name + zip, within-tract
  Pass 3 — Fuzzy name + neighborhood (cross-tract, boundary_duplicate only)

Outputs:
  data/processed/master_businesses.json
  data/processed/merge_review_queue.csv
  data/processed/merge_audit.txt
"""

import csv
import json
import os
import re
import sys
import uuid
import warnings
from collections import defaultdict

from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT   = os.path.join(os.path.dirname(__file__), "..", "..")
RAW_DIR     = os.path.join(REPO_ROOT, "data", "raw")
PROCESSED   = os.path.join(REPO_ROOT, "data", "processed")

GOOGLE_RAW  = os.path.join(RAW_DIR, "google_all_tracts_raw.json")
YELP_RAW    = os.path.join(RAW_DIR, "yelp_all_tracts_raw.json")
MASTER_OUT  = os.path.join(PROCESSED, "master_businesses.json")
REVIEW_OUT  = os.path.join(PROCESSED, "merge_review_queue.csv")
AUDIT_OUT   = os.path.join(PROCESSED, "merge_audit.txt")

FUZZY_AUTO_THRESHOLD   = 90
FUZZY_REVIEW_THRESHOLD = 75

REVIEW_CSV_COLS = [
    "google_place_id", "google_name", "google_address", "google_phone", "google_geoid",
    "yelp_id", "yelp_name", "yelp_address", "yelp_phone", "yelp_geoid",
    "similarity_score", "match_confidence", "pass_number", "reviewer_decision",
]


# ---------------------------------------------------------------------------
# Step 2 — Phone normalization
# ---------------------------------------------------------------------------

def normalize_phone(raw):
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return digits
    return None


# ---------------------------------------------------------------------------
# Step 3 — Name normalization (matching only, never stored)
# ---------------------------------------------------------------------------

def normalize_name(raw):
    s = str(raw or "").lower().strip()
    for suffix in [" llc", " inc", " ltd", " co.", " co,", " corp"]:
        s = s.replace(suffix, "")
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------------------
# Step 1 — Load and normalize both datasets
# ---------------------------------------------------------------------------

def load_google(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    records = []
    for r in raw:
        # Extract zip from formattedAddress (5-digit group)
        addr = r.get("formattedAddress", "") or ""
        zip_match = re.search(r"\b(\d{5})\b", addr)
        zip_code = zip_match.group(1) if zip_match else None

        rec = {
            "google_place_id":    r.get("id") or r.get("place_id"),
            "name":               (r.get("displayName") or {}).get("text"),
            "phone":              r.get("nationalPhoneNumber"),
            "address_raw":        addr,
            "zip_code":           zip_code,
            "website_url":        r.get("websiteUri"),
            "geoid":              r.get("geoid"),
            "neighborhood":       r.get("neighborhood"),
            "category":           r.get("category"),
            "boundary_duplicate": r.get("boundary_duplicate", False),
        }
        rec["phone_normalized"] = normalize_phone(rec["phone"])
        records.append(rec)

    return records


def load_yelp(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    records = []
    for r in raw:
        loc = r.get("location") or {}
        raw_zip = loc.get("zip_code", "") or ""
        zip_code = raw_zip[:5] if raw_zip else None

        rec = {
            "yelp_id":            r.get("id"),
            "name":               r.get("name"),
            "phone":              r.get("phone"),
            "address_raw":        loc.get("address1"),
            "zip_code":           zip_code,
            "geoid":              r.get("geoid"),
            "neighborhood":       r.get("neighborhood"),
            "category":           r.get("category"),
            "boundary_duplicate": r.get("boundary_duplicate", False),
            "rating":             r.get("rating"),
            "review_count":       r.get("review_count"),
            "yelp_url":           r.get("url"),
        }
        rec["phone_normalized"] = normalize_phone(rec["phone"])
        records.append(rec)

    return records


# ---------------------------------------------------------------------------
# Step 5 — Master record assembly helpers
# ---------------------------------------------------------------------------

def make_master_record(source, g=None, y=None, match_confidence=None):
    """
    Assemble a single master record from a Google record, a Yelp record, or both.
    Field resolution follows the spec exactly.
    """
    if source == "matched":
        # Detect geoid mismatch
        if g["geoid"] != y["geoid"]:
            print(f"  [WARN] GEOID mismatch — Google {g['geoid']} vs Yelp {y['geoid']} "
                  f"for '{g['name']}' / '{y['name']}'")

        name    = g["name"] or y["name"]
        phone   = g["phone"] or y["phone"]
        phone_n = g["phone_normalized"] or y["phone_normalized"]
        addr    = g["address_raw"] or y["address_raw"]
        geoid   = g["geoid"]        # prefer Google
        nbhd    = g["neighborhood"] or y["neighborhood"]
        cat     = g["category"]     or y["category"]
        bdup    = g["boundary_duplicate"] or y["boundary_duplicate"]

        return {
            "master_id":          str(uuid.uuid4()),
            "source":             "matched",
            "match_confidence":   match_confidence,
            "google_place_id":    g["google_place_id"],
            "yelp_id":            y["yelp_id"],
            "name":               name,
            "phone":              phone,
            "phone_normalized":   phone_n,
            "address_raw":        addr,
            "zip_code":           g["zip_code"] or y["zip_code"],
            "website_url":        g["website_url"],
            "geoid":              geoid,
            "neighborhood":       nbhd,
            "category":           cat,
            "boundary_duplicate": bdup,
            "rating":             y["rating"],
            "review_count":       y["review_count"],
            "yelp_url":           y["yelp_url"],
            "dii_google_maps_score": None,
            "dii_website_score":     None,
            "dii_yelp_score":        None,
            "dii_social_score":      None,
            "dii_accuracy_score":    None,
            "dii_total_score":       None,
        }

    elif source == "google_only":
        return {
            "master_id":          str(uuid.uuid4()),
            "source":             "google_only",
            "match_confidence":   "unmatched",
            "google_place_id":    g["google_place_id"],
            "yelp_id":            None,
            "name":               g["name"],
            "phone":              g["phone"],
            "phone_normalized":   g["phone_normalized"],
            "address_raw":        g["address_raw"],
            "zip_code":           g["zip_code"],
            "website_url":        g["website_url"],
            "geoid":              g["geoid"],
            "neighborhood":       g["neighborhood"],
            "category":           g["category"],
            "boundary_duplicate": g["boundary_duplicate"],
            "rating":             None,
            "review_count":       None,
            "yelp_url":           None,
            "dii_google_maps_score": None,
            "dii_website_score":     None,
            "dii_yelp_score":        None,
            "dii_social_score":      None,
            "dii_accuracy_score":    None,
            "dii_total_score":       None,
        }

    else:  # yelp_only
        return {
            "master_id":          str(uuid.uuid4()),
            "source":             "yelp_only",
            "match_confidence":   "unmatched",
            "google_place_id":    None,
            "yelp_id":            y["yelp_id"],
            "name":               y["name"],
            "phone":              y["phone"],
            "phone_normalized":   y["phone_normalized"],
            "address_raw":        y["address_raw"],
            "zip_code":           y["zip_code"],
            "website_url":        None,
            "geoid":              y["geoid"],
            "neighborhood":       y["neighborhood"],
            "category":           y["category"],
            "boundary_duplicate": y["boundary_duplicate"],
            "rating":             y["rating"],
            "review_count":       y["review_count"],
            "yelp_url":           y["yelp_url"],
            "dii_google_maps_score": None,
            "dii_website_score":     None,
            "dii_yelp_score":        None,
            "dii_social_score":      None,
            "dii_accuracy_score":    None,
            "dii_total_score":       None,
        }


def review_row(g, y, score, confidence, pass_num):
    return {
        "google_place_id":  g["google_place_id"],
        "google_name":      g["name"],
        "google_address":   g["address_raw"],
        "google_phone":     g["phone"],
        "google_geoid":     g["geoid"],
        "yelp_id":          y["yelp_id"],
        "yelp_name":        y["name"],
        "yelp_address":     y["address_raw"],
        "yelp_phone":       y["phone"],
        "yelp_geoid":       y["geoid"],
        "similarity_score": score,
        "match_confidence": confidence,
        "pass_number":      pass_num,
        "reviewer_decision": "",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(PROCESSED, exist_ok=True)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    print("Loading Google records...")
    google_records = load_google(GOOGLE_RAW)
    print(f"  {len(google_records)} records loaded")

    print("Loading Yelp records...")
    yelp_records = load_yelp(YELP_RAW)
    print(f"  {len(yelp_records)} records loaded")

    # ------------------------------------------------------------------
    # Hard constraint: every record must have a geoid
    # ------------------------------------------------------------------
    g_missing_geoid = [r for r in google_records if not r.get("geoid")]
    y_missing_geoid = [r for r in yelp_records   if not r.get("geoid")]
    if g_missing_geoid or y_missing_geoid:
        raise ValueError(
            f"HALT: {len(g_missing_geoid)} Google and {len(y_missing_geoid)} Yelp "
            f"records are missing geoid. Cannot proceed."
        )

    # Build lookup indices
    # Yelp by geoid
    yelp_by_geoid = defaultdict(list)
    for y in yelp_records:
        yelp_by_geoid[y["geoid"]].append(y)

    # Yelp by neighborhood
    yelp_by_nbhd = defaultdict(list)
    for y in yelp_records:
        yelp_by_nbhd[y["neighborhood"]].append(y)

    matched_google_ids = set()  # google_place_id
    matched_yelp_ids   = set()  # yelp_id

    confirmed_matches = []  # list of (g, y, confidence)
    review_queue      = []  # list of review_row dicts

    # Counters
    p1_confirmed  = 0
    p1_conflicts  = 0
    p2_auto       = 0
    p2_review     = 0
    p2_no_match   = 0
    p3_auto       = 0
    p3_review     = 0
    geoid_mismatches = 0

    # ------------------------------------------------------------------
    # Pass 1 — Exact phone, within-tract
    # ------------------------------------------------------------------
    print("\nPass 1 — exact phone match, within-tract...")

    # Build Yelp phone+geoid index
    yelp_phone_geoid = defaultdict(list)  # (phone_normalized, geoid) -> [yelp_rec, ...]
    for y in yelp_records:
        if y["phone_normalized"]:
            yelp_phone_geoid[(y["phone_normalized"], y["geoid"])].append(y)

    for g in google_records:
        if not g["phone_normalized"]:
            continue
        key = (g["phone_normalized"], g["geoid"])
        candidates = yelp_phone_geoid.get(key, [])
        # Filter out already-matched Yelp records
        candidates = [y for y in candidates if y["yelp_id"] not in matched_yelp_ids]

        if len(candidates) == 1:
            y = candidates[0]
            confirmed_matches.append((g, y, "exact_phone"))
            matched_google_ids.add(g["google_place_id"])
            matched_yelp_ids.add(y["yelp_id"])
            p1_confirmed += 1

        elif len(candidates) > 1:
            # Conflict — send all to review, confirm none
            for y in candidates:
                review_queue.append(review_row(g, y, None, "exact_phone_conflict", 1))
            p1_conflicts += len(candidates)

    print(f"  Confirmed: {p1_confirmed}  |  Conflicts to review: {p1_conflicts}")

    # ------------------------------------------------------------------
    # Pass 2 — Fuzzy name + zip, within-tract
    # ------------------------------------------------------------------
    print("Pass 2 — fuzzy name + zip, within-tract...")

    for g in google_records:
        if g["google_place_id"] in matched_google_ids:
            continue

        g_name_norm = normalize_name(g["name"])
        g_zip       = g["zip_code"]
        candidates  = [
            y for y in yelp_by_geoid.get(g["geoid"], [])
            if y["yelp_id"] not in matched_yelp_ids
            and y["zip_code"] == g_zip
        ]

        if not candidates:
            p2_no_match += 1
            continue

        scored = [
            (y, fuzz.token_sort_ratio(g_name_norm, normalize_name(y["name"])))
            for y in candidates
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        best_score = scored[0][1]

        if best_score < FUZZY_REVIEW_THRESHOLD:
            p2_no_match += 1
            continue

        # Collect all candidates at the best score
        top_matches = [(y, s) for y, s in scored if s == best_score]

        if best_score >= FUZZY_AUTO_THRESHOLD:
            if len(top_matches) == 1:
                y, s = top_matches[0]
                confirmed_matches.append((g, y, "fuzzy_confirmed"))
                matched_google_ids.add(g["google_place_id"])
                matched_yelp_ids.add(y["yelp_id"])
                p2_auto += 1
            else:
                # Tie at ≥90 — send to review rather than auto-confirm
                for y, s in top_matches:
                    review_queue.append(review_row(g, y, s, "fuzzy_review_pending", 2))
                p2_review += len(top_matches)

        else:
            # 75–89 range
            for y, s in top_matches:
                review_queue.append(review_row(g, y, s, "fuzzy_review_pending", 2))
            p2_review += len(top_matches)

    print(f"  Auto-confirmed: {p2_auto}  |  To review: {p2_review}  |  No match: {p2_no_match}")

    # ------------------------------------------------------------------
    # Pass 3 — Cross-tract boundary check
    # ------------------------------------------------------------------
    print("Pass 3 — cross-tract fuzzy, boundary_duplicate records only...")

    # Deduplicate Google boundary records by google_place_id before iterating.
    # A place collected under multiple category queries produces duplicate records;
    # only one instance should generate Pass 3 candidates. Stable tiebreak: lowest
    # geoid alphanumerically.
    seen_p3_google = {}  # google_place_id -> record
    for g in google_records:
        if g["google_place_id"] in matched_google_ids:
            continue
        if not g["boundary_duplicate"]:
            continue
        gid = g["google_place_id"]
        if gid not in seen_p3_google or g["geoid"] < seen_p3_google[gid]["geoid"]:
            seen_p3_google[gid] = g
    p3_google_candidates = list(seen_p3_google.values())

    for g in p3_google_candidates:
        if g["google_place_id"] in matched_google_ids:
            continue

        g_name_norm = normalize_name(g["name"])

        # Expand candidate pool to full neighborhood, excluding already-matched.
        # Deduplicate Yelp candidates by yelp_id: when the same Yelp business
        # appears in multiple tracts, keep the instance whose geoid matches the
        # Google record's geoid; fall back to lowest geoid alphanumerically.
        raw_candidates = [
            y for y in yelp_by_nbhd.get(g["neighborhood"], [])
            if y["yelp_id"] not in matched_yelp_ids
        ]
        yelp_deduped = {}  # yelp_id -> best instance
        for y in raw_candidates:
            yid = y["yelp_id"]
            if yid not in yelp_deduped:
                yelp_deduped[yid] = y
            else:
                existing = yelp_deduped[yid]
                # Prefer instance whose geoid matches the Google record
                existing_matches = existing["geoid"] == g["geoid"]
                current_matches  = y["geoid"] == g["geoid"]
                if current_matches and not existing_matches:
                    yelp_deduped[yid] = y
                elif not current_matches and not existing_matches:
                    # Neither matches — keep lowest geoid as stable tiebreak
                    if y["geoid"] < existing["geoid"]:
                        yelp_deduped[yid] = y
        candidates = list(yelp_deduped.values())

        if not candidates:
            continue

        scored = [
            (y, fuzz.token_sort_ratio(g_name_norm, normalize_name(y["name"])))
            for y in candidates
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        best_score = scored[0][1]

        if best_score < FUZZY_REVIEW_THRESHOLD:
            continue

        top_matches = [(y, s) for y, s in scored if s == best_score]

        if best_score >= FUZZY_AUTO_THRESHOLD:
            if len(top_matches) == 1:
                y, s = top_matches[0]
                confirmed_matches.append((g, y, "fuzzy_confirmed_cross_tract"))
                matched_google_ids.add(g["google_place_id"])
                matched_yelp_ids.add(y["yelp_id"])
                p3_auto += 1
            else:
                for y, s in top_matches:
                    review_queue.append(
                        review_row(g, y, s, "fuzzy_review_pending_cross_tract", 3)
                    )
                p3_review += len(top_matches)
        else:
            for y, s in top_matches:
                review_queue.append(
                    review_row(g, y, s, "fuzzy_review_pending_cross_tract", 3)
                )
            p3_review += len(top_matches)

    print(f"  Auto-confirmed: {p3_auto}  |  To review: {p3_review}")

    # ------------------------------------------------------------------
    # Step 5 — Assemble master dataset
    # ------------------------------------------------------------------
    print("\nAssembling master dataset...")
    master = []

    # Matched records
    for g, y, confidence in confirmed_matches:
        rec = make_master_record("matched", g=g, y=y, match_confidence=confidence)
        if g["geoid"] != y["geoid"]:
            geoid_mismatches += 1
        master.append(rec)

    # Google-only
    google_only_count = 0
    for g in google_records:
        if g["google_place_id"] not in matched_google_ids:
            master.append(make_master_record("google_only", g=g))
            google_only_count += 1

    # Yelp-only
    yelp_only_count = 0
    for y in yelp_records:
        if y["yelp_id"] not in matched_yelp_ids:
            master.append(make_master_record("yelp_only", y=y))
            yelp_only_count += 1

    total_matched = len(confirmed_matches)
    total_master  = len(master)

    # Hard constraint: every output record must have a geoid
    no_geoid = [r for r in master if not r.get("geoid")]
    if no_geoid:
        raise ValueError(
            f"HALT: {len(no_geoid)} master records are missing geoid. "
            "Cannot write partial output."
        )

    # ------------------------------------------------------------------
    # Write master dataset
    # ------------------------------------------------------------------
    with open(MASTER_OUT, "w", encoding="utf-8") as f:
        json.dump(master, f, indent=2, ensure_ascii=False)
    print(f"  Master dataset written -> {os.path.relpath(MASTER_OUT)}")
    print(f"  Total records: {total_master}")

    # ------------------------------------------------------------------
    # Step 6 — Deduplicate review queue, then write CSV
    # ------------------------------------------------------------------
    # When the same (google_place_id, yelp_id) pair appears in multiple passes
    # (e.g. a boundary_duplicate Google record generates rows in both Pass 2 and
    # Pass 3), keep the single most informative row: lowest pass_number first,
    # higher similarity_score as tiebreak within the same pass.
    pre_dedup_count = len(review_queue)
    deduped = {}
    for row in review_queue:
        key = (row["google_place_id"], row["yelp_id"])
        if key not in deduped:
            deduped[key] = row
        else:
            existing = deduped[key]
            existing_pass  = int(existing["pass_number"])
            current_pass   = int(row["pass_number"])
            existing_score = float(existing["similarity_score"]) if existing["similarity_score"] not in (None, "") else -1
            current_score  = float(row["similarity_score"])      if row["similarity_score"]      not in (None, "") else -1
            if current_pass < existing_pass:
                deduped[key] = row
            elif current_pass == existing_pass and current_score > existing_score:
                deduped[key] = row

    review_queue = list(deduped.values())
    removed = pre_dedup_count - len(review_queue)

    print(f"  Review queue before dedup:  {pre_dedup_count} rows")
    print(f"  Duplicate pairs removed:     {removed} rows")
    print(f"  Review queue after dedup:    {len(review_queue)} rows")

    # Halt if any pair still appears more than once (should be impossible after dedup)
    from collections import Counter
    pair_counts = Counter((r["google_place_id"], r["yelp_id"]) for r in review_queue)
    still_duped = {pair: cnt for pair, cnt in pair_counts.items() if cnt > 1}
    if still_duped:
        for pair, cnt in still_duped.items():
            print(f"  [DUPLICATE] {pair}  count={cnt}")
        raise RuntimeError("HALT: duplicate (google_place_id, yelp_id) pairs remain after dedup.")

    with open(REVIEW_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_CSV_COLS)
        writer.writeheader()
        writer.writerows(review_queue)
    print(f"  Review queue written -> {os.path.relpath(REVIEW_OUT)}")

    # ------------------------------------------------------------------
    # Step 7 — Write audit
    # ------------------------------------------------------------------
    audit_lines = [
        "=== ADEI Merge Audit ===",
        f"Input: {len(google_records)} Google records, {len(yelp_records)} Yelp records",
        "",
        "Pass 1 (exact phone):",
        f"  Confirmed matches: {p1_confirmed}",
        f"  Conflicts sent to review: {p1_conflicts}",
        "",
        "Pass 2 (fuzzy within-tract):",
        f"  Auto-confirmed (>=90): {p2_auto}",
        f"  Sent to review (75-89): {p2_review}",
        f"  No match (<75): {p2_no_match}",
        "",
        "Pass 3 (fuzzy cross-tract):",
        f"  Auto-confirmed: {p3_auto}",
        f"  Sent to review: {p3_review}",
        "",
        "Master dataset composition:",
        f"  Matched records: {total_matched}",
        f"  Google-only records: {google_only_count}",
        f"  Yelp-only records: {yelp_only_count}",
        f"  Total: {total_master}",
        "",
        f"Review queue: {len(review_queue)} rows requiring human decision",
        "",
        f"GEOID integrity check: {geoid_mismatches} records with mismatched "
        "Google/Yelp geoid (see warnings above)",
    ]

    audit_text = "\n".join(audit_lines)
    with open(AUDIT_OUT, "w", encoding="utf-8") as f:
        f.write(audit_text + "\n")
    print(f"  Audit written -> {os.path.relpath(AUDIT_OUT)}")

    print("\n" + audit_text)


if __name__ == "__main__":
    main()
