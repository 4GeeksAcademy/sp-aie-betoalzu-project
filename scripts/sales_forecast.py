"""Forecast consolidated monthly revenue with a fixed, unseen two-year holdout."""

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error


DATASET = Path(__file__).resolve().parents[1] / "data/raw/nexova_sales.csv"
MINIMUM_TRAINING_MONTHS = 36
LEARNING_CURVE_PATH = Path("data/eval/sales_forecast_learning_curve.png")
EVALUATION_REPORT_PATH = Path("data/eval/evaluation_report.md")


@dataclass(frozen=True)
class TemporalFold:
    train_indices: np.ndarray
    validation_indices: np.ndarray


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


def build_temporal_folds(
    revenue: pd.Series, n_splits: int = 5, validation_size: int = 12
) -> list[TemporalFold]:
    if n_splits < 5 or validation_size < 1:
        raise ValueError("Use at least five folds with a positive validation size")
    initial_training_size = len(revenue) - n_splits * validation_size
    if initial_training_size < MINIMUM_TRAINING_MONTHS:
        raise ValueError("Not enough history for the requested temporal folds")
    if revenue.index.has_duplicates or not revenue.index.is_monotonic_increasing:
        raise ValueError("Sales dates must be unique and strictly increasing")

    folds = []
    for fold_number in range(n_splits):
        validation_start = initial_training_size + fold_number * validation_size
        validation_end = validation_start + validation_size
        folds.append(TemporalFold(
            train_indices=np.arange(validation_start),
            validation_indices=np.arange(validation_start, validation_end),
        ))
    return folds


def create_model() -> RandomForestRegressor:
    return RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=42)


def _regression_metrics(actual: pd.Series, predicted: pd.Series) -> tuple[float, float]:
    errors = actual.to_numpy() - predicted.to_numpy()
    return float(np.mean(np.abs(errors))), float(np.sqrt(np.mean(errors ** 2)))


def evaluate_fold(revenue: pd.Series, fold: TemporalFold, fold_number: int = 1) -> dict:
    train = revenue.iloc[fold.train_indices]
    validation_months = revenue.index[fold.validation_indices]
    validation_actual = revenue.iloc[fold.validation_indices]
    features, growth = training_features(train)
    model = create_model()
    model.fit(features, growth)

    training_growth_prediction = pd.Series(model.predict(features), index=features.index)
    training_actual = train.loc[features.index]
    training_base = train.shift(12).loc[features.index]
    training_prediction = training_base * (1 + training_growth_prediction)
    train_mae, train_rmse = _regression_metrics(training_actual, training_prediction)

    validation_prediction, _, _ = forecast(model, train, validation_months)
    validation_mae, validation_rmse = _regression_metrics(validation_actual, validation_prediction)
    return {
        "fold": fold_number,
        "train_start": train.index.min(),
        "train_end": train.index.max(),
        "validation_start": validation_months.min(),
        "validation_end": validation_months.max(),
        "training_months": len(train),
        "training_observations": len(features),
        "validation_months": len(validation_months),
        "train_mae": train_mae,
        "train_rmse": train_rmse,
        "validation_mae": validation_mae,
        "validation_rmse": validation_rmse,
        "training_prediction": training_prediction,
        "validation_prediction": validation_prediction,
    }


def evaluate_temporal_cv(revenue: pd.Series) -> list[dict]:
    development, _ = split_sales(revenue)
    folds = build_temporal_folds(development)
    return [evaluate_fold(development, fold, number)
            for number, fold in enumerate(folds, start=1)]


def plot_learning_curve(results: list[dict], path: Path = LEARNING_CURVE_PATH) -> None:
    training_size = [result["training_observations"] for result in results]
    fig, ax = plt.subplots(figsize=(9, 5))
    for metric, label, color, marker in (
        ("train_mae", "Training MAE", "#174a50", "o"),
        ("validation_mae", "Validation MAE", "#c04832", "o"),
        ("train_rmse", "Training RMSE", "#174a50", "s"),
        ("validation_rmse", "Validation RMSE", "#c04832", "s"),
    ):
        ax.plot(training_size, [result[metric] for result in results],
                label=label, color=color, marker=marker,
                linestyle="-" if "MAE" in label else "--")
    ax.set(title="Temporal learning curve | Nexova revenue forecast",
           xlabel="Usable chronological training observations",
           ylabel="Error (USD per month)")
    ax.legend()
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _diagnose(results: list[dict]) -> tuple[str, str]:
    train_errors = np.array([result["train_mae"] for result in results])
    validation_errors = np.array([result["validation_mae"] for result in results])
    gaps = validation_errors - train_errors
    spread = float(np.std(validation_errors, ddof=1))
    early_validation = float(np.mean(validation_errors[:2]))
    late_validation = float(np.mean(validation_errors[-2:]))
    early_training = float(np.mean(train_errors[:2]))
    late_training = float(np.mean(train_errors[-2:]))

    if np.all(gaps > 0) and float(np.mean(gaps)) > spread:
        return (
            "overfitting",
            "La brecha MAE entrenamiento-validacion es positiva en todos los folds y su media supera la desviacion entre folds.",
        )
    if (abs(float(np.mean(gaps))) <= spread
            and late_validation < early_validation
            and late_training <= early_training):
        return (
            "bien ajustado",
            "La brecha media queda dentro de la variabilidad entre folds y ambos errores mejoran o se mantienen al crecer el entrenamiento.",
        )
    if (abs(float(np.mean(gaps))) <= spread
            and late_validation >= early_validation
            and late_training >= early_training):
        return (
            "underfitting",
            "Los errores de entrenamiento y validacion son cercanos y no mejoran en los folds con mas observaciones.",
        )
    return (
        "evidencia insuficiente para distinguir bien ajustado, underfitting u overfitting",
        "La brecha, su variabilidad entre folds y la evolucion de los errores no respaldan de forma consistente una de las tres categorias.",
    )


def write_evaluation_report(
    results: list[dict],
    learning_curve_path: Path = LEARNING_CURVE_PATH,
    report_path: Path = EVALUATION_REPORT_PATH,
) -> None:
    mae_mean = np.mean([result["validation_mae"] for result in results])
    mae_std = np.std([result["validation_mae"] for result in results], ddof=1)
    rmse_mean = np.mean([result["validation_rmse"] for result in results])
    rmse_std = np.std([result["validation_rmse"] for result in results], ddof=1)
    classification, evidence = _diagnose(results)
    rows = [
        "| Fold | Train period | Validation period | Train months | Validation months | Train MAE | Train RMSE | Validation MAE | Validation RMSE |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        rows.append(
            f"| {result['fold']} | {result['train_start']:%Y-%m} to {result['train_end']:%Y-%m} "
            f"| {result['validation_start']:%Y-%m} to {result['validation_end']:%Y-%m} "
            f"| {result['training_months']} | {result['validation_months']} "
            f"| ${result['train_mae']:,.2f} | ${result['train_rmse']:,.2f} "
            f"| ${result['validation_mae']:,.2f} | ${result['validation_rmse']:,.2f} |"
        )
    report = f"""# Evaluacion temporal del pronostico de ingresos

## Alcance y datos

Se evalua `RandomForestRegressor` sobre la serie consolidada mensual de `data/raw/nexova_sales.csv`, filtrada por `business_line == "consolidated"` y usando `month` y `revenue_usd` en USD. El desarrollo comprende enero de 2016 a diciembre de 2023. El holdout final de enero de 2024 a diciembre de 2025 se mantiene separado y no participa en folds, ajuste ni diagnostico.

Las features son mes calendario y `recent_vs_year`, calculada con ingresos de meses anteriores; el objetivo es el crecimiento interanual de `revenue_usd`. No se incluyen campos contemporaneos cuya disponibilidad previa no este demostrada. El modelo conserva 300 arboles, `min_samples_leaf=2` y `random_state=42`; no se ajustan transformaciones fuera de cada fold.

## Metodologia temporal

Se usa expanding-window con cinco bloques cronologicos de 12 meses, sin barajado. Cada modelo se ajusta solo con su prefijo anterior; cada bloque se pronostica recursivamente, incorporando las predicciones previas del propio bloque y nunca sus ingresos reales. El primer origen exige 36 meses de historia y deja 24 observaciones utilizables tras los rezagos. La tabla especifica el intervalo exacto de entrenamiento y validacion de cada fold.

{chr(10).join(rows)}

Media de validacion ± desviacion estandar muestral (`ddof=1`): MAE ${mae_mean:,.2f} ± ${mae_std:,.2f}/mes; RMSE ${rmse_mean:,.2f} ± ${rmse_std:,.2f}/mes.

## Curva y diagnostico

![Curva de aprendizaje temporal: errores de entrenamiento y validacion en USD/mes]({learning_curve_path.name})

**Clasificacion: {classification}.** {evidence} La curva debe leerse junto con la variabilidad de validacion entre los cinco folds; no se usa el holdout para escoger ni justificar esta conclusion.

MAE es la metrica principal porque expresa el error absoluto mensual tipico directamente en USD para Finanzas. RMSE se conserva como complemento: penaliza mas los errores grandes y hace visible el riesgo de desviaciones severas. No se presupone un costo asimetrico entre sobrestimacion y subestimacion.

Accion: { _recommended_action(classification) }

## Limitaciones y reproduccion

Cinco bloques anuales ofrecen una muestra limitada de origenes y no cubren cambios futuros de regimen; las features disponibles tampoco incorporan variables empresariales anticipadas. No se modifico el holdout ni se buscaron hiperparametros. Desde la raiz, ejecutar `uv run --no-project --with pandas --with scikit-learn --with matplotlib python scripts/sales_forecast.py --evaluate-cv`; las pruebas focalizadas se ejecutan con `uv run --no-project --with pandas --with scikit-learn --with matplotlib --with pytest pytest tests/pipelines/test_sales_forecast.py -q`.
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")


def _recommended_action(classification: str) -> str:
    if classification == "overfitting":
        return "Probar hojas mas grandes o limitar la profundidad y reevaluar exclusivamente en estos folds internos."
    if classification == "underfitting":
        return "Investigar primero si las features causales disponibles representan cambios de ingresos conocidos antes del pronostico; reevaluar solo con folds internos."
    if classification == "bien ajustado":
        return "Conservar la configuracion y repetir la evaluacion interna cuando haya un nuevo periodo de desarrollo, sin reutilizar el holdout final."
    return "Comparar, en los mismos folds, una variacion controlada de `min_samples_leaf` y la referencia estacional para identificar si la brecha o el nivel de error responde a varianza o a features insuficientes."


def run_temporal_evaluation(revenue: pd.Series) -> list[dict]:
    results = evaluate_temporal_cv(revenue)
    plot_learning_curve(results)
    write_evaluation_report(results)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plot", type=Path, default=Path("audit/sales_forecast.png"))
    parser.add_argument("--evaluate-cv", action="store_true",
                        help="Run temporal cross-validation and write evaluation artifacts")
    args = parser.parse_args()

    revenue = load_sales()
    if args.evaluate_cv:
        results = run_temporal_evaluation(revenue)
        print(f"Temporal folds: {len(results)}")
        for result in results:
            print(
                f"Fold {result['fold']}: {result['validation_start']:%Y-%m} to "
                f"{result['validation_end']:%Y-%m}; "
                f"MAE ${result['validation_mae']:,.2f}/month; "
                f"RMSE ${result['validation_rmse']:,.2f}/month"
            )
        return

    train, holdout = split_sales(revenue)
    features, growth = training_features(train)
    # Random Forest is robust with ~84 lagged rows and less prone to overfitting than
    # boosting; near-default settings avoid tuning on the holdout. Tree dispersion
    # supplies a variability range, and simple seasonality needs no XGBoost capacity.
    # Forests cannot extrapolate levels, so predict year-over-year growth instead.
    model = create_model()
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