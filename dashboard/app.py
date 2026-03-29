import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.neighborhood_map import build_map_1, build_map_2
from components.gentrification_chart import build_gentrification_chart
from streamlit_option_menu import option_menu

# Resolve data paths relative to the project root (one level up from dashboard/)
_ROOT = Path(__file__).resolve().parent.parent

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="Austin Digital Equity Index")

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #F7F5F2; }
    [data-testid="stSidebar"] { background-color: #F7F5F2; }
    body, p, li, span, div { color: #2C2C2A; }
    .stat-card {
        background: #FFFFFF;
        border: 1px solid #E0DBD4;
        border-radius: 8px;
        padding: 18px 20px 14px;
        text-align: center;
    }
    .stat-metric { font-size: 2rem; font-weight: 700; color: #0F6E56; }
    .stat-label  { font-size: 1.05rem; color: #5F5E5A; margin: 6px 0 2px; }
    .stat-sub    { font-size: 0.9rem; color: #888780; }
    .action-card {
        background: #FFFFFF;
        border: 1px solid #E0DBD4;
        border-radius: 8px;
        padding: 18px 20px;
    }
    .action-pts  { font-size: 1.4rem; font-weight: 700; color: #0F6E56; }
    .action-title{ font-size: 1.05rem; font-weight: 600; color: #2C2C2A; margin-bottom: 8px; }
    .action-body { font-size: 0.88rem; color: #5F5E5A; }
    .actor-card  {
        background: #FFFFFF;
        border-left: 3px solid #BA7517;
        border-radius: 4px;
        padding: 14px 16px;
    }
    .actor-title { font-size: 1rem; font-weight: 600; color: #2C2C2A; margin-bottom: 6px; }
    .actor-body  { font-size: 0.88rem; color: #5F5E5A; }
    .callout-box {
        background: #FFFFFF;
        border-left: 4px solid #BA7517;
        border-radius: 4px;
        padding: 16px 20px;
        font-size: 1.15rem;
        color: #2C2C2A;
        margin: 16px 0;
    }
    .transparent-box {
        background: rgba(15, 110, 86, 0.08);
        border: 1px solid rgba(15, 110, 86, 0.25);
        border-radius: 6px;
        padding: 10px 12px;
        color: #2C2C2A;
        margin: 6px 0 12px;
    }
    .dim-card {
        background: #FFFFFF;
        border: 1px solid #E0DBD4;
        border-radius: 8px;
        padding: 14px 12px;
        text-align: center;
    }
    .dim-card .dim-pts {
        font-size: 1.5rem;
        font-weight: 700;
        color: #0F6E56;
        margin: 6px 0;
    }
    .dim-card .dim-name {
        font-size: 1.05rem;
        font-weight: 600;
        color: #2C2C2A;
    }
    .dim-card .dim-desc {
        font-size: 0.9rem;
        color: #888780;
        margin-top: 4px;
    }
    .finding-card {
        background: #FFFFFF;
        border: 1px solid #E0DBD4;
        border-left: 4px solid #BA7517;
        border-radius: 8px;
        padding: 20px;
        height: 100%;
    }
    .finding-card .finding-text {
        font-size: 1.05rem;
        color: #2C2C2A;
        line-height: 1.6;
    }
    .finding-card .finding-stat {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0F6E56;
        margin-bottom: 10px;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #0F6E56 !important;
        font-size: 2.2rem !important;
    }
    [data-testid="stMarkdownContainer"] p {
        color: #2C2C2A !important;
    }
    [data-testid="stMarkdownContainer"] strong {
        color: #2C2C2A !important;
    }
    label, .stRadio label, .stSelectbox label {
        color: #2C2C2A !important;
    }
    .stCaption {
        color: #5F5E5A !important;
        font-size: 1rem !important;
    }
    .section-label {
        font-size: 1.45rem;
        font-weight: 600;
        color: #0F6E56;
        border-left: 3px solid #0F6E56;
        padding-left: 10px;
        margin: 24px 0 8px 0;
        line-height: 1.4;
    }
    .section-divider {
        border: none;
        border-top: 1px solid #E0DBD4;
        margin: 28px 0 20px 0;
    }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    footer { visibility: hidden !important; }
    footer:after {
        content: '';
        visibility: hidden;
        display: block;
        height: 0;
        clear: both;
    }
    [data-testid="stbottom"] { display: none !important; }
    .stBottom { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    .main .block-container { padding-bottom: 1rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ───────────────────────────────────────────────────────────────
DARK = dict(paper_bgcolor="#F7F5F2", plot_bgcolor="#F7F5F2",
            font=dict(color="#2C2C2A", size=14))


def _load_json(rel_path):
    path = _ROOT / rel_path
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Could not load {path}: {e}")
        return None


@st.cache_data
def load_filtered_businesses():
    raw = _load_json("data/analysis/filtered_businesses.json")
    if raw is None:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df = df.drop_duplicates(subset="google_place_id")
    return df


@st.cache_data
def load_master_businesses():
    raw = _load_json("data/processed/master_businesses.json")
    if raw is None:
        return pd.DataFrame()
    return pd.DataFrame(raw)


@st.cache_data
def load_neighborhood_summary():
    return _load_json("data/analysis/neighborhood_summary.json")


@st.cache_data
def load_statistical_tests():
    return _load_json("data/analysis/statistical_tests.json")


@st.cache_data
def load_dimension_breakdown():
    return _load_json("data/analysis/dimension_breakdown.json")


@st.cache_data
def load_acs_correlation():
    return _load_json("data/analysis/acs_correlation.json")


@st.cache_data
def load_yelp_only_distribution():
    return _load_json("data/analysis/yelp_only_distribution.json")


@st.cache_data
def load_acs_demographics():
    path = _ROOT / "data/raw/acs_demographics.csv"
    try:
        return pd.read_csv(path)
    except Exception as e:
        st.error(f"Could not load {path}: {e}")
        return pd.DataFrame()


# Eager-load at startup so cache warms before first render
df_biz        = load_filtered_businesses()
df_master     = load_master_businesses()
nbhd_summary  = load_neighborhood_summary()
stat_tests    = load_statistical_tests()
dim_breakdown = load_dimension_breakdown()
acs_corr      = load_acs_correlation()
yelp_dist     = load_yelp_only_distribution()
df_acs        = load_acs_demographics()

COLORS = {
    "East Austin":    "#0F6E56",
    "South Congress": "#BA7517",
    "The Domain":     "#4A90D9",
}

# ── Navigation ─────────────────────────────────────────────────────────────────
page = option_menu(
    menu_title="Austin Digital Equity Index",
    options=["The Case", "The Map", "The Evidence", "Take Action"],
    icons=["file-text", "map", "bar-chart", "lightning"],
    orientation="horizontal",
    default_index=0,
    styles={
        "container": {
            "background-color": "#E8F4F0",
            "padding": "8px 24px",
            "margin": "0 -1rem 1rem -1rem",
            "border-bottom": "2px solid #0F6E56",
        },
        "menu-title": {
            "color": "#0F6E56",
            "font-size": "1.4rem",
            "font-weight": "700",
            "padding-right": "24px",
            "border-right": "2px solid rgba(15,110,86,0.3)",
            "margin-right": "24px",
            "white-space": "nowrap",
        },
        "icon": {
            "color": "#BA7517",
            "font-size": "1rem",
        },
        "nav-link": {
            "color": "#2C2C2A",
            "font-size": "1.15rem",
            "font-weight": "500",
            "padding": "8px 20px",
            "border": "1px solid #E0DBD4",
            "border-radius": "6px",
            "background-color": "#FFFFFF",
        },
        "nav-link-selected": {
            "background-color": "#0F6E56",
            "color": "white",
            "border": "1px solid #0F6E56",
            "font-weight": "600",
            "font-size": "1.15rem",
        },
    },
)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — THE CASE
# ══════════════════════════════════════════════════════════════════════════════
if page == "The Case":

    # ── Section 1: Project purpose ────────────────────────────────────────────
    st.markdown(
        "<h2 style='color:#0F6E56; margin-bottom:8px;'>"
        "About This Project</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='font-size:1.45rem; font-weight:400; "
        "color:#2C2C2A; line-height:1.7;'>"
        "A business without a Google Maps listing, website, or Yelp presence "
        "is invisible to potential customers. In East Austin, that invisibility "
        "is not random. The Austin Digital Equity Index measures this gap across "
        "1,400+ small businesses in three Austin neighborhoods. "
        "The findings point toward solutions.</p>",
        unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 2: How the DII works ──────────────────────────────────────────
    st.markdown("<h3 style='color:#0F6E56;'>How we measure digital inclusion</h3>",
                unsafe_allow_html=True)
    st.markdown("Each business receives a Digital Inclusion Index (DII) score from 0–100 across five dimensions:")

    dims = [
        ("Google Maps",    "25 pts", "Listed, verified, complete profile"),
        ("Website",        "25 pts", "Reachable site with contact information"),
        ("Yelp / Reviews", "20 pts", "Listed, claimed, review presence"),
        ("Social Media",   "15 pts", "Active account with recent posts"),
        ("Info Accuracy",  "15 pts", "Hours, phone, address consistent"),
    ]
    cols = st.columns(5)
    for col, (name, pts, desc) in zip(cols, dims):
        with col:
            st.markdown(f"""
            <div class="dim-card">
                <div class="dim-name">{name}</div>
                <div class="dim-pts">{pts}</div>
                <div class="dim-desc">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(
        "<p style='color:#999999; font-size:0.88rem; margin-top:14px;'>"
        "A score of 100 means a business is fully visible and accurate across all five platforms. "
        "The average East Austin business scores 47.9."
        "</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 3: Headline findings ─────────────────────────────────────────
    st.markdown("<h3 style='color:#0F6E56;'>What we found</h3>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    findings = [
        {
            "stat": "6-point gap",
            "text": "East Austin businesses are significantly harder to find online than businesses "
                    "in comparable Austin neighborhoods — a gap that cannot be explained by chance alone.",
        },
        {
            "stat": "A structural pattern",
            "text": "In neighborhoods where more residents are people of color, businesses consistently "
                    "show lower digital inclusion scores. This reflects decades of unequal access to "
                    "resources and technical support — not a lack of effort by business owners.",
        },
        {
            "stat": "1,737 businesses",
            "text": "More than 1,700 East Austin businesses are completely invisible on Google Maps — "
                    "meaning any customer searching by phone simply cannot find them, no matter how "
                    "good the business is.",
        },
    ]
    c1, c2, c3 = st.columns(3)
    for col, f in zip([c1, c2, c3], findings):
        with col:
            st.markdown(f"""
            <div class="finding-card">
                <div class="finding-stat">{f['stat']}</div>
                <div class="finding-text">{f['text']}</div>
            </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — THE MAP
# ══════════════════════════════════════════════════════════════════════════════
elif page == "The Map":
    st.markdown(
        "<p style='font-size:2.0rem; font-weight:600; color:#2C2C2A;'>"
        "East Austin's digital inclusion gap is geographic — and it follows "
        "neighborhood lines drawn by decades of policy.</p>",
        unsafe_allow_html=True
    )

    st.markdown("#### A 15-point gap exists within East Austin — some tracts thriving, others left behind")
    st.caption("Circle color shows DII score. Hover for tract name and score.")
    fig1 = build_map_1()
    st.plotly_chart(fig1, use_container_width=True)

    st.markdown("#### Where are the businesses?")
    st.caption("Pin markers show business count per tract. Hover for details.")
    fig2 = build_map_2()
    st.plotly_chart(fig2, use_container_width=True)

    st.info(
        "Census tracts with higher minority population shares show significantly "
        "lower DII scores (r = \u22120.71, p = 0.007). Broadband access is uniformly "
        "high across all study areas — the barrier is not infrastructure, it is "
        "awareness and access to technical assistance."
    )

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — THE EVIDENCE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "The Evidence":

    # ── Section 1: Strip plot ─────────────────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>East Austin's gap is specific — the two comparison neighborhoods are statistically indistinguishable from each other.</div>", unsafe_allow_html=True)

    if not df_biz.empty:
        nbhd_data = [
            {"name": "East Austin",    "mean": 47.9, "ci_low": 46.7, "ci_high": 49.1, "color": "#0F6E56"},
            {"name": "South Congress", "mean": 54.2, "ci_low": 52.3, "ci_high": 56.1, "color": "#BA7517"},
            {"name": "The Domain",     "mean": 53.0, "ci_low": 50.5, "ci_high": 55.5, "color": "#4A90D9"},
        ]
        fig_compare = go.Figure()
        for n in nbhd_data:
            fig_compare.add_trace(go.Bar(
                x=[n["mean"]],
                y=[n["name"]],
                orientation="h",
                marker_color=n["color"],
                error_x=dict(
                    type="data",
                    symmetric=False,
                    array=[n["ci_high"] - n["mean"]],
                    arrayminus=[n["mean"] - n["ci_low"]],
                    color="#2C2C2A",
                    thickness=2,
                    width=6,
                ),
                showlegend=False,
                hovertemplate=f"{n['name']}<br>Mean DII: {n['mean']}<br>95% CI: [{n['ci_low']}, {n['ci_high']}]<extra></extra>",
            ))
        fig_compare.add_vline(
            x=54.2, line_dash="dash", line_color="#BA7517", line_width=1.5
        )
        fig_compare.update_layout(
            **DARK,
            xaxis=dict(
                title=dict(text="Mean DII Score", font=dict(color="#2C2C2A")),
                tickfont=dict(color="#2C2C2A"),
                range=[0, 70],
                showgrid=False,
                zeroline=False,
            ),
            yaxis=dict(
                tickfont=dict(color="#2C2C2A"),
                showgrid=False,
                zeroline=False,
            ),
            margin=dict(l=140, r=40, t=20, b=40),
            height=220,
            bargap=0.4,
        )
        st.plotly_chart(fig_compare, use_container_width=True)

    if stat_tests:
        with st.expander("Statistical detail"):
            rows = []
            for t in stat_tests:
                rows.append({
                    "Comparison": t["comparison"],
                    "Gap (pts)": round(t["mean_diff_a_minus_b"], 2),
                    "p-value": f"{t['p_value']:.6f}",
                    "Cohen's d": round(t["cohens_d"], 3),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 2: Dimension Breakdown ───────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>The gap is not about Google Maps — East Austin trails most on Website quality, Yelp presence, and Info Accuracy.</div>", unsafe_allow_html=True)

    if dim_breakdown:
        dims = [row["dimension"] for row in dim_breakdown]
        nbhds_order = ["East Austin", "South Congress", "The Domain"]

        fig_bar = go.Figure()

        for nbhd in nbhds_order:
            vals = [row[nbhd]["pct_of_max"] for row in dim_breakdown]
            fig_bar.add_trace(go.Bar(
                name=nbhd,
                x=dims,
                y=vals,
                marker_color=COLORS[nbhd],
                opacity=0.9,
            ))

        fig_bar.update_layout(
            **DARK,
            barmode="group",
            xaxis=dict(
                title="",
                tickfont=dict(color="#2C2C2A"),
                showgrid=False,
                zeroline=False,
            ),
            yaxis=dict(
                title=dict(text="% of Maximum Score", font=dict(color="#2C2C2A")),
                tickfont=dict(color="#2C2C2A"),
                showgrid=False,
                zeroline=False,
                range=[0, 105],
            ),
            legend=dict(
                bgcolor="#F7F5F2",
                bordercolor="#E0DBD4",
                borderwidth=1,
                font=dict(color="#2C2C2A"),
            ),
            margin=dict(l=40, r=20, t=20, b=40),
            height=380,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>Within East Austin, digital inclusion is lowest in tracts facing early-stage gentrification and displacement pressure.</div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#5F5E5A; font-size:0.9rem; margin-top:-8px;'>"
        "A ~15-point gap separates the highest- and lowest-performing tracts "
        "within East Austin alone.</p>",
        unsafe_allow_html=True
    )

    st.plotly_chart(build_gentrification_chart(), use_container_width=True)

    # ── Section 3: Demographic Context ───────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>The digital inclusion gap follows neighborhood demographics — not infrastructure.</div>", unsafe_allow_html=True)
    st.info(
        "Census tracts with higher minority population shares show significantly lower DII scores — "
        "the strongest demographic predictor in the dataset (r = \u22120.71). Broadband access shows "
        "no meaningful correlation, meaning lack of internet infrastructure is not driving the gap. "
        "The barrier is awareness, language access, and technical assistance."
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 4: Business Explorer ─────────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>Explore the underlying data — filter by neighborhood and business category.</div>", unsafe_allow_html=True)

    if not df_biz.empty:
        nbhd_options = ["All"] + sorted(df_biz["neighborhood"].dropna().unique().tolist())
        cat_options  = ["All"] + sorted(df_biz["category"].dropna().unique().tolist())

        fc1, fc2 = st.columns(2)
        with fc1:
            sel_nbhd = st.selectbox("Neighborhood", nbhd_options)
        with fc2:
            sel_cat = st.selectbox("Category", cat_options)

        view = df_biz.copy()
        if sel_nbhd != "All":
            view = view[view["neighborhood"] == sel_nbhd]
        if sel_cat != "All":
            view = view[view["category"] == sel_cat]

        display_cols = ["name", "neighborhood", "category", "source", "dii_total_score"]
        view = view[display_cols].sort_values("dii_total_score", ascending=True)
        st.dataframe(view, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — TAKE ACTION
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Take Action":
    st.title("The gap is measurable. The fixes are free.")

    st.markdown("""
    <div class="callout-box">
        1,737 East Austin businesses have no Google Maps presence — invisible to any customer
        using Maps or Search to find a local restaurant, salon, or repair shop.
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    actions = [
        {
            "title": "Claim your Yelp listing",
            "pts":   "+7 DII points",
            "body":  "Takes 15 minutes. Free. Lets you update hours, respond to reviews, "
                     "and appear in Yelp search.",
        },
        {
            "title": "Add contact info to your website",
            "pts":   "+9 DII points",
            "body":  "Phone, hours, and address on your site improves both Website and "
                     "Info Accuracy scores simultaneously.",
        },
        {
            "title": "Set up Google Business Profile",
            "pts":   "Restores Google Maps visibility",
            "body":  "Free setup. Appears in Maps and Search. The single highest-leverage "
                     "action for businesses with no Google presence.",
        },
    ]
    for col, action in zip([c1, c2, c3], actions):
        with col:
            st.markdown(f"""
            <div class="action-card">
                <div class="action-title">{action['title']}</div>
                <div class="action-pts">{action['pts']}</div>
                <br>
                <div class="action-body">{action['body']}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown("<div class='section-label'>Who should act</div>", unsafe_allow_html=True)

    a1, a2, a3 = st.columns(3)
    actors = [
        {
            "title": "City of Austin",
            "body":  "Office of Equity & Inclusion can fund digital inclusion workshops "
                     "targeting the bottom quartile of East Austin DII scores.",
        },
        {
            "title": "Local Nonprofits",
            "body":  "AIBA and Austin Community Foundation have existing business relationships "
                     "— this data identifies exactly which businesses need help first.",
        },
        {
            "title": "Business Owners",
            "body":  "Every action above is free, takes under an hour, and has a measurable "
                     "impact on your DII score and customer discoverability.",
        },
    ]
    for col, actor in zip([a1, a2, a3], actors):
        with col:
            st.markdown(f"""
            <div class="actor-card">
                <div class="actor-title">{actor['title']}</div>
                <div class="actor-body">{actor['body']}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("📋 Step-by-step guide for each DII dimension"):
        st.markdown("""
**Google Maps**
Claim or create your Google Business Profile at business.google.com — verify by postcard or phone.

**Website**
Add a page or section with your phone number, hours, and physical address.

**Yelp**
Search for your business at biz.yelp.com — claim the existing listing or create one.

**Social Media**
Create an Instagram business account — post at minimum once per month to stay active.

**Info Accuracy**
Audit your hours and phone number on Google, Yelp, and your website — they must match.
""")
