import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from config import GRIDSTATUS_API_KEY
from gridstatusio import GridStatusClient


START_DATE = datetime(2025, 1, 1) #year, month, day
END_DATE = datetime(2025, 2, 1)

"""Extract Load data"""
#Batch for large queries
def fetch_load_batches(client, dataset: str,start: datetime,end: datetime, batch_days: int = 7, **kwargs) -> pd.DataFrame:
    """Fetch data in batches to avoid timeouts."""
    all_data = []
    current = start

    while current < end:
        batch_end = min(current + timedelta(days=batch_days), end)

        print(f"Fetching {current.date()} to {batch_end.date()}...")

        data = client.get_dataset(
            dataset,
            start=current.isoformat(),
            end=batch_end.isoformat(),
            **kwargs
        )

        if len(data) > 0:
            all_data.append(data)

        current = batch_end

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

# Usage
def fetch_load(client): -> pd.DataFrame:

    df = fetch_load_batches(
        client,
        "spp_load_hourly",
        START_DATE,
        END_DATE,
        batch_days=7,
        columns = ["interval_start_utc", "balancing_area_name", "control_zone_name", "forecast_area_type", "load"],
        filter_column = "balancing_area_name",
        filter_value = "SPP",
        limit=100
    )

    return df

def clean_load(df: pd.DataFrame): -> pd.DataFrame:
    #make a copy of dataframe?
    df = df.copy()
    #filter out NC load
    df = df[df["forecast_area_type"]=="CF"]
    #aggregate control zones for total SPP load
    df = df.groupby("interval_start_utc", as_index = False).agg(load = ("load", "sum"))
    #set the datetime index and frequecy
    df.set_index("interval_start_utc", inplace = True)
    df.index.freq = 'h'

    return df

def get_weather_client(): #No API Key needed
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    openmeteo = openmeteo_requests.Client(session = retry_session)
    return openmeteo

def fetch_weather(client):
    url = "https://historical-forecast-api.open-meteo.com/v1/forecast"
    params = {
    	"latitude": 39.0997,
    	"longitude": -94.5786,
    	"start_date": "2025-01-01",
    	"end_date": "2025-01-02",
    	"hourly": "temperature_2m",
    }

    #batch the rest of this?
    #make request
    responses = openmeteo.weather_api(url, params = params)
    response = responses[0]

    #Process hourly data
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()

    hourly_data = {
	"date": pd.date_range(
		start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
		end =  pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
		freq = pd.Timedelta(seconds = hourly.Interval()),
		inclusive = "left"
        )
    }

    hourly_data["temperature_2m"] = hourly_temperature_2m
    hourly_dataframe = pd.DataFrame(data = hourly_data)



def run():

    load_client = GridStatusClient(api_key = GRIDSTATUS_API_KEY)
    weather_client = get_weather_client()

    load_df = fetch_load(load_client)
    weather_df = fetch_weather(weather_client)
