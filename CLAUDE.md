# Austin Digital Equity Index (ADEI) — Claude Code Context

## What this project is
A data research project measuring digital presence disparities among
small businesses across three Austin neighborhoods: East Austin (primary),
South Congress, and the Domain.

## Core output
A composite Digital Inclusion Index (DII) score (0–100) per business
across 5 dimensions:
- Google Maps presence (25pts)
- Website existence & quality (25pts)
- Yelp/review platform presence (20pts)
- Social media presence (15pts)
- Info accuracy (15pts)

## Tech stack
Python, Google Places API, Yelp Fusion API, BeautifulSoup,
pandas, scikit-learn, XGBoost, Streamlit

## Repo structure
data/raw → data/processed → data/scored → app (Streamlit dashboard)
src/collect → src/score → src/analyze

## Key constraints
- MVP dataset: 150–400 businesses, no manual gap-filling
- Never commit .env or data/ to Git
- Streamlit is the dashboard framework, not Tableau

## Current sprint
Sprint 1: GitHub setup ✓, folder structure ✓, API credentials (in progress),
ACS data pull, DII scoring pipeline scaffold
