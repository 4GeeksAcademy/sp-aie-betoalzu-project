"""Causal split and feature checks for the monthly sales forecast."""

from scripts.sales_forecast import (
    build_temporal_folds,
    evaluate_fold,
    load_sales,
    split_sales,
    training_features,
)


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


def test_temporal_folds_are_ordered_expanding_and_non_overlapping() -> None:
    train, _ = split_sales(load_sales())
    folds = build_temporal_folds(train)

    assert len(folds) >= 5
    previous_validation_end = None
    for fold in folds:
        train_indices = fold.train_indices
        validation_indices = fold.validation_indices
        train_dates = train.index[train_indices]
        validation_dates = train.index[validation_indices]
        assert (train_indices[1:] == train_indices[:-1] + 1).all()
        assert (validation_indices[1:] == validation_indices[:-1] + 1).all()
        assert train_dates.is_monotonic_increasing
        assert validation_dates.is_monotonic_increasing
        assert train_indices[-1] < validation_indices[0]
        assert not set(train_indices).intersection(validation_indices)
        assert train_indices[0] == 0
        if previous_validation_end is not None:
            assert train_indices[-1] == previous_validation_end
            assert validation_indices[0] > previous_validation_end
        assert len(validation_indices) == 12
        previous_validation_end = validation_indices[-1]


def test_validation_predictions_do_not_read_actuals_from_the_validation_block() -> None:
    train, _ = split_sales(load_sales())
    fold = build_temporal_folds(train)[0]
    original_result = evaluate_fold(train, fold)

    altered = train.copy()
    altered.iloc[fold.validation_indices] *= 100
    altered_result = evaluate_fold(altered, fold)

    assert original_result["validation_prediction"].equals(
        altered_result["validation_prediction"]
    )


def test_future_revenue_does_not_change_features_or_training_targets_before_origin() -> None:
    train, _ = split_sales(load_sales())
    origin = train.index[60]
    original_features, original_target = training_features(train)
    altered = train.copy()
    altered.loc[altered.index > origin] *= 100
    altered_features, altered_target = training_features(altered)

    assert original_features.loc[:origin].equals(altered_features.loc[:origin])
    assert original_target.loc[:origin].equals(altered_target.loc[:origin])