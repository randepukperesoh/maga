from pydantic import BaseModel, Field

from app.schemas.analysis import CalculationRequest


class QuasiStaticScenarioIn(BaseModel):
    name: str
    description: str | None = None
    request: CalculationRequest


class QuasiStaticScenario(QuasiStaticScenarioIn):
    id: str
    created_at: str
    updated_at: str


class QuasiStaticScenarioListResponse(BaseModel):
    items: list[QuasiStaticScenario]


class QuasiStaticRunRequest(BaseModel):
    run_inference: bool = True


class QuasiStaticRun(BaseModel):
    id: str
    scenario_id: str
    status: str
    created_at: str
    result_payload: dict


class QuasiStaticRunListResponse(BaseModel):
    items: list[QuasiStaticRun]


class QuasiStaticComparisonRodDelta(BaseModel):
    rod_id: str
    stress_from: float
    stress_to: float
    stress_delta: float
    risk_from: float
    risk_to: float
    risk_delta: float


class QuasiStaticComparisonArtifactIn(BaseModel):
    from_step: int
    to_step: int
    filter_mode: str = "all"
    min_change: float = 0.0
    rod_deltas: list[QuasiStaticComparisonRodDelta] = Field(default_factory=list)


class QuasiStaticRunArtifact(BaseModel):
    id: str
    run_id: str
    artifact_type: str
    payload: dict
    created_at: str


class QuasiStaticRunArtifactListResponse(BaseModel):
    items: list[QuasiStaticRunArtifact]
    total: int = 0
    limit: int = 0
    offset: int = 0
    sort: str = "desc"
    has_more: bool = False
