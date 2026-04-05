# 36 - Implementation Log (2026-04-03, PDF AI details)

Implemented in this iteration:

## Backend: richer AI block in PDF report

- Extended report schema in `apps/backend/app/schemas/report.py`:
  - `risk_heatmap`
  - `model`
  - `inference_source`
  - `model_metadata`
  - `evaluation`
- Updated PDF generator in `apps/backend/app/services/pdf.py`:
  - added new section `AI Details`
  - prints model version and inference source
  - prints model metadata (`dataset_size`, `defect_rate`) when available
  - prints quality metrics (`precision`, `recall`, `F1`, TP/FP/FN, top-k hit)
  - prints heatmap summary: max local risk by rod (top rows)

## Frontend: export additional AI payload to report endpoint

- Updated `apps/web/src/pages/editor-page/model/useEditorPage.ts`:
  - `downloadPdf` now includes `risk_heatmap`, `model`, `inference_source`, `model_metadata`, `evaluation` in `/report` payload.

## Verification

- `pytest tests -q` (backend) -> `5 passed`
- `mypy app` (backend) -> passed
- `pnpm --filter web build` -> passed

## Gap impact

- Gap #8 (PDF completeness) improved:
  - report now includes explicit AI-model context and prediction-quality diagnostics, not only top risky rods.
