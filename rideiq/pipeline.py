"""End to end: data -> SQL flows -> forecasts -> sample rebalancing plan.

    python -m rideiq.pipeline --demo
    python -m rideiq.pipeline --trips "data/real/*-citibike-tripdata.csv"
"""
import argparse
import json

import pandas as pd

from .config import PROCESSED, RAW
from .data import load_real_trips, make_demo, stations_from_trips
from .db import connect, query
from .forecast import fit_eval
from .rebalance import plan_moves, to_wide


def default_asof(fc: pd.DataFrame) -> pd.Timestamp:
    """First weekday 07:00 in the test window, the morning rush where rebalancing matters most."""
    hrs = pd.Series(sorted(fc["hour"].unique()))
    pick = hrs[(hrs.dt.hour == 7) & (hrs.dt.dayofweek < 5)]
    return pick.iloc[0] if len(pick) else hrs.iloc[len(hrs) // 2]


def run(trips_glob: str | None = None, days: int = 45):
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    if trips_glob:
        trips = load_real_trips(trips_glob)
        stations = stations_from_trips(trips)
        keep = trips["start_station_id"].isin(stations["station_id"]) & trips["end_station_id"].isin(stations["station_id"])
        trips = trips[keep][["ride_id", "started_at", "ended_at", "start_station_id", "end_station_id", "member_casual"]]
    else:
        trips, stations = make_demo(days=days)
    trips.to_parquet(RAW / "trips.parquet", index=False)
    stations.to_parquet(RAW / "stations.parquet", index=False)

    con = connect()
    flows = query(con, "hourly_flows")
    flows.to_parquet(PROCESSED / "flows.parquet", index=False)

    parts, metrics = [], []
    for target in ("departures", "arrivals"):
        _, out, m = fit_eval(flows, target)
        parts.append(out)
        metrics.append(m)
        print(f"{target}: MAE {m['mae']} vs baseline {m['baseline_mae']} ({m['improvement_pct']}% better)")
    fc = pd.concat(parts, ignore_index=True)
    fc.to_parquet(PROCESSED / "forecasts.parquet", index=False)
    (PROCESSED / "metrics.json").write_text(json.dumps(metrics, indent=2))

    asof = default_asof(fc)
    risk, moves = plan_moves(to_wide(fc), stations, asof)
    moves.to_csv(PROCESSED / "sample_moves.csv", index=False)
    print(f"Sample plan as of {asof}: {(risk.status == 'shortage').sum()} shortages, "
          f"{(risk.status == 'surplus').sum()} surpluses, {len(moves)} moves, {moves['bikes'].sum()} bikes")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use synthetic data (default when --trips is absent)")
    ap.add_argument("--trips", help="glob of real Citi Bike trip files")
    ap.add_argument("--days", type=int, default=45)
    a = ap.parse_args()
    run(a.trips, a.days)
