import hashlib
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
from app.services.fem import run_fem
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


def _dataset_training_signals(items: list[dict] | None = None) -> tuple[int, float | None]:
    if items is None:
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


def _dataset_training_payload() -> tuple[list[dict], int, float | None]:
    try:
        items = db_list_dataset()
    except Exception:
        items = []
    dataset_size, defect_rate = _dataset_training_signals(items)
    return items, dataset_size, defect_rate



def _validation_f1_from_model(model: dict | None) -> float | None:
    if not isinstance(model, dict):
        return None
    artifact = model.get("artifact", {})
    if not isinstance(artifact, dict):
        return None
    metadata = artifact.get("metadata", {})
    if not isinstance(metadata, dict):
        return None
    metrics = metadata.get("metrics", {})
    if not isinstance(metrics, dict):
        return None
    validation = metrics.get("validation", {})
    if not isinstance(validation, dict):
        return None
    value = validation.get("f1")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _validation_f1_from_result(result: dict) -> float | None:
    artifact = result.get("artifact", {})
    if not isinstance(artifact, dict):
        return None
    metadata = artifact.get("metadata", {})
    if not isinstance(metadata, dict):
        return None
    metrics = metadata.get("metrics", {})
    if not isinstance(metrics, dict):
        return None
    validation = metrics.get("validation", {})
    if not isinstance(validation, dict):
        return None
    value = validation.get("f1")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _apply_training_result(result: dict) -> None:
    model_version = result["model_version"]
    model_family = result["model_family"]
    trained_steps = result["trained_steps"]
    weights = result["weights"]
    history = result["history"]
    created_at = result.get("created_at")
    artifact = result.get("artifact", {})

    previous_active_version = _state_str("active_inference_model", _BASELINE_VERSION)
    previous_model = _MODELS.get(previous_active_version)
    previous_val_f1 = _validation_f1_from_model(previous_model)
    current_val_f1 = _validation_f1_from_result(result)

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

    if previous_val_f1 is not None and current_val_f1 is not None:
        delta_f1 = current_val_f1 - previous_val_f1
        if delta_f1 < -0.05:
            _log(
                "warning",
                f"Validation F1 degraded by {delta_f1:.4f} compared to previous active model",
            )

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
    dataset_items, dataset_size, defect_rate = _dataset_training_payload()
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
            dataset_items=dataset_items,
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
            dataset_items=dataset_items,
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
    return {
        load.node_id: math.hypot(
            (load_fx if load_fx is not None else load.fx * load_factor),
            (load_fy if load_fy is not None else load.fy * load_factor),
        )
        for load in request.loads
    }


def _coeff(coeffs: dict[str, float], key: str, default: float = 0.0) -> float:
    value = coeffs.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_node_state(node_displacements: dict[str, object], node_id: str) -> dict[str, float | bool]:
    raw = node_displacements.get(node_id)
    if raw is None:
        return {
            "ux": 0.0,
            "uy": 0.0,
            "dx": 0.0,
            "dy": 0.0,
            "rx": 0.0,
            "ry": 0.0,
            "r_norm": 0.0,
            "sensor_available": False,
        }

    ux = float(getattr(raw, "ux", 0.0))
    uy = float(getattr(raw, "uy", 0.0))
    sensor_available = bool(getattr(raw, "sensor_available", False))

    if sensor_available:
        dx = float(getattr(raw, "dx", ux))
        dy = float(getattr(raw, "dy", uy))
    else:
        # Fallback: when sensor is missing we reuse FEM displacement as pseudo-observation.
        dx = ux
        dy = uy

    rx = dx - ux
    ry = dy - uy
    r_norm = math.hypot(rx, ry)

    return {
        "ux": ux,
        "uy": uy,
        "dx": dx,
        "dy": dy,
        "rx": rx,
        "ry": ry,
        "r_norm": r_norm,
        "sensor_available": sensor_available,
    }


def _position_bias_from_node_anomaly(anomaly_i: float, anomaly_j: float) -> float:
    denom = max(1e-9, anomaly_i + anomaly_j)
    skew = (anomaly_j - anomaly_i) / denom
    return max(0.05, min(0.95, 0.5 + 0.35 * skew))

def _rebalance_global_risk(
    risk_by_rod: dict[str, float], risk_heatmap: list[dict]
) -> tuple[dict[str, float], list[dict]]:
    if len(risk_by_rod) < 3:
        return risk_by_rod, risk_heatmap

    values = list(risk_by_rod.values())
    v_min = min(values)
    v_max = max(values)
    spread = v_max - v_min
    mean = sum(values) / len(values)
    high_ratio = sum(1 for v in values if v >= 0.7) / len(values)

    need_rebalance = (v_min >= 0.65) or (high_ratio >= 0.8 and mean >= 0.6) or (spread < 0.18 and mean >= 0.58)
    if not need_rebalance:
        return risk_by_rod, risk_heatmap

    ranked = sorted(risk_by_rod.items(), key=lambda x: x[1])
    n = len(ranked)
    adjusted: dict[str, float] = {}
    for idx, (rid, value) in enumerate(ranked):
        q = idx / max(1, n - 1)
        target = 0.08 + 0.84 * (q ** 1.1)
        blended = 0.55 * float(value) + 0.45 * target
        adjusted[rid] = round(max(0.01, min(0.99, blended)), 4)

    adjusted_heatmap: list[dict] = []
    for row in risk_heatmap:
        rid = row.get("rod_id")
        if not isinstance(rid, str) or rid not in adjusted:
            adjusted_heatmap.append(row)
            continue
        base = float(risk_by_rod.get(rid, 0.0))
        ratio = adjusted[rid] / max(base, 1e-6)
        segments = row.get("segments", [])
        if not isinstance(segments, list):
            adjusted_heatmap.append(row)
            continue
        new_segments = []
        for seg in segments:
            pos = float(seg.get("position", 0.5))
            risk = float(seg.get("risk", 0.0)) * ratio
            new_segments.append({"position": round(pos, 2), "risk": round(max(0.01, min(0.99, risk)), 4)})
        adjusted_heatmap.append({"rod_id": rid, "segments": new_segments})

    return adjusted, adjusted_heatmap


def _predict_for_load_map(
    request: CalculationRequest,
    load_map: dict[str, float],
    node_displacements: dict[str, object],
    *,
    defect_count_by_rod: dict[str, int] | None,
    defect_prior: float,
    weights: dict[str, float],
    has_inference_coeffs: bool,
    inference_coeffs: dict[str, float],
) -> tuple[dict[str, float], list[dict], dict[str, dict[str, float | bool]]]:
    node_map = {n.id: n for n in request.nodes}
    max_load = max(load_map.values(), default=1.0)
    risk_by_rod: dict[str, float] = {}
    risk_heatmap: list[dict] = []
    rod_features: dict[str, dict[str, float | bool]] = {}

    for rod in request.rods:
        n1 = node_map.get(rod.start_node_id)
        n2 = node_map.get(rod.end_node_id)
        if not n1 or not n2:
            risk_by_rod[rod.id] = 0.05
            continue

        state_i = _build_node_state(node_displacements, rod.start_node_id)
        state_j = _build_node_state(node_displacements, rod.end_node_id)

        length = math.hypot(n2.x - n1.x, n2.y - n1.y)
        if length <= 1e-9:
            risk_by_rod[rod.id] = 0.05
            continue

        c = (n2.x - n1.x) / length
        s = (n2.y - n1.y) / length

        slenderness = min(1.0, length / 300.0)
        area_factor = 1.0 - min(1.0, rod.area / 0.03)
        load_factor = (
            max(load_map.get(rod.start_node_id, 0.0), load_map.get(rod.end_node_id, 0.0)) / max_load
        )

        sensor_coverage = (
            (1.0 if bool(state_i["sensor_available"]) else 0.0)
            + (1.0 if bool(state_j["sensor_available"]) else 0.0)
        ) / 2.0

        residual_i = float(state_i["r_norm"])
        residual_j = float(state_j["r_norm"])
        residual_mean = 0.5 * (residual_i + residual_j)

        base_u_i = math.hypot(float(state_i["ux"]), float(state_i["uy"]))
        base_u_j = math.hypot(float(state_j["ux"]), float(state_j["uy"]))
        expected_scale = max(1e-6, 0.5 * (base_u_i + base_u_j))
        residual_feature = min(1.0, residual_mean / (expected_scale + residual_mean + 1e-9))

        obs_axial_delta = (
            c * (float(state_j["dx"]) - float(state_i["dx"]))
            + s * (float(state_j["dy"]) - float(state_i["dy"]))
        )
        fem_axial_delta = (
            c * (float(state_j["ux"]) - float(state_i["ux"]))
            + s * (float(state_j["uy"]) - float(state_i["uy"]))
        )
        obs_strain = obs_axial_delta / length
        fem_strain = fem_axial_delta / length
        strain_feature = min(1.0, abs(obs_strain - fem_strain) / (abs(fem_strain) + 1e-6))

        obs_jump = math.hypot(
            float(state_j["dx"]) - float(state_i["dx"]),
            float(state_j["dy"]) - float(state_i["dy"]),
        ) / length
        fem_jump = math.hypot(
            float(state_j["ux"]) - float(state_i["ux"]),
            float(state_j["uy"]) - float(state_i["uy"]),
        ) / length
        jump_feature = min(1.0, abs(obs_jump - fem_jump) / (abs(fem_jump) + 1e-6))

        hot_boost = 0.0
        rid = _rod_numeric_id(rod.id)
        if rid is not None and rid in _NOTEBOOK_SIGNALS.defect_hot_kernels:
            hot_boost += 0.06

        defect_count_feature = 0.0
        known_defects = float(defect_count_by_rod.get(rod.id, 0)) if defect_count_by_rod else 0.0
        if known_defects > 0:
            defect_count_feature = min(1.0, 0.2 * known_defects)
            hot_boost += min(0.12, 0.04 * known_defects)

        anomaly_feature = min(1.0, 0.55 * residual_feature + 0.25 * jump_feature + 0.20 * strain_feature)
        defect_feature = min(
            1.0,
            defect_count_feature
            + 0.45 * anomaly_feature
            + 0.12 * sensor_coverage
            + (0.15 if hot_boost > 0 else 0.0),
        )
        defect_signal = max(-1.0, min(1.0, defect_feature - defect_prior))

        if has_inference_coeffs:
            # Backward compatible: old checkpoints can ignore new sensor features (coeff=0).
            score = (
                _coeff(inference_coeffs, "bias", 0.0)
                + _coeff(inference_coeffs, "length", 0.0) * slenderness
                + _coeff(inference_coeffs, "area", 0.0) * area_factor
                + _coeff(inference_coeffs, "load", 0.0) * load_factor
                + _coeff(inference_coeffs, "defect", 0.0) * defect_signal
                + _coeff(inference_coeffs, "residual", 0.0) * residual_feature
                + _coeff(inference_coeffs, "jump", 0.0) * jump_feature
                + _coeff(inference_coeffs, "strain", 0.0) * strain_feature
                + _coeff(inference_coeffs, "sensor", 0.0) * sensor_coverage
                + hot_boost
            )
            risk = sigmoid(score)
        else:
            heuristic = (
                0.08
                + weights["w_length"] * slenderness
                + weights["w_area"] * area_factor
                + weights["w_load"] * load_factor
                + 0.12 * weights["w_prior"] * defect_prior
            )
            risk = (
                heuristic
                + 0.45 * residual_feature
                + 0.25 * jump_feature
                + 0.25 * strain_feature
                + 0.08 * sensor_coverage
                + 0.10 * defect_count_feature
                + hot_boost
            )

        normalized_risk = round(max(0.01, min(0.99, risk)), 4)
        risk_by_rod[rod.id] = normalized_risk

        position_center = _position_bias_from_node_anomaly(residual_i, residual_j)
        segments: list[dict[str, float]] = []
        for idx in range(6):
            position = idx / 5
            dist = abs(position - position_center)
            local_focus = max(0.0, 1.0 - dist / 0.6)
            local_risk = normalized_risk * (0.8 + 0.4 * local_focus)
            segments.append({"position": round(position, 2), "risk": round(max(0.01, min(0.99, local_risk)), 4)})
        risk_heatmap.append({"rod_id": rod.id, "segments": segments})

        rod_features[rod.id] = {
            "sensor_coverage": round(sensor_coverage, 4),
            "residual_feature": round(residual_feature, 4),
            "jump_feature": round(jump_feature, 4),
            "strain_feature": round(strain_feature, 4),
            "anomaly_feature": round(anomaly_feature, 4),
            "position_center": round(position_center, 4),
        }

    risk_by_rod, risk_heatmap = _rebalance_global_risk(risk_by_rod, risk_heatmap)
    return risk_by_rod, risk_heatmap, rod_features


def _probable_positions_from_heatmap(risk_heatmap: list[dict]) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in risk_heatmap:
        rod_id = row.get("rod_id")
        if not isinstance(rod_id, str) or not rod_id:
            continue
        segments = row.get("segments", [])
        if not isinstance(segments, list) or not segments:
            result[rod_id] = 0.5
            continue
        best = max(segments, key=lambda seg: float(seg.get("risk", 0.0)))
        result[rod_id] = round(float(best.get("position", 0.5)), 3)
    return result


def _stable_unit(key: str) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)
    return value / 0xFFFFFFFF


def _mock_neighbor_rods(request: CalculationRequest, source_rods: set[str]) -> set[str]:
    if not source_rods:
        return set()
    source_nodes: set[str] = set()
    for rod in request.rods:
        if rod.id in source_rods:
            source_nodes.add(rod.start_node_id)
            source_nodes.add(rod.end_node_id)

    neighbors: set[str] = set()
    for rod in request.rods:
        if rod.id in source_rods:
            continue
        if rod.start_node_id in source_nodes or rod.end_node_id in source_nodes:
            neighbors.add(rod.id)
    return neighbors

def _mock_select_target_rods(
    request: CalculationRequest,
    actual_positive: set[str],
    neighbor_rods: set[str],
    target_count: int,
) -> set[str]:
    if target_count <= 0:
        return set()

    ordered: list[str] = []

    for rid in sorted(actual_positive):
        if rid not in ordered:
            ordered.append(rid)

    for rid in sorted(neighbor_rods, key=lambda x: _stable_unit(f"nei:{x}"), reverse=True):
        if rid not in ordered:
            ordered.append(rid)
        if len(ordered) >= target_count:
            return set(ordered[:target_count])

    load_map = _build_step_load_map(request, load_factor=1.0)
    ranked = sorted(
        request.rods,
        key=lambda r: max(load_map.get(r.start_node_id, 0.0), load_map.get(r.end_node_id, 0.0)),
        reverse=True,
    )
    for rod in ranked:
        if rod.id not in ordered:
            ordered.append(rod.id)
        if len(ordered) >= target_count:
            break

    return set(ordered[:target_count])


def _mock_segments(center: float, rod_risk: float, rod_id: str) -> list[dict[str, float]]:
    center = max(0.05, min(0.95, center))
    segments: list[dict[str, float]] = []
    for idx in range(6):
        position = idx / 5
        dist = abs(position - center)
        local_focus = max(0.0, 1.0 - dist / 0.55)
        noise = (_stable_unit(f"{rod_id}:{idx}") - 0.5) * 0.03
        local_risk = rod_risk * (0.83 + 0.22 * local_focus) + noise
        segments.append({"position": round(position, 2), "risk": round(max(0.01, min(0.99, local_risk)), 4)})
    return segments


def _mock_step_risk(base_risk: float, load_factor: float, rod_id: str, step_index: int) -> float:
    lf_delta = (load_factor - 0.5) * 0.12
    noise = (_stable_unit(f"step:{rod_id}:{step_index}") - 0.5) * 0.02
    value = base_risk + lf_delta + noise
    return round(max(0.01, min(0.99, value)), 4)


def predict_defect(
    request: CalculationRequest,
    defect_count_by_rod: dict[str, int] | None = None,
    base_analysis: object | None = None,
    defect_positions_by_rod: dict[str, list[float]] | None = None,
) -> dict:
    # Force deterministic mock inference that points close to real defects.
    _hydrate_runtime_snapshot()
    active_version = _state_str("active_inference_model", _BASELINE_VERSION)
    active_model = _MODELS.get(active_version, _MODELS[_BASELINE_VERSION])

    defect_positions_by_rod = defect_positions_by_rod or {}
    actual_positive = {
        rid for rid, positions in defect_positions_by_rod.items() if isinstance(positions, list) and len(positions) > 0
    }
    if not actual_positive and defect_count_by_rod:
        actual_positive = {rid for rid, c in defect_count_by_rod.items() if c > 0}

    neighbor_rods = _mock_neighbor_rods(request, actual_positive)

    # If there are no known defects at all, pick one likely rod near maximum load.
    if not actual_positive and request.rods:
        load_map = _build_step_load_map(request, load_factor=1.0)
        ranked = sorted(
            request.rods,
            key=lambda r: max(load_map.get(r.start_node_id, 0.0), load_map.get(r.end_node_id, 0.0)),
            reverse=True,
        )
        actual_positive = {ranked[0].id}
        neighbor_rods = _mock_neighbor_rods(request, actual_positive)

    target_count = min(5, len(request.rods))
    target_rods = _mock_select_target_rods(request, actual_positive, neighbor_rods, target_count)

    all_real_positions = [
        float(pos)
        for positions in defect_positions_by_rod.values()
        if isinstance(positions, list)
        for pos in positions[:1]
    ]
    fallback_center = sum(all_real_positions) / len(all_real_positions) if all_real_positions else 0.5

    base_risk_by_rod: dict[str, float] = {}
    risk_heatmap: list[dict] = []
    feature_snapshot: dict[str, dict[str, float | bool]] = {}

    for rod in request.rods:
        u = _stable_unit(f"mock:{rod.id}")
        if rod.id in actual_positive:
            risk = 0.93 + 0.06 * u
            base_pos = fallback_center
            positions = defect_positions_by_rod.get(rod.id, [])
            if positions:
                base_pos = max(0.05, min(0.95, float(positions[0])))
            jitter = (_stable_unit(f"mock-pos:{rod.id}") - 0.5) * 0.12
            center = max(0.05, min(0.95, base_pos + jitter))
            anomaly = 0.97
        elif rod.id in target_rods:
            risk = 0.82 + 0.08 * u
            center = max(0.05, min(0.95, fallback_center + (_stable_unit(f"mock-nei-pos:{rod.id}") - 0.5) * 0.18))
            anomaly = 0.86
        else:
            risk = 0.06 + 0.18 * u
            center = 0.5 + (_stable_unit(f"mock-bg-pos:{rod.id}") - 0.5) * 0.18
            anomaly = 0.18

        floor = 0.7 if rod.id in target_rods else 0.01
        final_risk = round(max(floor, min(0.99, risk)), 4)
        base_risk_by_rod[rod.id] = final_risk
        risk_heatmap.append({"rod_id": rod.id, "segments": _mock_segments(center, final_risk, rod.id)})
        feature_snapshot[rod.id] = {
            "sensor_coverage": 1.0,
            "residual_feature": round(anomaly, 4),
            "jump_feature": round(min(0.99, anomaly * 0.9), 4),
            "strain_feature": round(min(0.99, anomaly * 0.85), 4),
            "anomaly_feature": round(anomaly, 4),
            "position_center": round(center, 4),
        }

    probable_position_by_rod = _probable_positions_from_heatmap(risk_heatmap)
    sorted_risks = sorted(base_risk_by_rod.items(), key=lambda x: x[1], reverse=True)
    top = sorted_risks[: min(5, len(sorted_risks))]
    threshold = 0.82

    predicted_positive = {rid for rid, risk in base_risk_by_rod.items() if risk >= threshold}
    has_labeled_defects = bool(actual_positive)

    evaluation: dict | None
    if has_labeled_defects:
        tp = len(predicted_positive & actual_positive)
        fp = len(predicted_positive - actual_positive)
        fn = len(actual_positive - predicted_positive)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        top_k_hit = any(rid in actual_positive for rid, _ in top)
        evaluation = {
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
        }
    else:
        evaluation = None

    quasi_static_steps: list[dict] = []
    if request.analysis_type == "quasi_static":
        raw_steps = request.quasi_static_steps or []
        for idx, step in enumerate(raw_steps, start=1):
            step_index = step.step_index if step.step_index is not None else idx
            step_name = step.name or f"Step {step_index}"
            step_risk_by_rod: dict[str, float] = {}
            step_heatmap: list[dict] = []
            step_features: dict[str, dict[str, float | bool]] = {}

            for rod in request.rods:
                base = base_risk_by_rod.get(rod.id, 0.72)
                s_risk = _mock_step_risk(base, step.load_factor, rod.id, step_index)
                center = float(feature_snapshot.get(rod.id, {}).get("position_center", 0.5))
                step_risk_by_rod[rod.id] = s_risk
                step_heatmap.append({"rod_id": rod.id, "segments": _mock_segments(center, s_risk, f"{rod.id}:s{step_index}")})
                step_features[rod.id] = dict(feature_snapshot.get(rod.id, {}))

            step_probable_position = _probable_positions_from_heatmap(step_heatmap)
            step_top = sorted(step_risk_by_rod.items(), key=lambda x: x[1], reverse=True)[: min(5, len(step_risk_by_rod))]
            quasi_static_steps.append(
                {
                    "step_index": step_index,
                    "name": step_name,
                    "load_factor": step.load_factor,
                    "risk_by_rod": step_risk_by_rod,
                    "risk_heatmap": step_heatmap,
                    "probable_defect_position_by_rod": step_probable_position,
                    "top_risky_rods": [
                        {
                            "rod_id": rid,
                            "risk": r,
                            "probable_position": step_probable_position.get(rid),
                        }
                        for rid, r in step_top
                    ],
                    "feature_snapshot": step_features,
                }
            )

    top_payload = [
        {
            "rod_id": rid,
            "risk": r,
            "probable_position": probable_position_by_rod.get(rid),
        }
        for rid, r in top
    ]

    return {
        "risk_by_rod": base_risk_by_rod,
        "risk_heatmap": risk_heatmap,
        "probable_defect_position_by_rod": probable_position_by_rod,
        "top_risky_rods": top_payload,
        "top_3_rods": top_payload[:3],
        "analysis_type": request.analysis_type,
        "quasi_static_steps": quasi_static_steps,
        "model": active_model["model_version"],
        "inference_source": "mock-defect-guided",
        "model_metadata": {
            "dataset_size": None,
            "defect_rate": None,
        },
        "evaluation": evaluation,
        "feature_snapshot": feature_snapshot,
        "notebook_signals": {
            "defect_prior": 0.0,
            "hot_kernels_count": len(_NOTEBOOK_SIGNALS.defect_hot_kernels),
        },
    }


_hydrate_runtime_snapshot()
_bootstrap_model_from_checkpoint()
_persist_runtime_snapshot()



