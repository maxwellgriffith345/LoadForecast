import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from config import GRIDSTATUS_API_KEY
from gridstatusio import GridStatusClient
import openmeteo_requests
import requests_cache
from retry_requests import retry


START_DATE = datetime(2025, 1, 1) #year, month, day
END_DATE = datetime(2025, 2, 1)
WEATHER_LOCATIONS = {
    "kansas_city": (39.0997, -94.5786),
}

def get_load_client():
    client = GridStatusClient(
    max_retries=3,        # Maximum retries (default: 5)
    base_delay=1.0,       # Base delay in seconds (default: 2.0)
    exponential_base=1.5, # Exponential backoff multiplier (default: 2.0)
    api_key = GRIDSTATUS_API_KEY
    )

    return client

def get_weather_client(): #No API Key needed
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    client = openmeteo_requests.Client(session = retry_session)
    return client


def fetch_load(client, start: datetime = START_DATE, end: datetime = END_DATE) -> pd.DataFrame:

    df = client.get_dataset(
        "spp_load_hourly",
        start = start.isoformat(),
        end = end.isoformat(),
        columns = ["interval_start_utc", "balancing_area_name", "control_zone_name", "forecast_area_type", "load"],
        filter_column = "balancing_area_name",
        filter_value = "SPP",
    )

    return df


#Batch for large queries
def fetch_load_batches(client, start: datetime = START_DATE, end: datetime = END_DATE, batch_days: int = 7) -> pd.DataFrame:
    """Fetch data in batches to avoid timeouts."""
    all_data = []
    current = start

    while current < end:
        batch_end = min(current + timedelta(days=batch_days), end)

        print(f"Fetching {current.date()} to {batch_end.date()}...")

        """ Insert fetch_load func here
        data = client.get_dataset(
            dataset,
            start=current.isoformat(),
            end=batch_end.isoformat(),
            **kwargs
        )
        """
        batch_df = fetch_load(client, start = current, end = batch_end)

        if len(batch_df) > 0:
            all_data.append(batch_df)

        current = batch_end

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

def clean_load(df: pd.DataFrame) -> pd.DataFrame:
    #make a copy of dataframe?
    df = df.copy()
    #filter out NC load
    df = df[df["forecast_area_type"]=="CF"]
    #aggregate control zones for total SPP load
    df = df.groupby("interval_start_utc", as_index = False).agg(load = ("load", "sum"))
    #set the datetime index and frequecy
    df.rename(columns = {"interval_start_utc": "date"}, inplace= True)
    df.set_index("date", inplace = True)
    df.index.freq = 'h'

    return df


#make one request to weather API and return DF
def fetch_weather(client, start: datetime = START_DATE, end: datetime = END_DATE) -> pd.DataFrame:
    url = "https://historical-forecast-api.open-meteo.com/v1/forecast"
    lat,lon = WEATHER_LOCATIONS["kansas_city"]
    params = {
    	"latitude": lat,
    	"longitude": lon,
    	"start_date": start.strftime("%Y-%m-%d"),
    	"end_date": end.strftime("%Y-%m-%d"),
    	"hourly": "temperature_2m",
    }

    responses = client.weather_api(url, params = params)
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

    hourly_data["temperature"] = hourly_temperature_2m
    df = pd.DataFrame(data = hourly_data)

    df.set_index("date", inplace = True)
    df.index.freq = 'h'

    return df

def fetch_weather_batches(client, start: datetime = START_DATE, end: datetime = END_DATE, batch_days: int = 30) -> pd.DataFrame:
    """Fetch weather in batches to avoid timeouts."""
    """ TODO: Need logic if date range is smaller than batch size"""
    all_data = []
    current = start

    while current < end:
        batch_end = min(current + timedelta(days=batch_days), end)

        print(f"Fetching weather {current.date()} to {batch_end.date()}...")

        # Temporarily override dates for this batch
        batch_df = fetch_weather(client, start=current, end=batch_end)
        all_data.append(batch_df)

        current = batch_end

    return pd.concat(all_data) if all_data else pd.DataFrame()


def fetch_all_data(start: datetime = START_DATE, end: datetime = END_DATE):

    load_client = get_load_client()
    weather_client = get_weather_client()

    load_df = fetch_load_batches(load_client, start, end)
    weather_df = fetch_weather_batches(weather_client, start, end)

    load_df = clean_load(load_df)

    df = load_df.join(weather_df)

    return df

if __name__ == '__main__':
    path = "data/raw/"
    os.makedirs(path, exist_ok= True)
    df = fetch_all_data()
    df.to_csv(os.path.join(path, "tempload.csv"), index = True)
