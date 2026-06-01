import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from config import GRIDSTATUS_API_KEY
from gridstatusio import GridStatusClient


"""Extract Load data"""
#Batch for large queries
def fetch_in_batches(client, dataset: str,start: datetime,end: datetime, batch_days: int = 7, **kwargs) -> pd.DataFrame:
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
def fetch_load(): -> pd.DataFrame:
    client = GridStatusClient(api_key = GRIDSTATUS_API_KEY)

    df = fetch_in_batches(
        client,
        "spp_load_hourly",
        datetime(2025, 1, 1),
        datetime(2025, 2, 1),
        batch_days=7,
        columns = ["interval_start_utc", "balancing_area_name", "control_zone_name", "forecast_area_type", "load"],
        filter_column = "balancing_area_name",
        filter_value = "SPP",
        limit=100
    )

    return df
