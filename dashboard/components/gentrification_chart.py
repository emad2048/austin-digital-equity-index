import plotly.graph_objects as go


def build_gentrification_chart() -> go.Figure:
    tracts = [
        {"label": "East Austin",       "geoid": "48453000902", "mean_dii": 57.44, "pct_minority": 49.1, "med_income": 104349, "gentrifica": "Late",           "displacement": "Active Displacement Risk"},
        {"label": "Chestnut",          "geoid": "48453000803", "mean_dii": 49.76, "pct_minority": 43.8, "med_income": 83833,  "gentrifica": "Continued Loss", "displacement": "Chronic Displacement Risk"},
        {"label": "Govalle",           "geoid": "48453002326", "mean_dii": 48.26, "pct_minority": 61.7, "med_income": 42317,  "gentrifica": "N/A",            "displacement": "Vulnerable"},
        {"label": "Johnston Terrace",  "geoid": "48453002111", "mean_dii": 48.09, "pct_minority": 60.4, "med_income": 142905, "gentrifica": "Late",           "displacement": "Active Displacement Risk"},
        {"label": "East Cesar Chavez", "geoid": "48453002320", "mean_dii": 46.50, "pct_minority": 67.2, "med_income": 85638,  "gentrifica": "Dynamic",        "displacement": "Active Displacement Risk"},
        {"label": "Foster Heights",    "geoid": "48453000804", "mean_dii": 46.18, "pct_minority": 59.7, "med_income": 73359,  "gentrifica": "Late",           "displacement": "Active Displacement Risk"},
        {"label": "Montopolis",        "geoid": "48453002321", "mean_dii": 42.45, "pct_minority": 68.5, "med_income": 53846,  "gentrifica": "N/A",            "displacement": "Vulnerable"},
        {"label": "East MLK",          "geoid": "48453002108", "mean_dii": 42.07, "pct_minority": 73.8, "med_income": 58459,  "gentrifica": "Early: Type 1",  "displacement": "Active Displacement Risk"},
    ]

    tracts.sort(key=lambda t: t["mean_dii"], reverse=True)

    color_map = {
        "Active Displacement Risk":  "#2E86AB",
        "Chronic Displacement Risk": "#888888",
        "Vulnerable":                "#C0392B",
    }

    labels     = [t["label"]    for t in tracts]
    x_vals     = [t["mean_dii"] for t in tracts]
    colors     = [color_map.get(t["displacement"], "#2E86AB") for t in tracts]
    customdata = [
        [t["pct_minority"], t["med_income"], t["displacement"], t["gentrifica"]]
        for t in tracts
    ]

    jt_index = next(i for i, t in enumerate(tracts) if t["label"] == "Johnston Terrace")

    bar = go.Bar(
        orientation="h",
        x=x_vals,
        y=labels,
        marker_color=colors,
        customdata=customdata,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "DII Score: %{x:.1f}<br>"
            "Minority: %{customdata[0]}%<br>"
            "Median Income: $%{customdata[1]:,}<br>"
            "Displacement: %{customdata[2]}<br>"
            "<extra></extra>"
        ),
    )

    annotations = [
        dict(
            x=54.2, y=7.6,
            text="South Congress avg (54.2)",
            font=dict(color="#27AE60", size=10),
            showarrow=False,
            xanchor="left",
        ),
        dict(
            x=48.5, y=jt_index,
            text="Despite $142k median income,<br>digital gap persists",
            font=dict(color="#CCCCCC", size=10),
            xanchor="left",
            showarrow=True,
            arrowcolor="#CCCCCC",
            arrowwidth=1,
        ),
        dict(
            x=96, y=0.5,
            text="Later-stage / higher DII",
            font=dict(color="#888888", size=9),
            showarrow=False,
            xanchor="left",
        ),
        dict(
            x=96, y=3.5,
            text="Active displacement",
            font=dict(color="#888888", size=9),
            showarrow=False,
            xanchor="left",
        ),
        dict(
            x=96, y=6.5,
            text="Early-stage / lowest DII",
            font=dict(color="#888888", size=9),
            showarrow=False,
            xanchor="left",
        ),
        dict(
            x=0, y=-0.18,
            xref="paper", yref="paper",
            text=(
                "Displacement classifications from City of Austin Displacement Risk Areas 2022 (updated Oct 2024).<br>"
                "Patterns are observational and do not imply causation."
            ),
            font=dict(color="#666666", size=9),
            showarrow=False,
            xanchor="left",
        ),
    ]

    shapes = [
        go.layout.Shape(
            type="line",
            x0=54.2, x1=54.2,
            y0=-0.5, y1=7.5,
            line=dict(color="#27AE60", width=1.5, dash="dash"),
        )
    ]

    layout = go.Layout(
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="white"),
        xaxis=dict(title="Mean DII Score", range=[0, 100], showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False),
        margin=dict(l=140, r=120, t=60, b=80),
        height=420,
        showlegend=False,
        shapes=shapes,
        annotations=annotations,
    )

    return go.Figure(data=[bar], layout=layout)
