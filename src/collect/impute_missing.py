import json
import statistics
from datetime import datetime, timezone

with open('data/processed/master_businesses.json', encoding='utf-8') as f:
    data = json.load(f)

assert len(data) == 5626, f"Unexpected record count before imputation: {len(data)}"

in_scope = [r for r in data if r.get('exclusion_flag') is None]
flagged  = [r for r in data if r.get('exclusion_flag') is not None]

print(f"In-scope records: {len(in_scope)}")
print(f"Flagged records:  {len(flagged)}")
print()

# ── Missing value audit (in-scope only) ──────────────────────────────────────
all_fields = list(data[0].keys())
print("=== MISSING VALUE AUDIT (in-scope records only) ===")
print(f"{'Field':<35} {'Null count':>10} {'Pct null':>10}")
print("-" * 58)
for field in all_fields:
    null_count = sum(1 for r in in_scope if r.get(field) is None)
    pct = null_count / len(in_scope) * 100
    print(f"{field:<35} {null_count:>10} {pct:>9.1f}%")
print()

# ── Compute medians from in-scope records only ────────────────────────────────
rating_values       = [r['rating']       for r in in_scope if r.get('rating')       is not None]
review_count_values = [r['review_count'] for r in in_scope if r.get('review_count') is not None]

rating_median       = statistics.median(rating_values)
review_count_median = int(statistics.median(review_count_values))

# ── Apply imputation to in-scope records only ─────────────────────────────────
filled = {'rating': 0, 'review_count': 0, 'category': 0, 'zip_code': 0}

for rec in data:
    if rec.get('exclusion_flag') is not None:
        continue  # skip flagged records entirely

    if rec.get('rating') is None:
        rec['rating'] = rating_median
        filled['rating'] += 1

    if rec.get('review_count') is None:
        rec['review_count'] = review_count_median
        filled['review_count'] += 1

    if rec.get('category') is None:
        rec['category'] = 'Unknown'
        filled['category'] += 1

    if rec.get('zip_code') is None:
        rec['zip_code'] = 'Unknown'
        filled['zip_code'] += 1

# ── Safety check ──────────────────────────────────────────────────────────────
assert len(data) == 5626, f"RECORD COUNT CHANGED: {len(data)}"

# ── Write updated dataset ─────────────────────────────────────────────────────
with open('data/processed/master_businesses.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# ── Save imputation log ───────────────────────────────────────────────────────
log = {
    "run_timestamp": datetime.now(timezone.utc).isoformat(),
    "source_file": "data/processed/master_businesses.json",
    "total_records": len(data),
    "in_scope_records": len(in_scope),
    "flagged_records": len(flagged),
    "imputation_parameters": {
        "rating_median": rating_median,
        "review_count_median": review_count_median,
        "category_fill_value": "Unknown",
        "zip_code_fill_value": "Unknown"
    },
    "records_filled": filled,
    "fields_intentionally_left_null": {
        "google_place_id": "null = yelp_only record, valid absence",
        "yelp_id":         "null = google_only record, valid absence",
        "website_url":     "null = no website, DII scoring signal",
        "phone":           "null = no phone listed, DII signal",
        "yelp_url":        "null = no Yelp presence, DII signal",
        "dii_*_score":     "scored in separate pipeline step"
    }
}

with open('data/processed/imputation_log.json', 'w', encoding='utf-8') as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

# ── Counts for intentionally-null fields (post-imputation, in-scope only) ────
null_website  = sum(1 for r in data if r.get('exclusion_flag') is None and r.get('website_url')      is None)
null_phone    = sum(1 for r in data if r.get('exclusion_flag') is None and r.get('phone')            is None)
null_yelp_id  = sum(1 for r in data if r.get('exclusion_flag') is None and r.get('yelp_id')          is None)
null_gplace   = sum(1 for r in data if r.get('exclusion_flag') is None and r.get('google_place_id')  is None)

# ── Print summary ─────────────────────────────────────────────────────────────
print("Imputation summary — in-scope records only (5,350):")
print()
print("  Fields imputed:")
print(f"    rating:        {filled['rating']:>4} records filled  (median used: {rating_median})")
print(f"    review_count:  {filled['review_count']:>4} records filled  (median used: {review_count_median})")
print(f"    category:      {filled['category']:>4} records filled  (value used: \"Unknown\")")
print(f"    zip_code:      {filled['zip_code']:>4} records filled  (value used: \"Unknown\")")
print()
print("  Fields intentionally left null:")
print(f"    website_url:     {null_website:>4} null records  (no website = DII signal)")
print(f"    phone:           {null_phone:>4} null records  (no phone listed)")
print(f"    yelp_id:         {null_yelp_id:>4} null records  (google_only records)")
print(f"    google_place_id: {null_gplace:>4} null records  (yelp_only records)")
print()
print(f"  Total in-scope records:  {len(in_scope):>6}")
print(f"  Total flagged records:   {len(flagged):>6}  (not imputed)")
print(f"  Grand total:             {len(data):>6}")
print()
print("Imputation log written to data/processed/imputation_log.json")
