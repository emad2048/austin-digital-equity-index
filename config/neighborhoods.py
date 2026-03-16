"""
Neighborhood definitions for the Austin Digital Equity Index.

Each entry in NEIGHBORHOODS maps a neighborhood key to its human-readable
name and the list of Census tract GEOIDs (as strings) that fall within it.

IMPORTANT: Tract lists must be fully populated before running any data
collection scripts. Placeholder and empty lists are not suitable for
production data pulls.
"""

# NOTE — Domain income anomaly observed in ACS pull ($84k vs $97k East Austin):
# likely reflects residential tracts adjacent to commercial core rather than
# Domain proper. Expand tract coverage in v2 to capture true demographic profile.

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
