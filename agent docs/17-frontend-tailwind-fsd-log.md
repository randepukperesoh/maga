# 17 - Frontend Tailwind + FSD Refactor Log

Date: 2026-04-01

## Done

- Added TailwindCSS to `apps/web` and `apps/training-dashboard` with PostCSS config and base style entrypoints.
- Refactored `apps/web` to FSD-like structure:
  - `app` layer: app entry and global styles.
  - `pages/editor-page`: page composition and `useEditorPage` hook.
  - `widgets`: toolbar, defects panel, results panel, canvas panel.
  - `features/editor/api`: API calls separated from UI logic.
  - `entities/editor/model`: domain types and zustand store.
  - `shared/api`: isolated HTTP client.
- Refactored `apps/training-dashboard` to FSD-like structure:
  - `app` layer.
  - `pages/training-page` with `useTrainingPage` hook.
  - `widgets`: controls, metrics, chart.
  - `features/training/api` and `entities/training/model`.
  - `shared/api` client.
- Updated frontend visual style to cleaner modern cards, spacing, hierarchy and responsive layout using Tailwind utility classes.

## Validation

- `pnpm --filter web build` passed.
- `pnpm --filter training-dashboard build` passed.

## Notes

- Neural-network behavior remains mocked from backend side, as requested.
- Legacy files were kept for compatibility during transition; active imports now point to new FSD paths.

---

Date: 2026-04-02

## Iteration Update

- Stabilized dashboard polling to remove layout jitter on each backend request:
  - Added silent background refresh mode in `useTrainingPage` (`silent` + `includeModels` options).
  - Split states into `loading` (initial/manual) and `refreshing` (polling) to avoid full-page loading toggles during interval updates.
  - Added in-flight request guard to prevent overlapping poll calls.
  - Reduced unnecessary `models` refetch on every poll; models now refresh on first load or explicit include.
- Updated dashboard UI status behavior:
  - Added lightweight header sync badge (`Syncing...`) for background polling.
  - Added fixed-height status area for loading/error messages to avoid vertical reflow jumps.

## Validation

- `pnpm --filter training-dashboard build` passed.

## Iteration Update (Layout Jump Fix)

- Eliminated remaining layout-shift points on dashboard polling:
  - header sync indicator no longer appears/disappears, only inner state changes;
  - status notification area now keeps fixed height with placeholder slot;
  - chart/table widgets now use fixed minimum heights;
  - history table got fixed scroll container height (`max-h`) to prevent growing/shrinking with row count;
  - raw payload panel constrained by fixed max height with internal scrolling.

## Iteration Update (Official shadcn Migration)

- Initialized official shadcn in `apps/training-dashboard` via CLI (`shadcn init`) after adding `@/*` alias in:
  - `tsconfig.json`
  - `vite.config.ts`
- Installed official components via CLI (`shadcn add`):
  - `button`, `card`, `input`, `select`, `badge`, `table`, `label`, `switch`.
- Migrated dashboard UI from custom primitives to official shadcn components in:
  - `TrainingPage`
  - `TrainingControls`
  - `TrainingMetrics`
  - `TrainingChart`
  - `TrainingHistoryTable`
  - `TrainingRunSummary`
  - `TrainingCompareDelta`
- Removed temporary homemade pseudo-shadcn files from `src/shared/ui`.
- Simplified global CSS to avoid mixed design-system conflicts and preserve minimal styling.

## Validation

- `pnpm --filter training-dashboard build` passed after shadcn migration.

---

Date: 2026-04-02

## Iteration Update (UI Cleanup + RU Localization)

- Redesigned control panel layout to remove "tetris" effect:
  - moved to 12-column grid with fixed button heights/widths and aligned form blocks.
- Improved visual consistency and readability:
  - softer background gradients, cleaner shadows, stronger text contrast.
  - reduced overly heavy typography accents and normalized numeric rendering via tabular numerals.
- Added Russian localization across dashboard UI (except domain terms like `loss`, `accuracy`, `inference`, `learning rate`).
- Additional anti-jitter fixes:
  - after first bootstrap, all subsequent status requests use non-blocking refresh indicator instead of global loading state.
  - reserved header space for sync chip to avoid layout shift when polling.

## Validation

- `pnpm --filter training-dashboard build` passed.

---

Date: 2026-04-02

## Iteration Update (Design Consistency Pass)

- Introduced a unified style system for the dashboard in `apps/training-dashboard/src/app/styles/index.css`:
  - Diamond/premium color tokens.
  - Reusable component classes (`td-panel`, `td-panel-dark`, `td-title`, `td-subtle`, `td-chip`, `td-input`, `td-button*`, `td-kpi`).
  - Updated global background and surface treatment for consistent visual language.
- Refactored dashboard widgets to the same design primitives:
  - `TrainingPage`, `TrainingControls`, `TrainingMetrics`, `TrainingChart`,
    `TrainingHistoryTable`, `TrainingRunSummary`, `TrainingCompareDelta`, `ToastStack`.
- Result: unified hierarchy, button/input/card consistency, and cleaner cross-widget styling without ad-hoc color mixes.

## Validation

- `pnpm --filter training-dashboard build` passed.
