"""
score_master.py — DII scoring runner for data/processed/master_businesses.json.

Reads each master record, maps fields to the shapes expected by DIIScorer,
calls individual dimension methods, and writes the five DII score fields back
into the master dataset in place.

DIIScorer class methods are not modified — only the data wiring changes here.

Source-based routing:
  matched     — all five dimensions scored
  google_only — google_maps, website, social scored; yelp=0, accuracy=0
  yelp_only   — yelp, website, social scored; google_maps=0, accuracy=0

Note: calculate_total_dii() is NOT used because it hard-codes score_social_media({})
(line 395 of dii_scorer.py), which always returns 0 regardless of website URL.
Individual dimension methods are called directly with the correct inputs.
"""

import json
import logging
import os
import statistics
import traceback
from collections import defaultdict

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT       = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
MASTER_PATH     = os.path.join(REPO_ROOT, 'data', 'processed', 'master_businesses.json')
ERRORS_LOG_PATH = os.path.join(REPO_ROOT, 'data', 'processed', 'scoring_errors.log')

# ── Error logger (file only — does not pollute stdout) ────────────────────────
error_logger = logging.getLogger('scoring_errors')
error_logger.setLevel(logging.ERROR)
_fh = logging.FileHandler(ERRORS_LOG_PATH, mode='w', encoding='utf-8')
_fh.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
error_logger.addHandler(_fh)
error_logger.propagate = False


# ── Field mapping ──────────────────────────────────────────────────────────────

def map_master_to_scorer(record: dict) -> tuple[dict, dict]:
    """
    Map one master record to (google_dict, yelp_dict).

    google_dict shape matches what score_google_maps(), score_website(), and
    score_social_media() expect from a Google Places API record.

    yelp_dict shape matches what score_yelp() and score_accuracy() expect from
    a Yelp Fusion API record.

    Fields dropped at merge (businessStatus, regularOpeningHours, photos, hours)
    are set to None so the scorer handles them as missing without fabricating values.
    address_raw is threaded in as both formattedAddress (google) and
    location.display_address (yelp) so score_accuracy() can do fuzzy comparison
    on matched records.
    """
    name         = record.get('name') or ''
    phone        = record.get('phone')
    address_raw  = record.get('address_raw') or ''
    website_url  = record.get('website_url')
    rating       = record.get('rating')
    review_count = record.get('review_count')

    google_dict = {
        # score_website / score_social_media key
        'websiteUri':          website_url,
        # score_google_maps keys
        'businessStatus':      None,   # dropped at merge — scores as missing
        'regularOpeningHours': None,   # dropped at merge — scores as missing
        'userRatingCount':     review_count,
        'rating':              rating,
        'photos':              None,   # dropped at merge — scores as missing
        # score_accuracy keys (google side)
        'nationalPhoneNumber': phone,
        'formattedAddress':    address_raw,
        # display name (used by calculate_total_dii, included for completeness)
        'displayName':         {'text': name},
    }

    yelp_dict = {
        # score_yelp keys
        'name':         name,
        'rating':       rating,
        'review_count': review_count,
        'is_claimed':   None,   # not available from search endpoint — scores as 0
        'hours':        None,   # dropped at merge — scores as missing
        # score_accuracy keys (yelp side)
        'phone':        phone,
        'location':     {'display_address': [address_raw] if address_raw else []},
    }

    return google_dict, yelp_dict


# ── Per-record scoring ─────────────────────────────────────────────────────────

def score_record(scorer, record: dict) -> dict:
    """
    Score one master record across all five DII dimensions.

    Explicit source routing (not implicit null handling):
      matched     — all five dimensions scored
      google_only — google_maps ✓  website ✓  social ✓  yelp=0  accuracy=(google_dict,{})
      yelp_only   — yelp ✓  accuracy=({},yelp_dict)  google_maps=0  website=0  social=0
    """
    source = record.get('source', '')
    google_dict, yelp_dict = map_master_to_scorer(record)

    # Dimension 1 — Google Maps (0–25)
    # yelp_only: no Google listing → explicit 0 via empty dict
    g_for_maps = google_dict if source in ('matched', 'google_only') else {}
    google_result = scorer.score_google_maps(g_for_maps)

    # Dimension 2 — Website (0–25, effective ceiling 16 for MVP)
    # yelp_only: explicit 0 by routing rule — website dimension is Google-sourced
    if source == 'yelp_only':
        website_result = {'score': 0, 'breakdown': {'website_state': 1}}
    else:
        website_result = scorer.score_website(google_dict)

    # Dimension 3 — Yelp (0–20, effective ceiling 13 — is_claimed stubbed)
    # google_only: no Yelp listing → explicit 0 via empty dict
    y_for_yelp = yelp_dict if source in ('matched', 'yelp_only') else {}
    yelp_result = scorer.score_yelp(y_for_yelp)

    # Dimension 4 — Social media (0–15)
    # yelp_only: explicit 0 by routing rule — social proxies through website dimension
    # Called directly (NOT via calculate_total_dii) to bypass the line-395 hardcode
    # score_social_media({}) which always returns 0 regardless of websiteUri.
    if source == 'yelp_only':
        social_result = {'score': 0, 'breakdown': {'social_state': 0, 'social_platforms': []}}
    else:
        social_result = scorer.score_social_media(google_dict)

    # Dimension 5 — Info accuracy (0–15)
    # matched:     full cross-source comparison
    # google_only: pass (google_dict, {}) — scorer returns what it can on partial data
    # yelp_only:   pass ({}, yelp_dict)   — scorer returns what it can on partial data
    if source == 'matched':
        accuracy_result = scorer.score_accuracy(google_dict, yelp_dict)
    elif source == 'google_only':
        accuracy_result = scorer.score_accuracy(google_dict, {})
    else:  # yelp_only
        accuracy_result = scorer.score_accuracy({}, yelp_dict)

    total = (
        google_result['score']   +
        website_result['score']  +
        yelp_result['score']     +
        social_result['score']   +
        accuracy_result['score']
    )

    return {
        'dii_google_maps_score': google_result['score'],
        'dii_website_score':     website_result['score'],
        'dii_yelp_score':        yelp_result['score'],
        'dii_social_score':      social_result['score'],
        'dii_accuracy_score':    accuracy_result['score'],
        'dii_total_score':       total,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    with open(MASTER_PATH, encoding='utf-8') as f:
        data = json.load(f)

    assert len(data) == 5626, f"Unexpected record count before scoring: {len(data)}"

    # Import here so path setup above is complete first
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from score.dii_scorer import DIIScorer

    scorer = DIIScorer()
    error_count = 0

    for rec in data:
        try:
            scores = score_record(scorer, rec)
        except Exception as exc:
            error_count += 1
            error_logger.error(
                "master_id=%s  name=%r  error=%s\n%s",
                rec.get('master_id'), rec.get('name'), exc, traceback.format_exc(),
            )
            scores = {
                'dii_google_maps_score': 0,
                'dii_website_score':     0,
                'dii_yelp_score':        0,
                'dii_social_score':      0,
                'dii_accuracy_score':    0,
                'dii_total_score':       0,
            }

        rec.update(scores)

    # ── Safety checks ──────────────────────────────────────────────────────────
    assert len(data) == 5626, f"Record count changed during scoring: {len(data)}"

    score_fields = [
        'dii_google_maps_score', 'dii_website_score', 'dii_yelp_score',
        'dii_social_score', 'dii_accuracy_score', 'dii_total_score',
    ]
    for field in score_fields:
        nulls = sum(1 for r in data if r.get(field) is None)
        assert nulls == 0, f"HALT: {field} still has {nulls} null values after scoring"

    # ── Write ──────────────────────────────────────────────────────────────────
    with open(MASTER_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # ── Summary stats (in-scope records only) ──────────────────────────────────
    in_scope = [r for r in data if r.get('exclusion_flag') is None]
    flagged  = [r for r in data if r.get('exclusion_flag') is not None]
    totals   = [r['dii_total_score'] for r in in_scope]

    print(f"DII Scoring complete — {len(data):,} records scored")
    if error_count:
        print(f"  Errors: {error_count} record(s) scored as 0 — see data/processed/scoring_errors.log")
    print()
    print("Score distribution (in-scope records, exclusion_flag=null):")
    print(f"  dii_total_score:")
    print(f"    mean:    {statistics.mean(totals):.1f}")
    print(f"    median:  {statistics.median(totals):.1f}")
    print(f"    min:     {min(totals)}")
    print(f"    max:     {max(totals)}")
    print()

    hood_scores = defaultdict(list)
    for r in in_scope:
        hood_scores[r.get('neighborhood', 'Unknown')].append(r['dii_total_score'])

    print("By neighborhood (in-scope only, mean dii_total_score):")
    for hood in ['East Austin', 'South Congress', 'The Domain']:
        scores = hood_scores.get(hood, [])
        mean_val = statistics.mean(scores) if scores else 0.0
        print(f"  {hood:<20}  {mean_val:.1f}  (n={len(scores):,})")

    print()
    zeros = sum(1 for s in totals if s == 0)
    maxes = sum(1 for s in totals if s == 84)
    print(f"Records with dii_total_score = 0:   {zeros:,}")
    print(f"Records with dii_total_score = 84:  {maxes:,}")


if __name__ == '__main__':
    main()
