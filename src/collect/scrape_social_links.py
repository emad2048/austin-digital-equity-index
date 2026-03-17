"""
Social media link scraper.

For each reachable URL in data/raw/website_reachability.json, fetches the
page HTML and searches for links to known social media platforms.

Output: data/raw/social_links.json
  [
    {
      "url": "https://example.com/",
      "platforms_found": ["facebook", "instagram"],
      "platform_count": 2
    },
    ...
  ]

Only URLs where reachable == true are fetched. Unreachable URLs are written
with platforms_found: [] and platform_count: 0.
"""

import json
import os
import time

import requests
from bs4 import BeautifulSoup

# twitter.com and x.com are treated as a single platform (twitter_x).
PLATFORMS = {
    "facebook":  ["facebook.com"],
    "instagram": ["instagram.com"],
    "tiktok":    ["tiktok.com"],
    "twitter_x": ["twitter.com", "x.com"],
}

REPO_ROOT    = os.path.join(os.path.dirname(__file__), "..", "..")
INPUT_PATH   = os.path.join(REPO_ROOT, "data", "raw", "website_reachability.json")
OUTPUT_PATH  = os.path.join(REPO_ROOT, "data", "raw", "social_links.json")
SLEEP_SECS   = 0.3
TIMEOUT_SECS = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ADEI-research-bot/1.0; "
        "+https://github.com/your-org/austin-digital-equity-index)"
    )
}


def detect_platforms(html: str) -> list[str]:
    """Return sorted list of platform names whose domains appear in any <a href>."""
    soup = BeautifulSoup(html, "html.parser")
    found = set()
    for tag in soup.find_all("a", href=True):
        href = tag["href"].lower()
        for name, domains in PLATFORMS.items():
            if any(domain in href for domain in domains):
                found.add(name)
    return sorted(found)


def scrape(reachability: list[dict]) -> list[dict]:
    results = []
    reachable   = [e for e in reachability if e.get("reachable") is True]
    unreachable = [e for e in reachability if e.get("reachable") is not True]

    print(f"URLs to fetch : {len(reachable)}  |  skipped (unreachable): {len(unreachable)}")

    for entry in unreachable:
        results.append({
            "url": entry["url"],
            "platforms_found": [],
            "platform_count": 0,
        })

    for i, entry in enumerate(reachable, 1):
        url = entry["url"]
        try:
            resp = requests.get(url, timeout=TIMEOUT_SECS, headers=HEADERS, allow_redirects=True)
            platforms = detect_platforms(resp.text)
        except requests.RequestException:
            platforms = []

        results.append({
            "url": url,
            "platforms_found": platforms,
            "platform_count": len(platforms),
        })

        if i % 50 == 0:
            print(f"  {i}/{len(reachable)} fetched...")

        time.sleep(SLEEP_SECS)

    return results


def print_summary(results: list[dict]) -> None:
    total    = len(results)
    zero     = sum(1 for r in results if r["platform_count"] == 0)
    one      = sum(1 for r in results if r["platform_count"] == 1)
    two_plus = sum(1 for r in results if r["platform_count"] >= 2)

    platform_counts: dict[str, int] = {}
    for r in results:
        for p in r["platforms_found"]:
            platform_counts[p] = platform_counts.get(p, 0) + 1

    print(f"\n=== Social Link Scrape Summary (n={total}) ===")
    print(f"  0 platforms : {zero:>4}  ({zero/total*100:.1f}%)")
    print(f"  1 platform  : {one:>4}  ({one/total*100:.1f}%)")
    print(f"  2+ platforms: {two_plus:>4}  ({two_plus/total*100:.1f}%)")
    if platform_counts:
        print("\n  Platform breakdown:")
        for name, count in sorted(platform_counts.items(), key=lambda x: -x[1]):
            print(f"    {name:<12} {count}")


if __name__ == "__main__":
    with open(INPUT_PATH, encoding="utf-8") as f:
        reachability = json.load(f)

    results = scrape(reachability)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved -> {OUTPUT_PATH}")
    print_summary(results)
