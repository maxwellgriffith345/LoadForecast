#this is where the app goes
from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import os

class InputData(BaseModel):
    Date: string


def make_prediction(forecaster):
    #get current date and time
    now = datetime.now()

    """
    "yesterdays" actual is available until 6pm central
    so if it is before 6pm predict "todays" load
    """
    if now.hour <= 18:
        now = now - timedelta(days = 1)

    #get the date ranges
    date_ranges = get_date_ranges(day_one = now)

    #get weather forecast
    weather_client = get_weather_client
    weather_data = fetch_weather(
                    weather_client,
                    start = date_ranges["exo_start"]
                    end = date_ranges["exo_end"]
    )

    #get the weather features


    #get the load
    load_client = get_load_client()
    load_data = fetch_load(
                load_client,
                start = date_ranges["lw_start"],
                end = date_ranges["lw_end"]
    )
    lw_data = clean_load(load_data)

    #make predictions
    predictions = forecaster.predict(
                    steps = 48,
                    last_window = lw_data,
                    exog = exo_predict
    )

    #change the format to send over json?


    return predictions

#create app object with name
app = FastAPI(title = "Load Forecast")


#load model
model_path = os.path.join('model', "forecaster_001.joblib")
forecaster = load_forecaster(model_path, verbose = False, suppress_warnings = True)

#prediction endpoint
@app.post("/predict")
async def predict(data: InputData):


    prediction = make_prediction(forecaster)

    return {}
