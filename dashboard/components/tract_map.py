import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
from shapely import wkt
from shapely.geometry import mapping


def build_tract_map() -> go.Figure:
    root = Path(__file__).resolve().parent.parent.parent
    displacement_path = root / "data/raw/austin_displacement_risk_2022.csv"

    east_austin_geoids = [
        "48453000902",
        "48453000803",
        "48453002326",
        "48453002111",
        "48453002320",
        "48453000804",
        "48453002321",
        "48453002108",
    ]

    df_disp = pd.read_csv(displacement_path, dtype={"GEOID22": str})
    df_disp = df_disp[df_disp["GEOID22"].isin(east_austin_geoids)].copy()

    features = []
    for _, row in df_disp.iterrows():
        geoid = row["GEOID22"]
        geom_string = row["the_geom"]
        shape = wkt.loads(geom_string)
        geojson_geometry = mapping(shape)
        features.append(
            {
                "type": "Feature",
                "id": geoid,
                "geometry": geojson_geometry,
                "properties": {"geoid": geoid},
            }
        )

    geojson_fc = {"type": "FeatureCollection", "features": features}
    geojson_fc = json.loads(json.dumps(geojson_fc))

    tract_data = [
        {"geoid": "48453000902", "label": "East Austin",       "mean_dii": 57.44, "pct_minority": 49.1,  "med_income": 104349, "displacement": "Active Displacement Risk",  "gentrifica": "Late"},
        {"geoid": "48453000803", "label": "Chestnut",          "mean_dii": 49.76, "pct_minority": 43.8,  "med_income": 83833,  "displacement": "Chronic Displacement Risk", "gentrifica": "Continued Loss"},
        {"geoid": "48453002326", "label": "Govalle",           "mean_dii": 48.26, "pct_minority": 61.7,  "med_income": 42317,  "displacement": "Vulnerable",                "gentrifica": "N/A"},
        {"geoid": "48453002111", "label": "Johnston Terrace",  "mean_dii": 48.09, "pct_minority": 60.4,  "med_income": 142905, "displacement": "Active Displacement Risk",  "gentrifica": "Late"},
        {"geoid": "48453002320", "label": "East Cesar Chavez", "mean_dii": 46.50, "pct_minority": 67.2,  "med_income": 85638,  "displacement": "Active Displacement Risk",  "gentrifica": "Dynamic"},
        {"geoid": "48453000804", "label": "Foster Heights",    "mean_dii": 46.18, "pct_minority": 59.7,  "med_income": 73359,  "displacement": "Active Displacement Risk",  "gentrifica": "Late"},
        {"geoid": "48453002321", "label": "Montopolis",        "mean_dii": 42.45, "pct_minority": 68.5,  "med_income": 53846,  "displacement": "Vulnerable",                "gentrifica": "N/A"},
        {"geoid": "48453002108", "label": "East MLK",          "mean_dii": 42.07, "pct_minority": 73.8,  "med_income": 58459,  "displacement": "Active Displacement Risk",  "gentrifica": "Early: Type 1"},
    ]
    df_tracts = pd.DataFrame(tract_data)

    load_dotenv()
    mapbox_token = os.getenv("MAPBOX_TOKEN", "")

    fig = go.Figure(
        go.Choroplethmapbox(
            geojson=geojson_fc,
            locations=df_tracts["geoid"],
            z=df_tracts["mean_dii"],
            colorscale=[[0, "#C0392B"], [0.5, "#E67E22"], [1, "#27AE60"]],
            zmin=40,
            zmax=60,
            marker_opacity=0.7,
            marker_line_width=1,
            marker_line_color="white",
            colorbar=dict(
                title=dict(text="DII Score", font=dict(color="white")),
                thickness=12,
                len=0.5,
                bgcolor="rgba(0,0,0,0)",
                tickfont=dict(color="white"),
            ),
            customdata=df_tracts[
                ["label", "pct_minority", "med_income", "displacement", "gentrifica"]
            ].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "DII Score: %{z:.1f}<br>"
                "Minority: %{customdata[1]}%<br>"
                "Median Income: $%{customdata[2]:,}<br>"
                "Displacement: %{customdata[3]}<br>"
                "Gentrification: %{customdata[4]}<br>"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        mapbox=dict(
            accesstoken=mapbox_token,
            style="outdoors",
            center=dict(lat=30.27, lon=-97.71),
            zoom=11.5,
        ),
        paper_bgcolor="#0E1117",
        margin=dict(l=0, r=0, t=0, b=0),
        height=480,
    )

    return fig
