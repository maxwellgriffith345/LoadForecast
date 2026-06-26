import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

#Modeling and Forecasting
import skforecast
import lightgbm
import sklearn
from lightgbm import LGBMRegressor
from skforecast.recursive import ForecasterRecursive
from skforecast.utils import save_forecaster
from skforecast.model_selection import TimeSeriesFold, bayesian_search_forecaster, backtesting_forecaster
from skforecast.feature_selection import select_features
from sklearn.feature_selection import RFECV

# Exogenous features helpers
from features import set_holidays, cal_features, cyclic_features

import warnings
warnings.filterwarnings('once')

#--- Read in data ---
df = (pd.read_csv("data/raw/loadtempday_clean.csv")
        .drop_duplicates()
        .pipe(lambda df: df.set_index(pd.to_datetime(df["date"])))
        .drop(columns = ["date"])
     )
#this will throw an error if there are duplicates
df.index = df.index.tz_localize(None)
df.index.freq = 'h'

print("Data load complete")

# Train Val Test Split
TRAIN_START = "2023-01-01 00:00:00"
TRAIN_END   = "2024-06-30 23:00:00"
VAL_START   = "2024-07-01 00:00:00"
VAL_END     = "2024-12-31 23:00:00"
TEST_START  = "2025-01-01 00:00:00"
TEST_END    = "2025-12-31 23:00:00"

#Create Exogenous features
data = df.copy()
data = (data
            .pipe(set_holidays)
            .pipe(cal_features)
            .pipe(cyclic_features)
            .assign(Holiday=lambda d: d["Holiday"].astype(int))
            .assign(Temp_3D_Mean=lambda d: d["Temperature"].rolling("3D", center = False).mean())
            .assign(Temp_2D_Mean =lambda d: d["Temperature"].rolling("2D", center = False).mean())
            .assign(Temp_2D_Max =lambda d: d["Temperature"].rolling("2D", center = False).max())
            .assign(Temp_2D_Min =lambda d: d["Temperature"].rolling("2D", center = False).min())
            .assign(Temp_1D_Max =lambda d: d["Temperature"].rolling("1D", center = False).max())
            .assign(Temp_1D_Min =lambda d: d["Temperature"].rolling("1D", center = False).min())
           )

#list of exogenous variables
#exo_vars = list(data.columns)[1:]
exo_vars = [col for col in data.columns if col != "Demand"]

print("Exogenous features created")

#Split the data
data_train = data.loc[: TRAIN_END, :].copy()
data_val   = data.loc[VAL_START:VAL_END, :].copy()
data_test  = data.loc[TEST_START:, :].copy()

print(f"Train dates      : {data_train.index.min()} --- {data_train.index.max()}  (n={len(data_train)})")
print(f"Validation dates : {data_val.index.min()} --- {data_val.index.max()}  (n={len(data_val)})")
print(f"Test dates       : {data_test.index.min()} --- {data_test.index.max()}  (n={len(data_test)})")

print("Data splits created")

#Get the most important lags
ar_week_forecaster = ForecasterRecursive(
                 estimator       = LGBMRegressor(random_state=15926, verbose=-1),
                 lags            = 175,
             )
ar_week_forecaster.fit(y=data.loc[:VAL_END, 'Demand'])

lags_df = ar_week_forecaster.get_feature_importances(sort_importance=True).head(40)
lags_df["lags"] = lags_df["feature"].str.replace("lag_", "", regex=False).astype(int)
top_lags = lags_df.lags.to_list()[:15]
if 24 not in top_lags:
    top_lags.append(24)

print("Top lags selected")

#Feature Selection
#create estimator(solver) and the forecaster (matrix formulation)
estimator = LGBMRegressor(
                n_estimators = 100,
                max_depth    = 4,
                random_state = 15926,
                verbose      = -1
            )

forecaster = ForecasterRecursive(
                 estimator       = estimator,
                 lags            = top_lags,
             )

warnings.filterwarnings("ignore", message="X does not have valid feature names.*")
selector = RFECV(
    estimator = estimator,
    step      = 1,
    cv        = 5,
)
lags_select, window_features_select, exog_select = select_features(
    forecaster      = forecaster,
    selector        = selector,
    y               = data_train['Demand'],
    exog            = data_train[exo_vars],
    select_only     = None,
    force_inclusion = ["lag_24", "Holiday"],
    random_state    = 123,
    verbose         = True,
)

print("Best features selected")
print(f"Lags selected: {len(lags_select)}")
print(f"Exog selected: {len(exog_select)}")

#Hyper Parameter Tuning
tuned_forecaster = ForecasterRecursive(
                 estimator       = LGBMRegressor(random_state=15926, verbose=-1),
                 lags            = lags_select
             )

# Estimator hyperparameters search space
def search_space(trial):
    search_space  = {
        'n_estimators' : trial.suggest_int('n_estimators', 300, 1000, step=100),
        'max_depth'    : trial.suggest_int('max_depth', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.5),
        'reg_alpha'    : trial.suggest_float('reg_alpha', 0, 1),
        'reg_lambda'   : trial.suggest_float('reg_lambda', 0, 1),
    }
    return search_space

# Folds training and validation
cv_search = TimeSeriesFold(
                steps              = 24,
                initial_train_size = len(data[:TRAIN_END]),
                refit              = False,
            )

results_search, frozen_trial = bayesian_search_forecaster(
                                   forecaster   = tuned_forecaster,
                                   y            = data.loc[:VAL_END, 'Demand'],
                                   exog         = data.loc[:VAL_END, exog_select],
                                   cv           = cv_search,
                                   metric       = 'mean_absolute_error',
                                   search_space = search_space,
                                   n_trials     = 30,  # Increase for more exhaustive search
                                   return_best  = True
                               )
print("Model tuning complete")

# Backtest final model on test data
cv = TimeSeriesFold(
        steps              = 24,
        initial_train_size = len(data.loc[:VAL_END]),
        refit              = False
)

metric, predictions = backtesting_forecaster(
                          forecaster = tuned_forecaster,
                          y          = data['Demand'],
                          exog       = data[exog_select],
                          cv         = cv,
                          metric     = 'mean_absolute_error'
                      )
print(f"Final model mean absolute error {metric}")


# Save the Model
os.makedirs("model", exist_ok=True)
results_search.to_csv("model/tuning_results.csv", index=False)
save_forecaster(tuned_forecaster, file_name='model/forecaster_001.joblib', verbose=False)
print("Model saved")
