from dash import Dash, dcc, html
import plotly.express as px

from nycparking.queries.dashboard_queries import (
    summary_metrics,
    tickets_by_month,
    tickets_by_precinct,
    tickets_by_weather,
    top_violations,
)


def metric_card(label: str, value) -> html.Div:
    return html.Div(
        [
            html.Div(label, className="metric-label"),
            html.Div(f"{int(value):,}", className="metric-value"),
        ],
        className="metric-card",
    )


def create_app() -> Dash:
    app = Dash(__name__)

    metrics = summary_metrics()
    monthly = tickets_by_month()
    violations = top_violations()
    precincts = tickets_by_precinct()
    weather = tickets_by_weather()

    app.layout = html.Div(
        [
            html.H1("NYC Parking Analytics"),
            html.Div(
                [
                    metric_card("Total Tickets", metrics["total_tickets"]),
                    metric_card("Active Days", metrics["active_days"]),
                    metric_card("Violation Types", metrics["violation_types"]),
                    metric_card("Precincts", metrics["precincts"]),
                ],
                className="metrics",
            ),
            html.Div(
                [
                    dcc.Graph(
                        figure=px.line(
                            monthly,
                            x="month",
                            y="tickets",
                            title="Tickets by Month",
                            markers=True,
                        )
                    ),
                    dcc.Graph(
                        figure=px.bar(
                            violations,
                            x="violation_code",
                            y="tickets",
                            title="Top Violation Codes",
                        )
                    ),
                    dcc.Graph(
                        figure=px.bar(
                            precincts,
                            x="issuer_precinct",
                            y="tickets",
                            title="Tickets by Issuer Precinct",
                        )
                    ),
                    dcc.Graph(
                        figure=px.bar(
                            weather,
                            x="weather_condition",
                            y="tickets",
                            title="Tickets by Weather Condition",
                        )
                    ),
                ],
                className="grid",
            ),
        ],
        className="page",
    )

    app.index_string = """
    <!DOCTYPE html>
    <html>
        <head>
            {%metas%}
            <title>NYC Parking Analytics</title>
            {%favicon%}
            {%css%}
            <style>
                body {
                    margin: 0;
                    background: #f5f7fa;
                    color: #17202a;
                    font-family: Segoe UI, Arial, sans-serif;
                }
                .page {
                    padding: 24px;
                }
                h1 {
                    margin: 0 0 18px;
                    font-size: 28px;
                }
                .metrics {
                    display: grid;
                    grid-template-columns: repeat(4, minmax(160px, 1fr));
                    gap: 12px;
                    margin-bottom: 16px;
                }
                .metric-card {
                    background: white;
                    border: 1px solid #d8dee8;
                    border-radius: 8px;
                    padding: 14px 16px;
                }
                .metric-label {
                    color: #5f6b7a;
                    font-size: 13px;
                }
                .metric-value {
                    font-size: 24px;
                    font-weight: 700;
                    margin-top: 4px;
                }
                .grid {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(360px, 1fr));
                    gap: 16px;
                }
                .dash-graph {
                    background: white;
                    border: 1px solid #d8dee8;
                    border-radius: 8px;
                }
            </style>
        </head>
        <body>
            {%app_entry%}
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
            </footer>
        </body>
    </html>
    """

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
