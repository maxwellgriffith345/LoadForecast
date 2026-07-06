#this is where the app goes
from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import os

class InputData(BaseModel):
    Date: string


#create app object with name
app = FastAPI(title = "Load Forecast")


#load model
model_path = os.path.join('model', INSERTMODELNAME)

#prediction endpoint
@app.post("/predict")
async def predict(data: InputData):
    #do all the stuff to make the predictions


    return {}
