"""
recheck_403s.py — Re-check 403 Forbidden URLs using headless Chromium (Playwright).

Steps:
  1. Read data/raw/website_reachability.json
  2. Extract all entries where status_code == 403
  3. Re-check each with a real browser (realistic user-agent, 10s timeout)
  4. Print summary and prompt for confirmation before writing
  5. Update only those 403 entries in-place — total URL count must stay at 625

Usage:
  python3 src/collect/recheck_403s.py
"""

import json
import os
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT        = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
REACHABILITY_PATH = os.path.join(REPO_ROOT, 'data', 'raw', 'website_reachability.json')

# Realistic desktop user-agent (Chrome 124 on Windows)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

TIMEOUT_MS = 10_000  # 10 seconds per URL


def recheck_url(page, url: str) -> dict:
    """Navigate to url with Playwright. Return result dict."""
    try:
        response = page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
        if response is None:
            return {
                "url": url,
                "status_code": None,
                "reachable": False,
                "error": "no response",
                "recheck_method": "playwright",
            }
        status = response.status
        # Treat 2xx and 3xx final destinations as reachable;
        # 4xx/5xx as not reachable (except we'll accept anything < 400 as reachable)
        reachable = status < 400
        return {
            "url": url,
            "status_code": status,
            "reachable": reachable,
            "error": None,
            "recheck_method": "playwright",
        }
    except PlaywrightTimeout:
        return {
            "url": url,
            "status_code": None,
            "reachable": False,
            "error": "timeout",
            "recheck_method": "playwright",
        }
    except Exception as exc:
        return {
            "url": url,
            "status_code": None,
            "reachable": False,
            "error": str(exc)[:200],
            "recheck_method": "playwright",
        }


def main():
    # ── Load reachability file ─────────────────────────────────────────────────
    with open(REACHABILITY_PATH, encoding="utf-8") as f:
        data = json.load(f)

    original_count = len(data)
    assert original_count == 625, f"Expected 625 entries, got {original_count}"

    # ── Identify 403 entries (by index to allow in-place update) ──────────────
    indices_403 = [i for i, r in enumerate(data) if r.get("status_code") == 403]
    urls_403    = [data[i]["url"] for i in indices_403]

    print(f"Found {len(indices_403)} URLs with status_code 403.")
    print(f"Starting Playwright re-check (10s timeout per URL)...\n")

    # ── Run Playwright ─────────────────────────────────────────────────────────
    new_results: dict[str, dict] = {}  # url → result

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        for idx, url in enumerate(urls_403, 1):
            result = recheck_url(page, url)
            new_results[url] = result

            status_str = str(result["status_code"]) if result["status_code"] else "null"
            reach_str  = "REACHABLE" if result["reachable"] else "unreachable"
            error_str  = f"  [{result['error']}]" if result["error"] else ""
            print(f"  [{idx:>3}/{len(urls_403)}] {reach_str}  {status_str:>4}  {url}{error_str}")

        page.close()
        context.close()
        browser.close()

    # ── Tally results ──────────────────────────────────────────────────────────
    now_reachable   = sum(1 for r in new_results.values() if r["reachable"])
    still_unreach   = sum(1 for r in new_results.values() if not r["reachable"] and r["error"] not in ("timeout", "no response") and r["status_code"] is not None)
    errors_timeouts = sum(1 for r in new_results.values() if r["error"] in ("timeout", "no response") or (not r["reachable"] and r["status_code"] is None and r["error"] and r["error"] != "timeout"))

    # Simpler split: reachable / not-reachable-non-error / errors
    now_reachable_count   = sum(1 for r in new_results.values() if r["reachable"])
    errors_count          = sum(1 for r in new_results.values() if r["error"] is not None)
    still_unreach_count   = len(new_results) - now_reachable_count - errors_count

    print()
    print("403 re-check results:")
    print(f"  Previously 403, now reachable:     {now_reachable_count}  (these will score higher)")
    print(f"  Previously 403, still unreachable: {still_unreach_count}  (score unchanged)")
    print(f"  Errors / timeouts:                 {errors_count}")
    print(f"  Total re-checked:                  {len(new_results)}")
    print()

    # ── Confirm before writing ─────────────────────────────────────────────────
    answer = input("Write updated entries to data/raw/website_reachability.json? [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted — no files modified.")
        sys.exit(0)

    # ── Update in-place — only the 403 entries ─────────────────────────────────
    for i in indices_403:
        url = data[i]["url"]
        if url in new_results:
            data[i] = new_results[url]

    # ── Safety checks before writing ──────────────────────────────────────────
    assert len(data) == original_count, (
        f"HALT: entry count changed from {original_count} to {len(data)}"
    )

    with open(REACHABILITY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {REACHABILITY_PATH}  ({len(data)} total entries — count unchanged)")


if __name__ == "__main__":
    main()
