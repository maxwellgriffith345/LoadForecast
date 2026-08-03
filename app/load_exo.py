
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


from features import set_holidays, cal_features, cyclic_features
from datetime import datetime
from datetime import timedelta

WEATHER_LOCATIONS = {
    "kansas_city": (39.0997, -94.5786),
}

def get_date_ranges(day_one = None):
    dates = {}
    if day_one is None:
        day_one = datetime.today().replace(hour = 0, minute = 0, second = 0, microsecond = 0)
    else:
        day_one = day_one.replace(hour = 0, minute = 0, second = 0, microsecond = 0)

    dates["today"] = day_one
    #D-1 midnight to D-1 11pm
    lw_start = day_one-timedelta(days = 8)
    dates["lw_start"] = lw_start
    lw_end = day_one - timedelta(hours = 1)
    dates["lw_end"] = lw_end

    dates["exo_start"] = day_one
    exo_end = day_one + timedelta(hours = 47)
    dates["exo_end"] = exo_end

    return dates

def get_weather_client(): #No API Key needed
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    client = openmeteo_requests.Client(session = retry_session)
    return client

# CHANGE THIS URL
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
