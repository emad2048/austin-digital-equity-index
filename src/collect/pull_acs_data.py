"""
Pull ACS 5-year estimates (2023) for every census tract defined in
config/neighborhoods.py and save results to data/raw/acs_demographics.csv.

Census API key is optional for low-volume calls (<500/day) but recommended
for production use. Store it as CENSUS_API_KEY in .env if available.

Limitation: pct_broadband and income figures come directly from ACS.
Population *density* requires tract land area in sq km, which is not
available in the ACS API response. Land area must be joined separately
(e.g., from the Census TIGER/Line shapefile or the ACS subject table
B01001). This script records raw population only; density is not computed.
"""

import os
import sys

import pandas as pd
import requests
from dotenv import load_dotenv

# Ensure repo root is on the path so config/ is importable regardless of
# where the script is invoked from.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config.neighborhoods import NEIGHBORHOODS

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://api.census.gov/data/2023/acs/acs5"
STATE = "48"
COUNTY = "453"

# A Census API key is optional for low-volume calls but recommended.
# Register free at https://api.census.gov/data/key_signup.html and store as
# CENSUS_API_KEY in .env.
CENSUS_API_KEY = os.getenv("CENSUS_API_KEY")

ACS_VARIABLES = {
    "B19013_001E": "median_household_income",
    "B03002_003E": "non_hispanic_white_pop",
    "B03002_001E": "total_pop_race",
    "B01003_001E": "total_pop",
    "B28002_004E": "households_broadband",
    "B28002_001E": "total_households",
}

OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "raw", "acs_demographics.csv"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_tract(tract_geoid: str) -> dict | None:
    """
    Fetch ACS variables for a single tract GEOID (11-digit string).
    Returns a flat dict of {column_name: value} or None on failure.
    """
    # GEOID format: 2-digit state + 3-digit county + 6-digit tract
    tract_code = tract_geoid[5:]  # last 6 digits

    params = {
        "get": ",".join(ACS_VARIABLES.keys()),
        "for": f"tract:{tract_code}",
        "in": f"state:{STATE} county:{COUNTY}",
    }
    if CENSUS_API_KEY:
        params["key"] = CENSUS_API_KEY

    try:
        response = requests.get(BASE_URL, params=params, timeout=15)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"  [ERROR] HTTP {response.status_code} for tract {tract_geoid}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Request failed for tract {tract_geoid}: {e}")
        return None

    data = response.json()
    if len(data) < 2:
        print(f"  [WARN] No data rows returned for tract {tract_geoid}")
        return None

    headers, values = data[0], data[1]
    row = dict(zip(headers, values))

    result = {"geoid": tract_geoid}
    for api_var, col_name in ACS_VARIABLES.items():
        raw = row.get(api_var)
        # Census uses negative values (e.g. -666666666) as null sentinels
        result[col_name] = float(raw) if raw is not None and float(raw) >= 0 else None

    return result


def build_geoid_to_neighborhood() -> dict[str, str]:
    """Return a mapping of GEOID -> neighborhood name."""
    mapping = {}
    for key, info in NEIGHBORHOODS.items():
        for geoid in info["census_tracts"]:
            mapping[geoid] = info["name"]
    return mapping


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    geoid_to_neighborhood = build_geoid_to_neighborhood()
    all_geoids = list(geoid_to_neighborhood.keys())

    print(f"Fetching ACS data for {len(all_geoids)} tracts across "
          f"{len(NEIGHBORHOODS)} neighborhoods...\n")

    rows = []
    for geoid in all_geoids:
        neighborhood = geoid_to_neighborhood[geoid]
        print(f"  Pulling tract {geoid} ({neighborhood})...")
        row = fetch_tract(geoid)
        if row:
            row["neighborhood"] = neighborhood
            rows.append(row)

    if not rows:
        print("\n[FATAL] No data was retrieved. Check API connectivity and GEOIDs.")
        sys.exit(1)

    df = pd.DataFrame(rows)

    # Derived columns
    df["pct_minority"] = (
        1 - df["non_hispanic_white_pop"] / df["total_pop_race"]
    ).clip(0, 1)

    df["pct_broadband"] = (
        df["households_broadband"] / df["total_households"]
    ).clip(0, 1)

    # Reorder columns for readability
    col_order = [
        "geoid",
        "neighborhood",
        "median_household_income",
        "total_pop",
        "total_pop_race",
        "non_hispanic_white_pop",
        "pct_minority",
        "total_households",
        "households_broadband",
        "pct_broadband",
    ]
    df = df[col_order]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(df)} rows to {os.path.relpath(OUTPUT_PATH)}\n")

    # Summary
    summary = (
        df.groupby("neighborhood")
        .agg(
            avg_median_income=("median_household_income", "mean"),
            avg_pct_minority=("pct_minority", "mean"),
            avg_pct_broadband=("pct_broadband", "mean"),
            tracts=("geoid", "count"),
        )
        .reset_index()
    )

    print("=== Neighborhood Summary ===")
    for _, r in summary.iterrows():
        print(f"\n{r['neighborhood']} ({int(r['tracts'])} tract(s))")
        print(f"  Avg median income : ${r['avg_median_income']:,.0f}")
        print(f"  Avg % minority    : {r['avg_pct_minority']:.1%}")
        print(f"  Avg % broadband   : {r['avg_pct_broadband']:.1%}")


if __name__ == "__main__":
    main()
