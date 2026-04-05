# 37 - Implementation Log (2026-04-03, notebook-derived baseline artifact)

Implemented in this iteration:

## Backend: notebook-derived baseline model artifact

- Extended notebook integration service:
  - Added `build_notebook_artifact(signals)` in `apps/backend/app/services/notebook_integration.py`.
  - Artifact is built from notebook signals (`class_priors`, `defect_hot_kernels`) and provides linear coefficients:
    - `bias`, `length`, `area`, `load`, `defect`
  - Added metadata block with source and notebook-derived priors.

- Updated training/inference runtime in `apps/backend/app/services/nn.py`:
  - Baseline model now has an explicit artifact (`_BASELINE_ARTIFACT`) generated from notebook signals.
  - Baseline weights are initialized from artifact coefficients instead of hardcoded-only values.
  - Baseline version bumped to `notebook-informed-baseline-v3`.
  - Added `_ensure_baseline_model()` to keep backward compatibility with old runtime snapshots and prevent missing-model KeyError.

## Why this improves gap #5

- Even without external checkpoint, inference for baseline model can now run through model coefficients (`model-artifact`) derived from notebook data, rather than pure heuristic fallback.
- Integration with `Дип.ipynb` becomes more explicit and reproducible.

## Verification

- `pytest tests -q` (backend) -> `5 passed`
- `mypy app` (backend) -> passed
