"""Causal split and feature checks for the monthly sales forecast."""

from scripts.sales_forecast import load_sales, split_sales, training_features


def test_eight_year_split_and_no_holdout_leakage() -> None:
    revenue = load_sales()
    train, holdout = split_sales(revenue)

    assert len(train) == 96
    assert len(holdout) == 24
    assert train.index.min().strftime("%Y-%m") == "2016-01"
    assert train.index.max().strftime("%Y-%m") == "2023-12"
    assert holdout.index.min().strftime("%Y-%m") == "2024-01"
    assert holdout.index.max().strftime("%Y-%m") == "2025-12"
    assert train.index.intersection(holdout.index).empty

    features, target = training_features(train)
    altered = revenue.copy()
    altered.iloc[96:] *= 100
    altered_train, _ = split_sales(altered)
    altered_features, altered_target = training_features(altered_train)
    assert features.equals(altered_features)
    assert target.equals(altered_target)
    assert features.index.max() < holdout.index.min()
    assert len(target) == 84


def test_future_training_month_does_not_change_past_features() -> None:
    train, _ = split_sales(load_sales())
    original_features, _ = training_features(train)
    changed = train.copy()
    changed.iloc[-1] *= 100
    changed_features, _ = training_features(changed)

    assert original_features.equals(changed_features)