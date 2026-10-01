"""Forecast monthly drink revenue per active venue and for the group, from the month after the
latest data to December of the following year (currently Sep 2026 - Dec 2027).

Models compared (per venue, RCI-owned months only):
  snaive    same month last year (the baseline every model must beat)
  ets       Holt-Winters on log revenue, damped trend + seasonality (post-COVID data)
  prophet   Prophet, multiplicative yearly seasonality (history since 2015, COVID months dropped)
  gbm       one global gradient-boosting model trained on all venues: predicts each month's
            revenue relative to the venue's last-12-month level from season, momentum,
            venue type and age (history since 2012, windows touching COVID dropped)
  ensemble  mean of ets, prophet and gbm

Backtest: forecast 12 months ahead from the same month 3, 2 and 1 years before the latest month
(currently Aug 2023, Aug 2024 and Aug 2025) using only data
available at that date, and score against actuals (WAPE = sum|error| / sum actual).
The model with the lowest average venue-level WAPE is used for the final forecast.
Venues with < 24 post-COVID months follow their type's typical post-opening ramp curve.

Outputs (data/intermediate/)
  forecast_backtest.csv       error by model and origin (venue-level and group-level)
  forecast_venue_monthly.csv  actuals + forecast (with 80% range) per venue per month
  forecast_group_monthly.csv  group total actuals + forecast (with approximate 80% range)
  forecast_selected_model.txt the model used for the final forecast (read by 06 and 07)
"""
import logging
import warnings

import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.ensemble import HistGradientBoostingRegressor
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from common import INTERMEDIATE, SELECTED_MODEL, VENUE_MONTH, VENUES, backtest_origins, forecast_year

# Prophet fits ~100 small models: keep its Stan backend quiet. Only the known, harmless
# warnings are silenced (ETS convergence on short or near-zero venue series, and pandas /
# numpy notices raised inside statsmodels and Prophet); anything else still shows.
logging.getLogger("cmdstanpy").disabled = True
logging.getLogger("prophet").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", category=ConvergenceWarning)
warnings.filterwarnings("ignore", module=r"statsmodels\..*")
warnings.filterwarnings("ignore", module=r"prophet\..*")

COVID = (pd.Timestamp("2020-03-01"), pd.Timestamp("2021-06-01"))
POST_COVID = pd.Timestamp("2021-07-01")
PROPHET_FROM = pd.Timestamp("2015-01-01")
GBM_FROM = pd.Timestamp("2012-01-01")
MIN_HISTORY = 24          # post-COVID months needed for a model-based venue forecast
TYPES = ["Gentlemen's club", "Latin-themed club", "Other bar / nightclub", "Sports-bar restaurant"]


def months_between(a: pd.Timestamp, b: pd.Timestamp) -> int:
    return (b.year - a.year) * 12 + b.month - a.month


# ---------------------------------------------------------------- models
def f_snaive(y: pd.Series, idx: pd.DatetimeIndex) -> np.ndarray:
    last_year = y[y.index > y.index[-1] - pd.DateOffset(months=12)]
    by_month = dict(zip(last_year.index.month, last_year.values))
    return np.array([by_month[m.month] for m in idx])


def f_ets(y: pd.Series, idx: pd.DatetimeIndex) -> np.ndarray:
    # Fitted on log revenue (additive in logs = multiplicative seasonality), which stays
    # stable when a venue has near-zero months; fall back to the baseline if it runs away.
    y = y[y.index >= POST_COVID]
    model = ExponentialSmoothing(np.log1p(y.values), trend="add", damped_trend=True, seasonal="add",
                                 seasonal_periods=12, initialization_method="estimated").fit()
    pred = np.expm1(model.forecast(len(idx)))
    if not np.isfinite(pred).all() or pred.max() > 3 * y.max():
        return f_snaive(y, idx)
    return np.clip(pred, 0, None)


def f_prophet(y: pd.Series, idx: pd.DatetimeIndex) -> np.ndarray:
    y = y[(y.index >= PROPHET_FROM) & ~((y.index >= COVID[0]) & (y.index <= COVID[1]))]
    df = pd.DataFrame({"ds": y.index, "y": y.values})
    m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False,
                seasonality_mode="multiplicative", changepoint_prior_scale=0.1)
    m.fit(df)
    return np.clip(m.predict(pd.DataFrame({"ds": idx}))["yhat"].values, 0, None)


def gbm_features(y: pd.Series, origin: pd.Timestamp, h: int, vtype: str, entry: pd.Timestamp):
    """Features known at `origin` for predicting month origin + h (None if not enough history)."""
    hist = y[y.index <= origin]
    if len(hist) < 24 or hist.index[-24] != origin - pd.DateOffset(months=23):
        return None
    level = hist.iloc[-12:].mean()
    if level <= 0:
        return None
    target = origin + pd.DateOffset(months=h)
    same_month = target - pd.DateOffset(months=12 * ((h - 1) // 12 + 1))
    season = hist.get(same_month, np.nan)
    prev_level = hist.iloc[-24:-12].mean()
    return {
        "h": h, "month": target.month, "type": TYPES.index(vtype),
        "season_ratio": np.log((season + 1) / (level + 1)),
        "momentum": np.log((hist.iloc[-3:].sum() + 1) / (hist.iloc[-15:-12].sum() + 1)),
        "level_trend": np.log((level + 1) / (prev_level + 1)),
        "age": min(months_between(entry, origin), 120),
        "log_level": np.log(level + 1),
    }, level


def touches_covid(start: pd.Timestamp, end: pd.Timestamp) -> bool:
    return start <= COVID[1] and end >= COVID[0]


def train_gbm(series: dict, meta: pd.DataFrame, cutoff: pd.Timestamp, horizon: int):
    rows, targets = [], []
    for v, y in series.items():
        vtype, entry = meta.loc[v, "venue_type"], meta.loc[v, "rci_first_month"]
        y = y[(y.index >= GBM_FROM) & (y.index <= cutoff)]
        for origin in y.index[23:]:
            for h in range(1, horizon + 1):
                target = origin + pd.DateOffset(months=h)
                if target > cutoff or target not in y.index:
                    continue
                if touches_covid(origin - pd.DateOffset(months=23), target):
                    continue
                f = gbm_features(y, origin, h, vtype, entry)
                if f is None:
                    continue
                rows.append(f[0])
                targets.append(np.log((y[target] + 1) / (f[1] + 1)))
    X = pd.DataFrame(rows)
    model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                          min_samples_leaf=40, l2_regularization=1.0,
                                          categorical_features=[X.columns.get_loc("type")],
                                          random_state=0)
    model.fit(X, targets)
    return model


def f_gbm(model, y: pd.Series, idx: pd.DatetimeIndex, vtype: str, entry: pd.Timestamp) -> np.ndarray:
    origin = y.index[-1]
    out = []
    for target in idx:
        f = gbm_features(y, origin, months_between(origin, target), vtype, entry)
        if f is None:
            return None
        out.append(np.exp(model.predict(pd.DataFrame([f[0]]))[0]) * (f[1] + 1) - 1)
    return np.clip(np.array(out), 0, None)


def forecast_all(series: dict, meta: pd.DataFrame, origin: pd.Timestamp, idx: pd.DatetimeIndex,
                 gbm) -> dict:
    """Forecasts from every model for every venue with enough history at `origin`."""
    out = {}
    for v, y_full in series.items():
        y = y_full[y_full.index <= origin]
        if len(y) == 0 or y.index[-1] != origin or (y.index >= POST_COVID).sum() < MIN_HISTORY:
            continue
        vtype, entry = meta.loc[v, "venue_type"], meta.loc[v, "rci_first_month"]
        preds = {"snaive": f_snaive(y, idx), "ets": f_ets(y, idx), "prophet": f_prophet(y, idx)}
        g = f_gbm(gbm, y, idx, vtype, entry)
        preds["gbm"] = g if g is not None else preds["ets"]
        preds["ensemble"] = np.mean([preds["ets"], preds["prophet"], preds["gbm"]], axis=0)
        out[v] = preds
    return out


def ramp_forecast(y: pd.Series, idx: pd.DatetimeIndex, entry: pd.Timestamp,
                  ramp: pd.Series, season: pd.Series) -> np.ndarray:
    """Young venues: follow the type's typical path after opening (e.g. the opening
    'honeymoon' fading), scaled to how this venue is doing vs that path, with type seasonality."""
    ramp = ramp.rolling(3, center=True, min_periods=1).mean()
    age = lambda t: min(months_between(entry, t) + 1, ramp.index.max())
    recent = y.iloc[-3:]
    scale = (recent / (ramp.loc[[age(t) for t in recent.index]].values
                       * season.loc[recent.index.month].values)).mean()
    return scale * ramp.loc[[age(t) for t in idx]].values * season.loc[idx.month].values


# ---------------------------------------------------------------- main
def main() -> None:
    vm = pd.read_csv(VENUE_MONTH, parse_dates=["month"])
    venues = pd.read_csv(VENUES, parse_dates=["rci_first_month"]).set_index("venue_name")
    rci = vm[vm["owner_period"] == "RCI"]
    latest = rci["month"].max()
    fy = forecast_year(latest)
    forecast_end = pd.Timestamp(f"{fy}-12-01")
    series = {v: g.set_index("month")["total"].asfreq("MS").fillna(0) for v, g in rci.groupby("venue_name")}
    season = pd.read_csv(INTERMEDIATE / "seasonality.csv").pivot(index="month_num", columns="venue_type",
                                                             values="seasonality_index")
    ramp = pd.read_csv(INTERMEDIATE / "ramp_curves.csv").set_index(["venue_type", "months_since_entry"])
    models = ["snaive", "ets", "prophet", "gbm", "ensemble"]

    # ---- backtest
    bt_rows, err_rows = [], []
    for origin in backtest_origins(latest):
        idx = pd.date_range(origin + pd.DateOffset(months=1), periods=12, freq="MS")
        gbm = train_gbm(series, venues, origin, 16)
        fc = forecast_all(series, venues, origin, idx, gbm)
        fc = {v: p for v, p in fc.items() if set(idx) <= set(series[v].index)}   # still trading
        actual = {v: series[v].loc[idx].values for v in fc}
        for m in models:
            abs_err = sum(np.abs(fc[v][m] - actual[v]).sum() for v in fc)
            tot = sum(actual[v].sum() for v in fc)
            g_pred = np.sum([fc[v][m] for v in fc], axis=0)
            g_act = np.sum([actual[v] for v in fc], axis=0)
            bt_rows.append({"origin": origin, "model": m, "venues": len(fc),
                            "venue_wape": abs_err / tot,
                            "group_monthly_wape": np.abs(g_pred - g_act).sum() / g_act.sum(),
                            "group_12m_total_error_pct": g_pred.sum() / g_act.sum() - 1})
            for v in fc:
                for i, t in enumerate(idx):
                    err_rows.append({"model": m, "origin": origin, "venue_name": v, "h": i + 1,
                                     "ratio": (actual[v][i] + 1) / (fc[v][m][i] + 1)})
        print(f"backtest origin {origin:%b %Y}: {len(fc)} venues")
    bt = pd.DataFrame(bt_rows)
    summary = bt.groupby("model")[["venue_wape", "group_monthly_wape", "group_12m_total_error_pct"]].mean()
    summary["group_12m_abs_error_pct"] = bt.assign(a=bt["group_12m_total_error_pct"].abs()).groupby("model")["a"].mean()
    best = summary["venue_wape"].idxmin()
    print("\nBacktest (mean of 3 origins):")
    print(summary.sort_values("venue_wape").to_string(float_format="{:.1%}".format))
    beats = summary.loc[best, "venue_wape"] < summary.loc["snaive", "venue_wape"]
    print(f"\nSelected model: {best} ({'beats' if beats else 'does NOT beat'} the seasonal-naive baseline)")
    if not beats:
        best = "snaive"

    # ---- 80% ranges from backtest errors of the selected model (by horizon)
    errs = pd.DataFrame(err_rows)
    errs = errs[errs["model"] == best]
    venue_q = errs.groupby("h")["ratio"].quantile([0.1, 0.9]).unstack()
    grp = bt[bt["model"] == best]

    # ---- final forecast
    idx = pd.date_range(latest + pd.DateOffset(months=1), forecast_end, freq="MS")
    horizon = len(idx)
    gbm = train_gbm(series, venues, latest, horizon)
    active = venues[venues["status"] == "Active"].index
    fc = forecast_all({v: series[v] for v in active}, venues, latest, idx, gbm)
    rows = []
    for v in active:
        y = series[v]
        if v in fc:
            pred, method = fc[v][best], best
        else:
            vtype = venues.loc[v, "venue_type"]
            pred = ramp_forecast(y, idx, venues.loc[v, "rci_first_month"],
                                 ramp.loc[vtype, "median_revenue"], season[vtype])
            method = "ramp curve (young venue)"
        h = np.minimum(np.arange(1, horizon + 1), 12)
        lo = pred * venue_q.loc[h, 0.1].values
        hi = pred * venue_q.loc[h, 0.9].values
        rows += [{"venue_name": v, "month": t, "forecast": p, "forecast_low": l, "forecast_high": u,
                  "method": method} for t, p, l, u in zip(idx, pred, lo, hi)]
    f = pd.DataFrame(rows)
    hist = rci[rci["venue_name"].isin(active)][["venue_name", "month", "total"]].rename(columns={"total": "actual"})
    venue_out = pd.concat([hist, f], ignore_index=True).merge(
        venues[["venue_type"]], left_on="venue_name", right_index=True).sort_values(["venue_name", "month"])
    venue_out.to_csv(INTERMEDIATE / "forecast_venue_monthly.csv", index=False)

    # Group: actuals from all RCI venues; forecast = sum of active venues.
    # Approximate 80% range: +/- the selected model's worst monthly group WAPE across the back-tests
    # (at least 3%), widened with the horizon (sqrt ramp over the first 12 months, then +1/24 a month).
    # A rule of thumb, not a fitted interval.
    g_act = rci.groupby("month")["total"].sum().rename("actual")
    g_fc = f.groupby("month")[["forecast"]].sum()
    spread = max(grp["group_monthly_wape"].max(), 0.03)
    widen = np.sqrt(np.minimum(np.arange(1, horizon + 1), 12) / 12) + np.maximum(np.arange(1, horizon + 1) - 12, 0) / 24
    g_fc["forecast_low"] = g_fc["forecast"] * (1 - spread * widen)
    g_fc["forecast_high"] = g_fc["forecast"] * (1 + spread * widen)
    group_out = pd.concat([g_act, g_fc], axis=1).reset_index().rename(columns={"index": "month"})
    group_out.to_csv(INTERMEDIATE / "forecast_group_monthly.csv", index=False)
    bt.to_csv(INTERMEDIATE / "forecast_backtest.csv", index=False)
    SELECTED_MODEL.write_text(best + "\n")

    cy = group_out.assign(year=group_out["month"].dt.year)
    by_year = cy.groupby("year")[["actual", "forecast"]].sum().loc[[fy - 2, fy - 1, fy]] / 1e6
    print("\nGroup drink revenue ($M): actual / forecast")
    print(by_year.round(2).to_string())
    print(f"{fy - 1} = actual Jan-{latest:%b} + forecast; {fy} = forecast "
          f"(80% range ${g_fc.loc[str(fy), 'forecast_low'].sum() / 1e6:,.1f}M - ${g_fc.loc[str(fy), 'forecast_high'].sum() / 1e6:,.1f}M)")
    print("Methods:", f.groupby("method")["venue_name"].nunique().to_dict())


if __name__ == "__main__":
    main()
