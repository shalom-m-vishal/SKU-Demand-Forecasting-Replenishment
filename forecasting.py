
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


WINDOW_DAYS = 28


def _boolean_series(series):
    """Convert boolean-like values safely."""
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes", "y"])
    )


def prepare_demand(sales):
    """Prepare demand estimates while accounting for stockouts."""
    result = sales.copy()

    result["sale_date"] = pd.to_datetime(
        result["sale_date"], errors="coerce"
    )
    result["units_sold"] = pd.to_numeric(
        result["units_sold"], errors="coerce"
    )

    result["demand_for_training"] = result["units_sold"]

    stockout = _boolean_series(result["stockout_flag"])

    if "units_requested_est" in result.columns:
        requested = pd.to_numeric(
            result["units_requested_est"], errors="coerce"
        )

        usable_estimate = (
            stockout
            & requested.notna()
            & result["units_sold"].notna()
            & (requested >= result["units_sold"])
        )

        result.loc[stockout, "demand_for_training"] = np.nan
        result.loc[
            usable_estimate, "demand_for_training"
        ] = requested.loc[usable_estimate]
    else:
        result.loc[stockout, "demand_for_training"] = np.nan

    result.loc[
        result["demand_for_training"] < 0,
        "demand_for_training"
    ] = np.nan

    return result


def _calendar_window_demand(history, cutoff_date):
    """Return usable demand estimates within 28 calendar days."""
    start_date = cutoff_date - pd.Timedelta(
        days=WINDOW_DAYS - 1
    )

    recent = history.loc[
        history["sale_date"].between(start_date, cutoff_date),
        "demand_for_training"
    ]

    return recent.dropna()


def forecast_all(data, horizon_days=14):
    if horizon_days < 1:
        raise ValueError("horizon_days must be at least 1.")

    sales = prepare_demand(data["SalesHistory"])

    pairs = sales[["store_id", "sku_id"]].drop_duplicates()
    results = []

    for row in pairs.itertuples(index=False):
        history = sales.loc[
            (sales["store_id"] == row.store_id)
            & (sales["sku_id"] == row.sku_id)
        ].dropna(subset=["sale_date"]).copy()

        if history.empty:
            continue

        history = history.sort_values("sale_date")
        cutoff_date = history["sale_date"].max()

        demand = _calendar_window_demand(history, cutoff_date)

        # Fallback only when the recent calendar window has
        # no usable demand estimates.
        if demand.empty:
            demand = history["demand_for_training"].dropna()

        daily = (
            float(demand.mean()) if not demand.empty else 0.0
        )
        daily = max(0.0, daily)

        forecast_date = cutoff_date + pd.Timedelta(days=1)

        results.append({
            "forecast_id": (
                f"FC-{row.store_id}-{row.sku_id}-"
                f"{cutoff_date:%Y%m%d}"
            ),
            "store_id": row.store_id,
            "sku_id": row.sku_id,
            "training_end_date": cutoff_date.strftime("%Y-%m-%d"),
            "forecast_date": forecast_date.strftime("%Y-%m-%d"),
            "horizon_days": horizon_days,
            "predicted_daily_demand": round(daily, 4),
            "predicted_horizon_demand": round(
                daily * horizon_days, 2
            ),
            "model_name": (
                "28-calendar-day stockout-aware moving average"
            )
        })

    return pd.DataFrame(results)


def evaluate_forecast(
    sales, store_id, sku_id, holdout_days=14
):
    if holdout_days < 1:
        raise ValueError("holdout_days must be at least 1.")

    prepared = prepare_demand(sales)

    history = prepared.loc[
        (prepared["store_id"] == store_id)
        & (prepared["sku_id"] == sku_id)
    ].dropna(subset=["sale_date"]).copy()

    history = (
        history.sort_values("sale_date")
        .drop_duplicates("sale_date", keep="last")
        .reset_index(drop=True)
    )

    if len(history) < holdout_days + WINDOW_DAYS:
        return {"status": "INSUFFICIENT_HISTORY"}

    # Chronological holdout: test rows are never used for training.
    train = history.iloc[:-holdout_days].copy()
    test = history.iloc[-holdout_days:].copy()

    training_end = train["sale_date"].max()
    train_demand = _calendar_window_demand(train, training_end)

    if train_demand.empty:
        return {"status": "INSUFFICIENT_TRAINING_DEMAND"}

    prediction = max(0.0, float(train_demand.mean()))

    # Exclude test dates whose demand cannot be estimated reliably.
    test = test.dropna(subset=["demand_for_training"])

    if test.empty:
        return {
            "status": "INSUFFICIENT_TEST_DEMAND",
            "training_end_date": training_end.strftime("%Y-%m-%d")
        }

    actual = test["demand_for_training"].to_numpy(dtype=float)
    predicted = np.full(len(actual), prediction)
    denominator = float(np.abs(actual).sum())

    return {
        "status": "OK",
        "training_end_date": training_end.strftime("%Y-%m-%d"),
        "test_days_evaluated": int(len(test)),
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(
            mean_squared_error(actual, predicted)
        )),
        "wape": (
            float(np.abs(actual - predicted).sum() / denominator)
            if denominator > 0 else None
        )
    }
