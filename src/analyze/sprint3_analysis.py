"""
Sprint 3 Analysis — Austin Digital Equity Index
================================================
Runs seven numbered sections matching Sprint 3 objectives.
Each section is self-contained, prints a summary, and writes its own output
file to data/analysis/.

Usage:
    python src/analyze/sprint3_analysis.py

Outputs:
    data/analysis/filtered_businesses.json
    data/analysis/filtered_businesses_acs.json
    data/analysis/neighborhood_summary.json
    data/analysis/statistical_tests.json
    data/analysis/dimension_breakdown.json
    data/analysis/income_correlation.png
    data/analysis/acs_correlation.json
    data/analysis/yelp_only_distribution.json

Confirmed data facts (do not change without re-verifying):
  - ACS source file : data/raw/acs_demographics.csv  (CSV, NOT JSON)
  - ACS geoid dtype : int64  -> must cast to str before joining
  - Master geoid    : already str  (e.g. '48453000902')
  - exclusion_flag  : NaN for in-scope records (use .isna(), not == None)
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")          # headless — no display required
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MASTER   = os.path.join(BASE, "data", "processed", "master_businesses.json")
ACS_CSV  = os.path.join(BASE, "data", "raw", "acs_demographics.csv")   # confirmed filename
OUT_DIR  = os.path.join(BASE, "data", "analysis")
os.makedirs(OUT_DIR, exist_ok=True)

NEIGHBORHOODS = ["East Austin", "South Congress", "The Domain"]

DIM_COLS = [
    ("dii_google_maps_score", "Google Maps",   25),
    ("dii_website_score",     "Website",       25),
    ("dii_yelp_score",        "Yelp",          20),
    ("dii_social_score",      "Social Media",  15),
    ("dii_accuracy_score",    "Info Accuracy", 15),
]

BONFERRONI_ALPHA = 0.05 / 3   # 0.0167 — three pairwise comparisons


# ===========================================================================
# SECTION 1 — Filtered dataset
# ===========================================================================
# We restrict to businesses that have a Google Maps presence (source IN
# 'matched' or 'google_only') and are in-scope (exclusion_flag IS NULL).
# Yelp-only records score 0 on Google, Website, and Social by design, which
# would suppress neighborhood means if included. This cohort is the primary
# analytical population for Sections 3–6.
# ===========================================================================

print("\n" + "=" * 68)
print("SECTION 1 — Filtered dataset (google_present, in-scope)")
print("=" * 68)

with open(MASTER, encoding="utf-8") as f:
    raw = json.load(f)

master = pd.DataFrame(raw)

google_present = master[
    master["source"].isin(["matched", "google_only"]) &
    master["exclusion_flag"].isna()
].copy()

counts = google_present.groupby("neighborhood").size().reindex(NEIGHBORHOODS)
print(f"\n  Total google_present records : {len(google_present):,}")
for hood, n in counts.items():
    print(f"    {hood:<20} {n:,}")

out1 = os.path.join(OUT_DIR, "filtered_businesses.json")
google_present.to_json(out1, orient="records", force_ascii=False, indent=2)
print(f"\n  Saved -> {os.path.relpath(out1, BASE)}")


# ===========================================================================
# SECTION 2 — ACS join
# ===========================================================================
# Join ACS demographic data (one row per census tract) to the filtered
# business records. The join key is GEOID.
#
# IMPORTANT: ACS geoid is int64 in the CSV; master geoid is a string.
# Both sides are cast to str before merging to prevent silent null joins.
#
# Records with no ACS match are flagged acs_match=False but retained.
# ===========================================================================

print("\n" + "=" * 68)
print("SECTION 2 — ACS join")
print("=" * 68)

acs = pd.read_csv(ACS_CSV)
print(f"\n  ACS file loaded: {ACS_CSV}")
print(f"  ACS columns    : {acs.columns.tolist()}")
print(f"  ACS geoid dtype: {acs['geoid'].dtype}  (casting to str)")

# Cast both sides to string — mandatory, see file header note
acs["geoid"] = acs["geoid"].astype(str)
google_present["geoid"] = google_present["geoid"].astype(str)

acs_cols = [
    "geoid",
    "median_household_income",
    "pct_minority",
    "pct_broadband",
    "total_pop",
]

joined = google_present.merge(
    acs[acs_cols],
    on="geoid",
    how="left",
)

unmatched_mask = joined["median_household_income"].isna()
joined["acs_match"] = ~unmatched_mask

n_unmatched = unmatched_mask.sum()
print(f"\n  Matched records   : {(~unmatched_mask).sum():,}")
print(f"  Unmatched records : {n_unmatched:,}  (acs_match=False, retained)")
if n_unmatched > 0:
    unmatched_geoids = joined.loc[unmatched_mask, "geoid"].unique().tolist()
    print(f"  Unmatched GEOIDs  : {unmatched_geoids}")

out2 = os.path.join(OUT_DIR, "filtered_businesses_acs.json")
joined.to_json(out2, orient="records", force_ascii=False, indent=2)
print(f"\n  Saved -> {os.path.relpath(out2, BASE)}")


# ===========================================================================
# SECTION 3 — Neighborhood DII means + confidence intervals
# ===========================================================================
# Uses the full google_present cohort from Section 1 (not the ACS-joined
# subset) so every in-scope record contributes, even the few without ACS
# tract coverage.
#
# 95% CI uses the t-distribution (scipy.stats.sem + t.ppf) which is correct
# for finite sample sizes.
# ===========================================================================

print("\n" + "=" * 68)
print("SECTION 3 — Neighborhood DII means + 95% confidence intervals")
print("=" * 68)

def ci_95(series):
    """Return (lo, hi) 95% CI around the mean using the t-distribution."""
    n  = len(series)
    m  = series.mean()
    se = stats.sem(series)
    h  = se * stats.t.ppf(0.975, df=n - 1)
    return round(m - h, 3), round(m + h, 3)

hood_summary = []
for hood in NEIGHBORHOODS:
    s = google_present.loc[google_present["neighborhood"] == hood, "dii_total_score"]
    lo, hi = ci_95(s)
    hood_summary.append({
        "neighborhood": hood,
        "n":            int(len(s)),
        "mean_dii":     round(float(s.mean()), 3),
        "median_dii":   round(float(s.median()), 3),
        "std_dii":      round(float(s.std(ddof=1)), 3),
        "ci_95_lo":     lo,
        "ci_95_hi":     hi,
    })

print(f"\n  {'Neighborhood':<20} {'n':>5}  {'mean':>6}  {'median':>7}  {'std':>5}  {'95% CI'}")
print("  " + "-" * 62)
for r in hood_summary:
    print(f"  {r['neighborhood']:<20} {r['n']:>5}  {r['mean_dii']:>6.2f}  "
          f"{r['median_dii']:>7.2f}  {r['std_dii']:>5.2f}  "
          f"[{r['ci_95_lo']}, {r['ci_95_hi']}]")

out3 = os.path.join(OUT_DIR, "neighborhood_summary.json")
with open(out3, "w", encoding="utf-8") as f:
    json.dump(hood_summary, f, indent=2)
print(f"\n  Saved -> {os.path.relpath(out3, BASE)}")


# ===========================================================================
# SECTION 4 — Pairwise t-tests with Bonferroni correction
# ===========================================================================
# Welch's t-test (equal_var=False) is used because neighborhood groups have
# different sizes and potentially different variances. Bonferroni-corrected
# significance threshold = 0.05 / 3 comparisons = 0.0167.
# Cohen's d measures effect size independent of sample size.
# ===========================================================================

print("\n" + "=" * 68)
print("SECTION 4 — Pairwise t-tests (Bonferroni alpha = 0.0167)")
print("=" * 68)

def cohens_d(a, b):
    na, nb = len(a), len(b)
    pooled_var = ((na - 1) * np.var(a, ddof=1) + (nb - 1) * np.var(b, ddof=1)) / (na + nb - 2)
    return float((np.mean(a) - np.mean(b)) / np.sqrt(pooled_var)) if pooled_var > 0 else None

pairs = [
    ("East Austin",    "South Congress"),
    ("East Austin",    "The Domain"),
    ("South Congress", "The Domain"),
]

ttest_results = []
for a_name, b_name in pairs:
    a = google_present.loc[google_present["neighborhood"] == a_name, "dii_total_score"].values
    b = google_present.loc[google_present["neighborhood"] == b_name, "dii_total_score"].values
    t_stat, p_val = stats.ttest_ind(a, b, equal_var=False)
    d = cohens_d(a, b)
    clears = bool(p_val < BONFERRONI_ALPHA)
    ttest_results.append({
        "comparison":           f"{a_name} vs {b_name}",
        "mean_a":               round(float(np.mean(a)), 3),
        "mean_b":               round(float(np.mean(b)), 3),
        "mean_diff_a_minus_b":  round(float(np.mean(a) - np.mean(b)), 3),
        "t_stat":               round(float(t_stat), 4),
        "p_value":              round(float(p_val), 6),
        "cohens_d":             round(d, 4) if d is not None else None,
        "bonferroni_alpha":     round(BONFERRONI_ALPHA, 4),
        "clears_bonferroni":    clears,
    })

print(f"\n  {'Comparison':<38} {'diff':>6}  {'t':>7}  {'p':>9}  {'d':>7}  Sig?")
print("  " + "-" * 78)
for r in ttest_results:
    sig = "YES" if r["clears_bonferroni"] else "no"
    print(f"  {r['comparison']:<38} {r['mean_diff_a_minus_b']:>+6.2f}  "
          f"{r['t_stat']:>7.3f}  {r['p_value']:>9.6f}  "
          f"{r['cohens_d']:>7.4f}  {sig}")

out4 = os.path.join(OUT_DIR, "statistical_tests.json")
with open(out4, "w", encoding="utf-8") as f:
    json.dump(ttest_results, f, indent=2)
print(f"\n  Saved -> {os.path.relpath(out4, BASE)}")


# ===========================================================================
# SECTION 5 — Dimension decomposition
# ===========================================================================
# For each of the five DII dimensions, we calculate (a) mean raw score and
# (b) mean score as a percentage of the dimension's maximum possible value.
# Showing both units side-by-side makes it easy to see which dimensions are
# uniformly low across all neighborhoods vs. which show inter-neighborhood
# gaps.
# ===========================================================================

print("\n" + "=" * 68)
print("SECTION 5 — Dimension decomposition (mean pts | % of max)")
print("=" * 68)

dim_records = []
for col, label, max_pts in DIM_COLS:
    row = {"dimension": label, "max_pts": max_pts}
    for hood in NEIGHBORHOODS:
        vals = google_present.loc[google_present["neighborhood"] == hood, col]
        mean_raw = round(float(vals.mean()), 3)
        pct_max  = round(mean_raw / max_pts * 100, 1)
        row[hood] = {"mean_raw": mean_raw, "pct_of_max": pct_max}
    dim_records.append(row)

# Header
hood_headers = "".join(f"  {h[:14]:<22}" for h in NEIGHBORHOODS)
print(f"\n  {'Dimension':<16}  {'Max':>3}  {hood_headers}")
print("  " + "-" * (22 + 26 * len(NEIGHBORHOODS)))
for row in dim_records:
    cells = ""
    for hood in NEIGHBORHOODS:
        v = row[hood]
        cells += f"  {v['mean_raw']:>5.2f} ({v['pct_of_max']:>4.1f}%)     "
    print(f"  {row['dimension']:<16}  {row['max_pts']:>3}  {cells}")

out5 = os.path.join(OUT_DIR, "dimension_breakdown.json")
with open(out5, "w", encoding="utf-8") as f:
    json.dump(dim_records, f, indent=2)
print(f"\n  Saved -> {os.path.relpath(out5, BASE)}")


# ===========================================================================
# SECTION 6 — ACS income correlation
# ===========================================================================
# Aggregate mean DII score to the census tract level (one row per tract).
# Join to ACS median household income. Compute Pearson's r and p-value.
# Only records where acs_match=True are included so we're not correlating
# against imputed/missing income values.
#
# Scatter plot: one dot per tract, x = median income, y = mean DII,
# colored by neighborhood, labeled with neighborhood name.
# ===========================================================================

print("\n" + "=" * 68)
print("SECTION 6 — ACS income correlation (tract-level)")
print("=" * 68)

acs_matched = joined[joined["acs_match"] == True].copy()

tract_agg = (
    acs_matched
    .groupby("geoid")
    .agg(
        mean_dii              =("dii_total_score",          "mean"),
        n_businesses          =("dii_total_score",          "count"),
        median_income         =("median_household_income",  "first"),
        pct_minority          =("pct_minority",             "first"),
        pct_broadband         =("pct_broadband",            "first"),
        neighborhood          =("neighborhood",             "first"),
    )
    .reset_index()
)

n_tracts = len(tract_agg)
r_val, p_val = stats.pearsonr(
    tract_agg["median_income"],
    tract_agg["mean_dii"],
)

print(f"\n  Tracts included : {n_tracts}")
print(f"  Pearson r       : {r_val:+.4f}")
print(f"  p-value         : {p_val:.6f}")

# Scatter plot
hood_colors = {
    "East Austin":    "#E05C3A",
    "South Congress": "#4A90D9",
    "The Domain":     "#5AB26E",
}

fig, ax = plt.subplots(figsize=(8, 6))
for hood in NEIGHBORHOODS:
    sub = tract_agg[tract_agg["neighborhood"] == hood]
    ax.scatter(
        sub["median_income"] / 1000,
        sub["mean_dii"],
        color=hood_colors[hood],
        label=hood,
        s=80,
        zorder=3,
    )
    for _, row in sub.iterrows():
        ax.annotate(
            hood[:4],
            (row["median_income"] / 1000, row["mean_dii"]),
            textcoords="offset points",
            xytext=(5, 3),
            fontsize=7,
            color=hood_colors[hood],
        )

# Regression line
x = tract_agg["median_income"].values / 1000
y = tract_agg["mean_dii"].values
m, b = np.polyfit(x, y, 1)
x_line = np.linspace(x.min(), x.max(), 100)
ax.plot(x_line, m * x_line + b, color="gray", linewidth=1, linestyle="--", zorder=2)

ax.set_xlabel("Median Household Income ($000s)", fontsize=11)
ax.set_ylabel("Mean DII Score (google_present cohort)", fontsize=11)
ax.set_title(
    f"Tract-Level Income vs Mean DII Score\n"
    f"Pearson r = {r_val:+.3f}, p = {p_val:.4f}  (n = {n_tracts} tracts)",
    fontsize=12,
)
ax.legend(title="Neighborhood", fontsize=9)
ax.grid(True, alpha=0.3)
fig.tight_layout()

out6_png = os.path.join(OUT_DIR, "income_correlation.png")
fig.savefig(out6_png, dpi=150)
plt.close(fig)

corr_stats = {
    "median_household_income": {
        "pearson_r": round(float(r_val), 4),
        "p_value":   round(float(p_val), 6),
        "n_tracts":  int(n_tracts),
    },
    "tract_data": tract_agg[
        ["geoid", "neighborhood", "median_income", "mean_dii", "n_businesses",
         "pct_minority", "pct_broadband"]
    ].round(3).to_dict(orient="records"),
}

# acs_correlation.json written after Section 6b so all three correlations
# are included in a single file.
print(f"\n  Saved -> {os.path.relpath(out6_png, BASE)}")


# ===========================================================================
# SECTION 6b — ACS minority and broadband correlations (tract-level)
# ===========================================================================
# Extends Section 6 using the same tract_agg aggregation. Runs Pearson r
# between mean tract DII and (1) pct_minority and (2) pct_broadband.
# pct_minority direction: expect negative r if more-minority tracts score
# lower. pct_broadband direction: expect positive r if higher broadband
# penetration correlates with stronger digital presence.
# All three ACS correlations are written together to acs_correlation.json.
# ===========================================================================

print("\n" + "=" * 68)
print("SECTION 6b — ACS minority and broadband correlations (tract-level)")
print("=" * 68)

r_min, p_min = stats.pearsonr(tract_agg["pct_minority"],  tract_agg["mean_dii"])
r_bb,  p_bb  = stats.pearsonr(tract_agg["pct_broadband"], tract_agg["mean_dii"])

print(f"\n  {'Variable':<30}  {'r':>7}  {'p-value':>10}  {'n':>4}")
print("  " + "-" * 56)
print(f"  {'median_household_income':<30}  {r_val:>+7.4f}  {p_val:>10.6f}  {n_tracts:>4}")
print(f"  {'pct_minority':<30}  {r_min:>+7.4f}  {p_min:>10.6f}  {n_tracts:>4}")
print(f"  {'pct_broadband':<30}  {r_bb:>+7.4f}  {p_bb:>10.6f}  {n_tracts:>4}")

corr_stats["pct_minority"] = {
    "pearson_r": round(float(r_min), 4),
    "p_value":   round(float(p_min), 6),
    "n_tracts":  int(n_tracts),
}
corr_stats["pct_broadband"] = {
    "pearson_r": round(float(r_bb), 4),
    "p_value":   round(float(p_bb), 6),
    "n_tracts":  int(n_tracts),
}

out6_json = os.path.join(OUT_DIR, "acs_correlation.json")
with open(out6_json, "w", encoding="utf-8") as f:
    json.dump(corr_stats, f, indent=2)
print(f"\n  Saved -> {os.path.relpath(out6_json, BASE)}")


# ===========================================================================
# SECTION 7 — Yelp-only volume analysis
# ===========================================================================
# Platform absence (a business appearing only on Yelp, with no Google Maps
# presence) is itself a digital equity signal. This section measures how
# unevenly that absence is distributed across neighborhoods.
#
# Two cuts:
#   (a) yelp_only as % of ALL records (including excluded chains)
#   (b) yelp_only as % of in-scope records only (exclusion_flag IS NULL)
#       — this is the more meaningful equity comparison
# ===========================================================================

print("\n" + "=" * 68)
print("SECTION 7 — Yelp-only volume (platform absence by neighborhood)")
print("=" * 68)

all_records  = master.copy()
inscope      = all_records[all_records["exclusion_flag"].isna()]

def yelp_counts(df, label):
    rows = []
    for hood in NEIGHBORHOODS:
        sub      = df[df["neighborhood"] == hood]
        total    = len(sub)
        yo_count = int((sub["source"] == "yelp_only").sum())
        pct      = round(yo_count / total * 100, 1) if total else 0
        rows.append({
            "neighborhood":   hood,
            "yelp_only_count": yo_count,
            "total_records":   total,
            "pct_yelp_only":   pct,
            "cut":             label,
        })
    return rows

cut_all    = yelp_counts(all_records, "all_records")
cut_inscope= yelp_counts(inscope,     "inscope_only")

print(f"\n  Cut A — all records (including excluded chains)")
print(f"  {'Neighborhood':<20} {'yelp_only':>9}  {'total':>6}  {'%':>6}")
print("  " + "-" * 48)
for r in cut_all:
    print(f"  {r['neighborhood']:<20} {r['yelp_only_count']:>9,}  "
          f"{r['total_records']:>6,}  {r['pct_yelp_only']:>5.1f}%")

print(f"\n  Cut B — in-scope only (exclusion_flag IS NULL)")
print(f"  {'Neighborhood':<20} {'yelp_only':>9}  {'total':>6}  {'%':>6}")
print("  " + "-" * 48)
for r in cut_inscope:
    print(f"  {r['neighborhood']:<20} {r['yelp_only_count']:>9,}  "
          f"{r['total_records']:>6,}  {r['pct_yelp_only']:>5.1f}%")

out7 = os.path.join(OUT_DIR, "yelp_only_distribution.json")
with open(out7, "w", encoding="utf-8") as f:
    json.dump({"all_records": cut_all, "inscope_only": cut_inscope}, f, indent=2)
print(f"\n  Saved -> {os.path.relpath(out7, BASE)}")

# ---------------------------------------------------------------------------
print("\n" + "=" * 68)
print("Sprint 3 analysis complete.")
print(f"All outputs in: {os.path.relpath(OUT_DIR, BASE)}")
print("=" * 68 + "\n")
