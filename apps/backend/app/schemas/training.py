from pydantic import BaseModel


class TrainingStartRequest(BaseModel):
    epochs: int = 5
    learning_rate: float = 0.01
    model_family: str = "notebook-informed"


class TrainingStatusResponse(BaseModel):
    status: str
    model_version: str
    trained_steps: int
    weights: dict[str, float]
    active_inference_model: str | None = None
    model_family: str | None = None


class TrainingHistoryPoint(BaseModel):
    step: int
    loss: float
    accuracy: float


class TrainingHistoryResponse(BaseModel):
    model_version: str
    points: list[TrainingHistoryPoint]


class InferenceModelRequest(BaseModel):
    model_version: str


class ModelCard(BaseModel):
    model_version: str
    model_family: str
    trained_steps: int
    created_at: str


class TrainingModelsResponse(BaseModel):
    active_inference_model: str | None
    models: list[ModelCard]


class TrainingStopResponse(BaseModel):
    status: str
    message: str


class TrainingLogLine(BaseModel):
    ts: str
    level: str
    message: str


class TrainingLogsResponse(BaseModel):
    lines: list[TrainingLogLine]


class DatasetSampleIn(BaseModel):
    name: str
    payload: dict
    label: str | None = None
    note: str | None = None


class DatasetSample(DatasetSampleIn):
    id: str
    created_at: str


class DatasetListResponse(BaseModel):
    items: list[DatasetSample]
