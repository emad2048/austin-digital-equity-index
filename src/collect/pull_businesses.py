"""
Pull raw business listings from Google Places API (New) and Yelp Fusion API.

Google pulls are now tract-centroid-based: one Places API query per census
tract using a locationRestriction circle (1200m radius) centered on the
tract's internal point. This replaces the previous free-text neighborhood
query and ensures low-visibility businesses in underserved tracts are captured.

Centroids are fetched once from the Census TIGERweb REST API and cached to
config/tract_centroids.json. Subsequent runs load from the cache.

Note on Census endpoint: the Census geocoder at
  geocoding.geo.census.gov/geocoder/geographies/coordinates
is a coordinates-to-geography lookup (inverse of what we need). For
GEOID-to-centroid we use the TIGERweb REST service which returns
INTPTLAT/INTPTLON (internal point) for each tract.

Output files:
  data/raw/google_all_tracts_raw.json   (all tracts, all neighborhoods)
  data/raw/yelp_<neighborhood_slug>_raw.json  (unchanged from Sprint 1)
"""

import copy
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config.neighborhoods import NEIGHBORHOODS, TRACTS

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
YELP_API_KEY = os.getenv("YELP_API_KEY")

GOOGLE_URL = "https://places.googleapis.com/v1/places:searchText"
YELP_URL = "https://api.yelp.com/v3/businesses/search"

TIGERWEB_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services"
    "/TIGERweb/tigerWMS_ACS2023/MapServer/8/query"
)

GOOGLE_FIELD_MASK = (
    "places.displayName,"
    "places.formattedAddress,"
    "places.nationalPhoneNumber,"
    "places.regularOpeningHours,"
    "places.websiteUri,"
    "places.rating,"
    "places.userRatingCount,"
    "places.photos,"
    "places.businessStatus,"
    "places.id"
)

RATE_LIMIT_DELAY = 0.5       # seconds between API calls
TIGERWEB_DELAY = 0.3         # seconds between centroid fetches
GOOGLE_MAX_PAGES = 5
GOOGLE_TRACT_RADIUS_M = 800  # 800m radius per tract; pagination unavailable for
                              # locationBias circle queries (confirmed diagnostic)
YELP_MAX_BUSINESSES = 200
YELP_PAGE_SIZE = 50

# One query per category per tract. Replaces the single "small business" query
# which hit the 20-record ceiling with no pagination available.
BUSINESS_CATEGORIES = [
    "restaurant",
    "beauty salon",
    "auto repair",
    "convenience store",
    "finance",
    "fitness",
    "retail store",
]

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RAW_DIR = os.path.join(REPO_ROOT, "data", "raw")
CENTROIDS_CACHE = os.path.join(REPO_ROOT, "config", "tract_centroids.json")


# ---------------------------------------------------------------------------
# Step 1 — Tract centroid fetch (one-time, cached)
# ---------------------------------------------------------------------------

def fetch_tract_centroids(tracts: dict, test_geoids: list[str] | None = None) -> dict:
    """
    Populate lat/lng for every tract in `tracts` by querying the Census
    TIGERweb REST API for each GEOID's internal point (INTPTLAT / INTPTLON).

    Saves the populated result to CENTROIDS_CACHE (config/tract_centroids.json)
    so subsequent runs skip the network calls.

    Args:
        tracts:       The TRACTS dict from config/neighborhoods.py.
        test_geoids:  If provided, only fetch centroids for these GEOIDs
                      (used for pre-run validation — pass None for full fetch).

    Returns:
        A deep copy of `tracts` with lat/lng fields populated.
    """
    populated = copy.deepcopy(tracts)

    for neighborhood, tract_list in populated.items():
        for tract in tract_list:
            geoid = tract["geoid"]

            if test_geoids is not None and geoid not in test_geoids:
                continue

            params = {
                "where": f"GEOID='{geoid}'",
                "outFields": "GEOID,INTPTLAT,INTPTLON",
                "returnGeometry": "false",
                "f": "json",
            }
            try:
                resp = requests.get(TIGERWEB_URL, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                features = data.get("features", [])
                if features:
                    attrs = features[0]["attributes"]
                    tract["lat"] = float(attrs["INTPTLAT"])
                    tract["lng"] = float(attrs["INTPTLON"])
                    print(f"  {geoid} ({neighborhood}): ({tract['lat']}, {tract['lng']})")
                else:
                    print(f"  [WARN] No features returned for {geoid}")
            except requests.RequestException as e:
                print(f"  [ERROR] Centroid fetch failed for {geoid}: {e}")

            time.sleep(TIGERWEB_DELAY)

    if test_geoids is None:
        # Only cache after a full fetch
        with open(CENTROIDS_CACHE, "w", encoding="utf-8") as f:
            json.dump(populated, f, indent=2)
        print(f"\nCentroids cached to {os.path.relpath(CENTROIDS_CACHE)}")

    return populated


def load_tracts_with_centroids() -> dict:
    """
    Return TRACTS with lat/lng populated. Loads from cache if available,
    otherwise runs a full centroid fetch and saves the cache.
    """
    if os.path.exists(CENTROIDS_CACHE):
        with open(CENTROIDS_CACHE, encoding="utf-8") as f:
            return json.load(f)
    print("Centroid cache not found — fetching from TIGERweb...")
    return fetch_tract_centroids(TRACTS)


# ---------------------------------------------------------------------------
# Step 2 — Google Places (tract-centroid-based)
# ---------------------------------------------------------------------------

def pull_google(tract: dict, neighborhood_name: str, category: str) -> list[dict]:
    """
    Search Google Places for businesses of a specific category within 800m of
    a tract centroid.

    Querying by category rather than "small business" works around the hard
    20-record ceiling: pagination is unavailable for locationBias circle queries
    (confirmed diagnostic), so multiple category queries per tract are used to
    increase total coverage.

    Note: the Places API (New) searchText only supports locationRestriction with
    a rectangle, not a circle. locationBias supports circles and is used here —
    it biases results toward the tract centroid within the given radius.

    Args:
        tract:             {"geoid": str, "lat": float, "lng": float}
        neighborhood_name: Human-readable name added to every returned record.
        category:          Business category string (e.g. "restaurant").

    Returns:
        List of place dicts with "geoid", "neighborhood", and "category" fields
        appended to each record.
    """
    if tract.get("lat") is None or tract.get("lng") is None:
        print(f"    [SKIP] No centroid for {tract['geoid']} — run fetch_tract_centroids first.")
        return []

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": GOOGLE_FIELD_MASK,
    }
    body = {
        "textQuery": category,
        "locationBias": {
            "circle": {
                "center": {"latitude": tract["lat"], "longitude": tract["lng"]},
                "radius": float(GOOGLE_TRACT_RADIUS_M),
            }
        },
    }

    all_places = []
    page = 0

    while page < GOOGLE_MAX_PAGES:
        page += 1
        try:
            response = requests.post(GOOGLE_URL, headers=headers, json=body, timeout=15)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"    [ERROR] Google HTTP {response.status_code} on page {page}: {e}")
            break
        except requests.exceptions.RequestException as e:
            print(f"    [ERROR] Google request failed on page {page}: {e}")
            break

        data = response.json()
        places = data.get("places", [])

        # Annotate each record with tract provenance and category before accumulating
        for place in places:
            place["geoid"] = tract["geoid"]
            place["neighborhood"] = neighborhood_name
            place["category"] = category

        all_places.extend(places)

        next_token = data.get("nextPageToken")
        if not next_token:
            break

        body["pageToken"] = next_token
        time.sleep(RATE_LIMIT_DELAY)

    return all_places


# ---------------------------------------------------------------------------
# Yelp Fusion — tract-centroid-based, mirroring Google pull architecture
# ---------------------------------------------------------------------------

YELP_BUSINESS_FIELDS = {
    "id", "name", "location", "phone", "hours", "rating",
    "review_count", "url", "is_claimed", "categories",
}


def _filter_yelp_business(business: dict) -> dict:
    """Return only the fields we care about from a Yelp business object."""
    return {k: v for k, v in business.items() if k in YELP_BUSINESS_FIELDS}


def pull_yelp(tract: dict, neighborhood_name: str, category: str) -> list[dict]:
    """
    Search Yelp for businesses of a specific category within 800m of a tract
    centroid. Mirrors the pull_google architecture: one call per tract/category.

    Uses latitude, longitude, and radius instead of the location string to
    respect census tract boundaries. Yelp radius max is 40,000m; 800m used here
    to match the Google pull radius.

    Paginates with offset until results are exhausted or YELP_MAX_BUSINESSES.

    Args:
        tract:             {"geoid": str, "lat": float, "lng": float}
        neighborhood_name: Human-readable name added to every returned record.
        category:          Business category string used as Yelp `term` param.

    Returns:
        List of filtered business dicts with "geoid", "neighborhood", and
        "category" fields appended to each record.
    """
    if tract.get("lat") is None or tract.get("lng") is None:
        print(f"    [SKIP] No centroid for {tract['geoid']} — run fetch_tract_centroids first.")
        return []

    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    all_businesses = []
    offset = 0

    while offset < YELP_MAX_BUSINESSES:
        params = {
            "term": category,
            "latitude": tract["lat"],
            "longitude": tract["lng"],
            "radius": GOOGLE_TRACT_RADIUS_M,  # 800m, same as Google pull
            "limit": YELP_PAGE_SIZE,
            "offset": offset,
        }
        try:
            response = requests.get(YELP_URL, headers=headers, params=params, timeout=15)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"    [ERROR] Yelp HTTP {response.status_code} at offset {offset}: {e}")
            break
        except requests.exceptions.RequestException as e:
            print(f"    [ERROR] Yelp request failed at offset {offset}: {e}")
            break

        data = response.json()
        businesses = data.get("businesses", [])
        if not businesses:
            break

        for b in businesses:
            filtered = _filter_yelp_business(b)
            filtered["geoid"] = tract["geoid"]
            filtered["neighborhood"] = neighborhood_name
            filtered["category"] = category
            all_businesses.append(filtered)

        total = data.get("total", 0)
        offset += len(businesses)

        if offset >= total:
            break

        time.sleep(RATE_LIMIT_DELAY)

    return all_businesses


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def save_json(data: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def flag_boundary_duplicates(records: list[dict]) -> list[dict]:
    """
    Mark records whose Google Place ID appears in more than one tract.
    Sets "boundary_duplicate": true on duplicates, false otherwise.
    Does NOT remove any records — deduplication is a Sprint 2 human step.
    """
    from collections import Counter
    id_counts = Counter(r.get("id") for r in records if r.get("id"))
    for record in records:
        record["boundary_duplicate"] = id_counts.get(record.get("id"), 1) > 1
    return records


# ---------------------------------------------------------------------------
# Step 3 & 4 — Main collection loop
# ---------------------------------------------------------------------------

def main():
    if not GOOGLE_API_KEY:
        print("[WARN] GOOGLE_PLACES_API_KEY not set — Google pulls will fail.")
    if not YELP_API_KEY:
        print("[WARN] YELP_API_KEY not set — Yelp pulls will fail.")

    os.makedirs(RAW_DIR, exist_ok=True)

    # Load centroids (from cache or fresh fetch)
    tracts_with_centroids = load_tracts_with_centroids()

    # --- Google: one call per neighborhood > tract > category ---
    all_google = []
    total_calls = sum(len(v) for v in tracts_with_centroids.values()) * len(BUSINESS_CATEGORIES)
    call_num = 0

    for neighborhood_name, tract_list in tracts_with_centroids.items():
        print(f"\n{'=' * 50}")
        print(f"[Google] {neighborhood_name} ({len(tract_list)} tracts x "
              f"{len(BUSINESS_CATEGORIES)} categories = "
              f"{len(tract_list) * len(BUSINESS_CATEGORIES)} calls)")
        print(f"{'=' * 50}")

        for tract in tract_list:
            geoid = tract["geoid"]
            for category in BUSINESS_CATEGORIES:
                call_num += 1
                print(f"  [{call_num}/{total_calls}] {geoid} / {category}...",
                      end=" ", flush=True)
                try:
                    results = pull_google(tract, neighborhood_name, category)
                    all_google.extend(results)
                    print(f"{len(results)} records")
                except Exception as e:
                    print(f"ERROR: {e}")

                time.sleep(RATE_LIMIT_DELAY)

    # Flag records whose Place ID appears more than once across any tract or
    # category combination. Do NOT remove — deduplication is a Sprint 2 step.
    all_google = flag_boundary_duplicates(all_google)
    dupes = sum(1 for r in all_google if r.get("boundary_duplicate"))
    print(f"\n[Google] Total: {len(all_google)} records, {dupes} duplicates flagged")

    google_path = os.path.join(RAW_DIR, "google_all_tracts_raw.json")
    save_json(all_google, google_path)
    print(f"[Google] Saved -> {os.path.relpath(google_path)}")

    # Summary by neighborhood
    from collections import Counter, defaultdict
    by_neighborhood = defaultdict(int)
    by_category = Counter()
    for r in all_google:
        by_neighborhood[r.get("neighborhood", "unknown")] += 1
        by_category[r.get("category", "unknown")] += 1

    print(f"\n{'=' * 50}")
    print("Records by neighborhood:")
    for name, count in sorted(by_neighborhood.items()):
        print(f"  {name:<18} {count:>5}")

    print("\nRecords by category:")
    for cat, count in by_category.most_common():
        print(f"  {cat:<20} {count:>5}")

    # --- Yelp: one call per neighborhood > tract > category ---
    all_yelp = []
    yelp_total_calls = sum(len(v) for v in tracts_with_centroids.values()) * len(BUSINESS_CATEGORIES)
    yelp_call_num = 0

    for neighborhood_name, tract_list in tracts_with_centroids.items():
        print(f"\n{'=' * 50}")
        print(f"[Yelp] {neighborhood_name} ({len(tract_list)} tracts x "
              f"{len(BUSINESS_CATEGORIES)} categories = "
              f"{len(tract_list) * len(BUSINESS_CATEGORIES)} calls)")
        print(f"{'=' * 50}")

        for tract in tract_list:
            geoid = tract["geoid"]
            for category in BUSINESS_CATEGORIES:
                yelp_call_num += 1
                print(f"  [{yelp_call_num}/{yelp_total_calls}] {geoid} / {category}...",
                      end=" ", flush=True)
                try:
                    results = pull_yelp(tract, neighborhood_name, category)
                    all_yelp.extend(results)
                    print(f"{len(results)} records")
                except Exception as e:
                    print(f"ERROR: {e}")

                time.sleep(RATE_LIMIT_DELAY)

    all_yelp = flag_boundary_duplicates(all_yelp)
    yelp_dupes = sum(1 for r in all_yelp if r.get("boundary_duplicate"))
    print(f"\n[Yelp] Total: {len(all_yelp)} records, {yelp_dupes} duplicates flagged")

    yelp_path = os.path.join(RAW_DIR, "yelp_all_tracts_raw.json")
    save_json(all_yelp, yelp_path)
    print(f"[Yelp] Saved -> {os.path.relpath(yelp_path)}")

    yelp_by_neighborhood = defaultdict(int)
    yelp_by_category = Counter()
    for r in all_yelp:
        yelp_by_neighborhood[r.get("neighborhood", "unknown")] += 1
        yelp_by_category[r.get("category", "unknown")] += 1

    print(f"\n{'=' * 50}")
    print("Records by neighborhood:")
    for name, count in sorted(yelp_by_neighborhood.items()):
        print(f"  {name:<18} {count:>5}")

    print("\nRecords by category:")
    for cat, count in yelp_by_category.most_common():
        print(f"  {cat:<20} {count:>5}")

    print(f"\n{'=' * 50}")
    print("All neighborhoods complete.")
    print(f"Raw files saved to: {os.path.relpath(RAW_DIR)}")


if __name__ == "__main__":
    main()
