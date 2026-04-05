# 26 - Implementation Log (2026-04-03, lint cleanup)

Implemented in this iteration:

## JavaScript/TypeScript quality cleanup

- Brought `lint:js` to clean state (no warnings/errors in current scope).
- Fixed unstable keyboard handler dependencies in editor view-model:
  - converted `notify`, `handleRemoveLastNode`, `handleRemoveLastRod` to `useCallback`
  - aligned `useEffect` dependency array for hotkeys
- Updated file:
  - `apps/web/src/pages/editor-page/model/useEditorPage.ts`

## ESLint config refinement for shadcn ui

- Disabled `react-refresh/only-export-components` specifically for generated `components/ui` files in both apps.
- Kept rule active for the rest of source code.
- Updated file:
  - `eslint.config.mjs`

## Verification

- `pnpm lint:js` -> passed (clean)
- `pnpm --filter web build` -> passed
- `pnpm --filter training-dashboard build` -> passed
- `pytest tests -q` (backend) -> `5 passed`

## Gap impact

- Gap #9 (code quality) improved:
  - lint baseline now operational and clean for target frontend source scope.
