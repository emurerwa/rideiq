import numpy as np
import pandas as pd

LAGS = (1, 2, 24, 168)


def add_features(flows: pd.DataFrame, target: str) -> pd.DataFrame:
    """Calendar + lag features for one target (departures or arrivals). Only past values are used."""
    df = flows.sort_values(["station_id", "hour"]).copy()
    g = df.groupby("station_id")[target]
    for lag in LAGS:
        df[f"lag_{lag}"] = g.shift(lag)
    df["roll_24"] = g.transform(lambda s: s.shift(1).rolling(24).mean())
    df["hod"] = df["hour"].dt.hour
    df["dow"] = df["hour"].dt.dayofweek
    df["is_weekend"] = (df["dow"] >= 5).astype(int)
    df["hod_sin"] = np.sin(2 * np.pi * df["hod"] / 24)
    df["hod_cos"] = np.cos(2 * np.pi * df["hod"] / 24)
    df["station_code"] = df["station_id"].astype("category").cat.codes
    return df


FEATURES = [f"lag_{l}" for l in LAGS] + ["roll_24", "hod", "dow", "is_weekend", "hod_sin", "hod_cos", "station_code"]
