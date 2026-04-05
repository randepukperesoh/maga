# 35 - Implementation Log (2026-04-03, model-scoped inference artifact)

Implemented in this iteration:

## Backend: model-scoped inference coefficients

- Updated inference pipeline in `apps/backend/app/services/nn.py`:
  - model cards now persist training `artifact` together with weights/history.
  - prediction now resolves coefficients in strict order:
    1. artifact of currently selected model (`active_inference_model`);
    2. checkpoint file only if `checkpoint.model_version` matches selected model;
    3. heuristic fallback.
- Added helpers:
  - `_artifact_coefficients(model)`
  - `_checkpoint_coefficients_for_model(model_version)`
- Added startup bootstrap helper:
  - `_bootstrap_model_from_checkpoint()`
  - imports model card from `risk_model.json` when snapshot does not yet contain that model.
- If active/last model is still baseline at startup, it is automatically switched to imported checkpoint model.
- Fixed previous global checkpoint coupling where one checkpoint could affect inference for another model version.
- Extended `inference_source` values:
  - `model-artifact`
  - `checkpoint`
  - `heuristic`

## Verification

- `pytest tests -q` (backend) -> `5 passed`
- `mypy app` (backend) -> passed

## Gap impact

- Gap #5 (neural integration parity) improved:
  - inference is now tied to the selected model version instead of a global checkpoint side effect.
- Gap #1 (runtime persistence resilience) improved:
  - trained checkpoint can repopulate model registry after restart.
