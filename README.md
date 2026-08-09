# SPP Hourly Load Forecasting with Machine Learning

## Overview
Southwest Power Pool (SPP) is a regional transmission organization (RTO) that manages
the electric grid across 14 states from North Dakota to Oklahoma, serving over 20 million
customers. Accurate load forecasting is critical for grid reliability, energy trading,
and resource planning — even small forecast errors at SPP's scale translate to significant
operational costs.

This project builds an end-to-end hourly load forecasting pipeline using LightGBM and
skforecast, trained on 3 years of hourly SPP conforming load data (2023–2025) with
weather and calendar features. The trained model is served via a FastAPI application
that returns a 48-hour load forecast on demand.

The project was inspired by an example in the skforecast user guide on demand forecasting

_Forecasting energy demand with machine learning by Joaquín Amat Rodrigo and Javier Escobar Ortiz, available under Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0 DEED) at https://www.cienciadedatos.net/documentos/py29-forecasting-electricity-power-demand-python.html_

## Results
| Metric | Value |
|--------|-------|
| MAE    | 910 MW |
| MAPE   | 2.75% |
| Forecast Horizon | 48 hours |
| Training Period | Jan 2023 – Jun 2024 |
| Test Period | Jan 2025 – Dec 2025 |


## Tech Stack
| Category | Tools |
|----------|-------|
| Modeling | LightGBM, skforecast, scikit-learn |
| Data | GridStatus API, EIA Open Data API, Open-Meteo API |
| Feature Engineering | pandas, NumPy |
| EDA & Visualization | matplotlib, seaborn |
| API | FastAPI, Uvicorn |
| Environment | Python 3.11, Conda |
|Claude   |[Claude Project Session](https://claude.ai/share/b1118519-ca37-487a-9680-4e7baaffecde)   |


## Data

### Load Data
Hourly SPP conforming load data was sourced from the GridStatus API (`spp_load_hourly`)
covering January 2023 through December 2025. SPP reports load broken out by control zone —
these were aggregated to a single system-wide total for each hour.

**Conforming vs. Non-Conforming Load**
SPP separates load into two categories: conforming load, which follows predictable patterns
driven primarily by weather and calendar effects, and non-conforming load, which does not
follow a predictable pattern and is forecast separately. This project focuses on conforming
load only.

**Data Pipeline**
The extraction script pulls data in 60-day batches with rate limit handling (30
requests/minute) and saves each batch to CSV as a checkpoint in case of failure mid-run.
Each batch is written to `data/raw/load/` and read back in and concatenated at the end
of the pull.

**Data Challenges & Dead Ends**
During development the GridStatus API rate limit was hit, requiring a temporary switch to
the EIA Open Data API as an alternative source. The EIA data had significant quality
issues such as flat/stuck demand values persisting across multiple consecutive hours. Thi issue were not in the GridStatus data. Several approaches were tried
to work around this including:
- Flagging flat demand runs using a rolling difference threshold and replacing with NaN
- Down-weighting anomalous periods during training using skforecast's `weight_func`
  parameter to preserve time series continuity

Once the GridStatus rate limit cleared, the pipeline was reverted to GridStatus as the
primary data source. The GridStatus data required no anomaly handling other than 7 missing hours
were identified across the 3-year window, primarily on DST transition dates, and filled
via time-based interpolation.

### Weather Data
Hourly temperature data for Kansas City, MO was sourced from the Open-Meteo API.
SPPs region has a large north-south spread so Kansas City has slected as a selected weather location close to the middle of the region. Other weather locations in the north and south were considered but not added to simplfy the feature selection process


- Training data used the **archive API** (`archive-api.open-meteo.com`) for complete
historical coverage
- Production forecasts use the **forecast API** (`api.open-meteo.com`) for forward-looking
temperature inputs

**Note:** The model is trained on historical weather forecasts not actuals to try to mitage any noise in the difference between wweather forecast and real values. In production, forecasted
temperature values are used as exogenous inputs

### Final Dataset
- 26,304 hourly observations (January 2023 – December 2025)
- 7 missing hours filled via time interpolation
- No anomalous values in the final GridStatus dataset


## Features

Features were engineered from two sources: the weather data and the datetime index.
All feature engineering is encapsulated in `app/features.py` and applied via pandas
method chaining.

### Calendar Features
| Feature | Description |
|---------|-------------|
| `month` | Month of year (1–12) |
| `week` | ISO week of year |
| `day_of_week` | Day of week (0=Monday, 6=Sunday) |
| `hour` | Hour of day (0–23) |
| `Holiday` | Binary flag for US federal holidays |

### Cyclical Encoding
Raw calendar features were sine/cosine encoded to preserve their cyclical nature
(e.g. hour 23 is close to hour 0, not far from it):

| Feature | Description |
|---------|-------------|
| `month_sin`, `month_cos` | Cyclical encoding of month |
| `week_sin`, `week_cos` | Cyclical encoding of week |
| `day_sin`, `day_cos` | Cyclical encoding of day of week |
| `hour_sin`, `hour_cos` | Cyclical encoding of hour |

### Temperature Features
| Feature | Description |
|---------|-------------|
| `Temperature` | Hourly temperature in Kansas City (°C) |
| `Temp_3D_Mean` | 3-day rolling mean temperature |
| `Temp_2D_Max` | 2-day rolling maximum temperature |
| `Temp_2D_Min` | 2-day rolling minimum temperature |
| `Temp_1D_Min` | 1-day rolling minimum temperature |

Rolling temperature features capture the lagged effect of sustained heat or cold on
energy demand

### Autoregressive Lags
Lagged demand values were selected by training an initial autoregressive model over
a 175-lag window and selecting the top 15 most important lags by feature importance,
with `lag_24` (same hour yesterday) force-included. Final lags selected:

```python
lags = [1, 2, 3, 23, 24, 25, 47, 48, 49, ...]  # top lags from importance ranking
```

### Feature Selection
Recursive Feature Elimination with Cross Validation (RFECV) was used to select the
final feature set from the full candidate pool. Features were selected using a
5-fold time-series aware cross validation scheme to avoid data leakage.

## Modeling

### Approach
The model uses a recursive multi-step forecasting strategy via skforecast's
`ForecasterRecursive`, which wraps a LightGBM regressor (`LGBMRegressor`) and handles
the time series specific logic of constructing lag features, managing the forecast
horizon, and iterating predictions forward step by step.

In a recursive forecaster, each predicted value is fed back as an input to predict
the next step so a single model can be used for forecasting any time horizons but the forecast error will compound at each step

### Train / Validation / Test Split
All splits are strictly chronological to prevent data leakage.

| Split | Date Range | Observations |
|-------|------------|--------------|
| Train | Jan 2023 – Jun 2024 | 13,128 hours |
| Validation | Jul 2024 – Dec 2024 | 4,416 hours |
| Test | Jan 2025 – Dec 2025 | 8,760 hours |

### Hyperparameter Tuning
Bayesian hyperparameter search was performed using skforecast's
`bayesian_search_forecaster` over the train + validation window. The following
parameters were tuned:

| Parameter | Search Range |
|-----------|-------------|
| `n_estimators` | 300 – 1000 |
| `max_depth` | 3 – 10 |
| `learning_rate` | 0.01 – 0.5 |
| `reg_alpha` | 0 – 1 |
| `reg_lambda` | 0 – 1 |

### Backtesting
Final model performance was evaluated using
skforecast's `backtesting_forecaster` with a 24-step forecast horizon and a
growing training window. This simulates realistic production conditions where
the model predicts one day ahead using all available historical data.

### Results
| Metric | Value |
|--------|-------|
| MAE | 910 MW |
| MAPE | 2.75% |


## API

The trained model is served via a FastAPI application that pulls live data,
constructs features, and returns a 48-hour hourly load forecast on demand.

### Endpoints

#### `GET /predict`
Returns a 48-hour SPP load forecast starting from the current day.

**Logic:**
- If called **after 6:00 PM local time**: returns a forecast for tomorrow (D+1),
  using yesterday's actual load as the last window
- If called **before 6:00 PM local time**: returns a forecast for today (D),
  using the prior day's actual load as the last window

This logic reflects the GridStatus data release schedule — prior day actual load
is typically available by 6:00 PM the following day.

**Response:**
```json
{
  "predictions": [
    {"date": "2025-08-09 00:00:00", "Demand": 31245.6},
    {"date": "2025-08-09 01:00:00", "Demand": 29876.3},
    ...
  ]
}
```

**Data pulled at request time:**
- Last 8 days of actual SPP load from GridStatus API (used as the last window
  for the recursive forecaster)
- 48-hour temperature forecast from Open-Meteo (used as exogenous input)

### Running Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Start the API
fastapi dev app/main.py

# Test the endpoint
curl http://localhost:8000/predict
```

Interactive API docs available at `http://localhost:8000/docs`

## Setup

### Prerequisites
- Python 3.11
- Conda

### Installation
```bash
# Clone the repository
git clone https://github.com/maxwellgriffith345/spp-load-forecast.git
cd spp-load-forecast

# Create and activate conda environment
conda create -n loadcast python=3.11
conda activate loadcast

# Install dependencies
conda install -c conda-forge skforecast
pip install -r requirements.txt
```

### Configuration
Create a `config.py` file in the `app/` directory with your API keys:
```python
GRIDSTATUS_API_KEY = "your_gridstatus_api_key"
```

A GridStatus API key is required to run the application. A free tier is available
at [gridstatus.io](https://www.gridstatus.io/products/api). No API key is needed
for Open-Meteo.

### Reproducing the Model
To retrain the model from scratch:
```bash
# Pull raw data
python scripts/extract.py

# Train model (saves to model/forecaster_001.joblib)
python scripts/train_model.py
```

### Running the API
```bash
fastapi dev app/main.py
```
API docs available at `http://localhost:8000/docs`

---

## Known Limitations & Future Work

### Current Limitations
- **Single weather location** — only Kansas City temperature is used. SPP spans
  North Dakota to Oklahoma and a single location may not capture regional demand
  drivers in the northern or southern extremes of the footprint
- **No data persistence** — the API pulls fresh data on every request with no
  local storage. This increases latency and API dependency at request time
- **Local deployment only** — the app is not currently deployed to a cloud
  environment

### Future Work
- **Additional weather locations** — add Oklahoma City and Sioux Falls weather
  stations and use feature selection to determine which locations add predictive
  value
- **Containerization & cloud deployment** — package the app in Docker and deploy
  to Google Cloud Run for public access
- **Data persistence** — add a database container to store actual load values and
  predictions, reducing API calls at request time and enabling drift monitoring
- **Drift monitoring** — log predicted vs. actual load after each day's data is
  released to track model performance over time and trigger retraining when error
  exceeds a threshold
- **Streamlit dashboard** — build a simple visualization layer showing forecast vs.
  actual load, feature importance, and model error metrics
- **Automated prediction trigger** — automate the API call when GridStatus releases
  the prior day's actual load (~6:00 PM) rather than relying on manual requests
