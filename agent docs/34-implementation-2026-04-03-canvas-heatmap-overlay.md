# 34 - Implementation Log (2026-04-03, canvas heatmap overlay)

Implemented in this iteration:

## Web constructor: heatmap visualization on scheme

- Added persistent storage for per-rod heatmap data in editor state:
  - `predictedRiskHeatmap` in store
  - `setPredictedRiskHeatmap` setter
  - included in project snapshots/save/load flow
- Updated prediction flow:
  - `useEditorPage.runPrediction` now stores backend `risk_heatmap` in state.
- Updated canvas renderer (`RodCanvas`):
  - if stress map is absent and heatmap exists for a rod, draws segment dots along rod
  - dot color intensity follows local risk value
  - keeps existing stress-based rendering priority when stress data exists

Updated files:

- `apps/web/src/entities/editor/model/types.ts`
- `apps/web/src/entities/editor/model/editorStore.ts`
- `apps/web/src/pages/editor-page/model/useEditorPage.ts`
- `apps/web/src/widgets/canvas-panel/ui/RodCanvas.tsx`

## Verification

- `pnpm lint:js` -> passed
- `pnpm --filter web build` -> passed
- `pnpm --filter training-dashboard build` -> passed
- `mypy app` -> passed
- `pytest tests -q` -> `5 passed`

## Gap impact

- Gap #10 neural visualization part improved:
  - defect probability heatmap is now visualized directly on the structural canvas, not only in result text widgets.
