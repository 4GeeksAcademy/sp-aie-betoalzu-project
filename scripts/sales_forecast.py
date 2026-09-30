"""Forecast consolidated monthly revenue with a fixed, unseen two-year holdout."""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error


DATASET = Path(__file__).resolve().parents[1] / "data/raw/nexova_sales.csv"


def load_sales(path: Path = DATASET) -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["month"])
    frame = frame.loc[frame["business_line"] == "consolidated", ["month", "revenue_usd"]]
    if frame["month"].isna().any() or frame["month"].duplicated().any():
        raise ValueError("Sales months must be present and unique")
    frame = frame.sort_values("month").set_index("month")
    revenue = pd.to_numeric(frame["revenue_usd"], errors="coerce")
    if revenue.isna().any() or (revenue <= 0).any():
        raise ValueError("Monthly revenue must be positive and present")
    if not revenue.index.equals(pd.date_range(revenue.index.min(), periods=len(revenue), freq="MS")):
        raise ValueError("Sales must contain consecutive calendar months")
    return revenue


def split_sales(revenue: pd.Series) -> tuple[pd.Series, pd.Series]:
    if len(revenue) != 120:
        raise ValueError("Expected exactly ten years of monthly sales")
    train, holdout = revenue.iloc[:96], revenue.iloc[96:]
    if train.index.max() >= holdout.index.min():
        raise ValueError("Training and holdout periods must not overlap")
    return train, holdout


def training_features(train: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    features = pd.DataFrame(index=train.index)
    features["month"] = train.index.month
    features["recent_vs_year"] = train.shift(1).rolling(3).mean() / train.shift(1).rolling(12).mean() - 1
    growth = train / train.shift(12) - 1
    valid = growth.notna() & features.notna().all(axis=1)
    return features.loc[valid], growth.loc[valid]


def forecast(model: RandomForestRegressor, train: pd.Series, months: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series, pd.Series]:
    history = train.tolist()
    scenarios = [history.copy() for _ in model.estimators_]
    estimates = []
    lower = []
    upper = []
    for month in months:
        row = pd.DataFrame([{
            "month": month.month,
            "recent_vs_year": np.mean(history[-3:]) / np.mean(history[-12:]) - 1,
        }])
        growth = model.predict(row)[0]
        estimate = history[-12] * (1 + growth)
        history.append(estimate)
        estimates.append(estimate)

        tree_estimates = []
        for tree, path in zip(model.estimators_, scenarios):
            tree_row = pd.DataFrame([{
                "month": month.month,
                "recent_vs_year": np.mean(path[-3:]) / np.mean(path[-12:]) - 1,
            }])
            tree_estimate = path[-12] * (1 + tree.predict(tree_row.to_numpy())[0])
            path.append(tree_estimate)
            tree_estimates.append(tree_estimate)
        lower.append(np.percentile(tree_estimates, 5))
        upper.append(np.percentile(tree_estimates, 95))
    return (pd.Series(estimates, index=months), pd.Series(lower, index=months),
            pd.Series(upper, index=months))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plot", type=Path, default=Path("audit/sales_forecast.png"))
    args = parser.parse_args()

    revenue = load_sales()
    train, holdout = split_sales(revenue)
    features, growth = training_features(train)
    # Random Forest is robust with ~84 lagged rows and less prone to overfitting than
    # boosting; near-default settings avoid tuning on the holdout. Tree dispersion
    # supplies a variability range, and simple seasonality needs no XGBoost capacity.
    # Forests cannot extrapolate levels, so predict year-over-year growth instead.
    model = RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=42)
    model.fit(features, growth)
    predicted, lower, upper = forecast(model, train, holdout.index)

    baseline = pd.Series(train.iloc[-12:].to_numpy().tolist() * 2, index=holdout.index)
    mae = mean_absolute_error(holdout, predicted)
    baseline_mae = mean_absolute_error(holdout, baseline)
    coverage = ((holdout >= lower) & (holdout <= upper)).mean()
    print(f"Training: {train.index.min():%Y-%m} to {train.index.max():%Y-%m} ({len(features)} usable months)")
    print(f"Unseen validation: {holdout.index.min():%Y-%m} to {holdout.index.max():%Y-%m}")
    print(f"Forest MAE: ${mae:,.2f}/month; seasonal naive MAE: ${baseline_mae:,.2f}/month")
    print(f"Mean signed error (predicted - actual): ${(predicted - holdout).mean():,.2f}/month")
    print(f"Months inside 5th-95th tree scenario range: {coverage:.0%} (not calibrated)")
    print(f"Mean actual revenue: ${holdout.mean():,.2f}/month")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(revenue.index, revenue, label="Actual monthly revenue", color="#174a50")
    ax.plot(predicted.index, predicted, label="Random Forest forecast", color="#c04832")
    ax.plot(baseline.index, baseline, label="Seasonal naive", color="#8a8a8a", linestyle=":")
    ax.fill_between(holdout.index, lower, upper, alpha=0.2, color="#c04832",
                    label="5th-95th percentile of tree trajectories")
    ax.axvspan(holdout.index.min(), holdout.index.max(), color="#dfebea", alpha=0.3,
               label="Unseen validation period")
    ax.axvline(holdout.index.min(), color="#174a50", linestyle="--")
    ax.set(title="Nexova | Monthly consolidated revenue", ylabel="USD per month", xlabel="Month")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    args.plot.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.plot, dpi=160)
    plt.close(fig)
    print(f"Chart: {args.plot}")


if __name__ == "__main__":
    main()