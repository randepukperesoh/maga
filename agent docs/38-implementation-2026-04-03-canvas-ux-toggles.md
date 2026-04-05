# 38 - Implementation Log (2026-04-03, canvas UX toggles)

Implemented in this iteration:

## Web constructor: explicit drag/snap controls

- Added persistent canvas UX settings to editor project model:
  - `analysis.dragNodes`
  - `analysis.snapToGrid`
- Updated store defaults and normalize/save/load flow in:
  - `apps/web/src/entities/editor/model/types.ts`
  - `apps/web/src/entities/editor/model/editorStore.ts`

- Extended toolbar with official shadcn switches:
  - `Drag nodes`
  - `Snap to grid`
  - file: `apps/web/src/widgets/editor-toolbar/ui/EditorToolbar.tsx`

- Wired settings through page model and page UI:
  - `apps/web/src/pages/editor-page/model/useEditorPage.ts`
  - `apps/web/src/pages/editor-page/ui/EditorPage.tsx`

- Updated canvas behavior in `apps/web/src/widgets/canvas-panel/ui/RodCanvas.tsx`:
  - adding node now respects `snapToGrid`
  - node movement now respects both toggles
  - when drag is disabled, nodes are locked (`lockMovementX/Y`)

## Verification

- `pnpm lint:js` -> passed
- `pnpm --filter web build` -> passed

## Gap impact

- Gap #6 (constructor UX) improved:
  - node interaction is now explicitly controllable by user, with predictable snap behavior.
