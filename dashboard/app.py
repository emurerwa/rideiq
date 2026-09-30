import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from rideiq.config import PROCESSED, RAW
from rideiq.db import connect, query
from rideiq.gbfs import fetch_live_status
from rideiq.rebalance import plan_moves, to_wide

st.set_page_config(page_title="RideIQ", layout="wide")
st.title("RideIQ: Citi Bike demand forecasting and rebalancing")

if not (PROCESSED / "forecasts.parquet").exists():
    st.error("No outputs yet. Run `python -m rideiq.pipeline --demo` first.")
    st.stop()


@st.cache_resource
def get_con():
    return connect()


@st.cache_data
def load():
    fc = pd.read_parquet(PROCESSED / "forecasts.parquet")
    stations = pd.read_parquet(RAW / "stations.parquet")
    metrics = json.loads((PROCESSED / "metrics.json").read_text())
    return fc, stations, metrics


fc, stations, metrics = load()
con = get_con()
tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Forecast", "Rebalancing", "Live feed"])

with tab1:
    trips_n = con.execute("SELECT count(*) FROM trips").fetchone()[0]
    c1, c2 = st.columns(2)
    c1.metric("Trips", f"{trips_n:,}")
    c2.metric("Stations", len(stations))
    peak = query(con, "peak_hours").pivot(index="hour_of_day", columns="day_type", values="avg_trips")
    st.subheader("Average trips by hour of day")
    st.line_chart(peak)
    st.subheader("Busiest stations")
    st.dataframe(query(con, "station_summary"), width="stretch")

with tab2:
    m = pd.DataFrame(metrics).set_index("target")[["mae", "baseline_mae", "improvement_pct"]]
    st.dataframe(m)
    c1, c2 = st.columns(2)
    sid = c1.selectbox("Station", stations["station_id"])
    tgt = c2.radio("Target", ["departures", "arrivals"], horizontal=True)
    d = fc[(fc["station_id"] == sid) & (fc["target"] == tgt)].sort_values("hour").tail(7 * 24)
    st.line_chart(d.set_index("hour")[["actual", "pred", "baseline"]])

with tab3:
    wide = to_wide(fc)
    hours = sorted(wide["hour"].unique())
    asof = st.select_slider("Plan as of", options=hours, value=hours[len(hours) // 2])
    c1, c2, c3 = st.columns(3)
    horizon = c1.slider("Horizon (hours)", 3, 12, 6)
    fill = c2.slider("Starting fill", 0.2, 0.8, 0.5)
    c3.caption("Shortage below 15% of capacity, surplus above 85%.")
    risk, moves = plan_moves(wide, stations, asof, horizon=horizon, start_fill=fill)
    k1, k2, k3 = st.columns(3)
    k1.metric("Shortages", int((risk.status == "shortage").sum()))
    k2.metric("Surpluses", int((risk.status == "surplus").sum()))
    k3.metric("Bikes to move", int(moves["bikes"].sum()))
    st.dataframe(moves, width="stretch")
    flagged = risk[risk.status != "ok"]
    if len(flagged):
        st.map(flagged[["lat", "lon"]])

with tab4:
    st.caption("Pulls current availability from the public GBFS feed. Needs internet access.")
    if st.button("Fetch live status"):
        try:
            live = fetch_live_status()
            st.metric("Stations reporting", len(live))
            st.dataframe(live.sort_values("fill_pct").head(25), width="stretch")
        except Exception as e:
            st.warning(f"Could not reach GBFS: {e}")
