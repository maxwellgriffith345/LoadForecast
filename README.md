# Using Machine Learning for Load Forecasting
Forecast SPP Load
what is SPP?
Why would it be of interest to forecast it's load?

[SPP Site](https://spp.org/)
[SPP Map (Prices)](https://pricecontourmap.spp.org/pricecontourmap/)

use SKLearn to forecast SPP load

[SKForecast Load Forecasting](https://cienciadedatos.net/documentos/py29-forecasting-electricity-power-demand-python#Exogenous_variables%5D)

Forecasting energy demand with machine learning by Joaquín Amat Rodrigo and Javier Escobar Ortiz, available under Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0 DEED) at https://www.cienciadedatos.net/documentos/py29-forecasting-electricity-power-demand-python.html

## 1. Build Data Set
- Data window: 3 years 2023-1-1 to 2025-12-31
- Target
  - SPP Load Data: [Grid Status API](https://www.gridstatus.io/products/api)
  - [GS Data Catalog](https://www.gridstatus.io/datasets?filter=load&source=spp)
  - Load Hourly [GS API](https://www.gridstatus.io/datasets/spp_load_hourly)
  - [Python Client for GS API](https://github.com/gridstatus/gridstatusio)
  - [Grid Status Dev Best Practices](https://docs.gridstatus.io/developers/concepts/best-practices#python)
  - There are two forecast types: Conforming load and non-conforming Load
  - conforming load is load that changes predictably and mainly driven by env factors like temperture
  - non-conforming does not follow a predictable pattern and is forecast separately and added to the confirming load forecast
  - we will focus on confirming load
- Historical Weather Data:
  - [Open Meteo](https://open-meteo.com/)
  - also use for weather forecast for exogenous variables for predictions
  - make sure to train on on the historical forecast not the actuals
  - SPP has a large north/south footprint cover North Dakota to Oklahoma
  - We will select three weather locatoins to pull temperture data from and then refine during the feature selection process
  -  Kansas City
  - TODO: make a note of train/validation split e.g. 2023–2024 train, Q1 2025 val, Q2–Q4 2025 test
  - we will also pull the hourly boolean "is day" which gives aprox sunrise/sunset times
- **Deliverables**:
  - data.py script to pull all data (load and weather) into csv file
- Challenge
  - I hit the rate limit in the gridstatus api
  - Switched to using the EIA Open data api
  - the grid status api is more robust with built in retry logic and error catching

## 1.5: Exploratory Data
 - notebook showing load patterns (daily, weekly, seasonal cycles), the OKC/KC temperature correlation with load, and the demand peaks

## 2. Feature Engineering
- Extract Calendar Features
- Cyclical Encoding (hour of day ect)
  - [ML Mastery Cyclic Features](https://machinelearningmastery.com/7-pandas-tricks-for-time-series-feature-engineering/)
  - [Kaggle Cyclic Feautres](https://www.kaggle.com/code/avanwyk/encoding-cyclical-features-for-deep-learning)
  - [ML Pills Cyclic Encoding](https://mlpills.substack.com/p/issue-89-encoding-cyclical-features)
  - [Cyclic Encoding for NN](https://medium.com/@dhanyahari07/improving-time-series-prediction-models-using-cyclic-features-encoding-in-neural-networks-0eebef307fc2)
- Window features (running averages)
- Federal Holidays
- Sunlight-Related Features:
  -  we will pull the bool "is_day" from the weather API
  - astral package (see example doc)
- Lagged target variables (auto-regressive model)
- heating/cooling degree days (what is this?)
- Exogenous Variables
  - created a features.py with functions to set the holiday and calendar features month, week, day of week and hour, and turning those calendar features into cyclic features with sin and cos sin componenents
  - I import those and pipe them on the data frame.
  - I also include a 3 day centered average temperture feature
  - this is in a jupyter notebook in /notebooks/Train
  - possible extensions is to create polynomial features and add additional averages and daylight features such as hours a a day
- **Deliverables**:
  - features.py file that creates that needed features

## 3. Feature Selection
- use a simple model (gradient boost) and a small set of the data
- working in notebooks/Train
- used recursive feature selection from Scikit-learn
- of the 26 features available on13 were selected
- lags: [1, 2, 3, 23, 25, 47]
- No window feature was selected- only tested a 3 day window feature
- and the exogenous variables were ['Temperature', 'week', 'day_of_week', 'hour', 'hour_sin', 'hour_cos', 'Temp_3D_Mean']
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
