import pandas as pd

from rideiq.data import make_demo
from rideiq.db import connect, query
from rideiq.forecast import fit_eval
from rideiq.rebalance import plan_moves, to_wide


def _setup(tmp_path, days=21, stations=8):
    trips, st = make_demo(days=days, n_stations=stations, seed=1)
    trips.to_parquet(tmp_path / "t.parquet")
    st.to_parquet(tmp_path / "s.parquet")
    con = connect(tmp_path / "t.parquet", tmp_path / "s.parquet")
    return trips, st, query(con, "hourly_flows")


def test_flow_grid_is_complete_and_conserves_trips(tmp_path):
    trips, st, flows = _setup(tmp_path)
    hours = flows["hour"].nunique()
    assert len(flows) == hours * len(st)
    assert flows["departures"].sum() == len(trips)


def test_forecast_beats_baseline(tmp_path):
    _, _, flows = _setup(tmp_path)
    _, out, m = fit_eval(flows, "departures")
    assert m["mae"] < m["baseline_mae"]
    assert (out["pred"] >= 0).all()


def test_rebalance_moves_are_valid(tmp_path):
    _, st, flows = _setup(tmp_path)
    fcs = pd.concat([fit_eval(flows, t)[1] for t in ("departures", "arrivals")])
    wide = to_wide(fcs)
    asof = sorted(wide["hour"].unique())[10]
    risk, moves = plan_moves(wide, st, asof)
    assert set(risk["status"]) <= {"ok", "shortage", "surplus"}
    assert (moves["bikes"] > 0).all()
    assert moves["from_station"].isin(st["station_id"]).all()
