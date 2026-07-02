import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from config import GRIDSTATUS_API_KEY, EIA_KEY
from gridstatusio import GridStatusClient
import openmeteo_requests
import requests
import requests_cache
from retry_requests import retry
import time

START_DATE = datetime(2023, 1, 1) #year, month, day
END_DATE = datetime(2026, 1, 1)
WEATHER_LOCATIONS = {
    "kansas_city": (39.0997, -94.5786),
}

def get_weather_client(): #No API Key needed
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    client = openmeteo_requests.Client(session = retry_session)
    return client

# --- GridStatus (commented out, hit API limit) ---
def get_load_client():
    client = GridStatusClient(
    max_retries=3,        # Maximum retries (default: 5)
    base_delay=1.0,       # Base delay in seconds (default: 2.0)
    exponential_base=1.5, # Exponential backoff multiplier (default: 2.0)
    api_key = GRIDSTATUS_API_KEY
    )

    return client
def fetch_load(client, start: datetime = START_DATE, end: datetime = END_DATE, write_csv = True) -> pd.DataFrame:
    df = client.get_dataset(
        "spp_load_hourly",
        start = start.isoformat(),
        end = end.isoformat(),
        columns = ["interval_start_utc", "balancing_area_name", "control_zone_name", "forecast_area_type", "load"],
        filter_column = "control_zone_name",
        filter_value = "SYSTEM_TOTAL",
    )

    if write_csv:
        file_name = f"rawgs_{end.isoformat()[:-9]}.csv"
        path = "data/raw/load"
        os.makedirs(path, exist_ok= True)
        df.to_csv(os.path.join(path, file_name), index = False)

    return df

#Batch for large queries
def fetch_load_batches(client, start: datetime = START_DATE, end: datetime = END_DATE, batch_days: int = 60) -> pd.DataFrame:
    all_data = []
    current = start
    while current < end:
        batch_end = min(current + timedelta(days=batch_days), end)
        print(f"Fetching {current.date()} to {batch_end.date()}...")
        try:
            batch_df = fetch_load(client, start=current, end=batch_end)
            if len(batch_df) > 0:
                all_data.append(batch_df)
        except Exception as e:
            if "429" in str(e):
                print(f"  Rate limit hit, waiting 60 seconds...")
                time.sleep(60)
                # Retry the same batch
                batch_df = fetch_load(client, start=current, end=batch_end)
                if len(batch_df) > 0:
                    all_data.append(batch_df)
            else:
                raise
        current = batch_end
        time.sleep(4)  # Stay under 30 requests/minute

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

def read_load_csvs(path: str = "data/raw/load") -> pd.DataFrame:
    files = [f for f in os.listdir(path) if f.endswith(".csv")]

    if not files:
        raise FileNotFoundError(f"No CSV files found in {path}")

    all_dfs = []
    for file in files:
        print(f"Reading {file}...")
        df = pd.read_csv(os.path.join(path, file))
        all_dfs.append(df)

    df = pd.concat(all_dfs, ignore_index=True)
    df.sort_index(inplace = True)
    print(f"Total rows loaded: {len(df)}")

    return df

def clean_load(df: pd.DataFrame) -> pd.DataFrame:
    #make a copy of dataframe?
    df = df.copy()
    #filter out NC load
    #aggregate control zones for total SPP load

    #df = df.groupby("interval_start_utc", as_index = False).agg(load = ("load", "sum"))
    #set the datetime index and frequecy
    df = df.drop_duplicates()
    df.rename(columns = {"interval_start_utc": "date"}, inplace= True)
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%dT%H", utc=True)
    df.set_index("date", inplace = True)

    #remove time zone info
    df.index = df.index.tz_localize(None)
    #df.index.freq = 'h'

    df.rename(columns = {"load": "Demand"}, inplace = True)

    return df[["Demand"]]

def clean_csv_load(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.drop_duplicates()
    df.rename(columns={"interval_start_utc": "date"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"], utc=True)  # format inferred from "2025-10-17 05:00:00+00:00"
    df.set_index("date", inplace=True)
    df.index = df.index.tz_localize(None)
    df.rename(columns={"load": "Demand"}, inplace=True)
    return df[["Demand"]]

# --- EIA Load Pull ---
# DON"T USE BAD DATA
# TODO: double check date format
# EIA's API accepts YYYY-MM-DD for hourly data or prefers YYYY-MM-DDTHH
def make_request(name: str, route: str, params: dict, start: datetime = START_DATE, end: datetime = END_DATE, batch_days: int = 30) -> pd.DataFrame:
    all_dfs = []
    current = start

    while current < end:
        batch_end = min(current + timedelta(days=batch_days), end)

        # EIA expects "YYYY-MM-DD" format for daily batching
        params["start"]  = current.strftime("%Y-%m-%d")
        params["end"]    = batch_end.strftime("%Y-%m-%d")
        params["offset"] = 0
        params["length"] = 5000
        batch_rows = []
        print(f"  {name} {current.date()} to {batch_end.date()}: starting...")

        while True:
            for attempt in range(3):
                try:
                    response = requests.get(route, params=params)
                    response.raise_for_status()
                    break
                except requests.exceptions.HTTPError as e:
                    if response.status_code in (500, 502, 503, 504):
                        wait = 2 ** attempt
                        print(f"    Server error attempt {attempt + 1}, retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        raise
            else:
                raise Exception(f"Failed after 3 attempts — {name} {current.date()} offset {params['offset']}")

            data = response.json()
            rows = data["response"]["data"]
            total = int(data["response"]["total"])
            if not rows:
                break
            batch_rows.extend(rows)
            print(f"  {name} {current.date()} to {batch_end.date()}: fetched {len(batch_rows)} / {total} rows")
            if len(batch_rows) >= total:
                break
            params["offset"] += 5000
            time.sleep(0.5)

        all_dfs.append(pd.DataFrame(batch_rows))
        print(f"  {name} {current.date()} to {batch_end.date()}: complete")
        current = batch_end+timedelta(days=1)

    return pd.concat(all_dfs, ignore_index=True)


def fetch_EIA_load(start: datetime = START_DATE, end: datetime = END_DATE, batch_days: int = 30) -> pd.DataFrame:
    name = "load"
    url = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
    params = {
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": "SWPP",
        "facets[type][]": "D",
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "api_key": EIA_KEY
    }
    df = make_request(name, url, params, start=start, end=end, batch_days=batch_days)
    return df

def clean_EIA_load(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["period"] = pd.to_datetime(df["period"], format="%Y-%m-%dT%H", utc=True)
    df = df.set_index("period")
    df.index.name = "date"
    df.index.freq = "h"
    df.rename(columns = {"value": "Demand"}, inplace = True)
    return df[["Demand"]]

#make one request to weather API and return DF
def fetch_weather(client, start: datetime = START_DATE, end: datetime = END_DATE) -> pd.DataFrame:
    url = "https://archive-api.open-meteo.com/v1/archive"
    lat,lon = WEATHER_LOCATIONS["kansas_city"]
    params = {
    	"latitude": lat,
    	"longitude": lon,
    	"start_date": start.strftime("%Y-%m-%d"),
    	"end_date": end.strftime("%Y-%m-%d"),
    	"hourly": "temperature_2m",
    }
        #"timezone": "America/Chicago"
    responses = client.weather_api(url, params = params)
    response = responses[0]

    #Process hourly data
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    #hourly_is_day = hourly.Variables(1).ValuesAsNumpy()

    hourly_data = {
	"date": pd.date_range(
		start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
		end =  pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
		freq = pd.Timedelta(seconds = hourly.Interval()),
		inclusive = "left"
        )
    }

    hourly_data["Temperature"] = hourly_temperature_2m
    #hourly_data["is_day"] = hourly_is_day
    df = pd.DataFrame(data = hourly_data)

    df.set_index("date", inplace = True)
    df.index = df.index.tz_localize(None)
    #df.index.freq = 'h'

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

        current = batch_end+timedelta(days=1)

    return pd.concat(all_data) if all_data else pd.DataFrame()

def fetch_all_data(start: datetime = START_DATE, end: datetime = END_DATE):

    path = "data/raw/"
    os.makedirs(path, exist_ok= True)

    weather_client = get_weather_client()

    print("Fetching load...")
    #Grid Status Fetch
    #load_client = get_load_client()
    #load_df = fetch_load_batches(load_client, start, end)
    #load_df = clean_load(load_df)

    #read csv files
    load_df = read_load_csvs()
    load_df = clean_csv_load(load_df)

    load_df.to_csv(os.path.join(path, "gsallload.csv"), index = True)
    #EIA fetch
    #load_df = fetch_EIA_load(start, end)
    #load_df = clean_EIA_load(load_df)


    print ("Fetching weather...")
    weather_df = fetch_weather_batches(weather_client, start, end)
    weather_df.to_csv(os.path.join(path, "allweather.csv"), index = True)



    print("Joining load and weather...")
    df = load_df.join(weather_df)
    df.sort_index(inplace=True)
    print("Data pull complete")
    return df

if __name__ == '__main__':
    path = "data/raw/"
    os.makedirs(path, exist_ok= True)
    df = fetch_all_data()
    df.to_csv(os.path.join(path, "gstempload.csv"), index = True)
