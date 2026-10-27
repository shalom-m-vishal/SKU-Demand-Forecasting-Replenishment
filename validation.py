
import pandas as pd


def validate_data(data):
    checks = []

    def add_check(name, condition, detail=""):
        checks.append({
            "check": name,
            "status": "PASS" if condition else "FAIL",
            "details": detail
        })

    def get_table(name):
        return data.get(name, pd.DataFrame())

    # --------------------------------------------------
    # 1. PRIMARY KEY VALIDATION
    # --------------------------------------------------
    primary_keys = {
        "SKU": "sku_id",
        "Store": "store_id",
        "Supplier": "supplier_id",
        "SupplierSKU": "supplier_sku_id",
        "SalesHistory": "sale_id",
        "InventorySnapshot": "snapshot_id",
        "LeadTimeObservation": "lead_time_observation_id",
        "ReorderPolicy": "policy_id",
        "Forecast": "forecast_id",
        "PurchaseRecommendation": "recommendation_id",
        "GroundTruth": "case_id"
    }

    for table, key in primary_keys.items():
        df = get_table(table)

        if df.empty and table not in data:
            continue

        ok = (
            key in df.columns
            and df[key].notna().all()
            and not df[key].duplicated().any()
        )

        add_check(
            f"{table} primary key",
            ok,
            f"Rows: {len(df)}; key: {key}"
        )

    # --------------------------------------------------
    # 2. FOREIGN KEY VALIDATION
    # --------------------------------------------------
    relationships = [
        ("SupplierSKU", "sku_id", "SKU", "sku_id"),
        ("SupplierSKU", "supplier_id", "Supplier", "supplier_id"),
        ("SalesHistory", "sku_id", "SKU", "sku_id"),
        ("SalesHistory", "store_id", "Store", "store_id"),
        ("InventorySnapshot", "sku_id", "SKU", "sku_id"),
        ("InventorySnapshot", "store_id", "Store", "store_id"),
        ("LeadTimeObservation", "supplier_id", "Supplier", "supplier_id"),
        ("ReorderPolicy", "sku_id", "SKU", "sku_id"),
        ("ReorderPolicy", "store_id", "Store", "store_id"),
        ("PurchaseRecommendation", "sku_id", "SKU", "sku_id"),
        ("PurchaseRecommendation", "store_id", "Store", "store_id"),
        ("PurchaseRecommendation", "supplier_id", "Supplier", "supplier_id")
    ]

    for child, col, parent, parent_col in relationships:
        if child not in data or parent not in data:
            continue

        child_df = get_table(child)
        parent_df = get_table(parent)

        if col not in child_df.columns or parent_col not in parent_df.columns:
            add_check(
                f"{child}.{col} foreign key",
                False,
                "Required column missing"
            )
            continue

        valid_ids = set(parent_df[parent_col].dropna())
        invalid = (
            child_df[col].isna()
            | ~child_df[col].isin(valid_ids)
        )

        add_check(
            f"{child}.{col} foreign key",
            not invalid.any(),
            f"Invalid references: {int(invalid.sum())}"
        )

    # --------------------------------------------------
    # 3. BASIC NUMERIC AND INVENTORY VALIDATION
    # --------------------------------------------------
    numeric_rules = {
        "SKU": ["unit_cost", "unit_price"],
        "InventorySnapshot": [
            "on_hand_units", "reserved_units", "capacity_units"
        ],
        "LeadTimeObservation": ["observed_days"],
        "SupplierSKU": ["unit_cost", "pack_size", "moq"],
        "PurchaseRecommendation": [
            "recommended_order_units", "estimated_order_cost"
        ]
    }

    for table, columns in numeric_rules.items():
        if table not in data:
            continue

        df = get_table(table)

        for col in columns:
            if col not in df.columns:
                continue

            values = pd.to_numeric(df[col], errors="coerce")

            ok = (
                values.notna().all()
                and values.ge(0).all()
                and values.map(
                    lambda x: abs(x) != float("inf")
                ).all()
            )

            add_check(
                f"{table}.{col} non-negative numeric",
                ok,
                f"Invalid values: {int((~ok_values(values)).sum())}"
                if not ok else "All values valid"
            )

    # --------------------------------------------------
    # 4. INVENTORY RESERVATION AND CAPACITY
    # --------------------------------------------------
    inventory = get_table("InventorySnapshot")

    required_inventory = {
        "on_hand_units", "reserved_units", "capacity_units"
    }

    if required_inventory.issubset(inventory.columns):
        over_reserved = (
            inventory["reserved_units"] > inventory["on_hand_units"]
        )

        add_check(
            "Inventory reservations do not exceed on-hand stock",
            not over_reserved.any(),
            f"Invalid rows: {int(over_reserved.sum())}"
        )

        over_capacity = (
            inventory["on_hand_units"] > inventory["capacity_units"]
        )

        add_check(
            "Inventory does not exceed store capacity",
            not over_capacity.any(),
            f"Invalid rows: {int(over_capacity.sum())}"
        )

    # --------------------------------------------------
   
    # --------------------------------------------------
    # 5. STOCKOUT-AWARE DEMAND HANDLING
    # --------------------------------------------------
    sales = get_table("SalesHistory")

    required = {
        "units_sold",
        "units_requested_est",
        "stockout_flag"
    }

    if required.issubset(sales.columns):
        sold = pd.to_numeric(
            sales["units_sold"], errors="coerce"
        )
        requested = pd.to_numeric(
            sales["units_requested_est"], errors="coerce"
        )
        stockout = (
            sales["stockout_flag"]
            .fillna(False)
            .astype(bool)
        )

        censored = stockout & (requested > sold)

        # Count records with a usable estimated demand.
        usable_estimates = (
            censored
            & requested.notna()
            & sold.notna()
            & (requested >= sold)
        )

        add_check(
            "GT-001 STOCKOUT_AS_ZERO_DEMAND",
            not (censored & ~usable_estimates).any(),
            (
                f"Censored records: {int(censored.sum())}; "
                f"usable estimates: {int(usable_estimates.sum())}; "
                f"unhandled records: "
                f"{int((censored & ~usable_estimates).sum())}"
            )
        )
    # --------------------------------------------------
    # 6. PACK SIZE VIOLATION
    # --------------------------------------------------
    recs = get_table("PurchaseRecommendation")

    pack_columns = {
        "recommended_order_units", "pack_size"
    }

    if pack_columns.issubset(recs.columns):
        qty = pd.to_numeric(
            recs["recommended_order_units"], errors="coerce"
        )
        pack = pd.to_numeric(
            recs["pack_size"], errors="coerce"
        )

        invalid_pack = (
            qty.isna()
            | pack.isna()
            | (pack <= 0)
            | (qty < 0)
            | ((qty > 0) & ((qty % pack) != 0))
        )

        add_check(
            "GT-002 PACK_SIZE_VIOLATION",
            not invalid_pack.any(),
            f"Invalid recommendations: {int(invalid_pack.sum())}"
        )

    # --------------------------------------------------
    # 7. DISCONTINUED SKU ORDER
    # --------------------------------------------------
    if (
        "sku_id" in recs.columns
        and "recommended_order_units" in recs.columns
        and {"sku_id", "lifecycle_status"}.issubset(
            get_table("SKU").columns
        )
    ):
        lifecycle = get_table("SKU")[
            ["sku_id", "lifecycle_status"]
        ]

        joined = recs.merge(
            lifecycle,
            on="sku_id",
            how="left"
        )

        qty = pd.to_numeric(
            joined["recommended_order_units"],
            errors="coerce"
        )

        invalid = (
            joined["lifecycle_status"].eq("DISCONTINUED")
            & (qty > 0)
        )

        add_check(
            "GT-003 DISCONTINUED_SKU_ORDER",
            not invalid.any(),
            f"Discontinued SKU orders: {int(invalid.sum())}"
        )

    # --------------------------------------------------
    # 8. NEGATIVE LEAD TIME
    # --------------------------------------------------
    lead = get_table("LeadTimeObservation")

    if "observed_days" in lead.columns:
        lead_days = pd.to_numeric(
            lead["observed_days"], errors="coerce"
        )

        invalid = lead_days.isna() | (lead_days < 0)

        add_check(
            "GT-004 NEGATIVE_LEAD_TIME",
            not invalid.any(),
            f"Invalid lead-time records: {int(invalid.sum())}"
        )

    # --------------------------------------------------
    # 9. FUTURE DATA LEAKAGE
    # --------------------------------------------------
    # A leakage test needs an explicit forecast cutoff or
    # training cutoff to compare against data timestamps.
    forecast = get_table("Forecast")

    leakage_checked = False

    date_pairs = [
        ("training_end_date", "forecast_date"),
        ("data_cutoff_date", "forecast_date"),
        ("as_of_date", "forecast_date")
    ]

    for cutoff_col, forecast_col in date_pairs:
        if {
            cutoff_col, forecast_col
        }.issubset(forecast.columns):
            cutoff = pd.to_datetime(
                forecast[cutoff_col], errors="coerce"
            )
            forecast_date = pd.to_datetime(
                forecast[forecast_col], errors="coerce"
            )

            invalid = (
                cutoff.isna()
                | forecast_date.isna()
                | (forecast_date <= cutoff)
            )

            add_check(
                "GT-005 FUTURE_DATA_LEAKAGE",
                not invalid.any(),
                f"Invalid cutoff/forecast dates: {int(invalid.sum())}"
            )

            leakage_checked = True
            break

    if not leakage_checked:
        checks.append({
            "check": "GT-005 FUTURE_DATA_LEAKAGE",
            "status": "NOT_TESTED",
            "details": (
                "Forecast table needs an explicit cutoff date "
                "and forecast date to test temporal leakage."
            )
        })

    # --------------------------------------------------
    # 10. RECOMMENDATION COST VALIDATION
    # --------------------------------------------------
    if {
        "recommended_order_units",
        "estimated_order_cost",
        "sku_id"
    }.issubset(recs.columns) and {
        "sku_id", "unit_cost"
    }.issubset(get_table("SupplierSKU").columns):

        costs = get_table("SupplierSKU")[
            ["sku_id", "unit_cost"]
        ]

        joined = recs.merge(
            costs,
            on="sku_id",
            how="left",
            suffixes=("", "_supplier")
        )

        expected_cost = (
            pd.to_numeric(
                joined["recommended_order_units"],
                errors="coerce"
            )
            * pd.to_numeric(
                joined["unit_cost"], errors="coerce"
            )
        )

        actual_cost = pd.to_numeric(
            joined["estimated_order_cost"], errors="coerce"
        )

        mismatch = (
            expected_cost.isna()
            | actual_cost.isna()
            | ((expected_cost - actual_cost).abs() > 0.01)
        )

        add_check(
            "Purchase recommendation cost calculation",
            not mismatch.any(),
            f"Cost mismatches: {int(mismatch.sum())}"
        )

    return pd.DataFrame(checks)


def ok_values(series):
    return (
        series.notna()
        & series.ge(0)
        & series.map(lambda x: abs(x) != float("inf"))
    )
