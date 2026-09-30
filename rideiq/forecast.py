import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .features import FEATURES, add_features


def fit_eval(flows: pd.DataFrame, target: str, test_frac: float = 0.2, seed: int = 0):
    """Time-ordered split. Gradient boosting (Poisson loss) vs a same-hour-last-week baseline."""
    df = add_features(flows, target).dropna(subset=FEATURES)
    hours = np.sort(df["hour"].unique())
    cutoff = hours[int(len(hours) * (1 - test_frac))]
    train, test = df[df["hour"] < cutoff], df[df["hour"] >= cutoff].copy()

    model = HistGradientBoostingRegressor(
        loss="poisson",
        max_iter=300,
        learning_rate=0.08,
        categorical_features=["station_code"],
        random_state=seed,
    )
    model.fit(train[FEATURES], train[target])
    test["pred"] = model.predict(test[FEATURES])
    test["baseline"] = test["lag_168"]
    test["actual"] = test[target]

    mae = float(np.mean(np.abs(test["actual"] - test["pred"])))
    base = float(np.mean(np.abs(test["actual"] - test["baseline"])))
    metrics = {
        "target": target,
        "mae": round(mae, 4),
        "baseline_mae": round(base, 4),
        "improvement_pct": round(100 * (base - mae) / base, 1),
        "test_start": str(pd.Timestamp(cutoff)),
        "n_test_rows": int(len(test)),
    }
    out = test[["station_id", "hour", "actual", "pred", "baseline"]].assign(target=target)
    return model, out, metrics
