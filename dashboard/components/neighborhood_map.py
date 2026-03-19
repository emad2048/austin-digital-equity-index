from __future__ import annotations
import os

from dotenv import load_dotenv
import plotly.graph_objects as go

load_dotenv()
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")


def build_neighborhood_map(size_mode: str = "businesses") -> go.Figure:
    nodes = [
        {
            "name": "East Austin",
            "lat": 30.2602, "lon": -97.7205,
            "mean_dii": 47.9,
            "n_businesses": 738,
            "yelp_match": "17.5% Yelp match",
        },
        {
            "name": "South Congress",
            "lat": 30.2382, "lon": -97.7520,
            "mean_dii": 54.2,
            "n_businesses": 306,
            "yelp_match": "29.1% Yelp match",
        },
        {
            "name": "The Domain",
            "lat": 30.4007, "lon": -97.7223,
            "mean_dii": 53.0,
            "n_businesses": 217,
            "yelp_match": "28.1% Yelp match",
        },
    ]

    # --- size scaling ---
    def scale(values, lo=40, hi=90):
        mn, mx = min(values), max(values)
        return [lo + (v - mn) / (mx - mn) * (hi - lo) for v in values]

    raw = [n["n_businesses"] for n in nodes] if size_mode == "businesses" else [n["mean_dii"] for n in nodes]
    sizes = scale(raw)

    # --- Trace 1: connector lines ---
    pairs = [(0, 1), (0, 2), (1, 2)]
    llat, llon = [], []
    for a, b in pairs:
        llat += [nodes[a]["lat"], nodes[b]["lat"], None]
        llon += [nodes[a]["lon"], nodes[b]["lon"], None]

    trace_lines = go.Scattermapbox(
        lat=llat, lon=llon,
        mode="lines",
        line=dict(color="#4A4A4A", width=1.5),
        hoverinfo="skip",
        showlegend=False,
    )

    # --- Trace 2: nodes + labels (merged — separate text trace unreliable on Scattermapbox) ---
    trace_nodes = go.Scattermapbox(
        lat=[n["lat"] for n in nodes],
        lon=[n["lon"] for n in nodes],
        mode="markers+text",
        marker=dict(
            size=sizes,
            color=[n["mean_dii"] for n in nodes],
            colorscale=[[0, "#C0392B"], [0.5, "#E67E22"], [1, "#27AE60"]],
            cmin=44,
            cmax=56,
            showscale=False,
        ),
        text=[f"{n['name']} — {n['mean_dii']} DII · {n['yelp_match']}" for n in nodes],
        textfont=dict(color="#1A1A1A", size=13),
        textposition="top center",
        hoverinfo="skip",
        showlegend=False,
    )

    fig = go.Figure(data=[trace_lines, trace_nodes])
    fig.update_layout(
        paper_bgcolor="#0E1117",
        margin=dict(l=0, r=0, t=0, b=0),
        height=480,
        showlegend=False,
        mapbox=dict(
            accesstoken=MAPBOX_TOKEN,
            style="outdoors",
            center=dict(lat=30.32, lon=-97.74),
            zoom=10.5,
        ),
    )

    return fig
