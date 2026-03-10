# Using Machine Learning for Load Forecasting
Forecast SPP Load

use SKLearn to forecast SPP load

[https://cienciadedatos.net/documentos/py29-forecasting-electricity-power-demand-python#Exogenous_variables](SKForecast Example)

## 1.Build Data Set
- Load Data: [https://www.gridstatus.io/products/api](Grid Status API)
- Historical Weather Data: [https://open-meteo.com/](Open Meteo)
  - also use for weather forecast
  - make sure to train on on the historical *forecast* not the actuals
- **Deliverables**: data.py script to pull all data into csv files

## 2. Feature Engineering and Model Training
- Sunlight-Related Features: astral package (see example doc)
- Extract Calendar Features
- Cyclical Encoding
- Window features
- **Deliverables**: train_model.py script to train the model, exported model with joblib, exported datapipline to pre-process new data for predictions
