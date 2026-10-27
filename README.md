# SKU Demand Forecasting & Replenishment Intelligence

An end-to-end inventory planning application that forecasts demand at the **SKU-location level** and recommends replenishment quantities using lead time, safety stock, and ordering constraints. The system surfaces decisions, exceptions, and evaluation metrics while preserving traceability.

## Problem Statement

Inventory teams must decide **what to replenish, how much to order, and when to order** across multiple products and locations. Poor demand forecasts can cause stockouts, excess inventory, and avoidable costs.

This project combines demand forecasting with rule-based replenishment recommendations to support consistent, explainable inventory decisions.

## Key Features

- **Synthetic retail data generation** for repeatable development and evaluation.
- **SKU-location demand forecasting** using historical demand.
- **Forecast evaluation** with metrics such as MAE and RMSE.
- **Replenishment recommendations** based on lead time, safety stock, current inventory, and ordering rules.
- **Ordering constraints** such as minimum order quantity (MOQ), pack-size multiples, and supplier or storage limits where configured.
- **Data validation** to flag missing, invalid, or inconsistent records.
- **Exception handling** for cases such as insufficient supplier data, unusual demand, or constrained order quantities.
- **Traceability** through saved outputs and SQLite persistence.
- **Interactive dashboard** built with Streamlit and Plotly.

## End-to-End Workflow

1. Generate or load SKU, location, inventory, supplier, and historical demand data.
2. Validate input data and identify data-quality issues.
3. Forecast demand for each SKU-location combination.
4. Evaluate forecast quality using available historical observations.
5. Calculate replenishment needs using lead time and safety-stock policies.
6. Apply ordering constraints such as MOQ and pack size.
7. Display recommendations, exceptions, and relevant metrics in the dashboard.
8. Save results to SQLite for traceability.

## Data Design

The workflow can use related entities such as:

- **SKU:** product identifier and product-level attributes.
- **Location:** store, warehouse, or fulfillment location.
- **Demand history:** dated demand observations for each SKU-location pair.
- **Inventory:** available stock and other inventory quantities supported by the implementation.
- **Supplier / contract:** lead time, unit cost, MOQ, pack size, and other configured purchasing constraints.
- **Forecast:** predicted demand and evaluation results.
- **Replenishment recommendation:** proposed order quantity, estimated cost, and decision or exception details.

The project uses generated data so the workflow can be tested without exposing real business data. Dataset size should be selected to fit the available machine resources; large SKU-location-date combinations can create millions of rows.

## Forecasting and Evaluation

Forecasting is performed for SKU-location demand using the methods implemented in `forecasting.py`.

Evaluation can include:

- **MAE (Mean Absolute Error):** average absolute difference between actual and predicted demand.
- **RMSE (Root Mean Squared Error):** penalizes larger forecast errors more heavily.

Metrics should be calculated on appropriate historical or held-out observations. Forecast accuracy depends on the generated data, selected forecasting method, and evaluation window; results should not be interpreted as a guarantee of real-world performance.

## Replenishment Logic

The replenishment module uses forecast demand, lead time, safety stock, and available inventory to estimate whether an order is needed.

A common starting point is:

```text
Lead-time demand = Forecast daily demand × Lead time in days
Reorder threshold = Lead-time demand + Safety stock
Raw order quantity = max(0, Reorder threshold − Inventory position)
```

The final recommendation can then be adjusted to comply with configured ordering constraints, for example:

- Raise a positive order to the supplier's MOQ when required.
- Round the order quantity up to a valid pack-size multiple.
- Check supplier, storage, or other configured limits.
- Flag records where required inputs are missing or constraints cannot be satisfied.

The exact calculations and supported constraints are defined by the implementation in `replenishment.py`.

## Validation and Exceptions

The application validates input data before making recommendations. Depending on the configured rules, exceptions may include:

- Missing or invalid demand, inventory, or supplier fields.
- Invalid or non-positive lead times, pack sizes, or ordering quantities.
- Missing unit-cost or contract mappings.
- Unusual demand observations that require review.
- Recommendations altered by MOQ or pack-size rules.
- Orders that cannot be recommended safely because required information is unavailable.

Exceptions should remain visible rather than being silently treated as normal recommendations.

## Technology Stack

- **Python** — application logic and data processing
- **Streamlit** — interactive web application
- **Pandas** — tabular data processing
- **Plotly** — interactive charts
- **SQLite** — local persistence
- **Forecasting and replenishment modules** — demand prediction and inventory decision logic

## Project Structure

```text
SKU-Demand-Forecasting-Replenishment/
├── app.py
├── generator.py
├── forecasting.py
├── replenishment.py
├── validation.py
├── database.py
├── requirements.txt
└── README.md
```

Your actual repository may contain additional files or a different layout. Update this section to match the files committed to GitHub.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/shalom-m-vishal/SKU-Demand-Forecasting-Replenishment.git
cd SKU-Demand-Forecasting-Replenishment
```

### 2. Create and activate a virtual environment

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If the repository does not yet include a complete `requirements.txt`, install the packages used by the code, such as:

```bash
pip install streamlit pandas plotly
```

### 4. Run the application

```bash
streamlit run app.py
```

Streamlit will print a local URL in the terminal. Open that URL in your browser.

## Reproducibility

- Use the same generator settings and random seed, if supported, to reproduce synthetic datasets.
- Keep forecasting and replenishment rules in their dedicated modules.
- Record forecast metrics and recommendation outputs so decisions can be reviewed.
- Validate generated and uploaded data before using it in the workflow.

## Future Improvements

- Add time-series cross-validation and benchmark multiple forecasting models.
- Include service-level-based safety-stock calculations.
- Add supplier calendars, order-frequency rules, and budget constraints.
- Track forecast bias, stockout risk, and inventory carrying cost.
- Add automated tests for data validation and replenishment edge cases.
- Add export options for recommendations and exception reports.

## Author

**MUTTI REDDY SHALOM VISHAL**

GitHub: [shalom-m-vishal](https://github.com/shalom-m-vishal)

Project repository: [SKU Demand Forecasting & Replenishment](https://github.com/shalom-m-vishal/SKU-Demand-Forecasting-Replenishment)
