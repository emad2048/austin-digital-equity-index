import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
YELP_API_KEY = os.getenv("YELP_API_KEY")


def test_google_places():
    print("=== Google Places API (New) ===")
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress",
    }
    body = {
        "textQuery": "coffee in Austin TX",
    }

    try:
        response = requests.post(url, headers=headers, json=body)
        if response.ok:
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"ERROR {response.status_code}: {response.text}")
    except requests.RequestException as e:
        print(f"Request failed: {e}")


def test_yelp():
    print("\n=== Yelp Fusion API ===")
    url = "https://api.yelp.com/v3/businesses/search"
    headers = {
        "Authorization": f"Bearer {YELP_API_KEY}",
    }
    params = {
        "term": "coffee",
        "location": "Austin, TX",
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.ok:
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"ERROR {response.status_code}: {response.text}")
    except requests.RequestException as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    test_google_places()
    test_yelp()
