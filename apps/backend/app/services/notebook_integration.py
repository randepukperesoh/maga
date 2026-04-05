import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NotebookSignals:
    class_priors: dict[int, float]
    defect_hot_kernels: set[int]


_DEFECT_ON_RE = re.compile(r'"defect_on"\s*:\s*(\d+)')
_DEFECT_KERNEL_RE = re.compile(r'\{"id"\s*:\s*(\d+).*?"defect"\s*:\s*True')


def _safe_read_notebook(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def load_notebook_signals(notebook_path: Path) -> NotebookSignals:
    text = _safe_read_notebook(notebook_path)
    if not text:
        return NotebookSignals(
            class_priors={0: 0.25, 1: 0.25, 2: 0.25, 3: 0.25}, defect_hot_kernels=set()
        )

    defect_on_values = [int(x) for x in _DEFECT_ON_RE.findall(text)]
    total = len(defect_on_values)
    if total == 0:
        class_priors = {0: 0.25, 1: 0.25, 2: 0.25, 3: 0.25}
    else:
        counts = {0: 0, 1: 0, 2: 0, 3: 0}
        for v in defect_on_values:
            if v in counts:
                counts[v] += 1
        class_priors = {k: counts[k] / total for k in counts}

    hot_ids = {int(x) for x in _DEFECT_KERNEL_RE.findall(text)}
    return NotebookSignals(class_priors=class_priors, defect_hot_kernels=hot_ids)


def build_notebook_artifact(signals: NotebookSignals) -> dict:
    defect_prior = max(0.0, min(1.0, 1.0 - signals.class_priors.get(0, 0.25)))
    hot_density = min(1.0, len(signals.defect_hot_kernels) / 40.0)
    return {
        "kind": "linear-risk-v2",
        "feature_order": ["bias", "length", "area", "load", "defect"],
        "coefficients": {
            "bias": round(-1.25 + 1.4 * defect_prior + 0.2 * hot_density, 6),
            "length": round(0.34 + 0.06 * hot_density, 6),
            "area": round(0.30 - 0.04 * hot_density, 6),
            "load": round(0.20 + 0.03 * defect_prior, 6),
            "defect": round(0.16 + 0.12 * defect_prior, 6),
        },
        "metadata": {
            "source": "notebook-derived",
            "class_priors": {str(k): round(v, 6) for k, v in signals.class_priors.items()},
            "hot_kernels_count": len(signals.defect_hot_kernels),
            "defect_prior": round(defect_prior, 6),
        },
    }


def default_notebook_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "Дип.ipynb"
        if candidate.exists():
            return candidate
    return current.parent / "Дип.ipynb"
