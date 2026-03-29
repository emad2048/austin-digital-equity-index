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
        "Active Displacement Risk":  "#4A90D9",
        "Chronic Displacement Risk": "#BA7517",
        "Vulnerable":                "#C0392B",
    }

    jt_index = next(i for i, t in enumerate(tracts) if t["label"] == "Johnston Terrace")

    traces = []
    seen = set()
    for t in tracts:
        disp = t["displacement"]
        color = color_map.get(disp, "#4A90D9")
        show = disp not in seen
        seen.add(disp)
        traces.append(go.Bar(
            orientation="h",
            x=[t["mean_dii"]],
            y=[t["label"]],
            marker_color=color,
            name=disp,
            showlegend=show,
            legendgroup=disp,
            customdata=[[
                t["pct_minority"], t["med_income"],
                t["displacement"], t["gentrifica"]
            ]],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "DII Score: %{x:.1f}<br>"
                "Minority: %{customdata[0]}%<br>"
                "Median Income: $%{customdata[1]:,}<br>"
                "Displacement: %{customdata[2]}<br>"
                "<extra></extra>"
            ),
        ))

    annotations = [
        dict(
            x=54.2, y=7.6,
            text="South Congress avg (54.2)",
            font=dict(color="#BA7517", size=10),
            showarrow=False,
            xanchor="left",
        ),
        dict(
            x=48.5, y=jt_index,
            text="Despite $142k median income,<br>digital gap persists",
            font=dict(color="#2C2C2A", size=10),
            xanchor="left",
            showarrow=True,
            arrowcolor="#2C2C2A",
            arrowwidth=1,
        ),
        dict(
            x=96, y=0.5,
            text="<b>Later-stage</b><br>higher DII",
            font=dict(color="#5F5E5A", size=11),
            showarrow=False,
            xanchor="left",
        ),
        dict(
            x=96, y=3.5,
            text="<b>Active</b><br>displacement",
            font=dict(color="#5F5E5A", size=11),
            showarrow=False,
            xanchor="left",
        ),
        dict(
            x=96, y=6.5,
            text="<b>Early-stage</b><br>lowest DII",
            font=dict(color="#5F5E5A", size=11),
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
            font=dict(color="#888780", size=9),
            showarrow=False,
            xanchor="left",
        ),
    ]

    shapes = [
        go.layout.Shape(
            type="line",
            x0=54.2, x1=54.2,
            y0=-0.5, y1=7.5,
            line=dict(color="#BA7517", width=1.5, dash="dash"),
        )
    ]

    layout = go.Layout(
        paper_bgcolor="#F7F5F2",
        plot_bgcolor="#F7F5F2",
        font=dict(color="#2C2C2A"),
        xaxis=dict(
            title="Mean DII Score",
            titlefont=dict(color="#2C2C2A"),
            tickfont=dict(color="#2C2C2A"),
            range=[0, 100],
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            tickfont=dict(color="#2C2C2A", size=12),
        ),
        margin=dict(l=140, r=120, t=80, b=80),
        height=420,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(color="#2C2C2A", size=11),
            bgcolor="#F7F5F2",
            bordercolor="#E0DBD4",
            borderwidth=1,
        ),
        shapes=shapes,
        annotations=annotations,
    )

    return go.Figure(data=traces, layout=layout)
