from pydantic import BaseModel


class ReportDefectItem(BaseModel):
    id: str
    rod_id: str
    defect_type: str
    position: float | None = None
    depth: float | None = None


class ReportRiskItem(BaseModel):
    rod_id: str
    risk: float


class ReportHeatmapSegment(BaseModel):
    position: float
    risk: float


class ReportHeatmapItem(BaseModel):
    rod_id: str
    segments: list[ReportHeatmapSegment] = []


class ReportEvaluation(BaseModel):
    threshold: float
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    top_k_hit: bool
    actual_defect_rods: int
    predicted_defect_rods: int


class ReportModelMetadata(BaseModel):
    dataset_size: int | None = None
    defect_rate: float | None = None


class ReportNodeItem(BaseModel):
    id: str
    x: float
    y: float


class ReportRodItem(BaseModel):
    id: str
    start_node_id: str
    end_node_id: str


class ReportRequest(BaseModel):
    title: str = "Rod System Designer Report"
    nodes_count: int = 0
    rods_count: int = 0
    defects_count: int = 0
    stresses: dict[str, float] = {}
    top_risky_rods: list[ReportRiskItem] = []
    risk_heatmap: list[ReportHeatmapItem] = []
    defects: list[ReportDefectItem] = []
    nodes: list[ReportNodeItem] = []
    rods: list[ReportRodItem] = []
    model: str | None = None
    inference_source: str | None = None
    model_metadata: ReportModelMetadata | None = None
    evaluation: ReportEvaluation | None = None
    quasi_static_steps: list[dict] = []
