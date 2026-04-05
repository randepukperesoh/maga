from datetime import datetime, timezone


def run_training_job(
    *,
    epochs: int,
    learning_rate: float,
    model_family: str,
    base_weights: dict[str, float],
    base_trained_steps: int,
    dataset_size: int = 0,
    defect_rate: float | None = None,
    notebook_defect_prior: float | None = None,
) -> dict:
    epochs = max(1, min(epochs, 100))
    learning_rate = max(1e-5, min(learning_rate, 1.0))
    model_family = (model_family or "notebook-informed").strip() or "notebook-informed"

    history: list[dict[str, float | int]] = []
    loss = 1.0
    acc = 0.5
    for step in range(1, epochs + 1):
        loss *= 1.0 - 0.12 * learning_rate
        acc += (1.0 - acc) * 0.08 * learning_rate
        history.append({"step": step, "loss": round(loss, 4), "accuracy": round(acc, 4)})

    effective_defect_rate = (
        max(0.0, min(1.0, defect_rate))
        if defect_rate is not None
        else max(0.0, min(1.0, notebook_defect_prior or 0.5))
    )
    prior_shift = (effective_defect_rate - 0.5) * (0.08 if dataset_size > 0 else 0.04)

    weights = {
        "w_length": round(min(0.6, base_weights["w_length"] + 0.01 * learning_rate), 4),
        "w_area": round(max(0.1, base_weights["w_area"] - 0.005 * learning_rate), 4),
        "w_load": round(base_weights["w_load"], 4),
        "w_prior": round(
            max(0.05, min(0.35, base_weights["w_prior"] - 0.005 * learning_rate + prior_shift)),
            4,
        ),
    }

    model_version = f"{model_family}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    total_steps = base_trained_steps + epochs
    artifact = {
        "kind": "linear-risk-v2",
        "feature_order": ["bias", "length", "area", "load", "defect"],
        "coefficients": {
            "bias": round(0.1 + prior_shift, 6),
            "length": weights["w_length"],
            "area": weights["w_area"],
            "load": weights["w_load"],
            "defect": weights["w_prior"],
        },
        "metadata": {
            "dataset_size": dataset_size,
            "defect_rate": round(effective_defect_rate, 6),
            "notebook_defect_prior": round(float(notebook_defect_prior or 0.5), 6),
            "learning_rate": learning_rate,
            "epochs": epochs,
        },
    }
    return {
        "model_version": model_version,
        "model_family": model_family,
        "trained_steps": total_steps,
        "weights": weights,
        "history": history,
        "artifact": artifact,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
