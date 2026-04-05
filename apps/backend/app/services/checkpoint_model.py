import json
import math
import os
from pathlib import Path
from typing import Any

_CACHE: dict[str, Any] = {"path": None, "mtime": None, "payload": None}


def default_checkpoint_path() -> Path:
    from_current = Path(__file__).resolve().parent.parent / "models" / "risk_model.json"
    env_path = os.getenv("RISK_MODEL_PATH")
    if env_path:
        return Path(env_path)
    return from_current


def load_checkpoint_model() -> dict[str, Any] | None:
    path = default_checkpoint_path()
    if not path.exists():
        return None
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None

    if (
        _CACHE["path"] == str(path)
        and _CACHE["mtime"] == mtime
        and isinstance(_CACHE["payload"], dict)
    ):
        return _CACHE["payload"]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    _CACHE["path"] = str(path)
    _CACHE["mtime"] = mtime
    _CACHE["payload"] = payload
    return payload


def save_checkpoint_model(payload: dict[str, Any]) -> None:
    path = default_checkpoint_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    _CACHE["path"] = str(path)
    _CACHE["mtime"] = path.stat().st_mtime
    _CACHE["payload"] = payload


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)
