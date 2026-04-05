export type NodeDto = { id: string; x: number; y: number };

export type RodDto = {
  id: string;
  startNodeId: string;
  endNodeId: string;
  area: number;
  elasticModulus: number;
};

export type NodalLoadDto = {
  nodeId: string;
  fx: number;
  fy: number;
};

export type ConstraintDto = {
  nodeId: string;
  uxFixed: boolean;
  uyFixed: boolean;
};

export type DefectDto = {
  id: string;
  rodId: string;
  defectType: string;
  params: Record<string, number | string | boolean>;
};

export type CalculationResponseDto = {
  displacements: Record<string, number>;
  stresses: Record<string, number>;
};

export type TrainingStatusDto = {
  status: string;
  model_version: string;
  trained_steps: number;
  weights: Record<string, number>;
  active_inference_model?: string | null;
  model_family?: string | null;
};

export type TrainingHistoryPointDto = {
  step: number;
  loss: number;
  accuracy: number;
};

export type TrainingDatasetSampleDto = {
  id: string;
  name: string;
  payload: Record<string, unknown>;
  label: string | null;
  note: string | null;
  created_at: string;
};
