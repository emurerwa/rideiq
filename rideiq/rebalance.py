"""Turn demand forecasts into a truck rebalancing plan."""
import numpy as np
import pandas as pd


def to_wide(fc: pd.DataFrame) -> pd.DataFrame:
    """Long forecasts -> one row per station-hour with pred_departures / pred_arrivals."""
    w = fc.pivot_table(index=["station_id", "hour"], columns="target", values="pred").reset_index()
    return w.rename(columns={"departures": "pred_departures", "arrivals": "pred_arrivals"})


def _km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


def plan_moves(wide, stations, asof, horizon=6, start_fill=0.5, low=0.15, high=0.85, start_bikes=None):
    """Project inventory over the next `horizon` hours, flag shortages and surpluses, match them greedily.

    start_bikes: optional Series (station_id -> bikes now), e.g. from live GBFS. Defaults to start_fill * capacity.
    Shortage: projected bikes < low * capacity, refilled to 30%. Surplus: > high * capacity, drawn down to 70%.
    """
    asof = pd.Timestamp(asof)
    w = wide[(wide["hour"] > asof) & (wide["hour"] <= asof + pd.Timedelta(hours=horizon))].copy()
    w["net"] = w["pred_arrivals"] - w["pred_departures"]
    net = w.groupby("station_id")["net"].sum().rename("net_flow")

    r = stations.merge(net, on="station_id")
    if start_bikes is not None:
        r["start_bikes"] = r["station_id"].map(start_bikes).fillna(start_fill * r["capacity"])
    else:
        r["start_bikes"] = start_fill * r["capacity"]
    r["end_bikes"] = r["start_bikes"] + r["net_flow"]
    r["status"] = np.where(r["end_bikes"] < low * r["capacity"], "shortage",
                  np.where(r["end_bikes"] > high * r["capacity"], "surplus", "ok"))

    recv = r[r["status"] == "shortage"].copy()
    recv["need"] = np.ceil(0.30 * recv["capacity"] - recv["end_bikes"]).astype(int)
    donors = r[r["status"] == "surplus"].copy()
    donors["avail"] = np.minimum(np.ceil(donors["end_bikes"] - 0.70 * donors["capacity"]), donors["start_bikes"]).astype(int)
    donors = donors.set_index("station_id")

    moves = []
    for _, rc in recv.sort_values("need", ascending=False).iterrows():
        need = int(rc["need"])
        d = donors[donors["avail"] > 0]
        if d.empty:
            break
        km = _km(rc["lat"], rc["lon"], d["lat"].values, d["lon"].values)
        order = np.argsort(km)
        for sid, dist in zip(d.index[order], km[order]):
            if need <= 0:
                break
            q = int(min(need, donors.at[sid, "avail"]))
            if q > 0:
                moves.append({"from_station": sid, "to_station": rc["station_id"], "bikes": q, "km": round(float(dist), 2)})
                donors.at[sid, "avail"] -= q
                need -= q
    return r, pd.DataFrame(moves, columns=["from_station", "to_station", "bikes", "km"])
