from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class Node(AnalysisBaseModel):
    id: str
    x: float
    y: float


class Rod(AnalysisBaseModel):
    id: str
    start_node_id: str = Field(alias="startNodeId")
    end_node_id: str = Field(alias="endNodeId")
    area: float
    elastic_modulus: float = Field(alias="elasticModulus")


class NodalLoad(AnalysisBaseModel):
    node_id: str = Field(alias="nodeId")
    fx: float = 0.0
    fy: float = 0.0


class Constraint(AnalysisBaseModel):
    node_id: str = Field(alias="nodeId")
    ux_fixed: bool = Field(default=True, alias="uxFixed")
    uy_fixed: bool = Field(default=True, alias="uyFixed")


class QuasiStaticStep(AnalysisBaseModel):
    step_index: int | None = Field(default=None, alias="stepIndex")
    name: str | None = None
    load_factor: float = Field(default=1.0, alias="loadFactor")
    load_fx: float | None = Field(default=None, alias="loadFx")
    load_fy: float | None = Field(default=None, alias="loadFy")


class CalculationRequest(AnalysisBaseModel):
    nodes: list[Node]
    rods: list[Rod]
    loads: list[NodalLoad] = []
    constraints: list[Constraint] = []
    analysis_type: Literal["static", "quasi_static"] = Field(default="static", alias="analysisType")
    quasi_static_steps: list[QuasiStaticStep] = Field(default_factory=list, alias="quasiStaticSteps")


class QuasiStaticStepResult(AnalysisBaseModel):
    step_index: int = Field(alias="stepIndex")
    name: str
    load_factor: float = Field(alias="loadFactor")
    displacements: dict[str, float]
    stresses: dict[str, float]


class CalculationResponse(AnalysisBaseModel):
    displacements: dict[str, float]
    stresses: dict[str, float]
    analysis_type: Literal["static", "quasi_static"] = Field(default="static", alias="analysisType")
    quasi_static_steps: list[QuasiStaticStepResult] = Field(default_factory=list, alias="quasiStaticSteps")
