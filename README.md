# SKU Demand Forecasting & Replenishment Intelligence

An intelligent inventory planning application that forecasts SKU-location demand and recommends replenishment quantities using demand patterns, lead times, safety stock, and ordering constraints.

## Overview

Inventory teams need to maintain sufficient stock while avoiding overstocking and unnecessary inventory costs. This project provides a data-driven approach to demand forecasting and replenishment planning through an interactive Streamlit dashboard.

## Key Features

- **Demand Forecasting:** Generate demand forecasts for individual SKUs and locations.
- **Replenishment Recommendations:** Calculate recommended order quantities based on forecast demand and inventory requirements.
- **Safety Stock & Lead Time:** Account for safety stock and supplier lead times when planning replenishment.
- **Ordering Constraints:** Incorporate applicable ordering rules and supplier contract information.
- **Interactive Dashboard:** Explore forecasting and replenishment results using Streamlit and Plotly.
- **Data Validation:** Validate input data before processing.
- **Database Integration:** Store application data in SQLite for local persistence.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application and business logic |
| Streamlit | Interactive web dashboard |
| Pandas | Data processing and analysis |
| Plotly | Data visualization |
| SQLite | Local database storage |
| Forecasting models | Demand prediction |
| Git & GitHub | Version control and project hosting |

## Project Structure

```text
SKU-Demand-Forecasting-Replenishment/
├── app.py             # Streamlit application
├── generator.py       # Data generation
├── forecasting.py     # Demand forecasting and evaluation
├── replenishment.py   # Replenishment recommendations
├── validation.py      # Data validation
├── database.py        # SQLite persistence
├── requirements.txt   # Python dependencies
├── .gitignore         # Files excluded from Git
└── README.md          # Project documentation
```

*The structure above assumes these files are present in the repository.*

## Application Workflow

1. Generate or load SKU-location demand data.
2. Validate the input data.
3. Forecast demand for the required planning horizon.
4. Calculate replenishment recommendations using lead time, safety stock, and ordering constraints.
5. Review results and visualizations in the dashboard.
6. Persist relevant data in the local SQLite database.

## Getting Started

### Prerequisites

- Python 3.10 or later
- pip
- Git

### Installation

Clone the repository:

```bash
git clone https://github.com/shalom-m-vishal/SKU-Demand-Forecasting-Replenishment.git
cd SKU-Demand-Forecasting-Replenishment
```

Create and activate a virtual environment on Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

If `requirements.txt` is not present yet, create it with the packages your application actually uses, including Streamlit, Pandas, and Plotly, plus any additional project dependencies.

### Run the Application

```bash
streamlit run app.py
```

Open the local URL displayed in your terminal, usually `http://localhost:8501`.

## Business Value

The application is designed to help inventory planners:

- Make more informed replenishment decisions.
- Account for demand variability and supplier lead times.
- Reduce the risk of stockouts and excess inventory.
- Improve visibility into SKU-level inventory planning.

Actual business impact depends on the quality of the input data, forecasting accuracy, and operational constraints.

## Future Enhancements

- Integrate real-world sales and inventory datasets.
- Compare multiple forecasting algorithms.
- Add forecast accuracy metrics such as MAE, RMSE, and MAPE where appropriate.
- Support multi-location inventory optimization.
- Add supplier integrations and automated replenishment alerts.
- Deploy the dashboard to a cloud platform.

## Author

**MUTTI REDDY SHALOM VISHAL**

- GitHub: [shalom-m-vishal](https://github.com/shalom-m-vishal)
- Project Repository: [SKU Demand Forecasting & Replenishment](https://github.com/shalom-m-vishal/SKU-Demand-Forecasting-Replenishment)

---

*Developed as an AI-driven inventory planning project focused on demand forecasting and intelligent replenishment.*
