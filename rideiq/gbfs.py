"""Live Citi Bike availability from the public GBFS feed."""
import pandas as pd
import requests

BASE = "https://gbfs.citibikenyc.com/gbfs/en"


def fetch_live_status(timeout: int = 10) -> pd.DataFrame:
    status = requests.get(f"{BASE}/station_status.json", timeout=timeout).json()["data"]["stations"]
    info = requests.get(f"{BASE}/station_information.json", timeout=timeout).json()["data"]["stations"]
    s = pd.DataFrame(status)[["station_id", "num_bikes_available", "num_docks_available"]]
    i = pd.DataFrame(info)[["station_id", "name", "lat", "lon", "capacity"]]
    df = s.merge(i, on="station_id")
    df["fill_pct"] = (df["num_bikes_available"] / df["capacity"].where(df["capacity"] > 0)).round(2)
    return df
