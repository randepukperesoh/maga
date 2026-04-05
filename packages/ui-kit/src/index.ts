// Placeholder ui-kit entrypoint for shared UI primitives across apps.
// Concrete components are currently consumed directly from local shadcn setups in apps.

export type UiTone = "default" | "secondary" | "destructive" | "outline" | "ghost";

export type UiSize = "xs" | "sm" | "md" | "lg";

export type UiOption = {
  value: string;
  label: string;
};
