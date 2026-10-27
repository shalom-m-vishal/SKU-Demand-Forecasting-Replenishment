
import streamlit as st
import plotly.express as px
import pandas as pd

from generator import generate_data
from forecasting import forecast_all, evaluate_forecast
from replenishment import recommend_replenishment
from validation import validate_data
from database import save_to_sqlite


st.set_page_config(
    page_title="Replenishment Intelligence",
    layout="wide"
)

st.title("SKU Demand Forecasting & Replenishment")
st.caption(
    "Demand forecasting, inventory optimization, "
    "supplier constraints, and replenishment validation."
)


# ---------------- Dataset Settings ----------------
with st.sidebar:
    st.header("Dataset settings")

    seed = st.number_input(
        "Seed", value=20261022, step=1
    )
    n_skus = st.number_input(
        "SKUs", min_value=5, max_value=2000, value=20
    )
    n_stores = st.number_input(
        "Stores", min_value=1, max_value=100, value=5
    )
    days = st.number_input(
        "History days", min_value=45, max_value=365, value=90
    )

    run = st.button("Generate data", type="primary")


# ---------------- Generate Data ----------------
if "data" not in st.session_state or run:
    with st.spinner("Building data and recommendations..."):
        data = generate_data(
            int(seed),
            int(n_skus),
            int(n_stores),
            int(days)
        )

        data["Forecast"] = forecast_all(data)
        data["PurchaseRecommendation"] = (
            recommend_replenishment(data)
        )

        st.session_state["data"] = data
        st.session_state["evaluation"] = None

data = st.session_state["data"]

sales = data["SalesHistory"]
forecasts = data["Forecast"]
recs = data["PurchaseRecommendation"]


# ---------------- Summary Metrics ----------------
ordered = recs[
    pd.to_numeric(
        recs["recommended_order_units"], errors="coerce"
    ).fillna(0) > 0
].copy()

pack_violations = 0

if not ordered.empty:
    pack = pd.to_numeric(
        ordered["pack_size"], errors="coerce"
    )
    qty = pd.to_numeric(
        ordered["recommended_order_units"], errors="coerce"
    )

    valid_pack = pack.notna() & (pack > 0) & qty.notna()
    checked_qty = qty.loc[valid_pack]
    checked_pack = pack.loc[valid_pack]

    pack_violations = int(
    (
        checked_qty.mod(checked_pack).abs() > 1e-9
    ).sum()
)

total_cost = pd.to_numeric(
    recs["estimated_order_cost"], errors="coerce"
).fillna(0).sum()

st.subheader("Current run summary")

m1, m2, m3, m4 = st.columns(4)

m1.metric("Forecast combinations", len(forecasts))
m2.metric("Recommendations", len(recs))
m3.metric("Proposed purchase cost", f"₹{total_cost:,.2f}")
m4.metric("Pack-size violations", pack_violations)

with st.expander("Recommendation status breakdown"):
    st.dataframe(
        recs["status"].value_counts()
        .rename_axis("Status")
        .reset_index(name="Count"),
        width="stretch",
        hide_index=True
    )


# ---------------- Tabs ----------------
overview, forecast_tab, orders, exceptions, exports = st.tabs([
    "Overview",
    "Forecast evaluation",
    "Replenishment",
    "Exceptions",
    "Data & validation"
])


# ---------------- Overview ----------------
with overview:
    st.subheader("Dataset overview")

    a, b, c = st.columns(3)
    a.metric("SKUs", len(data["SKU"]))
    b.metric("Stores", len(data["Store"]))
    c.metric("Sales records", f"{len(sales):,}")

    # Forecast KPIs
    st.subheader("Forecast summary")

    if not forecasts.empty:
        forecast_metrics = forecasts.copy()

        forecast_metrics["predicted_daily_demand"] = pd.to_numeric(
            forecast_metrics["predicted_daily_demand"],
            errors="coerce"
        )

        forecast_metrics["predicted_horizon_demand"] = pd.to_numeric(
            forecast_metrics["predicted_horizon_demand"],
            errors="coerce"
        )

        a, b = st.columns(2)

        avg_daily = forecast_metrics[
            "predicted_daily_demand"
        ].mean()

        total_horizon = forecast_metrics[
            "predicted_horizon_demand"
        ].sum()

        a.metric(
            "Average predicted daily demand",
            f"{avg_daily:.2f}" if pd.notna(avg_daily) else "N/A"
        )

        b.metric(
            "Total predicted horizon demand",
            f"{total_horizon:,.0f}"
        )
    else:
        st.info("No forecast records are available.")

    # Safely normalize stockout flags for chart aggregation.
    chart_sales = sales.copy()

    chart_sales["sale_date"] = pd.to_datetime(
        chart_sales["sale_date"], errors="coerce"
    )

    chart_sales["units_sold"] = pd.to_numeric(
        chart_sales["units_sold"], errors="coerce"
    ).fillna(0)

    chart_sales["stockout_flag"] = (
        chart_sales["stockout_flag"]
        .fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes", "y"])
    )

    daily = chart_sales.dropna(
        subset=["sale_date"]
    ).groupby(
        "sale_date", as_index=False
    ).agg(
        units_sold=("units_sold", "sum"),
        stockouts=("stockout_flag", "sum")
    ).sort_values("sale_date")

    fig = px.line(
        daily,
        x="sale_date",
        y="units_sold",
        title="Daily observed sales",
        labels={
            "sale_date": "Date",
            "units_sold": "Units sold"
        }
    )

    st.plotly_chart(
        fig,
        width="stretch",
        config={
            "displayModeBar": True,
            "displaylogo": False
        }
    )

    a, b = st.columns(2)

    stockout_count = int(
        chart_sales["stockout_flag"].sum()
    )

    total_units = chart_sales["units_sold"].sum()

    a.metric(
        "Stockout-flagged records",
        f"{stockout_count:,}"
    )

    b.metric(
        "Total observed units sold",
        f"{total_units:,.0f}"
    )

    st.info(
        "Observed sales may underestimate true demand during stockouts. "
        "The forecasting pipeline uses valid requested-demand estimates "
        "where available."
    )


# ---------------- Forecast Evaluation ----------------
with forecast_tab:
    st.subheader("Holdout forecast evaluation")

    left, right = st.columns(2)

    with left:
        store_id = st.selectbox(
            "Store",
            data["Store"]["store_id"].tolist(),
            key="evaluation_store"
        )

    with right:
        sku_id = st.selectbox(
            "SKU",
            data["SKU"]["sku_id"].tolist(),
            key="evaluation_sku"
        )

    if st.button("Evaluate forecast", type="primary"):
        result = evaluate_forecast(
            sales,
            store_id,
            sku_id,
            holdout_days=14
        )
        st.session_state["evaluation"] = result

    result = st.session_state.get("evaluation")

    if result:
        if result["status"] == "OK":
            a, b, c = st.columns(3)

            a.metric("MAE", f"{result['mae']:.3f}")
            b.metric("RMSE", f"{result['rmse']:.3f}")
            c.metric(
                "WAPE",
                "N/A" if result["wape"] is None
                else f"{result['wape']:.1%}"
            )

            st.write(
                "Training cutoff:",
                result["training_end_date"]
            )
            st.write(
                "Test observations evaluated:",
                result["test_days_evaluated"]
            )

            st.caption(
                "MAE and RMSE are measured in units per evaluated "
                "observation. WAPE is a weighted percentage error. "
                "Only test observations with usable demand estimates "
                "are included."
            )
        else:
            st.warning(
                f"Evaluation unavailable: {result['status']}. "
                "More usable historical demand may be required."
            )
    else:
        st.write(
            "Choose a store and SKU, then select "
            "**Evaluate forecast** to calculate holdout metrics."
        )


# ---------------- Replenishment ----------------
with orders:
    st.subheader("Purchase recommendations")

    statuses = sorted(
        recs["status"].dropna().unique().tolist()
    )

    selected = st.multiselect(
        "Filter by status",
        statuses,
        default=statuses
    )

    filtered = recs[
        recs["status"].isin(selected)
    ]

    st.metric("Displayed recommendations", len(filtered))

    st.dataframe(
        filtered,
        width="stretch",
        hide_index=True,
        height=500
    )

    st.download_button(
        "Download recommendations",
        filtered.to_csv(index=False).encode("utf-8"),
        "PurchaseRecommendation.csv",
        "text/csv"
    )


# ---------------- Exceptions ----------------
with exceptions:
    st.subheader("Ground-truth issue definitions")

    st.dataframe(
        data["GroundTruth"],
        width="stretch",
        hide_index=True
    )

    st.subheader("Operational exceptions")

    blocked = recs["status"].fillna("").str.startswith("BLOCKED")

    reason_flags = recs["reason_codes"].fillna("").str.contains(
        "STOCKOUT|LOW_HISTORY",
        case=False,
        na=False
    )

    exception_rows = recs[blocked | reason_flags]

    st.metric("Exceptions found", len(exception_rows))

    if exception_rows.empty:
        st.success("No matching operational exceptions found.")
    else:
        st.dataframe(
            exception_rows,
            width="stretch",
            hide_index=True,
            height=400
        )


# ---------------- Data & Validation ----------------
with exports:
    st.subheader("Generated dataset summary")

    summary_df = pd.DataFrame([
        {
            "Dataset": name,
            "Rows": len(df),
            "Columns": len(df.columns)
        }
        for name, df in data.items()
    ])

    st.dataframe(
        summary_df,
        width="stretch",
        hide_index=True
    )

    st.subheader("Inspect a dataset")

    entity = st.selectbox(
        "Select dataset",
        list(data.keys())
    )

    entity_df = data[entity]

    st.caption(
        f"{entity}: {len(entity_df):,} rows, "
        f"{len(entity_df.columns)} columns"
    )

    st.dataframe(
        entity_df,
        width="stretch",
        hide_index=True,
        height=500
    )

    st.download_button(
        "Download entity CSV",
        entity_df.to_csv(index=False).encode("utf-8"),
        f"{entity}.csv",
        "text/csv"
    )

    st.subheader("Validation results")

    checks = validate_data(data)

    st.dataframe(
        checks,
        width="stretch",
        hide_index=True
    )

    if st.button("Save SQLite database"):
        try:
            path = save_to_sqlite(data)
            st.success(f"Saved database: {path}")
        except Exception as exc:
            st.error(f"Database save failed: {exc}")
