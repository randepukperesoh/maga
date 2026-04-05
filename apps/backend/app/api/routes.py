import asyncio
from io import BytesIO
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.schemas.analysis import CalculationRequest, CalculationResponse, QuasiStaticStep
from app.schemas.common import HealthResponse
from app.schemas.defect import Defect, DefectIn
from app.schemas.report import ReportRequest
from app.schemas.quasi_static import (
    QuasiStaticComparisonArtifactIn,
    QuasiStaticRun,
    QuasiStaticRunArtifact,
    QuasiStaticRunArtifactListResponse,
    QuasiStaticRunListResponse,
    QuasiStaticRunRequest,
    QuasiStaticScenario,
    QuasiStaticScenarioIn,
    QuasiStaticScenarioListResponse,
)
from app.schemas.training import (
    DatasetListResponse,
    DatasetSample,
    DatasetSampleIn,
    InferenceModelRequest,
    ModelCard,
    TrainingHistoryResponse,
    TrainingLogsResponse,
    TrainingModelsResponse,
    TrainingStartRequest,
    TrainingStatusResponse,
    TrainingStopResponse,
)
from app.services.defects import apply_defects_to_result, defects
from app.services.fem import run_fem
from app.services.nn import (
    add_dataset_sample,
    delete_dataset_sample,
    get_training_history,
    get_training_logs,
    get_training_status,
    get_training_stream_payload,
    list_dataset,
    list_models,
    predict_defect,
    set_inference_model,
    start_training,
    stop_training,
    update_dataset_sample,
)
from app.services.pdf import generate_report_pdf
from app.db.training_store import (
    add_quasi_static_run_artifact,
    add_quasi_static_run,
    add_quasi_static_scenario,
    delete_quasi_static_run_artifact,
    delete_quasi_static_scenario,
    get_quasi_static_run_artifact,
    get_quasi_static_run,
    get_quasi_static_scenario,
    list_quasi_static_run_artifacts,
    list_quasi_static_runs,
    list_quasi_static_scenarios,
    update_quasi_static_scenario,
)

router = APIRouter()


def _default_quasi_static_steps() -> list[QuasiStaticStep]:
    return [
        QuasiStaticStep(step_index=1, name="Step 1", load_factor=0.25),
        QuasiStaticStep(step_index=2, name="Step 2", load_factor=0.5),
        QuasiStaticStep(step_index=3, name="Step 3", load_factor=0.75),
        QuasiStaticStep(step_index=4, name="Step 4", load_factor=1.0),
    ]


def _normalize_default_quasi_static_request(request: CalculationRequest) -> CalculationRequest:
    return request.model_copy(
        update={
            "analysis_type": "quasi_static",
            "quasi_static_steps": request.quasi_static_steps or _default_quasi_static_steps(),
        }
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/calculate", response_model=CalculationResponse)
def calculate(request: CalculationRequest) -> CalculationResponse:
    normalized = _normalize_default_quasi_static_request(request)
    return run_fem(normalized)


@router.post("/defect/add", response_model=Defect)
def add_defect(item: DefectIn) -> Defect:
    defect_id = str(uuid4())
    return defects.add(defect_id, item)


@router.put("/defect/{defect_id}", response_model=Defect)
def update_defect(defect_id: str, item: DefectIn) -> Defect:
    updated = defects.update(defect_id, item)
    if updated is None:
        raise HTTPException(status_code=404, detail="Defect not found")
    return updated


@router.delete("/defect/{defect_id}")
def delete_defect(defect_id: str) -> dict:
    deleted = defects.delete(defect_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Defect not found")
    return {"status": "deleted"}


@router.get("/defect/{rod_id}", response_model=list[Defect])
def get_defects(rod_id: str) -> list[Defect]:
    return defects.by_rod(rod_id)


@router.post("/defect/recalculate", response_model=CalculationResponse)
def recalculate(request: CalculationRequest) -> CalculationResponse:
    normalized = _normalize_default_quasi_static_request(request)
    base = run_fem(normalized)
    return apply_defects_to_result(normalized, base, defects)


@router.post("/predict-defect")
def predict(request: CalculationRequest) -> dict:
    normalized = _normalize_default_quasi_static_request(request)
    base_analysis = run_fem(normalized)
    defect_count_by_rod = {rod.id: len(defects.by_rod(rod.id)) for rod in normalized.rods}
    defect_positions_by_rod = {
        rod.id: [float(d.params.get("position", 0.5)) for d in defects.by_rod(rod.id)]
        for rod in normalized.rods
    }
    return predict_defect(
        normalized,
        defect_count_by_rod=defect_count_by_rod,
        base_analysis=base_analysis,
        defect_positions_by_rod=defect_positions_by_rod,
    )


@router.get("/training/status", response_model=TrainingStatusResponse)
def training_status() -> TrainingStatusResponse:
    return TrainingStatusResponse(**get_training_status())


@router.get("/training/history", response_model=TrainingHistoryResponse)
def training_history(model_version: str | None = None) -> TrainingHistoryResponse:
    return TrainingHistoryResponse(**get_training_history(model_version=model_version))


@router.get("/training/models", response_model=TrainingModelsResponse)
def training_models() -> TrainingModelsResponse:
    payload = list_models()
    return TrainingModelsResponse(
        active_inference_model=payload["active_inference_model"],
        models=[ModelCard(**m) for m in payload["models"]],
    )


@router.post("/training/inference-model")
def training_set_inference_model(request: InferenceModelRequest) -> dict:
    try:
        return set_inference_model(request.model_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/training/start", response_model=TrainingStatusResponse)
def training_start(request: TrainingStartRequest) -> TrainingStatusResponse:
    model = start_training(request.epochs, request.learning_rate, request.model_family)
    return TrainingStatusResponse(
        status="trained",
        model_version=model["model_version"],
        trained_steps=model["trained_steps"],
        weights=model["weights"],
        active_inference_model=model["active_inference_model"],
        model_family=model["model_family"],
    )


@router.post("/training/stop", response_model=TrainingStopResponse)
def training_stop() -> TrainingStopResponse:
    payload = stop_training()
    return TrainingStopResponse(**payload)


@router.get("/training/logs", response_model=TrainingLogsResponse)
def training_logs(limit: int = 200) -> TrainingLogsResponse:
    return TrainingLogsResponse(**get_training_logs(limit=limit))


@router.websocket("/training/ws")
async def training_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(get_training_stream_payload(log_limit=80))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return


@router.get("/training/dataset", response_model=DatasetListResponse)
def training_dataset_list() -> DatasetListResponse:
    return DatasetListResponse(**list_dataset())


@router.post("/training/dataset", response_model=DatasetSample)
def training_dataset_add(payload: DatasetSampleIn) -> DatasetSample:
    return DatasetSample(**add_dataset_sample(payload))


@router.put("/training/dataset/{sample_id}", response_model=DatasetSample)
def training_dataset_update(sample_id: str, payload: DatasetSampleIn) -> DatasetSample:
    updated = update_dataset_sample(sample_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Dataset sample not found")
    return DatasetSample(**updated)


@router.delete("/training/dataset/{sample_id}")
def training_dataset_delete(sample_id: str) -> dict:
    deleted = delete_dataset_sample(sample_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset sample not found")
    return {"status": "deleted"}


@router.post("/report")
def report(request: ReportRequest) -> StreamingResponse:
    pdf_bytes = generate_report_pdf(request)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="report.pdf"'},
    )


@router.get("/quasi-static/scenarios", response_model=QuasiStaticScenarioListResponse)
def get_quasi_static_scenarios() -> QuasiStaticScenarioListResponse:
    rows = list_quasi_static_scenarios()
    return QuasiStaticScenarioListResponse(
        items=[
            QuasiStaticScenario(
                id=row["id"],
                name=row["name"],
                description=row.get("description"),
                request=CalculationRequest.model_validate(row["request_payload"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
    )


@router.post("/quasi-static/scenarios", response_model=QuasiStaticScenario)
def create_quasi_static_scenario(payload: QuasiStaticScenarioIn) -> QuasiStaticScenario:
    request = payload.request.model_copy(update={"analysis_type": "quasi_static"})
    row = add_quasi_static_scenario(
        {
            "id": str(uuid4()),
            "name": payload.name,
            "description": payload.description,
            "request_payload": request.model_dump(by_alias=True),
        }
    )
    return QuasiStaticScenario(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        request=request,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/quasi-static/scenarios/{scenario_id}", response_model=QuasiStaticScenario)
def get_quasi_static_scenario_by_id(scenario_id: str) -> QuasiStaticScenario:
    row = get_quasi_static_scenario(scenario_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return QuasiStaticScenario(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        request=CalculationRequest.model_validate(row["request_payload"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.put("/quasi-static/scenarios/{scenario_id}", response_model=QuasiStaticScenario)
def update_quasi_static_scenario_by_id(
    scenario_id: str, payload: QuasiStaticScenarioIn
) -> QuasiStaticScenario:
    request = payload.request.model_copy(update={"analysis_type": "quasi_static"})
    row = update_quasi_static_scenario(
        scenario_id,
        {
            "name": payload.name,
            "description": payload.description,
            "request_payload": request.model_dump(by_alias=True),
        },
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return QuasiStaticScenario(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        request=request,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.delete("/quasi-static/scenarios/{scenario_id}")
def delete_quasi_static_scenario_by_id(scenario_id: str) -> dict:
    deleted = delete_quasi_static_scenario(scenario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"status": "deleted"}


@router.post("/quasi-static/scenarios/{scenario_id}/run", response_model=QuasiStaticRun)
def run_quasi_static_scenario(scenario_id: str, payload: QuasiStaticRunRequest) -> QuasiStaticRun:
    row = get_quasi_static_scenario(scenario_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    request = CalculationRequest.model_validate(row["request_payload"]).model_copy(
        update={"analysis_type": "quasi_static"}
    )
    analysis = run_fem(request)

    prediction = None
    if payload.run_inference:
        defect_count_by_rod = {rod.id: len(defects.by_rod(rod.id)) for rod in request.rods}
        defect_positions_by_rod = {
            rod.id: [float(d.params.get("position", 0.5)) for d in defects.by_rod(rod.id)]
            for rod in request.rods
        }
        prediction = predict_defect(
            request,
            defect_count_by_rod=defect_count_by_rod,
            base_analysis=analysis,
            defect_positions_by_rod=defect_positions_by_rod,
        )

    saved = add_quasi_static_run(
        {
            "id": str(uuid4()),
            "scenario_id": scenario_id,
            "status": "done",
            "result_payload": {
                "analysis": analysis.model_dump(by_alias=True),
                "prediction": prediction,
            },
        }
    )
    return QuasiStaticRun(**saved)


@router.get("/quasi-static/scenarios/{scenario_id}/runs", response_model=QuasiStaticRunListResponse)
def get_quasi_static_scenario_runs(scenario_id: str) -> QuasiStaticRunListResponse:
    if get_quasi_static_scenario(scenario_id) is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    rows = list_quasi_static_runs(scenario_id)
    return QuasiStaticRunListResponse(items=[QuasiStaticRun(**row) for row in rows])


@router.get("/quasi-static/runs/{run_id}", response_model=QuasiStaticRun)
def get_quasi_static_run_by_id(run_id: str) -> QuasiStaticRun:
    row = get_quasi_static_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return QuasiStaticRun(**row)


@router.get("/quasi-static/runs/{run_id}/steps/{step_index}")
def get_quasi_static_run_step(run_id: str, step_index: int) -> dict:
    row = get_quasi_static_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    analysis_steps = (
        row["result_payload"].get("analysis", {}).get("quasiStaticSteps", [])
        if isinstance(row.get("result_payload"), dict)
        else []
    )
    prediction_steps = (
        row["result_payload"].get("prediction", {}).get("quasi_static_steps", [])
        if isinstance(row.get("result_payload"), dict)
        else []
    )
    analysis_step = next((x for x in analysis_steps if int(x.get("stepIndex", -1)) == step_index), None)
    prediction_step = next((x for x in prediction_steps if int(x.get("step_index", -1)) == step_index), None)
    if analysis_step is None and prediction_step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    return {
        "run_id": run_id,
        "step_index": step_index,
        "analysis_step": analysis_step,
        "prediction_step": prediction_step,
    }


@router.post("/quasi-static/runs/{run_id}/artifacts/comparison", response_model=QuasiStaticRunArtifact)
def create_quasi_static_comparison_artifact(
    run_id: str, payload: QuasiStaticComparisonArtifactIn
) -> QuasiStaticRunArtifact:
    if get_quasi_static_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    saved = add_quasi_static_run_artifact(
        {
            "id": str(uuid4()),
            "run_id": run_id,
            "artifact_type": "comparison",
            "payload": payload.model_dump(),
        }
    )
    return QuasiStaticRunArtifact(**saved)


@router.get("/quasi-static/runs/{run_id}/artifacts", response_model=QuasiStaticRunArtifactListResponse)
def get_quasi_static_run_artifacts(
    run_id: str, limit: int = 20, offset: int = 0, sort: Literal["asc", "desc"] = "desc"
) -> QuasiStaticRunArtifactListResponse:
    if get_quasi_static_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    payload = list_quasi_static_run_artifacts(run_id, limit=limit, offset=offset, sort=sort)
    return QuasiStaticRunArtifactListResponse(
        items=[QuasiStaticRunArtifact(**row) for row in payload["items"]],
        total=payload["total"],
        limit=payload["limit"],
        offset=payload["offset"],
        sort=payload["sort"],
        has_more=payload["has_more"],
    )


@router.get("/quasi-static/runs/{run_id}/artifacts/{artifact_id}", response_model=QuasiStaticRunArtifact)
def get_quasi_static_run_artifact_by_id(run_id: str, artifact_id: str) -> QuasiStaticRunArtifact:
    if get_quasi_static_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    row = get_quasi_static_run_artifact(artifact_id)
    if row is None or row["run_id"] != run_id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return QuasiStaticRunArtifact(**row)


@router.delete("/quasi-static/runs/{run_id}/artifacts/{artifact_id}")
def delete_quasi_static_run_artifact_by_id(run_id: str, artifact_id: str) -> dict:
    if get_quasi_static_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    row = get_quasi_static_run_artifact(artifact_id)
    if row is None or row["run_id"] != run_id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    deleted = delete_quasi_static_run_artifact(artifact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {"status": "deleted"}
