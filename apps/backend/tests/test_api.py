from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _sample_payload() -> dict:
    return {
        "nodes": [
            {"id": "n1", "x": 0, "y": 0},
            {"id": "n2", "x": 100, "y": 0},
            {"id": "n3", "x": 200, "y": 0},
        ],
        "rods": [
            {
                "id": "r1",
                "startNodeId": "n1",
                "endNodeId": "n2",
                "area": 0.01,
                "elasticModulus": 2e11,
            },
            {
                "id": "r2",
                "startNodeId": "n2",
                "endNodeId": "n3",
                "area": 0.01,
                "elasticModulus": 2e11,
            },
        ],
        "loads": [{"nodeId": "n3", "fx": 1000, "fy": 0}],
        "constraints": [{"nodeId": "n1", "uxFixed": True, "uyFixed": True}],
    }


def test_health() -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_calculate_and_predict() -> None:
    payload = _sample_payload()

    calc = client.post("/api/v1/calculate", json=payload)
    assert calc.status_code == 200
    calc_data = calc.json()
    assert calc_data["analysisType"] == "quasi_static"
    assert len(calc_data["quasiStaticSteps"]) >= 1
    assert "stresses" in calc_data
    assert set(calc_data["stresses"].keys()) == {"r1", "r2"}

    pred = client.post("/api/v1/predict-defect", json=payload)
    assert pred.status_code == 200
    pred_data = pred.json()
    assert pred_data["analysis_type"] == "quasi_static"
    assert len(pred_data["quasi_static_steps"]) >= 1
    assert "risk_by_rod" in pred_data
    assert "evaluation" in pred_data
    assert "top_risky_rods" in pred_data
    assert "notebook_signals" in pred_data


def test_quasi_static_calculation() -> None:
    payload = _sample_payload()
    payload["analysisType"] = "quasi_static"
    payload["quasiStaticSteps"] = [
        {"stepIndex": 1, "name": "q1", "loadFactor": 0.25},
        {"stepIndex": 2, "name": "q2", "loadFactor": 1.0},
    ]

    resp = client.post("/api/v1/calculate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysisType"] == "quasi_static"
    assert len(data["quasiStaticSteps"]) == 2
    assert data["quasiStaticSteps"][0]["stepIndex"] == 1
    assert set(data["quasiStaticSteps"][1]["stresses"].keys()) == {"r1", "r2"}
    assert set(data["stresses"].keys()) == {"r1", "r2"}


def test_quasi_static_prediction() -> None:
    payload = _sample_payload()
    payload["analysisType"] = "quasi_static"
    payload["quasiStaticSteps"] = [
        {"stepIndex": 1, "name": "q1", "loadFactor": 0.25},
        {"stepIndex": 2, "name": "q2", "loadFactor": 0.75},
        {"stepIndex": 3, "name": "q3", "loadFactor": 1.0, "loadFx": 1250, "loadFy": 0},
    ]

    pred = client.post("/api/v1/predict-defect", json=payload)
    assert pred.status_code == 200
    data = pred.json()
    assert data["analysis_type"] == "quasi_static"
    assert len(data["quasi_static_steps"]) == 3
    assert set(data["quasi_static_steps"][0]["risk_by_rod"].keys()) == {"r1", "r2"}


def test_quasi_static_scenario_crud_and_run() -> None:
    scenario_payload = {
        "name": "Demo quasi-static scenario",
        "description": "test scenario",
        "request": {
            **_sample_payload(),
            "analysisType": "quasi_static",
            "quasiStaticSteps": [
                {"stepIndex": 1, "name": "s1", "loadFactor": 0.5},
                {"stepIndex": 2, "name": "s2", "loadFactor": 1.0},
            ],
        },
    }

    created = client.post("/api/v1/quasi-static/scenarios", json=scenario_payload)
    assert created.status_code == 200
    scenario_id = created.json()["id"]
    assert created.json()["request"]["analysisType"] == "quasi_static"

    listed = client.get("/api/v1/quasi-static/scenarios")
    assert listed.status_code == 200
    assert any(item["id"] == scenario_id for item in listed.json()["items"])

    run_resp = client.post(
        f"/api/v1/quasi-static/scenarios/{scenario_id}/run", json={"run_inference": True}
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]
    assert run_resp.json()["status"] == "done"

    runs = client.get(f"/api/v1/quasi-static/scenarios/{scenario_id}/runs")
    assert runs.status_code == 200
    assert any(item["id"] == run_id for item in runs.json()["items"])

    run_details = client.get(f"/api/v1/quasi-static/runs/{run_id}")
    assert run_details.status_code == 200
    assert "analysis" in run_details.json()["result_payload"]

    step = client.get(f"/api/v1/quasi-static/runs/{run_id}/steps/1")
    assert step.status_code == 200
    assert step.json()["step_index"] == 1
    assert step.json()["analysis_step"] is not None

    deleted = client.delete(f"/api/v1/quasi-static/scenarios/{scenario_id}")
    assert deleted.status_code == 200


def test_quasi_static_run_comparison_artifacts() -> None:
    scenario_payload = {
        "name": "Artifact scenario",
        "description": "artifact test",
        "request": {
            **_sample_payload(),
            "analysisType": "quasi_static",
            "quasiStaticSteps": [
                {"stepIndex": 1, "name": "s1", "loadFactor": 0.4},
                {"stepIndex": 2, "name": "s2", "loadFactor": 0.9},
            ],
        },
    }

    created = client.post("/api/v1/quasi-static/scenarios", json=scenario_payload)
    assert created.status_code == 200
    scenario_id = created.json()["id"]

    run_resp = client.post(
        f"/api/v1/quasi-static/scenarios/{scenario_id}/run", json={"run_inference": True}
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]

    artifact_payload = {
        "from_step": 1,
        "to_step": 2,
        "filter_mode": "risk_up",
        "min_change": 0.02,
        "rod_deltas": [
            {
                "rod_id": "r1",
                "stress_from": 10.0,
                "stress_to": 12.5,
                "stress_delta": 2.5,
                "risk_from": 0.15,
                "risk_to": 0.27,
                "risk_delta": 0.12,
            }
        ],
    }
    created_ids: list[str] = []
    for idx in range(3):
        payload = {
            **artifact_payload,
            "from_step": 1,
            "to_step": 2,
            "min_change": 0.02 + idx * 0.01,
        }
        artifact_created = client.post(
            f"/api/v1/quasi-static/runs/{run_id}/artifacts/comparison", json=payload
        )
        assert artifact_created.status_code == 200
        created_ids.append(artifact_created.json()["id"])
        assert artifact_created.json()["artifact_type"] == "comparison"
        assert artifact_created.json()["payload"]["from_step"] == 1

    artifacts = client.get(f"/api/v1/quasi-static/runs/{run_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["total"] == 3
    assert artifacts.json()["has_more"] is False
    assert all(any(item["id"] == expected for item in artifacts.json()["items"]) for expected in created_ids)

    page_1 = client.get(f"/api/v1/quasi-static/runs/{run_id}/artifacts?limit=2&offset=0&sort=desc")
    assert page_1.status_code == 200
    assert page_1.json()["total"] == 3
    assert page_1.json()["limit"] == 2
    assert page_1.json()["offset"] == 0
    assert page_1.json()["has_more"] is True
    assert len(page_1.json()["items"]) == 2

    page_2 = client.get(f"/api/v1/quasi-static/runs/{run_id}/artifacts?limit=2&offset=2&sort=desc")
    assert page_2.status_code == 200
    assert page_2.json()["total"] == 3
    assert page_2.json()["limit"] == 2
    assert page_2.json()["offset"] == 2
    assert page_2.json()["has_more"] is False
    assert len(page_2.json()["items"]) == 1
    assert set(item["id"] for item in page_1.json()["items"]).isdisjoint(
        set(item["id"] for item in page_2.json()["items"])
    )

    artifact_id = created_ids[0]
    artifact = client.get(f"/api/v1/quasi-static/runs/{run_id}/artifacts/{artifact_id}")
    assert artifact.status_code == 200
    assert artifact.json()["run_id"] == run_id
    assert artifact.json()["payload"]["to_step"] == 2

    artifact_deleted = client.delete(f"/api/v1/quasi-static/runs/{run_id}/artifacts/{artifact_id}")
    assert artifact_deleted.status_code == 200

    artifact_after_delete = client.get(f"/api/v1/quasi-static/runs/{run_id}/artifacts/{artifact_id}")
    assert artifact_after_delete.status_code == 404

    artifacts_after_delete = client.get(f"/api/v1/quasi-static/runs/{run_id}/artifacts")
    assert artifacts_after_delete.status_code == 200
    assert artifacts_after_delete.json()["total"] == 2

    missing_run = client.post(
        "/api/v1/quasi-static/runs/missing-run/artifacts/comparison", json=artifact_payload
    )
    assert missing_run.status_code == 404

    deleted = client.delete(f"/api/v1/quasi-static/scenarios/{scenario_id}")
    assert deleted.status_code == 200


def test_defect_lifecycle_and_recalculate() -> None:
    payload = _sample_payload()

    created = client.post(
        "/api/v1/defect/add",
        json={
            "rodId": "r1",
            "defectType": "crack",
            "params": {"position": 0.5, "depth": 2, "width": 10},
        },
    )
    assert created.status_code == 200
    defect_id = created.json()["id"]

    listed = client.get("/api/v1/defect/r1")
    assert listed.status_code == 200
    assert any(item["id"] == defect_id for item in listed.json())

    recalc = client.post("/api/v1/defect/recalculate", json=payload)
    assert recalc.status_code == 200
    assert "stresses" in recalc.json()

    updated = client.put(
        f"/api/v1/defect/{defect_id}",
        json={
            "rodId": "r1",
            "defectType": "corrosion",
            "params": {"position": 0.6, "depth": 1, "thickness": 10},
        },
    )
    assert updated.status_code == 200

    deleted = client.delete(f"/api/v1/defect/{defect_id}")
    assert deleted.status_code == 200


def test_report_pdf() -> None:
    resp = client.post(
        "/api/v1/report",
        json={
            "title": "Test Report",
            "nodes_count": 3,
            "rods_count": 2,
            "defects_count": 1,
            "stresses": {"r1": 10.0, "r2": 12.5},
            "top_risky_rods": [{"rod_id": "r1", "risk": 0.7}],
            "nodes": [
                {"id": "n1", "x": 0, "y": 0},
                {"id": "n2", "x": 100, "y": 0},
                {"id": "n3", "x": 200, "y": 50},
            ],
            "rods": [
                {"id": "r1", "start_node_id": "n1", "end_node_id": "n2"},
                {"id": "r2", "start_node_id": "n2", "end_node_id": "n3"},
            ],
            "defects": [
                {"id": "d1", "rod_id": "r1", "defect_type": "crack", "position": 0.5, "depth": 2}
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")


def test_training_start_status() -> None:
    start_resp = client.post(
        "/api/v1/training/start",
        json={"epochs": 3, "learning_rate": 0.05, "model_family": "notebook-informed"},
    )
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    assert start_data["status"] in {"training", "trained"}
    assert "model_version" in start_data
    assert "weights" in start_data

    status_resp = client.get("/api/v1/training/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] in {"training", "trained", "failed", "stopped", "idle"}
