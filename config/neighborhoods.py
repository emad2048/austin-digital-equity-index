"""
Neighborhood definitions for the Austin Digital Equity Index.

NEIGHBORHOODS maps slug keys to human-readable names and census tract GEOIDs.
Used by pull_acs_data.py and dii_scorer.py.

TRACTS maps neighborhood names to lists of tract dicts with GEOID and centroid
lat/lng. Used by pull_businesses.py for tract-level Google Places queries.
Centroids (lat/lng) are populated at runtime by fetch_tract_centroids() in
pull_businesses.py and cached to config/tract_centroids.json. The None values
below are placeholders — do not run data collection until centroids are fetched.

IMPORTANT: Tract lists must be fully populated before running any data
collection scripts. Placeholder and empty lists are not suitable for
production data pulls.
"""

# NOTE — Domain income anomaly observed in ACS pull ($84k vs $97k East Austin):
# likely reflects residential tracts adjacent to commercial core rather than
# Domain proper. Expand tract coverage in v2 to capture true demographic profile.

# Used by pull_acs_data.py and dii_scorer.py
NEIGHBORHOODS = {
    "east_austin": {
        "name": "East Austin",
        "census_tracts": [  # MVP coverage — will be expanded in v2
            "48453000902",
            "48453000803",
            "48453002108",
            "48453002111",
        ],
    },
    "south_congress": {
        "name": "South Congress",
        "census_tracts": [  # MVP coverage — will be expanded in v2
            "48453001312",
        ],
    },
    "the_domain": {
        "name": "The Domain",
        "census_tracts": [  # MVP coverage — will be expanded in v2
            "48453045400",
            "48453030800",
        ],
    },
}

# Used by pull_businesses.py for tract-centroid-based Google Places queries.
# lat/lng populated at runtime by fetch_tract_centroids(); cached to
# config/tract_centroids.json after first successful fetch.
TRACTS = {
    "East Austin": [
        {"geoid": "48453000902", "lat": None, "lng": None},
        {"geoid": "48453000803", "lat": None, "lng": None},
        {"geoid": "48453002108", "lat": None, "lng": None},
        {"geoid": "48453002111", "lat": None, "lng": None},
        {"geoid": "48453000804", "lat": None, "lng": None},
        {"geoid": "48453002320", "lat": None, "lng": None},
        {"geoid": "48453002321", "lat": None, "lng": None},
        {"geoid": "48453002326", "lat": None, "lng": None},
    ],
    "South Congress": [
        {"geoid": "48453001312", "lat": None, "lng": None},
        {"geoid": "48453001401", "lat": None, "lng": None},
        {"geoid": "48453002403", "lat": None, "lng": None},
    ],
    "The Domain": [
        {"geoid": "48453045400", "lat": None, "lng": None},
        {"geoid": "48453030800", "lat": None, "lng": None},
    ],
}
