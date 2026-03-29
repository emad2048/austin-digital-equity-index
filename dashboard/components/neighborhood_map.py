from __future__ import annotations
import os

from dotenv import load_dotenv
import plotly.graph_objects as go

load_dotenv()
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")

MAPBOX_STYLE = "mapbox://styles/mapbox/outdoors-v12"

# Optional reference box (not used by maps — both use center + zoom in mapbox dicts).
MAP_BOUNDS = dict(
    west=-97.777441,
    east=-97.626535,
    north=30.44,
    south=30.18,
)


def build_map_1() -> go.Figure:
    ea_tracts = [
        {"name": "Mueller/East 6th",   "lat": 30.2961, "lon": -97.7087, "mean_dii": 57.44},
        {"name": "East Cesar Chavez",  "lat": 30.2601, "lon": -97.7201, "mean_dii": 49.76},
        {"name": "Govalle",            "lat": 30.2641, "lon": -97.6891, "mean_dii": 48.26},
        {"name": "North Loop/Airport", "lat": 30.3121, "lon": -97.6971, "mean_dii": 48.09},
        {"name": "Johnston Terrace",   "lat": 30.2721, "lon": -97.7001, "mean_dii": 46.50},
        {"name": "MLK/Rosewood",       "lat": 30.2841, "lon": -97.7101, "mean_dii": 46.18},
        {"name": "East MLK",           "lat": 30.2761, "lon": -97.6821, "mean_dii": 42.45},
        {"name": "Montopolis",         "lat": 30.2341, "lon": -97.6891, "mean_dii": 42.07},
    ]

    lat_ea = [t["lat"] for t in ea_tracts]
    lon_ea = [t["lon"] for t in ea_tracts]
    # Black underlay (Scattermapbox has no marker.line) — reads as a border ring
    trace_ea_border = go.Scattermapbox(
        lat=lat_ea,
        lon=lon_ea,
        mode="markers",
        marker=dict(size=44, color="#000000"),
        hoverinfo="skip",
        showlegend=False,
    )
    trace_ea = go.Scattermapbox(
        lat=lat_ea,
        lon=lon_ea,
        mode="markers",
        marker=dict(
            size=40,
            color=[t["mean_dii"] for t in ea_tracts],
            colorscale="RdYlGn",
            cmin=40,
            cmax=58,
            colorbar=dict(
                orientation="h",
                title=dict(
                    text="<b>DII Score</b>",
                    font=dict(size=14, color="white"),
                    side="bottom",
                ),
                tickvals=[40, 58],
                ticktext=["Worst", "Best"],
                tickfont=dict(size=13, color="white"),
                thickness=14,
                len=0.55,
                x=0.5,
                xanchor="center",
                y=-0.02,
                yanchor="top",
            ),
        ),
        text=[t["name"] for t in ea_tracts],
        customdata=[[t["mean_dii"]] for t in ea_tracts],
        hovertemplate="<b>%{text}</b><br>DII: %{customdata[0]}/100<extra></extra>",
        showlegend=False,
    )

    fig = go.Figure(data=[trace_ea_border, trace_ea])
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=90),
        height=720,
        showlegend=False,
        mapbox=dict(
            accesstoken=MAPBOX_TOKEN,
            style=MAPBOX_STYLE,
            center=dict(lat=30.2750, lon=-97.7113),
            zoom=11.7,
            bearing=0,
            pitch=0,
        ),
    )
    return fig


def build_map_2() -> go.Figure:
    locations = [
        {"name": "Mueller/East 6th",   "lat": 30.2961, "lon": -97.7087, "business_count": 109},
        {"name": "East Cesar Chavez",  "lat": 30.2601, "lon": -97.7201, "business_count": 93},
        {"name": "Govalle",            "lat": 30.2641, "lon": -97.6891, "business_count": 86},
        {"name": "North Loop/Airport", "lat": 30.3121, "lon": -97.6971, "business_count": 102},
        {"name": "Johnston Terrace",   "lat": 30.2721, "lon": -97.7001, "business_count": 90},
        {"name": "MLK/Rosewood",       "lat": 30.2841, "lon": -97.7101, "business_count": 77},
        {"name": "East MLK",           "lat": 30.2761, "lon": -97.6821, "business_count": 74},
        {"name": "Montopolis",         "lat": 30.2341, "lon": -97.6891, "business_count": 107},
    ]

    lat_b = [l["lat"] for l in locations]
    lon_b = [l["lon"] for l in locations]
    trace_border = go.Scattermapbox(
        lat=lat_b,
        lon=lon_b,
        mode="markers",
        marker=dict(size=46, color="#000000", opacity=1.0, symbol="circle"),
        hoverinfo="skip",
        showlegend=False,
    )
    trace = go.Scattermapbox(
        lat=lat_b,
        lon=lon_b,
        mode="markers",
        marker=dict(size=42, color="#FF6600", opacity=1.0, symbol="circle"),
        text=[l["name"] for l in locations],
        customdata=[[l["business_count"]] for l in locations],
        hovertemplate="<b>%{text}</b><br>Businesses: %{customdata[0]}<extra></extra>",
        showlegend=False,
    )

    fig = go.Figure(data=[trace_border, trace])
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=720,
        showlegend=False,
        mapbox=dict(
            accesstoken=MAPBOX_TOKEN,
            style=MAPBOX_STYLE,
            center=dict(lat=30.2750, lon=-97.7113),
            zoom=11.7,
            bearing=0,
            pitch=0,
        ),
    )
    return fig
