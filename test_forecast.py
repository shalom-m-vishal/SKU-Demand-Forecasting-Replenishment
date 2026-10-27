
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from generator import generate_data
from forecasting import prepare_demand

data = generate_data()
sales = prepare_demand(data["SalesHistory"])

HOLDOUT_DAYS = 14
WINDOWS = [7, 28]
all_results = []

for (store_id, sku_id), group in sales.groupby(
    ["store_id", "sku_id"]
):
    group = (
        group.dropna(subset=["sale_date"])
        .sort_values("sale_date")
        .drop_duplicates("sale_date", keep="last")
        .reset_index(drop=True)
    )

    if len(group) < HOLDOUT_DAYS + 28:
        continue

    train = group.iloc[:-HOLDOUT_DAYS]
    test = group.iloc[-HOLDOUT_DAYS:]

    test = test.dropna(subset=["demand_for_training"])
    if test.empty:
        continue

    train_end = train["sale_date"].max()

    for window in WINDOWS:
        window_start = train_end - pd.Timedelta(days=window - 1)

        # Keep the calendar window intact, including censored days.
        recent = train.loc[
            train["sale_date"].between(window_start, train_end),
            "demand_for_training"
        ]

        valid_recent = recent.dropna()
        if valid_recent.empty:
            continue

        prediction = max(0.0, float(valid_recent.mean()))

        actual = test["demand_for_training"].to_numpy(dtype=float)
        predicted = np.full(len(actual), prediction)

        all_results.append({
            "store_id": store_id,
            "sku_id": sku_id,
            "window_days": window,
            "test_observations": len(actual),
            "absolute_error": float(
                np.abs(actual - predicted).sum()
            ),
            "actual_demand": float(np.abs(actual).sum()),
            "mae": mean_absolute_error(actual, predicted),
            "rmse": np.sqrt(
                mean_squared_error(actual, predicted)
            )
        })

results = pd.DataFrame(all_results)

if results.empty:
    print("No combinations had sufficient test data.")
else:
    summary = results.groupby("window_days").agg(
        combinations=("sku_id", "count"),
        mean_mae=("mae", "mean"),
        mean_rmse=("rmse", "mean"),
        total_absolute_error=("absolute_error", "sum"),
        total_actual_demand=("actual_demand", "sum")
    )

    summary["pooled_wape_pct"] = np.where(
        summary["total_actual_demand"] > 0,
        100 * summary["total_absolute_error"]
        / summary["total_actual_demand"],
        np.nan
    )

    print("\nCALENDAR-WINDOW FORECAST COMPARISON")
    print(summary.round(3).to_string())

    valid = summary["pooled_wape_pct"].dropna()
    if not valid.empty:
        print(
            f"\nBest window by pooled WAPE: "
            f"{valid.idxmin()} days"
        )
