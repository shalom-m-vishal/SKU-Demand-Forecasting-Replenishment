
import math
import pandas as pd


def _boolean_series(series):
    """Safely interpret Boolean values, including string values."""
    return (
        series.eq(True)
        | series.astype(str).str.strip().str.lower().isin(
            ["true", "1", "yes"]
        )
    )


def recommend_replenishment(data):
    # --------------------------------------------------
    # 1. PREPARE REFERENCE DATA
    # --------------------------------------------------
    sku = data["SKU"].set_index("sku_id")
    stores = data["Store"].set_index("store_id")
    suppliers = data["Supplier"].set_index("supplier_id")

    contracts_df = data["SupplierSKU"].copy()

    if contracts_df["sku_id"].duplicated().any():
        raise ValueError(
            "Multiple supplier contracts exist for a SKU. "
            "Select the preferred supplier before replenishment."
        )

    contracts = contracts_df.set_index("sku_id")
    policies = data["ReorderPolicy"].set_index(
        ["store_id", "sku_id"]
    )
    forecasts = data["Forecast"].set_index(
        ["store_id", "sku_id"]
    )

    lead_data = data["LeadTimeObservation"].copy()
    lead_data["observed_days"] = pd.to_numeric(
        lead_data["observed_days"], errors="coerce"
    )

    lead_stats = lead_data.groupby("supplier_id")[
        "observed_days"
    ].mean()

    # --------------------------------------------------
    # 2. SELECT LATEST INVENTORY PER STORE-SKU
    # --------------------------------------------------
    inventory = data["InventorySnapshot"].copy()
    inventory["snapshot_date"] = pd.to_datetime(
        inventory["snapshot_date"], errors="coerce"
    )

    inventory = inventory.dropna(subset=["snapshot_date"])

    latest = (
        inventory.sort_values("snapshot_date")
        .drop_duplicates(
            subset=["store_id", "sku_id"],
            keep="last"
        )
    )

    # --------------------------------------------------
    # 3. PREPARE STOCKOUT-AWARE DEMAND HISTORY
    # --------------------------------------------------
    sales = data["SalesHistory"].copy()
    sales["sale_date"] = pd.to_datetime(
        sales["sale_date"], errors="coerce"
    )

    sales["units_sold"] = pd.to_numeric(
        sales["units_sold"], errors="coerce"
    )

    sales["demand_for_training"] = sales["units_sold"]

    stockout = _boolean_series(sales["stockout_flag"])

    if "units_requested_est" in sales.columns:
        requested = pd.to_numeric(
            sales["units_requested_est"], errors="coerce"
        )

        usable_estimate = (
            stockout
            & requested.notna()
            & sales["units_sold"].notna()
            & (requested >= sales["units_sold"])
            & (sales["units_sold"] >= 0)
        )

        # Unknown censored demand is not assumed to equal sales.
        sales.loc[stockout, "demand_for_training"] = float("nan")

        sales.loc[
            usable_estimate, "demand_for_training"
        ] = requested.loc[usable_estimate]

    else:
        sales.loc[stockout, "demand_for_training"] = float("nan")

    sales.loc[
        sales["demand_for_training"] < 0,
        "demand_for_training"
    ] = float("nan")

    sales = sales.sort_values("sale_date")

    # --------------------------------------------------
    # 4. GENERATE RECOMMENDATIONS
    # --------------------------------------------------
    results = []

    for row in latest.itertuples(index=False):
        store_id = row.store_id
        sku_id = row.sku_id
        reasons = []

        # Keep every inventory pair visible; do not silently skip it.
        if (
            sku_id not in sku.index
            or sku_id not in contracts.index
            or store_id not in stores.index
            or (store_id, sku_id) not in policies.index
            or (store_id, sku_id) not in forecasts.index
        ):
            results.append({
                "recommendation_id": f"PO-{len(results) + 1:06d}",
                "store_id": store_id,
                "sku_id": sku_id,
                "supplier_id": None,
                "daily_demand_forecast": 0.0,
                "lead_time_days": 0.0,
                "safety_stock_units": 0,
                "reorder_point_units": 0,
                "stock_position_units": 0,
                "raw_order_units": 0,
                "pack_size": 0,
                "moq": 0,
                "recommended_order_units": 0,
                "status": "BLOCKED_MISSING_DATA",
                "reason_codes": "MISSING_REFERENCE_DATA",
                "estimated_order_cost": 0.0
            })
            continue

        product = sku.loc[sku_id]
        contract = contracts.loc[sku_id]
        policy = policies.loc[(store_id, sku_id)]
        forecast = forecasts.loc[(store_id, sku_id)]

        supplier_id = contract["supplier_id"]

        # --------------------------------------------------
        # 5. DEMAND FORECAST AND VARIABILITY
        # --------------------------------------------------
        daily = pd.to_numeric(
            pd.Series([forecast["predicted_daily_demand"]]),
            errors="coerce"
        ).iloc[0]

        if pd.isna(daily) or not math.isfinite(float(daily)):
            daily = 0.0
            reasons.append("INVALID_FORECAST")

        daily = max(0.0, float(daily))

        history = sales[
            (sales["store_id"] == store_id)
            & (sales["sku_id"] == sku_id)
        ]

        if not history.empty:
            last_date = history["sale_date"].max()
            history = history[
                history["sale_date"] >
                last_date - pd.Timedelta(days=28)
            ]

        stockout_history = _boolean_series(
            history["stockout_flag"]
        )

        if stockout_history.any():
            reasons.append("STOCKOUT_CENSORING_PRESENT")

        demand = history["demand_for_training"].dropna()

        if len(demand) > 1:
            sigma = float(demand.std())
        else:
            sigma = math.sqrt(daily)
            reasons.append("LOW_HISTORY")

        if len(demand) < 7:
            reasons.append("LOW_HISTORY")

        if not math.isfinite(sigma):
            sigma = math.sqrt(daily)
            reasons.append("VARIABILITY_FALLBACK")

        sigma = max(0.0, sigma)

        # --------------------------------------------------
        # 6. LEAD TIME AND INVENTORY POSITION
        # --------------------------------------------------
        lead_value = lead_stats.get(supplier_id, 7.0)

        if pd.isna(lead_value) or not math.isfinite(float(lead_value)):
            lead_value = 7.0
            reasons.append("LEAD_TIME_FALLBACK")

        lead_days = max(1.0, float(lead_value))

        on_hand = max(0, int(row.on_hand_units))
        reserved = max(0, int(row.reserved_units))

        stock_position = max(0, on_hand - reserved)

        # --------------------------------------------------
        # 7. SAFETY STOCK AND REORDER POINT
        # --------------------------------------------------
        z = float(policy["service_level_z"])
        review_days = int(policy["review_period_days"])

        if not math.isfinite(z) or z < 0:
            raise ValueError(
                f"Invalid service-level z-score for {store_id}/{sku_id}"
            )

        if review_days < 0:
            raise ValueError(
                f"Negative review period for {store_id}/{sku_id}"
            )

        safety = math.ceil(
            z * sigma * math.sqrt(lead_days)
        )

        reorder_point = math.ceil(
            daily * lead_days + safety
        )

        target = math.ceil(
            daily * (lead_days + review_days) + safety
        )

        raw = max(0, target - stock_position)

        # --------------------------------------------------
        # 8. SUPPLIER CONSTRAINTS
        # --------------------------------------------------
        pack_value = pd.to_numeric(
            pd.Series([contract["pack_size"]]),
            errors="coerce"
        ).iloc[0]

        moq_value = pd.to_numeric(
            pd.Series([contract["moq"]]),
            errors="coerce"
        ).iloc[0]

        cost_value = pd.to_numeric(
            pd.Series([contract["unit_cost"]]),
            errors="coerce"
        ).iloc[0]

        if (
            pd.isna(pack_value)
            or pd.isna(moq_value)
            or pd.isna(cost_value)
            or not math.isfinite(float(cost_value))
            or pack_value <= 0
            or moq_value < 0
            or cost_value < 0
        ):
            raise ValueError(
                f"Invalid supplier terms for SKU {sku_id}"
            )

        pack = int(pack_value)
        moq = int(moq_value)
        unit_cost = float(cost_value)

        if pack != pack_value or moq != moq_value:
            raise ValueError(
                f"Pack size and MOQ must be whole units for SKU {sku_id}"
            )

        # MOQ itself must also be achievable in pack multiples.
        effective_moq = (
            math.ceil(moq / pack) * pack if moq > 0 else 0
        )

        qty = 0
        status = "NO_ORDER"

        if stock_position <= reorder_point and raw > 0:
            qty = (
                math.ceil(max(raw, effective_moq) / pack) * pack
            )
            reasons.append("BELOW_REORDER_POINT")

        # --------------------------------------------------
        # 9. LIFECYCLE, SUPPLIER AND CAPACITY CHECKS
        # --------------------------------------------------
        if product["lifecycle_status"] == "DISCONTINUED":
            qty = 0
            status = "BLOCKED_DISCONTINUED"
            reasons.append("SKU_DISCONTINUED")

        elif (
            supplier_id not in suppliers.index
            or suppliers.loc[supplier_id, "status"] != "ACTIVE"
        ):
            qty = 0
            status = "BLOCKED_SUPPLIER"
            reasons.append("SUPPLIER_INACTIVE")

        elif qty > 0:
            capacity = max(
                0, int(stores.loc[store_id, "capacity_units"])
            )

            remaining = max(0, capacity - on_hand)
            max_order = (remaining // pack) * pack

            if max_order < effective_moq:
                qty = 0
                status = "BLOCKED_CAPACITY_OR_MOQ"
                reasons.append("CAPACITY_BELOW_MOQ")

            elif qty > max_order:
                qty = max_order
                status = "ORDER_PARTIAL_CAPACITY"
                reasons.append("CAPACITY_LIMITED")

            else:
                status = "ORDER"

        # --------------------------------------------------
        # 10. FINAL OUTPUT
        # --------------------------------------------------
        results.append({
            "recommendation_id": f"PO-{len(results) + 1:06d}",
            "store_id": store_id,
            "sku_id": sku_id,
            "supplier_id": supplier_id,
            "daily_demand_forecast": round(daily, 3),
            "lead_time_days": round(lead_days, 2),
            "safety_stock_units": int(safety),
            "reorder_point_units": int(reorder_point),
            "stock_position_units": int(stock_position),
            "raw_order_units": int(raw),
            "pack_size": pack,
            "moq": moq,
            "recommended_order_units": int(qty),
            "status": status,
            "reason_codes": "|".join(dict.fromkeys(reasons)),
            "estimated_order_cost": round(qty * unit_cost, 2)
        })

    return pd.DataFrame(results)
