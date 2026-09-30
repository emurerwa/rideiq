"""Trip data: a synthetic generator (works offline) and a loader for real Citi Bike files."""
from __future__ import annotations

from glob import glob

import numpy as np
import pandas as pd


def make_demo(days: int = 45, n_stations: int = 30, seed: int = 7, start: str = "2025-06-02"):
    """Simulate Citi Bike style trips with commute peaks, weekend leisure, and weather noise.

    Residential stations (bias > 0) send riders out in the morning and receive them in the
    evening. Business stations (bias < 0) do the opposite. That is what makes rebalancing matter.
    """
    rng = np.random.default_rng(seed)
    S = n_stations
    pop = rng.lognormal(0, 0.5, S)
    bias = rng.uniform(-1, 1, S)
    stations = pd.DataFrame(
        {
            "station_id": [f"S{i:03d}" for i in range(S)],
            "name": [f"Demo Station {i:03d}" for i in range(S)],
            "lat": 40.70 + rng.uniform(0, 0.10, S),
            "lon": -74.02 + rng.uniform(0, 0.08, S),
            "capacity": rng.integers(20, 60, S),
        }
    )

    hours = pd.date_range(start, periods=days * 24, freq="h")
    T = len(hours)
    h, dow = hours.hour.values, hours.dayofweek.values
    wd = dow < 5
    prof = np.where(
        wd,
        0.25 + 1.6 * np.exp(-((h - 8.5) ** 2) / 4) + 1.4 * np.exp(-((h - 17.5) ** 2) / 5) + 0.3 * np.exp(-((h - 12.5) ** 2) / 6),
        0.2 + 1.1 * np.exp(-((h - 14) ** 2) / 18),
    )
    morning = (wd & (h >= 6) & (h <= 10)).astype(float)
    evening = (wd & (h >= 16) & (h <= 19)).astype(float)
    daily = np.exp(rng.normal(0, 0.15, days))[np.arange(T) // 24]
    season = 1 + 0.25 * np.sin(np.pi * np.arange(T) / T)
    tmult = (prof * daily * season)[:, None]
    shape = 1 + 0.6 * bias[None, :] * morning[:, None] - 0.6 * bias[None, :] * evening[:, None]
    rates = 6.0 * pop[None, :] * tmult * shape

    flat = rng.poisson(rates).ravel()
    idx = np.repeat(np.arange(flat.size), flat)
    t, s = idx // S, idx % S
    n = len(idx)

    kind = np.where(morning[t] == 1, 0, np.where(evening[t] == 1, 1, 2))
    weights = [
        np.clip(pop * (1 - 0.6 * bias), 0.05, None),
        np.clip(pop * (1 + 0.6 * bias), 0.05, None),
        pop,
    ]
    dest = np.empty(n, dtype=int)
    for k, w in enumerate(weights):
        m = kind == k
        dest[m] = rng.choice(S, size=m.sum(), p=w / w.sum())

    started = hours[t] + pd.to_timedelta(rng.integers(0, 3600, n), unit="s")
    minutes = np.clip(rng.lognormal(np.log(11), 0.5, n), 2, 90)
    ids = stations["station_id"].values
    trips = pd.DataFrame(
        {
            "ride_id": np.arange(n),
            "started_at": started,
            "ended_at": started + pd.to_timedelta(minutes, unit="m"),
            "start_station_id": ids[s],
            "end_station_id": ids[dest],
            "member_casual": np.where(rng.random(n) < np.where(wd[t], 0.82, 0.6), "member", "casual"),
        }
    )
    return trips, stations


def load_real_trips(path_glob: str) -> pd.DataFrame:
    """Load one or more Citi Bike trip files (csv, or single-file zip) using the post-2021 schema."""
    frames = []
    for p in sorted(glob(path_glob)):
        df = pd.read_csv(p, low_memory=False, parse_dates=["started_at", "ended_at"])
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No files matched {path_glob}")
    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["start_station_id", "end_station_id"])
    df["start_station_id"] = df["start_station_id"].astype(str)
    df["end_station_id"] = df["end_station_id"].astype(str)
    if "member_casual" not in df:
        df["member_casual"] = "member"
    return df


def stations_from_trips(trips: pd.DataFrame, max_stations: int = 150, default_capacity: int = 40) -> pd.DataFrame:
    """Derive a station table from real trips (busiest stations only) and filter trips to match."""
    top = trips["start_station_id"].value_counts().head(max_stations).index
    g = trips[trips["start_station_id"].isin(top)].groupby("start_station_id")
    st = g.agg(name=("start_station_name", "first"), lat=("start_lat", "mean"), lon=("start_lng", "mean")).reset_index()
    st = st.rename(columns={"start_station_id": "station_id"})
    st["capacity"] = default_capacity
    return st
