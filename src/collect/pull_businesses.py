"""
Pull raw business listings from Google Places API (New) and Yelp Fusion API
for every neighborhood defined in config/neighborhoods.py.

Raw JSON responses are saved as-is to data/raw/ — no deduplication or
cleaning is performed here. That happens in Sprint 2.

Output files:
  data/raw/google_<neighborhood_slug>_raw.json
  data/raw/yelp_<neighborhood_slug>_raw.json
"""

import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config.neighborhoods import NEIGHBORHOODS

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
YELP_API_KEY = os.getenv("YELP_API_KEY")

GOOGLE_URL = "https://places.googleapis.com/v1/places:searchText"
YELP_URL = "https://api.yelp.com/v3/businesses/search"

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

RATE_LIMIT_DELAY = 0.5   # seconds between API calls
GOOGLE_MAX_PAGES = 5
YELP_MAX_BUSINESSES = 200
YELP_PAGE_SIZE = 50

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")


# ---------------------------------------------------------------------------
# Google Places
# ---------------------------------------------------------------------------

def pull_google(neighborhood_name: str) -> list[dict]:
    """
    Search Google Places for small businesses in a neighborhood.
    Paginates via nextPageToken up to GOOGLE_MAX_PAGES pages.
    Returns a flat list of place dicts exactly as returned by the API.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": GOOGLE_FIELD_MASK,
    }
    body = {"textQuery": f"small businesses in {neighborhood_name} Austin TX"}

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
        all_places.extend(places)

        next_token = data.get("nextPageToken")
        if not next_token:
            break

        body["pageToken"] = next_token
        time.sleep(RATE_LIMIT_DELAY)

    return all_places


# ---------------------------------------------------------------------------
# Yelp Fusion
# ---------------------------------------------------------------------------

YELP_BUSINESS_FIELDS = {
    "name", "location", "phone", "hours", "rating",
    "review_count", "url", "is_claimed", "categories",
}


def _filter_yelp_business(business: dict) -> dict:
    """Return only the fields we care about from a Yelp business object."""
    return {k: v for k, v in business.items() if k in YELP_BUSINESS_FIELDS}


def pull_yelp(neighborhood_name: str) -> list[dict]:
    """
    Search Yelp for businesses in a neighborhood.
    Paginates with offset until results are exhausted or YELP_MAX_BUSINESSES.
    Returns a flat list of (filtered) business dicts.
    """
    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    all_businesses = []
    offset = 0

    while offset < YELP_MAX_BUSINESSES:
        params = {
            "location": f"{neighborhood_name} Austin TX",
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

        all_businesses.extend(_filter_yelp_business(b) for b in businesses)

        total = data.get("total", 0)
        offset += len(businesses)

        # Stop if we've collected everything the API says exists
        if offset >= total:
            break

        time.sleep(RATE_LIMIT_DELAY)

    return all_businesses


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def save_json(data: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    if not GOOGLE_API_KEY:
        print("[WARN] GOOGLE_PLACES_API_KEY not set — Google pulls will fail.")
    if not YELP_API_KEY:
        print("[WARN] YELP_API_KEY not set — Yelp pulls will fail.")

    os.makedirs(RAW_DIR, exist_ok=True)

    for slug, info in NEIGHBORHOODS.items():
        name = info["name"]
        print(f"\n{'=' * 50}")
        print(f"Neighborhood: {name}")
        print(f"{'=' * 50}")

        # --- Google ---
        print(f"  [Google] Pulling businesses...")
        google_results = []
        try:
            google_results = pull_google(name)
        except Exception as e:
            print(f"  [ERROR] Google pull failed for {name}: {e}")

        google_path = os.path.join(RAW_DIR, f"google_{slug}_raw.json")
        save_json(google_results, google_path)
        print(f"  [Google] {len(google_results)} businesses saved -> {os.path.relpath(google_path)}")

        time.sleep(RATE_LIMIT_DELAY)

        # --- Yelp ---
        print(f"  [Yelp]   Pulling businesses...")
        yelp_results = []
        try:
            yelp_results = pull_yelp(name)
        except Exception as e:
            print(f"  [ERROR] Yelp pull failed for {name}: {e}")

        yelp_path = os.path.join(RAW_DIR, f"yelp_{slug}_raw.json")
        save_json(yelp_results, yelp_path)
        print(f"  [Yelp]   {len(yelp_results)} businesses saved -> {os.path.relpath(yelp_path)}")

    print(f"\n{'=' * 50}")
    print("All neighborhoods complete.")
    print(f"Raw files saved to: {os.path.relpath(RAW_DIR)}")


if __name__ == "__main__":
    main()
