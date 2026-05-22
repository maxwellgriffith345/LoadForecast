# Using Machine Learning for Load Forecasting
Forecast SPP Load
what is SPP?
Why would it be of interest to forecast it's load?

[SPP Site](https://spp.org/)
[SPP Map (Prices)](https://pricecontourmap.spp.org/pricecontourmap/)

use SKLearn to forecast SPP load

[SKForecast Load Forecasting](https://cienciadedatos.net/documentos/py29-forecasting-electricity-power-demand-python#Exogenous_variables%5D)

## 1. Build Data Set
- Data window: 3 years 2023-1-1 to 2025-12-31
- Target
  - SPP Load Data: [Grid Status API](https://www.gridstatus.io/products/api)
  - [GS Data Catalog](https://www.gridstatus.io/datasets?filter=load&source=spp)
  - Load Hourly [GS API](https://www.gridstatus.io/datasets/spp_load_hourly)
  - [Python Client for GS API](https://github.com/gridstatus/gridstatusio)
- Historical Weather Data:
  - [Open Meteo](https://open-meteo.com/)
  - also use for weather forecast for exogenous variables for predictions
  - make sure to train on on the historical forecast not the actuals
  - SPP has a large north/south footprint cover North Dakota to Oklahoma
  - We will select three weather locatoins to pull temperture data from and then refine during the feature selection process
  - Oklahoma City, Kansas City,Sioux Falls
  - TODO: make a note of train/validation split e.g. 2023–2024 train, Q1 2025 val, Q2–Q4 2025 test
- **Deliverables**:
  - data.py script to pull all data (load and weather) into csv file

## 1.5: Exploratory Data
 - notebook showing load patterns (daily, weekly, seasonal cycles), the OKC/KC temperature correlation with load, and the demand peaks

## 2. Feature Engineering
- Sunlight-Related Features: astral package (see example doc)
- Extract Calendar Features
- Cyclical Encoding (hour of day ect)
- Window features (running averages)
- Federal Holiday indicators (where do I pull this info?)
- Lagged target variables (auto-regressive model)
- heating/cooling degree days (what is this?)
- **Deliverables**:
  - features.py file that creates that needed features

## 3. Feature Selection
- use a simple model (gradient boost) and a small set of the data
- TODO: more detail on the method here

## 4. Train and Compare
- naive base line
- specify error metric
- use a few different estimators (ie LGBMRegressor) to create forecasters
- export the model with joblib
- dealing with prediction "gap" when are the predictions made

## 5. Production
- [SKForecast in Production](https://skforecast.org/latest/user_guides/forecaster-in-production)
- Create FastAPI app
- [Google Cloud Run](https://cloud.google.com/run)
  - Launch on google cloud run
- simple monitoring/drift check idea — even just logging predicted vs. actual after the fact shows production maturity
- Streamlit dashboard to visualize forecasts
