# Austin Digital Equity Index (ADEI)

A data research project measuring digital presence disparities among small businesses across three Austin neighborhoods: East Austin (primary), South Congress, and the Domain. Built to quantify the digital inclusion gap facing East Austin small businesses and surface evidence that can inform local policy and outreach.

**Status:** Active build. Scoring pipeline, merge logic, and dashboard complete through Sprint 4. Sprint 5 focuses on expanded dimension weighting and social media signal validation.

---

## The Problem

Small businesses without strong digital presence — Google Maps listings, functioning websites, review platform presence, accurate info — are less discoverable, less competitive, and less able to participate in the modern local economy. East Austin, a historically underserved area with ongoing displacement pressure, carries disproportionate exposure to this gap. ADEI measures it directly rather than assuming it.

## The Approach

A composite Digital Inclusion Index (DII) score from 0–100 is computed per business across five weighted dimensions:

| Dimension | Weight | What it measures |
|---|---|---|
| Google Maps presence | 25 pts | Listing existence, hours, photos, verification |
| Website quality | 25 pts | Reachability, content, mobile-readiness |
| Yelp / review presence | 20 pts | Listing existence, review count, response activity |
| Social media presence | 15 pts | Linked social accounts (via website scrape) |
| Info accuracy | 15 pts | Cross-source consistency (name, phone, address) |

Scores are then aggregated at the neighborhood and census tract level and correlated against ACS demographic data (median income, % minority-owned, displacement risk indicators) to surface where digital presence tracks with socioeconomic disadvantage.

## Data Sources

- **Google Places API** — business listings, hours, verification status
- **Yelp Fusion API** — review platform presence and metadata
- **Website scraping** (BeautifulSoup, Playwright for bot-blocked URLs) — reachability and social links
- **U.S. Census ACS** — tract-level demographic and economic indicators
- **TIGER/Line shapefiles** — tract geometry for choropleth mapping

## Architecture

```
data/raw       →  data/processed  →  data/scored   →  dashboard
(API pulls)       (merge & clean)     (DII scoring)     (Streamlit)

src/collect    →  src/process      →  src/score     →  src/analyze
```

Each stage is idempotent and independently runnable. Raw data is never mutated; processed outputs are versioned per sprint.

## Tech Stack

Python, pandas, scikit-learn, XGBoost, BeautifulSoup, Playwright, Google Places API, Yelp Fusion API, Streamlit, Plotly.

## Current Results (Sprint 4)

- **5,626 businesses** scored across the three neighborhoods
- **312 matched** across Google and Yelp; **1,086 Google-only**; **4,228 Yelp-only**
- Statistically significant DII gap identified between East Austin and comparison neighborhoods
- Intra-East-Austin tract-level variance surfaces specific areas of highest inclusion risk

## Repo Structure

```
src/collect/     API pulls, scraping, merge logic, human review pipeline
src/process/     Data cleaning and field recovery
src/score/       DII scoring engine and dimension-level scorers
src/analyze/     Statistical analysis and ACS correlation
dashboard/       Streamlit app with interactive maps and evidence views
config/          Neighborhood definitions and tract centroids
data/            Raw, processed, scored (gitignored except analysis outputs)
```

## Known Limitations

Documented in `src/score/dii_scorer.py`. Current primary limitation: social media dimension uses website-scraped link detection as a presence proxy rather than a direct activity signal.

## Running Locally

```bash
pip install -r requirements.txt
cp .env.example .env   # add Google Places + Yelp API keys
streamlit run dashboard/app.py
```

## License

MIT — see LICENSE.
