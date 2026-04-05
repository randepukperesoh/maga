# 39 - Implementation Log (2026-04-03, canvas interaction mode)

Implemented in this iteration:

## Web constructor: explicit interaction mode

- Added persistent canvas interaction mode in editor project model:
  - `analysis.interactionMode: "add-node" | "connect-nodes"`
- Updated type and store normalization/defaults:
  - `apps/web/src/entities/editor/model/types.ts`
  - `apps/web/src/entities/editor/model/editorStore.ts`

- Extended toolbar (shadcn) with mode selector:
  - `Canvas mode` with options:
    - `Add nodes`
    - `Connect nodes`
  - file: `apps/web/src/widgets/editor-toolbar/ui/EditorToolbar.tsx`

- Wired mode through page VM and page UI:
  - `apps/web/src/pages/editor-page/model/useEditorPage.ts`
  - `apps/web/src/pages/editor-page/ui/EditorPage.tsx`

- Updated canvas click behavior:
  - in `add-node` mode: click on empty canvas creates a node
  - in `connect-nodes` mode: clicking nodes runs quick rod-connection flow
  - file: `apps/web/src/widgets/canvas-panel/ui/RodCanvas.tsx`

## Verification

- `pnpm lint:js` -> passed
- `pnpm --filter web build` -> passed

## Gap impact

- Gap #6 (constructor UX) improved:
  - node/rod creation behavior is now explicit and predictable for user workflows.
