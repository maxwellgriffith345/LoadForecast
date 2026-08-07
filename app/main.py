#this is where the app goes
from fastapi import FastAPI
from pathlib import Path
import os
from skforecast.utils import load_forecaster

from load_exo import make_prediction


#load model
#model_path = os.path.join('model', "forecaster_001.joblib")
MODEL_PATH = Path("model/forecaster_001.joblib")
#forecaster = load_forecaster(MODEL_PATH, verbose = False, suppress_warnings = True)


#create app object with name
app = FastAPI(title = "Load Forecast")


@app.on_event("startup")
def load_model():
    if not MODEL_PATH.exists():
        raise RuntimeError(
                f"Model file not found at {MODEL_PATH}"
        )

    forecaster = load_forecaster(MODEL_PATH, verbose = False, suppress_warnings = True)
    app.state.model = forecaster

#prediction endpoint
@app.get("/predict")
async def predict():

    forecaster = app.state.model
    prediction = make_prediction(forecaster)

    return {"predictions": prediction}
