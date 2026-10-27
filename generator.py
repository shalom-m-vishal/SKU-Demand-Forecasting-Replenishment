import numpy as np
import pandas as pd


def generate_data(
    seed=20261022,
    n_skus=20,
    n_stores=5,
    days=90
):
    rng = np.random.default_rng(seed)

    dates = pd.date_range(
        end="2026-01-31",
        periods=days
    )

    # ---------------- SKU ----------------
    sku = pd.DataFrame({
        "sku_id": [
            f"SKU-{i+1:06d}" for i in range(n_skus)
        ],
        "unit_cost": np.round(
            rng.uniform(10, 100, n_skus), 2
        ),
        "lifecycle_status": rng.choice(
            ["ACTIVE", "ACTIVE", "LAUNCH", "DISCONTINUED"],
            n_skus
        )
    })

    sku["unit_price"] = (
        sku["unit_cost"] * 1.5
    ).round(2)

    # ---------------- Store ----------------
    stores = pd.DataFrame({
        "store_id": [
            f"STORE-{i+1:06d}" for i in range(n_stores)
        ],
        "capacity_units": rng.integers(
            500, 3000, n_stores
        )
    })

    # ---------------- Supplier ----------------
    n_suppliers = max(3, min(n_skus, 20))

    suppliers = pd.DataFrame({
        "supplier_id": [
            f"SUPPLIER-{i+1:06d}"
            for i in range(n_suppliers)
        ],
        "status": "ACTIVE"
    })

    # ---------------- SupplierSKU ----------------
    supplier_sku = pd.DataFrame({
        "supplier_sku_id": [
            f"SS-{i+1:06d}" for i in range(n_skus)
        ],
        "sku_id": sku["sku_id"],
        "supplier_id": [
            suppliers.iloc[i % n_suppliers]["supplier_id"]
            for i in range(n_skus)
        ],
        "pack_size": rng.choice(
            [1, 2, 4, 6, 12], n_skus
        ),
        "moq": rng.choice(
            [1, 4, 6, 12, 24], n_skus
        )
    })

    supplier_sku["moq"] = [
        int(np.ceil(moq / pack) * pack)
        for moq, pack in zip(
            supplier_sku["moq"],
            supplier_sku["pack_size"]
        )
    ]

    # FIX: Include costs in SupplierSKU
    supplier_sku = supplier_sku.merge(
        sku[["sku_id", "unit_cost", "unit_price"]],
        on="sku_id",
        how="left",
        validate="many_to_one"
    )

    # ---------------- Sales History ----------------
    matrix = pd.MultiIndex.from_product(
        [
            stores["store_id"],
            sku["sku_id"],
            dates
        ],
        names=["store_id", "sku_id", "sale_date"]
    ).to_frame(index=False)

    n = len(matrix)

    pair_base = matrix[
        ["store_id", "sku_id"]
    ].drop_duplicates()

    pair_base["base_demand"] = rng.uniform(
        0.5, 8, len(pair_base)
    )

    matrix = matrix.merge(
        pair_base,
        on=["store_id", "sku_id"],
        validate="many_to_one"
    )

    seasonal = (
        1 + 0.2 * np.sin(
            2 * np.pi
            * matrix["sale_date"].dt.dayofyear / 365.25
        )
    )

    weekend = np.where(
        matrix["sale_date"].dt.dayofweek >= 5,
        1.15, 1.0
    )

    matrix["promotion_flag"] = (
        rng.random(n) < 0.08
    )

    promotion = np.where(
        matrix["promotion_flag"], 1.5, 1.0
    )

    intermittent = rng.random(n) < 0.2

    demand = (
        matrix["base_demand"]
        * seasonal
        * weekend
        * promotion
    )

    demand = np.where(intermittent, 0, demand)

    matrix["units_requested_est"] = rng.poisson(
        np.clip(demand, 0, 100)
    )

    opening_stock = rng.integers(0, 30, n)

    matrix["stockout_flag"] = (
        (opening_stock == 0)
        | (
            (opening_stock < matrix["units_requested_est"])
            & (rng.random(n) < 0.6)
        )
    )

    matrix["units_sold"] = np.minimum(
        matrix["units_requested_est"],
        opening_stock
    ).astype(int)

    matrix["estimated_lost_units"] = (
        matrix["units_requested_est"]
        - matrix["units_sold"]
    )

    matrix["issue_type"] = np.where(
        matrix["stockout_flag"],
        "STOCKOUT_CENSORING",
        ""
    )

    matrix["sale_date"] = (
        matrix["sale_date"].dt.strftime("%Y-%m-%d")
    )

    matrix["sale_id"] = (
        "SALE-" + matrix["store_id"]
        + "-" + matrix["sku_id"]
        + "-" + matrix["sale_date"].str.replace("-", "")
    )

    sales = matrix[[
        "sale_id",
        "store_id",
        "sku_id",
        "sale_date",
        "units_sold",
        "units_requested_est",
        "promotion_flag",
        "stockout_flag",
        "estimated_lost_units",
        "issue_type"
    ]].copy()

    # ---------------- Inventory ----------------
    inventory = pd.DataFrame({
        "snapshot_id": [
            f"INV-{i+1:09d}" for i in range(n)
        ],
        "store_id": matrix["store_id"],
        "sku_id": matrix["sku_id"],
        "snapshot_date": matrix["sale_date"],
        "on_hand_units": (
            opening_stock - matrix["units_sold"]
        ).clip(lower=0),
        "reserved_units": 0
    })

    inventory["capacity_units"] = (
        inventory["store_id"].map(
            stores.set_index("store_id")["capacity_units"]
        )
    )

    # ---------------- Lead Time ----------------
    lead_count = max(100, n_skus * 5)

    lead = pd.DataFrame({
        "lead_time_observation_id": [
            f"LTO-{i+1:07d}" for i in range(lead_count)
        ],
        "supplier_id": rng.choice(
            suppliers["supplier_id"], lead_count
        ),
        "observed_days": np.maximum(
            1,
            rng.normal(8, 3, lead_count).round()
        ).astype(int),
        "observed_date": rng.choice(
            dates.strftime("%Y-%m-%d"),
            lead_count
        )
    })

    lead["delay_flag"] = (
        lead["observed_days"] > 12
    )

    # ---------------- Reorder Policy ----------------
    pairs = pair_base[
        ["store_id", "sku_id"]
    ].copy()

    pairs["policy_id"] = [
        f"RP-{i+1:08d}" for i in range(len(pairs))
    ]

    pairs["service_level_z"] = 1.65
    pairs["review_period_days"] = 7

    # ---------------- Ground Truth ----------------
    ground_truth = pd.DataFrame([
        ["GT-001", "STOCKOUT_AS_ZERO_DEMAND"],
        ["GT-002", "PACK_SIZE_VIOLATION"],
        ["GT-003", "DISCONTINUED_SKU_ORDER"],
        ["GT-004", "NEGATIVE_LEAD_TIME"],
        ["GT-005", "FUTURE_DATA_LEAKAGE"]
    ], columns=["case_id", "issue_type"])

    return {
        "SKU": sku,
        "Store": stores,
        "Supplier": suppliers,
        "SupplierSKU": supplier_sku,
        "SalesHistory": sales,
        "InventorySnapshot": inventory,
        "LeadTimeObservation": lead,
        "ReorderPolicy": pairs,
        "GroundTruth": ground_truth
    }