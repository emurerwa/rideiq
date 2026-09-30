# RideIQ

Citi Bike demand forecasting and rebalancing analytics. It turns raw trip records into hourly station demand forecasts, then into a concrete truck plan: which stations will run out of bikes, which will fill up, and what to move where.

```
trips + stations (parquet)
        |
   DuckDB SQL  (sql/hourly_flows.sql)   hourly departures and arrivals per station
        |
  Python features + HistGradientBoosting (Poisson loss), one model per direction
        |
  Rebalancer: project inventory over N hours, match surplus to shortage by distance
        |
  Streamlit dashboard: Overview, Forecast, Rebalancing, Live feed (GBFS)
```

## Quickstart

```bash
pip install -r requirements.txt
python -m rideiq.pipeline --demo      # builds data, flows, forecasts, sample plan
streamlit run dashboard/app.py
pytest
```

`--demo` uses a built-in simulator (commute peaks, weekend leisure, weather noise, residential vs business stations) so the whole project runs offline in about a minute.

## Use real Citi Bike data

Download monthly trip files from the public Citi Bike S3 bucket (listed at citibikenyc.com/system-data), unzip the CSVs, then:

```bash
python -m rideiq.pipeline --trips "data/real/*-citibike-tripdata.csv"
```

The loader expects the post-2021 schema (`ride_id`, `started_at`, `ended_at`, `start_station_id`, `end_station_id`, lat/lng columns). It keeps the 150 busiest stations and assumes capacity 40 unless you join capacities from GBFS `station_information`. Live availability in the dashboard comes from `gbfs.citibikenyc.com`.

## Results on demo data

Time-ordered split, last 20% of hours held out. Baseline is the same hour last week.

| Target | MAE | Baseline MAE | Improvement |
|---|---|---|---|
| Departures | 1.63 | 2.16 | 24.7% |
| Arrivals | 1.60 | 2.14 | 25.0% |

These numbers come from simulated data and show the pipeline works, not how it performs on the real system. Rerun with real trips for honest figures.

## Layout

| Path | What it does |
|---|---|
| `sql/` | All aggregation logic, kept in SQL and run through DuckDB |
| `rideiq/data.py` | Simulator and real-data loaders |
| `rideiq/features.py` | Lag, rolling, and calendar features (past values only) |
| `rideiq/forecast.py` | Model training and evaluation against the seasonal baseline |
| `rideiq/rebalance.py` | Inventory projection and greedy truck matching |
| `rideiq/gbfs.py` | Live station status |
| `dashboard/app.py` | Multi-tab Streamlit app |

## Known limits and next steps

- Rebalancer starts from an assumed fill level unless live bikes are passed in via `start_bikes`.
- Greedy matching is simple. A vehicle routing formulation with truck capacity and time windows is the natural upgrade.
- No weather or event features yet.
- Forecasts are point estimates. Quantile forecasts would let the plan target a stockout probability.

## License

MIT
