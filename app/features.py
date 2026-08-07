import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar as calendar


def set_holidays(df):
    cal = calendar()
    holidays = cal.holidays(start = df.index.min(), end = df.index.max())
    df["Holiday"]= df.index.isin(holidays)
    return df

def cal_features(df):
    df = df.assign(
            month = lambda df: df.index.month,
            week = lambda df: df.index.isocalendar().week,
            day_of_week = lambda df: df.index.day_of_week,
            hour = lambda df: df.index.hour
            )
    return df

def cyclic_features(df):
    df = df.assign(
        month_sin = lambda df: np.sin(2 * np.pi * df["month"] / 12),
        month_cos = lambda df: np.cos(2 * np.pi * df["month"] / 12),
        week_sin = lambda df: np.sin(2 * np.pi * df["week"] / 52),
        week_cos = lambda df: np.cos(2 * np.pi * df["week"] / 52),
        day_sin = lambda df: np.sin(2 * np.pi * df["day_of_week"] / 7),
        day_cos = lambda df: np.cos(2 * np.pi * df["day_of_week"] / 7),
        hour_sin = lambda df: np.sin(2 * np.pi * df["hour"] / 24),
        hour_cos = lambda df: np.cos(2 * np.pi * df["hour"] / 24)
    )
    return df
