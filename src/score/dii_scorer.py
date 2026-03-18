"""
Digital Inclusion Index (DII) Scorer.

Computes a composite 0-100 score across five dimensions for each business:
  - Google Maps presence  : 25 pts  (score_google_maps)
  - Website quality       : 25 pts  (score_website)
  - Yelp presence         : 20 pts  (score_yelp)
  - Social media presence : 15 pts  (score_social_media — Sprint 2)
  - Info accuracy         : 15 pts  (score_accuracy)

Input records are raw dicts as returned by pull_businesses.py and stored in
data/raw/. Records are never mutated by this class.
"""

import difflib
import json
import os
import re
import sys

# Machine-readable list of scoring gaps in the current sprint.
# Surface these in the Streamlit dashboard so users understand score ceilings.
KNOWN_LIMITATIONS = [
    "Social media dimension uses website social link detection as a proxy — presence signal only, not activity. Businesses without a reachable website score 0 regardless of actual social media presence.",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_phone(raw: str | None) -> str:
    """Strip all non-digit characters and return the last 10 digits.

    Handles both U.S. formats:
      "(512) 974-7800"  -> "5129747800"
      "+15125223031"    -> "5125223031"
    """
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    return digits[-10:] if len(digits) >= 10 else digits


def _address_string(record: dict, source: str) -> str:
    """Return a normalised single-line address string for fuzzy comparison."""
    if source == "google":
        return (record.get("formattedAddress") or "").lower().strip()
    if source == "yelp":
        loc = record.get("location") or {}
        parts = loc.get("display_address") or []
        return ", ".join(parts).lower().strip()
    return ""


def _fuzzy_similarity(a: str, b: str) -> float:
    """Return SequenceMatcher ratio between two strings (0.0 – 1.0)."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class DIIScorer:

    def __init__(self, reachability_path: str | None = None):
        """Load pre-computed website reachability data once at init time.

        Args:
            reachability_path: Path to website_reachability.json.
                               Defaults to data/raw/website_reachability.json
                               relative to the repo root.
        """
        import logging
        self._log = logging.getLogger(__name__)

        if reachability_path is None:
            repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
            reachability_path = os.path.join(
                repo_root, "data", "raw", "website_reachability.json"
            )

        try:
            with open(reachability_path, encoding="utf-8") as f:
                raw = json.load(f)
            # Index by URL for O(1) lookup
            self._reachability: dict[str, dict] = {entry["url"]: entry for entry in raw}
        except FileNotFoundError:
            self._log.warning(
                "website_reachability.json not found at %s — "
                "all websites will score as state 1 (no website)",
                reachability_path,
            )
            self._reachability = {}

        # social_links.json — sibling of website_reachability.json in data/raw/
        social_path = os.path.join(os.path.dirname(reachability_path), "social_links.json")
        try:
            with open(social_path, encoding="utf-8") as f:
                raw_social = json.load(f)
            self._social: dict[str, dict] = {entry["url"]: entry for entry in raw_social}
        except FileNotFoundError:
            self._log.warning(
                "social_links.json not found at %s — "
                "all businesses will score 0 pts on social media dimension",
                social_path,
            )
            self._social = {}

        # website_content.json — state 4 content check results (data/processed/)
        content_path = os.path.join(
            os.path.dirname(reachability_path), "..", "processed", "website_content.json"
        )
        try:
            with open(content_path, encoding="utf-8") as f:
                raw_content = json.load(f)
            # Index by URL for O(1) lookup in score_website
            self._website_content: dict[str, bool] = {
                v["url"]: v.get("state4_qualified", False)
                for v in raw_content.values()
                if v.get("url")
            }
        except FileNotFoundError:
            self._log.warning(
                "website_content.json not found — state 4 scoring disabled",
            )
            self._website_content = {}

    # ------------------------------------------------------------------
    # Dimension 1 — Google Maps presence (25 pts)
    # ------------------------------------------------------------------

    def score_google_maps(self, business: dict) -> dict:
        """
        Score a Google Places record on Maps presence (0-25 pts).

        Points breakdown:
          10  businessStatus == OPERATIONAL
           5  businessStatus == CLOSED_TEMPORARILY  (flagged)
           5  regularOpeningHours present
           5  websiteUri present
           3  rating present and userRatingCount > 0
           2  photos present and non-empty
        """
        breakdown = {}
        status_flag = None

        # Business status (up to 10 pts)
        status = business.get("businessStatus")
        if status == "OPERATIONAL":
            breakdown["business_status"] = 10
        elif status == "CLOSED_TEMPORARILY":
            breakdown["business_status"] = 5
            status_flag = "temporarily_closed"
        else:
            # CLOSED_PERMANENTLY, missing, or unknown
            breakdown["business_status"] = 0

        # Opening hours present (5 pts)
        breakdown["opening_hours"] = 5 if business.get("regularOpeningHours") else 0

        # Website URI present (5 pts)
        breakdown["website_uri"] = 5 if business.get("websiteUri") else 0

        # Rating with at least one review (3 pts)
        has_rating = (
            business.get("rating") is not None
            and (business.get("userRatingCount") or 0) > 0
        )
        breakdown["rating"] = 3 if has_rating else 0

        # Photos present and non-empty (2 pts)
        photos = business.get("photos")
        breakdown["photos"] = 2 if photos else 0

        score = sum(breakdown.values())
        return {"score": score, "breakdown": breakdown, "status_flag": status_flag}

    # ------------------------------------------------------------------
    # Dimension 2 — Website existence & quality (25 pts)
    # ------------------------------------------------------------------

    def score_website(self, business: dict) -> dict:
        """
        Score website presence using pre-computed reachability and content data (0-25 pts).

        Four states:
          State 1 — No websiteUri in Google record              →  0 pts
          State 2 — websiteUri present but unreachable
                    (status 4xx/5xx, error, or timeout)         →  6 pts
          State 3 — websiteUri present and reachable
                    (status 200-399)                            → 16 pts
          State 4 — Reachable and contact info detected
                    (2+ of: phone, email, hours)                → 25 pts

        States 1-3 are derived from data/raw/website_reachability.json.
        State 4 is derived from data/processed/website_content.json.
        Both files are loaded once at scorer init.

        State 4 is additive only — no record can be downgraded. A URL present
        in website_content.json but not state4_qualified remains at state 3.

        If a URL is present in the Google record but absent from the reachability
        data, the business is treated as state 1 and a warning is logged.
        """
        website_url = business.get("websiteUri")

        if not website_url:
            # State 1: no website
            return {
                "score": 0,
                "breakdown": {"website_state": 1},
            }

        entry = self._reachability.get(website_url)

        if entry is None:
            self._log.warning(
                "URL not found in reachability data, treating as state 1: %s",
                website_url,
            )
            return {
                "score": 0,
                "breakdown": {"website_state": 1},
            }

        status = entry.get("status_code")
        reachable = (
            entry.get("reachable") is True
            and status is not None
            and 200 <= status <= 399
        )

        if reachable:
            # State 4: reachable and contact info detected (2+ signals)
            if self._website_content.get(website_url) is True:
                return {
                    "score": 25,
                    "breakdown": {"website_state": 4},
                }
            # State 3: reachable, no qualifying content data
            return {
                "score": 16,
                "breakdown": {"website_state": 3},
            }
        else:
            # State 2: present but unreachable
            return {
                "score": 6,
                "breakdown": {"website_state": 2},
            }

    # ------------------------------------------------------------------
    # Dimension 3 — Yelp / review platform presence (20 pts)
    # ------------------------------------------------------------------

    def score_yelp(self, business: dict) -> dict:
        """
        Score a Yelp business record on review-platform presence (0-20 pts).

        Points breakdown:
           8  Business is listed (record exists and has a name)
           7  is_claimed == True
           3  review_count > 0
           2  rating present
        """
        breakdown = {}

        # Listed on Yelp (8 pts)
        breakdown["listed"] = 8 if business.get("name") else 0

        # Claimed listing (7 pts)
        # is_claimed is only available from the Yelp details endpoint,
        # not the search endpoint used in Sprint 1.
        is_claimed = business.get("is_claimed")
        breakdown["is_claimed"] = 7 if is_claimed is True else 0

        # Has at least one review (3 pts)
        breakdown["has_reviews"] = 3 if (business.get("review_count") or 0) > 0 else 0

        # Rating present (2 pts)
        breakdown["has_rating"] = 2 if business.get("rating") is not None else 0

        score = sum(breakdown.values())
        return {"score": score, "breakdown": breakdown}

    # ------------------------------------------------------------------
    # Dimension 4 — Social media presence (15 pts)
    # ------------------------------------------------------------------

    def score_social_media(self, business: dict) -> dict:
        """
        Score social media presence using website social link detection (0-15 pts).

        Proxy methodology: detects links to social platforms in the business's
        website HTML. This is a presence signal only — frequency, follower count,
        and posting activity are not measured.

        Businesses without a reachable website score 0 regardless of actual
        social media presence. This is a known MVP limitation documented in
        KNOWN_LIMITATIONS.

        Points breakdown:
          0 pts  No websiteUri, URL not in social_links data, or 0 platforms found
          8 pts  1 platform detected
         15 pts  2+ platforms detected

        Breakdown fields:
          social_state     int   0 = no signal, 1 = one platform, 2 = two or more
          social_platforms list  platform names detected (e.g. ["facebook", "instagram"])
        """
        website_url = business.get("websiteUri")

        if not website_url:
            return {
                "score": 0,
                "breakdown": {"social_state": 0, "social_platforms": []},
            }

        entry = self._social.get(website_url)

        if entry is None:
            return {
                "score": 0,
                "breakdown": {"social_state": 0, "social_platforms": []},
            }

        count     = entry.get("platform_count", 0)
        platforms = entry.get("platforms_found", [])

        if count >= 2:
            return {
                "score": 15,
                "breakdown": {"social_state": 2, "social_platforms": platforms},
            }
        elif count == 1:
            return {
                "score": 8,
                "breakdown": {"social_state": 1, "social_platforms": platforms},
            }
        else:
            return {
                "score": 0,
                "breakdown": {"social_state": 0, "social_platforms": platforms},
            }

    # ------------------------------------------------------------------
    # Dimension 5 — Info accuracy (15 pts)
    # ------------------------------------------------------------------

    def score_accuracy(self, google_record: dict | None, yelp_record: dict | None) -> dict:
        """
        Score cross-source information accuracy (0-15 pts).

        Points breakdown:
           5  Phone number present in both sources and matching
              (non-digit characters stripped; last 10 digits compared
              to handle country-code formatting differences)
           5  Address present in both sources with >80% fuzzy similarity
              (difflib.SequenceMatcher on normalised lowercase strings)
           5  Opening hours present in both sources
              (exact match not required for MVP — presence is sufficient)

        Returns score of 0 with flag "single_source_only" if either
        record is None.
        """
        if google_record is None or yelp_record is None:
            return {
                "score": 0,
                "breakdown": {"phone": 0, "address": 0, "hours": 0},
                "flag": "single_source_only",
            }

        breakdown = {}

        # Phone match (5 pts)
        g_phone = _normalize_phone(google_record.get("nationalPhoneNumber"))
        y_phone = _normalize_phone(yelp_record.get("phone"))
        breakdown["phone"] = 5 if (g_phone and y_phone and g_phone == y_phone) else 0

        # Address fuzzy match >80% (5 pts)
        g_addr = _address_string(google_record, "google")
        y_addr = _address_string(yelp_record, "yelp")
        similarity = _fuzzy_similarity(g_addr, y_addr)
        breakdown["address"] = 5 if similarity > 0.80 else 0

        # Hours present in both (5 pts)
        g_hours = bool(google_record.get("regularOpeningHours"))
        y_hours = bool(yelp_record.get("hours"))
        breakdown["hours"] = 5 if (g_hours and y_hours) else 0

        score = sum(breakdown.values())
        return {"score": score, "breakdown": breakdown, "flag": None}

    # ------------------------------------------------------------------
    # Composite DII score
    # ------------------------------------------------------------------

    def calculate_total_dii(self, google_record: dict | None, yelp_record: dict | None) -> dict:
        """
        Compute the full Digital Inclusion Index score (0-100) for a business.

        Returns:
          total_score        int   0-100, sum of all five dimensions
          dimension_scores   dict  per-dimension score + breakdown
          business_name      str   from Google displayName.text or Yelp name
          status_flags       list  any flags raised across dimensions
          data_completeness  float fraction of dimensions with a non-zero score
        """
        # Use whichever record is available per dimension
        g = google_record or {}
        y = yelp_record or {}

        google_dim = self.score_google_maps(g)
        website_dim = self.score_website(g)
        yelp_dim = self.score_yelp(y)
        social_dim = self.score_social_media({})
        accuracy_dim = self.score_accuracy(
            google_record if google_record else None,
            yelp_record if yelp_record else None,
        )

        dimension_scores = {
            "google_maps": google_dim,
            "website": website_dim,
            "yelp": yelp_dim,
            "social_media": social_dim,
            "accuracy": accuracy_dim,
        }

        total_score = sum(d["score"] for d in dimension_scores.values())

        # Collect all non-None flags
        status_flags = [
            flag for flag in [
                google_dim.get("status_flag"),
                social_dim.get("flag"),
                accuracy_dim.get("flag"),
            ]
            if flag is not None
        ]

        # Business name: prefer Google, fall back to Yelp
        display_name = g.get("displayName") or {}
        business_name = display_name.get("text") or y.get("name") or "Unknown"

        # Data completeness: fraction of dimensions with score > 0
        scored_dims = sum(1 for d in dimension_scores.values() if d["score"] > 0)
        data_completeness = round(scored_dims / len(dimension_scores), 2)

        return {
            "business_name": business_name,
            "total_score": total_score,
            "dimension_scores": dimension_scores,
            "status_flags": status_flags,
            "data_completeness": data_completeness,
        }


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")

    google_path = os.path.join(repo_root, "data", "raw", "google_all_tracts_raw.json")
    yelp_path = os.path.join(repo_root, "data", "raw", "yelp_east_austin_raw.json")

    with open(google_path, encoding="utf-8") as f:
        google_records = json.load(f)

    with open(yelp_path, encoding="utf-8") as f:
        yelp_records = json.load(f)

    scorer = DIIScorer()
    result = scorer.calculate_total_dii(google_records[0], yelp_records[0])

    print(json.dumps(result, indent=2))
