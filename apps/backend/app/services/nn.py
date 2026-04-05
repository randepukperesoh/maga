import math
from datetime import datetime, timezone
from uuid import uuid4

from celery.result import AsyncResult

from app.celery_app import celery_app
from app.db.training_store import add_dataset_sample as db_add_dataset_sample
from app.db.training_store import add_training_log as db_add_training_log
from app.db.training_store import delete_dataset_sample as db_delete_dataset_sample
from app.db.training_store import list_dataset as db_list_dataset
from app.db.training_store import list_training_logs as db_list_training_logs
from app.db.training_store import load_runtime_snapshot as db_load_runtime_snapshot
from app.db.training_store import save_runtime_snapshot as db_save_runtime_snapshot
from app.db.training_store import update_dataset_sample as db_update_dataset_sample
from app.schemas.analysis import CalculationRequest
from app.schemas.training import DatasetSampleIn
from app.services.checkpoint_model import load_checkpoint_model, save_checkpoint_model, sigmoid
from app.services.notebook_integration import (
    build_notebook_artifact,
    default_notebook_path,
    load_notebook_signals,
)
from app.services.training_runtime import run_training_job
from app.tasks.training import run_model_training_task

_NOTEBOOK_SIGNALS = load_notebook_signals(default_notebook_path())
_BASELINE_ARTIFACT = build_notebook_artifact(_NOTEBOOK_SIGNALS)


def _baseline_weights() -> dict[str, float]:
    coeffs = _BASELINE_ARTIFACT.get("coefficients", {})
    if isinstance(coeffs, dict):
        try:
            return {
                "w_length": float(coeffs.get("length", 0.35)),
                "w_area": float(coeffs.get("area", 0.30)),
                "w_load": float(coeffs.get("load", 0.20)),
                "w_prior": float(coeffs.get("defect", 0.15)),
            }
        except (TypeError, ValueError):
            pass
    return {
        "w_length": 0.35,
        "w_area": 0.30,
        "w_load": 0.20,
        "w_prior": 0.15,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_model_card(
    model_version: str,
    model_family: str,
    trained_steps: int,
    weights: dict[str, float],
    history: list[dict],
    created_at: str | None = None,
    artifact: dict | None = None,
) -> dict:
    return {
        "model_version": model_version,
        "model_family": model_family,
        "trained_steps": trained_steps,
        "weights": weights,
        "history": history,
        "created_at": created_at or _now_iso(),
        "artifact": artifact or {},
    }


def _log(level: str, message: str) -> None:
    payload = {"ts": _now_iso(), "level": level, "message": message}
    _TRAINING_LOGS.append(payload)
    if len(_TRAINING_LOGS) > 500:
        del _TRAINING_LOGS[: len(_TRAINING_LOGS) - 500]
    try:
        db_add_training_log(str(uuid4()), level, message)
    except Exception:
        pass


_BASELINE_VERSION = "notebook-informed-baseline-v3"
_MODELS: dict[str, dict] = {
    _BASELINE_VERSION: _new_model_card(
        _BASELINE_VERSION,
        "notebook-informed",
        0,
        _baseline_weights(),
        [],
        artifact=_BASELINE_ARTIFACT,
    )
}

_TRAINING_STATE = {
    "status": "idle",
    "last_model_version": _BASELINE_VERSION,
    "active_inference_model": _BASELINE_VERSION,
    "current_task_id": None,
}
_TRAINING_LOGS: list[dict] = [
    {"ts": _now_iso(), "level": "info", "message": "Training service initialized"}
]


def _ensure_baseline_model() -> None:
    if _BASELINE_VERSION not in _MODELS:
        _MODELS[_BASELINE_VERSION] = _new_model_card(
            _BASELINE_VERSION,
            "notebook-informed",
            0,
            _baseline_weights(),
            [],
            artifact=_BASELINE_ARTIFACT,
        )
    last_version = _TRAINING_STATE.get("last_model_version")
    if not isinstance(last_version, str) or last_version not in _MODELS:
        _TRAINING_STATE["last_model_version"] = _BASELINE_VERSION
    active_version = _TRAINING_STATE.get("active_inference_model")
    if not isinstance(active_version, str) or active_version not in _MODELS:
        _TRAINING_STATE["active_inference_model"] = _TRAINING_STATE["last_model_version"]


def _state_str(key: str, default: str) -> str:
    value = _TRAINING_STATE.get(key)
    return value if isinstance(value, str) else default


def _runtime_snapshot_payload() -> dict:
    return {
        "models": _MODELS,
        "training_state": _TRAINING_STATE,
    }


def _persist_runtime_snapshot() -> None:
    try:
        db_save_runtime_snapshot(_runtime_snapshot_payload())
    except Exception:
        pass


def _hydrate_runtime_snapshot() -> None:
    try:
        payload = db_load_runtime_snapshot()
    except Exception:
        payload = None
    if not payload:
        _ensure_baseline_model()
        return
    models = payload.get("models")
    training_state = payload.get("training_state")
    if isinstance(models, dict) and models:
        _MODELS.clear()
        _MODELS.update(models)
    if isinstance(training_state, dict) and training_state:
        _TRAINING_STATE.update(training_state)
    _ensure_baseline_model()


def _rod_numeric_id(rod_id: str) -> int | None:
    digits = "".join(ch for ch in rod_id if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _normalize_label(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower()


def _dataset_training_signals() -> tuple[int, float | None]:
    try:
        items = db_list_dataset()
    except Exception:
        return 0, None
    if not items:
        return 0, None
    defect_like = 0
    total_labeled = 0
    for item in items:
        label = _normalize_label(item.get("label"))
        if not label:
            continue
        total_labeled += 1
        if label in {"defect", "crack", "fault", "corrosion", "damage", "1", "true"}:
            defect_like += 1
    if total_labeled == 0:
        return len(items), None
    return len(items), defect_like / total_labeled


def _apply_training_result(result: dict) -> None:
    model_version = result["model_version"]
    model_family = result["model_family"]
    trained_steps = result["trained_steps"]
    weights = result["weights"]
    history = result["history"]
    created_at = result.get("created_at")
    artifact = result.get("artifact", {})

    _MODELS[model_version] = _new_model_card(
        model_version=model_version,
        model_family=model_family,
        trained_steps=trained_steps,
        weights=weights,
        history=history,
        created_at=created_at,
        artifact=artifact,
    )
    _TRAINING_STATE["last_model_version"] = model_version
    _TRAINING_STATE["active_inference_model"] = model_version
    _TRAINING_STATE["status"] = "trained"
    _TRAINING_STATE["current_task_id"] = None
    _persist_runtime_snapshot()
    coefficients = artifact.get("coefficients", {})
    try:
        save_checkpoint_model(
            {
                "model_version": model_version,
                "trained_steps": trained_steps,
                "weights": {
                    "bias": float(coefficients.get("bias", 0.1)),
                    "length": float(coefficients.get("length", weights["w_length"])),
                    "area": float(coefficients.get("area", weights["w_area"])),
                    "load": float(coefficients.get("load", weights["w_load"])),
                    "defect": float(coefficients.get("defect", weights["w_prior"])),
                },
                "artifact": artifact,
            }
        )
    except Exception:
        pass
    _log("info", f"Training finished: model={model_version}")


def _artifact_coefficients(model: dict) -> tuple[dict[str, float], dict]:
    artifact = model.get("artifact", {})
    coefficients = artifact.get("coefficients", {}) if isinstance(artifact, dict) else {}
    required = ("bias", "length", "area", "load", "defect")
    has_artifact_coeffs = isinstance(coefficients, dict) and all(key in coefficients for key in required)
    if has_artifact_coeffs:
        return (
            {
                "bias": float(coefficients["bias"]),
                "length": float(coefficients["length"]),
                "area": float(coefficients["area"]),
                "load": float(coefficients["load"]),
                "defect": float(coefficients["defect"]),
            },
            artifact.get("metadata", {}) if isinstance(artifact, dict) else {},
        )
    return {}, {}


def _checkpoint_coefficients_for_model(model_version: str) -> tuple[dict[str, float], dict]:
    checkpoint = load_checkpoint_model()
    if not checkpoint:
        return {}, {}
    if checkpoint.get("model_version") != model_version:
        return {}, {}
    checkpoint_weights = checkpoint.get("weights", {})
    required = ("bias", "length", "area", "load", "defect")
    if not isinstance(checkpoint_weights, dict) or not all(
        key in checkpoint_weights for key in required
    ):
        return {}, {}
    metadata = checkpoint.get("artifact", {}).get("metadata", {})
    return (
        {
            "bias": float(checkpoint_weights["bias"]),
            "length": float(checkpoint_weights["length"]),
            "area": float(checkpoint_weights["area"]),
            "load": float(checkpoint_weights["load"]),
            "defect": float(checkpoint_weights["defect"]),
        },
        metadata if isinstance(metadata, dict) else {},
    )


def _bootstrap_model_from_checkpoint() -> None:
    checkpoint = load_checkpoint_model()
    if not isinstance(checkpoint, dict):
        return
    model_version = checkpoint.get("model_version")
    checkpoint_weights = checkpoint.get("weights", {})
    if (
        not isinstance(model_version, str)
        or not model_version
        or model_version in _MODELS
        or not isinstance(checkpoint_weights, dict)
    ):
        return
    required = ("length", "area", "load", "defect")
    if not all(key in checkpoint_weights for key in required):
        return

    model_family = model_version.split("-", 1)[0] if "-" in model_version else "checkpoint"
    trained_steps = int(checkpoint.get("trained_steps", 0))
    artifact = checkpoint.get("artifact", {})
    _MODELS[model_version] = _new_model_card(
        model_version=model_version,
        model_family=model_family,
        trained_steps=trained_steps,
        weights={
            "w_length": float(checkpoint_weights["length"]),
            "w_area": float(checkpoint_weights["area"]),
            "w_load": float(checkpoint_weights["load"]),
            "w_prior": float(checkpoint_weights["defect"]),
        },
        history=[],
        artifact=artifact if isinstance(artifact, dict) else {},
    )
    if _TRAINING_STATE["last_model_version"] == _BASELINE_VERSION:
        _TRAINING_STATE["last_model_version"] = model_version
    if _TRAINING_STATE["active_inference_model"] == _BASELINE_VERSION:
        _TRAINING_STATE["active_inference_model"] = model_version


def _sync_async_training_state() -> None:
    _hydrate_runtime_snapshot()
    if _TRAINING_STATE["status"] != "training":
        return
    task_id = _TRAINING_STATE.get("current_task_id")
    if not task_id:
        return
    try:
        result = AsyncResult(task_id, app=celery_app)
        if result.successful():
            payload = result.get(timeout=0)
            _apply_training_result(payload)
        elif result.failed():
            _TRAINING_STATE["status"] = "failed"
            _TRAINING_STATE["current_task_id"] = None
            _persist_runtime_snapshot()
            _log("error", f"Training task failed: task_id={task_id}")
    except Exception:
        return


def get_training_status() -> dict:
    _sync_async_training_state()
    last_version = _state_str("last_model_version", _BASELINE_VERSION)
    if last_version not in _MODELS:
        last_version = _BASELINE_VERSION
    last = _MODELS[last_version]
    return {
        "status": _TRAINING_STATE["status"],
        "model_version": last["model_version"],
        "trained_steps": last["trained_steps"],
        "weights": last["weights"],
        "active_inference_model": _TRAINING_STATE["active_inference_model"],
        "model_family": last["model_family"],
    }


def get_training_history(model_version: str | None = None) -> dict:
    _sync_async_training_state()
    selected_version = model_version or _state_str("last_model_version", _BASELINE_VERSION)
    model = _MODELS.get(selected_version)
    if not model:
        fallback = _state_str("last_model_version", _BASELINE_VERSION)
        if fallback not in _MODELS:
            fallback = _BASELINE_VERSION
        model = _MODELS[fallback]
    return {
        "model_version": model["model_version"],
        "points": model["history"],
    }


def list_models() -> dict:
    _sync_async_training_state()
    cards = [
        {
            "model_version": m["model_version"],
            "model_family": m["model_family"],
            "trained_steps": m["trained_steps"],
            "created_at": m["created_at"],
        }
        for m in sorted(_MODELS.values(), key=lambda x: x["created_at"], reverse=True)
    ]
    return {
        "active_inference_model": _TRAINING_STATE["active_inference_model"],
        "models": cards,
    }


def set_inference_model(model_version: str) -> dict:
    _hydrate_runtime_snapshot()
    if model_version not in _MODELS:
        raise ValueError("Model not found")
    _TRAINING_STATE["active_inference_model"] = model_version
    _persist_runtime_snapshot()
    _log("info", f"Inference model switched to {model_version}")
    return {"active_inference_model": model_version}


def start_training(
    epochs: int, learning_rate: float, model_family: str = "notebook-informed"
) -> dict:
    _hydrate_runtime_snapshot()
    if _TRAINING_STATE["status"] == "training":
        _log("warning", "Training request ignored: training already in progress")
        return get_training_status()

    epochs = max(1, min(epochs, 100))
    learning_rate = max(1e-5, min(learning_rate, 1.0))
    model_family = (model_family or "notebook-informed").strip() or "notebook-informed"

    _TRAINING_STATE["status"] = "training"
    _TRAINING_STATE["current_task_id"] = None
    _persist_runtime_snapshot()
    _log(
        "info",
        f"Training queued: epochs={epochs}, lr={learning_rate}, family={model_family}",
    )

    base_version = _state_str("active_inference_model", _BASELINE_VERSION)
    base_model = _MODELS.get(base_version, _MODELS[_BASELINE_VERSION])
    base_weights = dict(base_model["weights"])
    base_trained_steps = int(base_model["trained_steps"])
    dataset_size, defect_rate = _dataset_training_signals()
    notebook_defect_prior = 1.0 - _NOTEBOOK_SIGNALS.class_priors.get(0, 0.25)

    try:
        async_result = run_model_training_task.delay(
            epochs=epochs,
            learning_rate=learning_rate,
            model_family=model_family,
            base_weights=base_weights,
            base_trained_steps=base_trained_steps,
            dataset_size=dataset_size,
            defect_rate=defect_rate,
            notebook_defect_prior=notebook_defect_prior,
        )
        _TRAINING_STATE["current_task_id"] = async_result.id
        _persist_runtime_snapshot()
        _log("info", f"Training task dispatched: task_id={async_result.id}")
    except Exception:
        _log("warning", "Celery unavailable, fallback to inline training")
        result = run_training_job(
            epochs=epochs,
            learning_rate=learning_rate,
            model_family=model_family,
            base_weights=base_weights,
            base_trained_steps=base_trained_steps,
            dataset_size=dataset_size,
            defect_rate=defect_rate,
            notebook_defect_prior=notebook_defect_prior,
        )
        _apply_training_result(result)

    return get_training_status()


def stop_training() -> dict:
    _hydrate_runtime_snapshot()
    if _TRAINING_STATE["status"] == "training":
        task_id = _TRAINING_STATE.get("current_task_id")
        if task_id:
            try:
                celery_app.control.revoke(task_id, terminate=True)
            except Exception:
                pass
        _TRAINING_STATE["status"] = "stopped"
        _TRAINING_STATE["current_task_id"] = None
        _persist_runtime_snapshot()
        _log("warning", "Training stopped by user")
        return {"status": "stopped", "message": "Training stopped"}
    return {"status": _TRAINING_STATE["status"], "message": "No active training job"}


def get_training_logs(limit: int = 200) -> dict:
    try:
        return {"lines": db_list_training_logs(limit=limit)}
    except Exception:
        safe_limit = max(1, min(limit, 1000))
        return {"lines": _TRAINING_LOGS[-safe_limit:]}


def get_training_stream_payload(log_limit: int = 50) -> dict:
    return {
        "type": "training_snapshot",
        "status": get_training_status(),
        "logs": get_training_logs(limit=log_limit)["lines"],
    }


def list_dataset() -> dict:
    try:
        return {"items": db_list_dataset()}
    except Exception:
        return {"items": []}


def add_dataset_sample(payload: DatasetSampleIn) -> dict:
    item = {
        "id": str(uuid4()),
        "name": payload.name,
        "payload": payload.payload,
        "label": payload.label,
        "note": payload.note,
        "created_at": _now_iso(),
    }
    try:
        item = db_add_dataset_sample(item)
    except Exception:
        pass
    _log("info", f"Dataset sample added: {item['id']}")
    return item


def update_dataset_sample(sample_id: str, payload: DatasetSampleIn) -> dict | None:
    try:
        updated = db_update_dataset_sample(
            sample_id,
            {
                "name": payload.name,
                "payload": payload.payload,
                "label": payload.label,
                "note": payload.note,
            },
        )
    except Exception:
        updated = None
    if updated is not None:
        _log("info", f"Dataset sample updated: {sample_id}")
    return updated


def delete_dataset_sample(sample_id: str) -> bool:
    try:
        deleted = db_delete_dataset_sample(sample_id)
    except Exception:
        deleted = False
    if deleted:
        _log("info", f"Dataset sample deleted: {sample_id}")
    return deleted


def _build_step_load_map(
    request: CalculationRequest, *, load_factor: float, load_fx: float | None = None, load_fy: float | None = None
) -> dict[str, float]:
    values = {
        load.node_id: math.hypot(
            (load_fx if load_fx is not None else load.fx * load_factor),
            (load_fy if load_fy is not None else load.fy * load_factor),
        )
        for load in request.loads
    }
    return values


def _predict_for_load_map(
    request: CalculationRequest,
    load_map: dict[str, float],
    *,
    defect_count_by_rod: dict[str, int] | None,
    defect_prior: float,
    weights: dict[str, float],
    has_inference_coeffs: bool,
    inference_coeffs: dict[str, float],
) -> tuple[dict[str, float], list[dict]]:
    node_map = {n.id: n for n in request.nodes}
    max_load = max(load_map.values(), default=1.0)
    risk_by_rod: dict[str, float] = {}
    risk_heatmap: list[dict] = []

    for rod in request.rods:
        n1 = node_map.get(rod.start_node_id)
        n2 = node_map.get(rod.end_node_id)
        if not n1 or not n2:
            risk_by_rod[rod.id] = 0.05
            continue

        length = math.hypot(n2.x - n1.x, n2.y - n1.y)
        slenderness = min(1.0, length / 300.0)
        area_factor = 1.0 - min(1.0, rod.area / 0.03)
        load_factor = (
            max(load_map.get(rod.start_node_id, 0.0), load_map.get(rod.end_node_id, 0.0)) / max_load
        )

        hot_boost = 0.0
        rid = _rod_numeric_id(rod.id)
        if rid is not None and rid in _NOTEBOOK_SIGNALS.defect_hot_kernels:
            hot_boost += 0.08

        defect_count_feature = 0.0
        if defect_count_by_rod:
            defect_count_feature = min(1.0, 0.2 * defect_count_by_rod.get(rod.id, 0))
            hot_boost += min(0.12, 0.04 * defect_count_by_rod.get(rod.id, 0))

        if has_inference_coeffs:
            defect_feature = min(
                1.0, defect_prior + defect_count_feature + (0.2 if hot_boost > 0 else 0.0)
            )
            score = (
                inference_coeffs["bias"]
                + inference_coeffs["length"] * slenderness
                + inference_coeffs["area"] * area_factor
                + inference_coeffs["load"] * load_factor
                + inference_coeffs["defect"] * defect_feature
            )
            risk = sigmoid(score)
        else:
            heuristic = (
                0.12
                + weights["w_length"] * slenderness
                + weights["w_area"] * area_factor
                + weights["w_load"] * load_factor
                + weights["w_prior"] * defect_prior
            )
            risk = heuristic + hot_boost

        normalized_risk = round(max(0.01, min(0.99, risk)), 4)
        risk_by_rod[rod.id] = normalized_risk

        rid_numeric = _rod_numeric_id(rod.id) or 1
        segments: list[dict[str, float]] = []
        for idx in range(6):
            position = idx / 5
            wave = 0.06 * math.sin((idx + 1) * (rid_numeric % 7 + 1))
            hot_zone_boost = 0.08 if hot_boost > 0 and 0.35 <= position <= 0.65 else 0.0
            local_risk = max(0.01, min(0.99, normalized_risk + wave + hot_zone_boost))
            segments.append({"position": round(position, 2), "risk": round(local_risk, 4)})
        risk_heatmap.append({"rod_id": rod.id, "segments": segments})

    return risk_by_rod, risk_heatmap


def predict_defect(
    request: CalculationRequest, defect_count_by_rod: dict[str, int] | None = None
) -> dict:
    _hydrate_runtime_snapshot()
    active_version = _state_str("active_inference_model", _BASELINE_VERSION)
    active_model = _MODELS.get(active_version, _MODELS[_BASELINE_VERSION])

    defect_prior = 1.0 - _NOTEBOOK_SIGNALS.class_priors.get(0, 0.25)
    weights = active_model["weights"]
    inference_coeffs, artifact_meta = _artifact_coefficients(active_model)
    inference_source = "model-artifact"
    if not inference_coeffs:
        inference_coeffs, artifact_meta = _checkpoint_coefficients_for_model(
            active_model["model_version"]
        )
        inference_source = "checkpoint"
    has_inference_coeffs = bool(inference_coeffs)
    if not has_inference_coeffs:
        inference_source = "heuristic"

    base_load_map = _build_step_load_map(request, load_factor=1.0)
    risk_by_rod, risk_heatmap = _predict_for_load_map(
        request,
        base_load_map,
        defect_count_by_rod=defect_count_by_rod,
        defect_prior=defect_prior,
        weights=weights,
        has_inference_coeffs=has_inference_coeffs,
        inference_coeffs=inference_coeffs,
    )

    sorted_risks = sorted(risk_by_rod.items(), key=lambda x: x[1], reverse=True)
    top = sorted_risks[:3]
    threshold = 0.6
    predicted_positive = {rod_id for rod_id, risk in risk_by_rod.items() if risk >= threshold}
    actual_positive = (
        {rod_id for rod_id, count in (defect_count_by_rod or {}).items() if count > 0}
        if defect_count_by_rod
        else set()
    )
    tp = len(predicted_positive & actual_positive)
    fp = len(predicted_positive - actual_positive)
    fn = len(actual_positive - predicted_positive)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    top_k_hit = any(rod_id in actual_positive for rod_id, _ in top)

    quasi_static_steps: list[dict] = []
    if request.analysis_type == "quasi_static":
        raw_steps = request.quasi_static_steps or []
        for idx, step in enumerate(raw_steps, start=1):
            step_index = step.step_index if step.step_index is not None else idx
            step_name = step.name or f"Step {step_index}"
            step_risk_by_rod, step_heatmap = _predict_for_load_map(
                request,
                _build_step_load_map(
                    request,
                    load_factor=step.load_factor,
                    load_fx=step.load_fx,
                    load_fy=step.load_fy,
                ),
                defect_count_by_rod=defect_count_by_rod,
                defect_prior=defect_prior,
                weights=weights,
                has_inference_coeffs=has_inference_coeffs,
                inference_coeffs=inference_coeffs,
            )
            step_top = sorted(step_risk_by_rod.items(), key=lambda x: x[1], reverse=True)[:3]
            quasi_static_steps.append(
                {
                    "step_index": step_index,
                    "name": step_name,
                    "load_factor": step.load_factor,
                    "risk_by_rod": step_risk_by_rod,
                    "risk_heatmap": step_heatmap,
                    "top_risky_rods": [{"rod_id": rid, "risk": r} for rid, r in step_top],
                }
            )

    return {
        "risk_by_rod": risk_by_rod,
        "risk_heatmap": risk_heatmap,
        "top_risky_rods": [{"rod_id": rid, "risk": r} for rid, r in top],
        "analysis_type": request.analysis_type,
        "quasi_static_steps": quasi_static_steps,
        "model": active_model["model_version"],
        "inference_source": inference_source,
        "model_metadata": {
            "dataset_size": artifact_meta.get("dataset_size"),
            "defect_rate": artifact_meta.get("defect_rate"),
        },
        "evaluation": {
            "threshold": threshold,
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "top_k_hit": top_k_hit,
            "actual_defect_rods": len(actual_positive),
            "predicted_defect_rods": len(predicted_positive),
        },
        "notebook_signals": {
            "defect_prior": round(defect_prior, 4),
            "hot_kernels_count": len(_NOTEBOOK_SIGNALS.defect_hot_kernels),
        },
    }


_hydrate_runtime_snapshot()
_bootstrap_model_from_checkpoint()
_persist_runtime_snapshot()
