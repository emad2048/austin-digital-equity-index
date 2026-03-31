import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.neighborhood_map import build_map_1, build_map_2
from components.gentrification_chart import build_gentrification_chart

_ROOT = Path(__file__).resolve().parent.parent

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="Austin Digital Equity Index")


# ── Reusable HTML components ──────────────────────────────────────────────────

def render_hero_kpi(value: str, label: str, detail: str = "") -> str:
    detail_html = f'<div class="kpi-detail">{detail}</div>' if detail else ""
    return (
        f'<div class="hero-kpi">'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-label">{label}</div>'
        f'{detail_html}'
        f'</div>'
    )


def render_section_header(title: str, subtitle: str = "") -> str:
    sub_html = f'<div class="sh-sub">{subtitle}</div>' if subtitle else ""
    return (
        f'<div class="sh">'
        f'<div class="sh-title">{title}</div>'
        f'{sub_html}'
        f'</div>'
    )


# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Base ── */
    [data-testid="stAppViewContainer"] { background-color: #F7F5F2; }
    [data-testid="stSidebar"] { background-color: #F7F5F2; }
    body, p, li, span, div { color: #2C2C2A; }

    /* ── Typography ── */
    h1 { color: #0F6E56 !important; font-size: 2.4rem !important;
         font-weight: 700 !important; letter-spacing: -0.01em; }
    h2 { color: #0F6E56 !important; font-size: 1.85rem !important;
         font-weight: 700 !important; }
    h3 { color: #0F6E56 !important; font-size: 1.45rem !important;
         font-weight: 600 !important; }
    h4 { color: #0F6E56 !important; font-size: 1.25rem !important;
         font-weight: 600 !important; }
    h5 { color: #0F6E56 !important; font-size: 1.1rem !important; }
    h6 { color: #0F6E56 !important; font-size: 1rem !important; }
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stMarkdownContainer"] h4,
    [data-testid="stMarkdownContainer"] h5,
    [data-testid="stMarkdownContainer"] h6 { color: #0F6E56 !important; }
    [data-testid="stMarkdownContainer"] p { color: #2C2C2A !important; }
    [data-testid="stMarkdownContainer"] strong { color: #2C2C2A !important; }
    label, .stRadio label, .stSelectbox label { color: #2C2C2A !important; }
    .stCaption { color: #5F5E5A !important; font-size: 0.92rem !important; }

    /* ── Hero KPI Row ── */
    .hero-kpi {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 28px 20px 24px;
        text-align: center;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        border-top: 3px solid #0F6E56;
    }
    .hero-kpi .kpi-value {
        font-size: 2.6rem;
        font-weight: 800;
        color: #0F6E56;
        line-height: 1.1;
        letter-spacing: -0.02em;
    }
    .hero-kpi .kpi-label {
        font-size: 0.88rem;
        font-weight: 600;
        color: #2C2C2A;
        margin-top: 10px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .hero-kpi .kpi-detail {
        font-size: 0.82rem;
        color: #888780;
        margin-top: 4px;
        line-height: 1.4;
    }

    /* ── Section Header ── */
    .sh {
        margin: 48px 0 20px 0;
        padding: 0;
    }
    .sh .sh-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0F6E56;
        margin: 0 0 6px 0;
        line-height: 1.3;
    }
    .sh .sh-sub {
        font-size: 1.0rem;
        color: #5F5E5A;
        font-weight: 400;
        line-height: 1.5;
        margin: 0;
    }

    /* ── Dimension Cards ── */
    .dim-card {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 18px 14px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .dim-card .dim-pts {
        font-size: 1.5rem;
        font-weight: 700;
        color: #0F6E56;
        margin: 6px 0;
    }
    .dim-card .dim-name {
        font-size: 1.0rem;
        font-weight: 600;
        color: #2C2C2A;
    }
    .dim-card .dim-desc {
        font-size: 0.85rem;
        color: #888780;
        margin-top: 4px;
    }

    /* ── Finding Cards ── */
    .finding-card {
        background: #FFFFFF;
        border-left: 4px solid #BA7517;
        border-radius: 10px;
        padding: 24px 22px;
        height: 100%;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .finding-card .finding-stat {
        font-size: 1.5rem;
        font-weight: 700;
        color: #0F6E56;
        margin-bottom: 10px;
    }
    .finding-card .finding-text {
        font-size: 0.95rem;
        color: #3D3D3B;
        line-height: 1.6;
    }

    /* ── Action Cards ── */
    .action-card {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 24px 22px;
        height: 100%;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .action-pts {
        font-size: 1.35rem;
        font-weight: 700;
        color: #0F6E56;
    }
    .action-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: #2C2C2A;
        margin-bottom: 8px;
    }
    .action-body {
        font-size: 0.88rem;
        color: #5F5E5A;
        line-height: 1.5;
    }

    /* ── Actor Cards ── */
    .actor-card {
        background: #FFFFFF;
        border-left: 3px solid #BA7517;
        border-radius: 6px;
        padding: 20px 18px;
        height: 100%;
    }
    .actor-title {
        font-size: 1.0rem;
        font-weight: 600;
        color: #2C2C2A;
        margin-bottom: 8px;
    }
    .actor-body {
        font-size: 0.88rem;
        color: #5F5E5A;
        line-height: 1.5;
    }

    /* ── Callout Box (amber accent) ── */
    .callout-box {
        background: #FFFFFF;
        border-left: 4px solid #BA7517;
        border-radius: 6px;
        padding: 18px 22px;
        font-size: 1.05rem;
        color: #2C2C2A;
        line-height: 1.6;
        margin: 8px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ── Evidence Callout (teal accent) ── */
    .evidence-callout {
        background: rgba(15, 110, 86, 0.04);
        border-left: 4px solid #0F6E56;
        border-radius: 6px;
        padding: 18px 22px;
        font-size: 0.98rem;
        color: #2C2C2A;
        line-height: 1.65;
        margin: 12px 0;
    }

    /* ── About List ── */
    .about-item {
        font-size: 1.05rem;
        color: #2C2C2A;
        line-height: 1.7;
        margin-bottom: 12px;
        padding-left: 4px;
    }
    .about-item strong {
        color: #0F6E56;
    }

    /* ── Section Divider ── */
    .section-divider {
        border: none;
        border-top: 1px solid #E0DBD4;
        margin: 44px 0 8px 0;
    }

    /* ── Stat Card (legacy) ── */
    .stat-card {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 18px 20px 14px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stat-metric { font-size: 2rem; font-weight: 700; color: #0F6E56; }
    .stat-label  { font-size: 1.05rem; color: #5F5E5A; margin: 6px 0 2px; }
    .stat-sub    { font-size: 0.9rem; color: #888780; }

    /* ── Chrome / Layout ── */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    #MainMenu * { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    [data-testid="stToolbar"] { visibility: hidden !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stStatusWidget"] { visibility: hidden !important; }
    header[data-testid="stHeader"] { display: none !important; }
    .main .block-container {
        padding-top: 0 !important;
        padding-bottom: 1rem !important;
        max-width: 1200px;
    }
    div[data-testid="stHorizontalBlock"] { width: 100% !important; }

    /* ── Branded top bar ── */
    .top-bar {
        background: #0F6E56;
        padding: 10px 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: -1rem -1rem 0 -1rem;
        width: calc(100% + 2rem);
    }
    .top-bar .tb-title {
        color: #FFFFFF;
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .top-bar .tb-desc {
        color: rgba(255,255,255,0.65);
        font-size: 0.85rem;
        font-weight: 400;
    }

    /* ── Nav tabs (st.radio styled as tab bar) ── */
    div[data-testid="stRadio"] {
        background: #EFF7F4 !important;
        padding: 10px 8px 12px 8px !important;
        border-bottom: 2px solid #0F6E56 !important;
        margin-bottom: 1.2rem !important;
    }
    div[data-testid="stRadio"] > label {
        display: none !important;
    }
    div[data-testid="stRadio"] > div {
        width: 100% !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] {
        display: flex !important;
        width: 100% !important;
        gap: 8px !important;
        flex-wrap: nowrap !important;
        justify-content: stretch !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] > label {
        flex: 1 1 0% !important;
        width: 0 !important;
        background: #FFFFFF !important;
        border: 1px solid rgba(15,110,86,0.3) !important;
        border-radius: 6px !important;
        padding: 8px 18px !important;
        text-align: center !important;
        justify-content: center !important;
        color: #0F6E56 !important;
        font-weight: 700 !important;
        font-size: 1.15rem !important;
        cursor: pointer !important;
        white-space: nowrap !important;
        min-width: 0 !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {
        background: #0F6E56 !important;
        color: #FFFFFF !important;
        border-color: #0F6E56 !important;
        font-weight: 600 !important;
    }
    div[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) p,
    div[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) span,
    div[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) div {
        color: #FFFFFF !important;
    }
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
st.markdown(
    '<div class="top-bar">'
    '<span class="tb-title">Austin Digital Equity Index</span>'
    '<span class="tb-desc">Civic Analytics Dashboard</span>'
    '</div>',
    unsafe_allow_html=True,
)
page = st.radio(
    "Navigation",
    options=["\U0001F4CB The Case", "\U0001F5FA The Map", "\U0001F4CA The Evidence", "\u26A1 Take Action"],
    horizontal=True,
    label_visibility="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — THE CASE
# ══════════════════════════════════════════════════════════════════════════════
if page == "\U0001F4CB The Case":

    # ── Hero framing ──────────────────────────────────────────────────────────
    st.markdown(
        "<div style='margin: 20px 0 6px 0;'>"
        "<div style='font-size: 1.15rem; color: #5F5E5A; line-height: 1.5;'>"
        "A data-driven assessment of digital visibility across 1,400+ small "
        "businesses in East Austin, South Congress, and the Domain."
        "</div></div>",
        unsafe_allow_html=True,
    )

    # ── Key Findings ──────────────────────────────────────────────────────────
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    findings = [
        {
            "stat": "15-point gap",
            "text": "Within East Austin alone, the spread between the most and "
                    "least digitally visible tracts exceeds the gap between "
                    "East Austin and comparison neighborhoods combined.",
        },
        {
            "stat": "Structural pattern",
            "text": "Neighborhoods with higher shares of residents who are "
                    "people of color show consistently lower digital inclusion "
                    "scores \u2014 reflecting decades of unequal access to "
                    "resources, not lack of effort.",
        },
        {
            "stat": "Website & Yelp gaps",
            "text": "East Austin businesses fall furthest behind on website "
                    "quality, Yelp presence, and information accuracy \u2014 "
                    "dimensions where free fixes can close the gap fastest.",
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

    # ── About This Project ────────────────────────────────────────────────────
    st.markdown(
        render_section_header("About This Project"),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="about-item">'
        '<strong>What it measures:</strong> Digital presence and discoverability '
        'of small businesses across five platforms — Google Maps, websites, Yelp, '
        'social media, and information accuracy.</div>'
        '<div class="about-item">'
        '<strong>Why it matters:</strong> A business without a Google listing, '
        'website, or review presence is invisible to customers searching online '
        '— and that invisibility concentrates in historically underinvested '
        'neighborhoods.</div>'
        '<div class="about-item">'
        '<strong>What this enables:</strong> Data-driven targeting of free, '
        'high-impact digital inclusion interventions to the businesses and '
        'neighborhoods that need them most.</div>',
        unsafe_allow_html=True,
    )

    # ── How We Measure ────────────────────────────────────────────────────────
    st.markdown(
        render_section_header(
            "How We Measure Digital Inclusion",
            "Each business receives a Digital Inclusion Index (DII) score "
            "from 0\u2013100 across five dimensions.",
        ),
        unsafe_allow_html=True,
    )
    dims = [
        ("Google Maps",    "25 pts", "Listed, verified, complete profile"),
        ("Website",        "25 pts", "Reachable site with contact info"),
        ("Yelp / Reviews", "20 pts", "Listed, claimed, review presence"),
        ("Social Media",   "15 pts", "Active account, recent posts"),
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
        "<p style='color:#999994; font-size:0.85rem; margin-top:14px;'>"
        "A score of 100 = fully visible and accurate across all platforms. "
        "The average East Austin business scores 47.9.</p>",
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — THE MAP
# ══════════════════════════════════════════════════════════════════════════════
elif page == "\U0001F5FA The Map":

    st.markdown(
        "<div style='font-size: 1.6rem; font-weight: 600; color: #2C2C2A; "
        "line-height: 1.4; margin: 16px 0 4px 0;'>"
        "East Austin\u2019s digital inclusion gap is geographic \u2014 following "
        "neighborhood lines drawn by decades of policy.</div>",
        unsafe_allow_html=True,
    )

    # ── Map 1: DII scores by tract ────────────────────────────────────────────
    st.markdown(
        render_section_header(
            "Digital Inclusion by Census Tract",
            "A 15-point gap separates the highest- and lowest-scoring tracts. "
            "Circle color shows DII score; hover for details.",
        ),
        unsafe_allow_html=True,
    )
    fig1 = build_map_1()
    st.plotly_chart(fig1, use_container_width=True)

    # ── Map 2: Business concentration ─────────────────────────────────────────
    st.markdown(
        render_section_header(
            "Business Concentration",
            "Pin markers show business count per tract. Hover for details.",
        ),
        unsafe_allow_html=True,
    )
    fig2 = build_map_2()
    st.plotly_chart(fig2, use_container_width=True)

    # ── Key takeaway ──────────────────────────────────────────────────────────
    st.markdown(
        '<div class="evidence-callout">'
        "Census tracts with higher minority population shares show significantly "
        "lower DII scores (r = \u22120.71, p = 0.007). Broadband access is "
        "uniformly high across all study areas \u2014 the barrier is not "
        "infrastructure, it is awareness and access to technical assistance."
        "</div>",
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — THE EVIDENCE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "\U0001F4CA The Evidence":

    # ── 1. Gentrification & Displacement ──────────────────────────────────────
    st.markdown(
        render_section_header(
            "Gentrification & Displacement",
            "Digital inclusion is lowest in East Austin tracts facing "
            "early-stage gentrification and displacement pressure. "
            "A ~15-point gap separates the highest- and lowest-performing tracts.",
        ),
        unsafe_allow_html=True,
    )
    st.plotly_chart(build_gentrification_chart(), use_container_width=True)

    # ── 2. Demographic Predictors ─────────────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown(
        render_section_header(
            "Demographic Predictors",
            "The digital inclusion gap follows neighborhood demographics "
            "\u2014 not infrastructure.",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="evidence-callout">'
        "Census tracts with higher minority population shares show "
        "significantly lower DII scores \u2014 the strongest demographic "
        "predictor in the dataset (r = \u22120.71). Broadband access shows "
        "no meaningful correlation, meaning internet infrastructure is not "
        "the barrier. The gap is driven by awareness, language access, and "
        "technical assistance."
        "</div>",
        unsafe_allow_html=True,
    )

    # ── 3. Dimension Breakdown ────────────────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown(
        render_section_header(
            "Dimension Breakdown",
            "Comparing neighborhoods, the largest scoring gaps appear in "
            "Website quality, Yelp presence, and Info Accuracy \u2014 not "
            "Google Maps, where all three areas score similarly.",
        ),
        unsafe_allow_html=True,
    )

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

    # ── 4. Neighborhood Comparison ────────────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown(
        render_section_header(
            "Neighborhood Comparison",
            "East Austin\u2019s gap is specific \u2014 the two comparison "
            "neighborhoods are statistically indistinguishable from each other.",
        ),
        unsafe_allow_html=True,
    )

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

    # ── 5. Business Explorer ──────────────────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown(
        render_section_header(
            "Business Explorer",
            "Filter by neighborhood and business category to explore "
            "the underlying data.",
        ),
        unsafe_allow_html=True,
    )

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
elif page == "\u26A1 Take Action":

    st.markdown(
        "<div style='font-size: 2.2rem; font-weight: 700; color: #0F6E56; "
        "margin: 16px 0 12px 0; line-height: 1.25;'>"
        "The gap is measurable. The fixes are free.</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="callout-box">'
        "1,737 East Austin businesses have no Google Maps presence \u2014 "
        "invisible to any customer using Maps or Search to find a local "
        "restaurant, salon, or repair shop."
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    actions = [
        {
            "title": "Claim your Yelp listing",
            "pts":   "+7 DII points",
            "body":  "Takes 15 minutes. Free. Lets you update hours, respond "
                     "to reviews, and appear in Yelp search.",
        },
        {
            "title": "Add contact info to your website",
            "pts":   "+9 DII points",
            "body":  "Phone, hours, and address on your site improves both "
                     "Website and Info Accuracy scores simultaneously.",
        },
        {
            "title": "Set up Google Business Profile",
            "pts":   "Restores Google Maps visibility",
            "body":  "Free setup. Appears in Maps and Search. The single "
                     "highest-leverage action for businesses with no Google "
                     "presence.",
        },
    ]
    for col, action in zip([c1, c2, c3], actions):
        with col:
            st.markdown(f"""
            <div class="action-card">
                <div class="action-title">{action['title']}</div>
                <div class="action-pts">{action['pts']}</div>
                <div style="height: 12px;"></div>
                <div class="action-body">{action['body']}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown(
        render_section_header("Who Should Act"),
        unsafe_allow_html=True,
    )

    a1, a2, a3 = st.columns(3)
    actors = [
        {
            "title": "City of Austin",
            "body":  "Office of Equity & Inclusion can fund digital inclusion "
                     "workshops targeting the bottom quartile of East Austin "
                     "DII scores.",
        },
        {
            "title": "Local Nonprofits",
            "body":  "AIBA and Austin Community Foundation have existing "
                     "business relationships \u2014 this data identifies "
                     "exactly which businesses need help first.",
        },
        {
            "title": "Business Owners",
            "body":  "Every action above is free, takes under an hour, and "
                     "has a measurable impact on your DII score and customer "
                     "discoverability.",
        },
    ]
    for col, actor in zip([a1, a2, a3], actors):
        with col:
            st.markdown(f"""
            <div class="actor-card">
                <div class="actor-title">{actor['title']}</div>
                <div class="actor-body">{actor['body']}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    with st.expander("Step-by-step guide for each DII dimension"):
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
